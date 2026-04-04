"""
backend/routes/ai_routes.py

AI-powered endpoints.
Migrated to Firestore.
"""

import json as _json
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
import io
from datetime import datetime
from services.firebase_service import (
    get_note_by_id, save_generated_paper, is_initialized, 
    get_firestore, get_generated_paper
)

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


# ── POST /api/ai/summarize ─────────────────────────────────────

@ai_bp.route('/summarize', methods=['POST'])
@login_required
def summarize_note():
    """
    Summarizes a note using Gemini.
    """
    try:
        data    = request.get_json(force=True) or {}
        note_id = data.get('note_id')

        if not note_id:
            return jsonify({"success": False, "error": "note_id is required"}), 400

        # ── Retrieve note ────────────────────────────────────────
        note_data = get_note_by_id(str(note_id))
        if not note_data:
            return jsonify({"success": False, "error": "Note not found"}), 404

        subject    = note_data.get("subject",    "General")
        university = note_data.get("university", "")
        important_sentences = note_data.get("important_sentences", [])

        # Fallback: re-run TF-IDF on extracted_text 
        if not important_sentences:
            extracted_text = note_data.get("extracted_text", "")
            if extracted_text:
                try:
                    from services.tfidf_service import analyze
                    _, important_sentences = analyze(extracted_text, subject, university)
                except Exception as e:
                    print(f"[summarize] TF-IDF fallback failed: {e}")
                    important_sentences = []

        # ── Summarize ────────────────────────────────────────────
        try:
            from services.summarizer import summarize
            summary = summarize(
                important_sentences=important_sentences,
                subject=subject,
                university=university
            )
        except Exception as e:
            print(f"[summarize] Summarizer failed: {e}")
            return jsonify({"success": False, "error": f"Summarizer error: {str(e)}"}), 500

        # ── Update summary in Firestore ──────────────────────────
        try:
            db = get_firestore()
            if db:
                db.collection("notes").document(str(note_id)).update({"summary": summary})
        except Exception as e:
            print(f"[summarize] Firestore update failed: {e}")

        return jsonify({"success": True, "summary": summary}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── POST /api/ai/generate-paper ────────────────────────────────

@ai_bp.route('/generate-paper', methods=['POST'])
@login_required
def generate_paper():
    """
    Generates a full exam question paper from a note's keywords.
    """
    try:
        data    = request.get_json(force=True) or {}
        note_id = data.get('note_id')

        if not note_id:
            return jsonify({"success": False, "error": "note_id is required"}), 400

        # ── Retrieve note ────────────────────────────────────────
        note_data = get_note_by_id(str(note_id))
        if not note_data:
            return jsonify({"success": False, "error": "Note not found"}), 404

        subject    = data.get('subject',    '') or note_data.get("subject",    "General")
        university = data.get('university', '') or note_data.get("university", "") or getattr(current_user, 'university', '') or "General"
        keywords   = data.get("keywords")
        if not keywords:
            keywords = note_data.get("keywords", [])

        # ── Generate paper ───────────────────────────────────────
        try:
            question_count = int(data.get('question_count', 20))
        except (TypeError, ValueError):
            question_count = 20
        
        try:
            from services.question_gen import generate_paper as gen
            from services.training_service import auto_train_if_ready
            
            result = gen(
                keywords   = keywords,
                university = university,
                subject    = subject,
                user_id    = str(current_user.id),
                target_count= question_count
            )

            # If we fell back to Gemini, check if we can trigger an auto-train for next time
            if result.get("mode") == "gemini_fallback":
                auto_train_if_ready(university, subject)

        except Exception as e:
            print(f"[generate_paper] question_gen failed: {e}")
            return jsonify({"success": False, "error": f"Paper generation failed: {str(e)}"}), 500

        sections        = result.get("sections",        {"A": [], "B": [], "C": []})
        questions       = result.get("questions",       [])
        mode            = result.get("mode",            "gemini_fallback")
        priority_topics = result.get("priority_topics", [])

        # ── Save to Firestore ────────────────────────────────────
        firestore_paper_id = ""
        try:
            if is_initialized():
                firestore_paper_id = save_generated_paper(
                    uid             = str(current_user.id),
                    subject         = subject,
                    university      = university,
                    note_id         = str(note_id),
                    paper_json      = sections,
                    mode            = mode,
                    priority_topics = priority_topics,
                    stats           = result.get("stats", {}),
                )
        except Exception as e:
            print(f"[generate_paper] Firestore save failed: {e}")
            return jsonify({"success": False, "error": "Failed to save paper to Firestore"}), 500

        stats = result.get("stats", {})
        return jsonify({
            "success":         True,
            "paper_id":        firestore_paper_id,
            "sections":        sections,
            "questions":       questions,
            "mode":            mode,
            "priority_topics": priority_topics,
            "stats":           stats,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── POST /api/ai/generate-quiz ──────────────────────────────────

@ai_bp.route('/generate-quiz', methods=['POST'])
@login_required
def generate_quiz():
    """
    Generates a 10-question MCQ quiz from a note's context.
    """
    try:
        data    = request.get_json(force=True) or {}
        note_id = data.get('note_id')

        if not note_id:
            return jsonify({"success": False, "error": "note_id is required"}), 400

        # ── Retrieve note ────────────────────────────────────────
        note_data = get_note_by_id(str(note_id))
        if not note_data:
            return jsonify({"success": False, "error": "Note not found"}), 404

        subject    = note_data.get("subject",    "General")
        university = note_data.get("university", "") or getattr(current_user, 'university', '')
        context    = note_data.get("extracted_text", "")
        keywords   = note_data.get("keywords", [])

        if not context and not keywords:
            return jsonify({"success": False, "error": "No content or keywords found in note to generate quiz."}), 400

        try:
            question_count = int(data.get('question_count', 10))
        except (TypeError, ValueError):
            question_count = 10

        # ── Generate Quiz ────────────────────────────────────────
        try:
            from services.quiz_gen import generate_quiz as gen_mcq
            quiz_data = gen_mcq(
                context=context, 
                subject=subject, 
                university=university,
                keywords=keywords,
                question_count=question_count
            )
        except Exception as e:
            print(f"[generate-quiz] Service failed: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

        # ── Save to Firestore ────────────────────────────────────
        from services.firebase_service import save_quiz
        quiz_id = save_quiz(
            uid       = str(current_user.id),
            note_id   = str(note_id),
            subject   = subject,
            quiz_data = quiz_data
        )

        return jsonify({
            "success": True,
            "quiz_id": quiz_id,
            "quiz":    quiz_data,
            "subject": subject
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ai_bp.route('/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    """
    Renders the question paper sections as a downloadable PDF.
    """
    try:
        data       = request.get_json(force=True) or {}
        sections   = data.get('sections',   {})
        subject    = data.get('subject',    'Exam')
        university = data.get('university', '')

        if not sections:
            return jsonify({"success": False, "error": "sections is required"}), 400

        try:
            from fpdf import FPDF
        except ImportError:
            return jsonify({"success": False, "error": "fpdf2 not installed"}), 500

        pdf = _build_pdf(sections, subject, university)
        pdf_bytes = pdf.output()
        buf       = io.BytesIO(bytes(pdf_bytes))
        buf.seek(0)

        safe_subject = "".join(c if c.isalnum() or c in "_-" else "_" for c in subject)
        filename     = f"{safe_subject}_question_paper.pdf"

        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        print(f"[export_pdf] Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ── GET /api/ai/topics/<university>/<subject> ───────────────────

@ai_bp.route('/topics/<university>/<subject>', methods=['GET'])
@login_required
def topic_frequency(university, subject):
    """
    Returns topic frequency from verified PYQ papers.
    """
    try:
        try:
            from services.tfidf_service import get_topic_frequency
            topics = get_topic_frequency(university, subject)
        except Exception as e:
            print(f"[topic_frequency] get_topic_frequency failed: {e}")
            topics = []

        return jsonify({"success": True, "topics": topics}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_pdf(sections, subject, university):
    from fpdf import FPDF
    diff_tag = {"Easy": "[E]", "Medium": "[M]", "Hard": "[H]"}

    class ExamPDF(FPDF):
        def header(self): pass
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')

    pdf = ExamPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    page_width = pdf.w - 40

    if university:
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 8, university.upper(), align='C', ln=True)

    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, 'End Semester Examination', align='C', ln=True)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 7, subject, align='C', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(page_width / 2, 6, 'Time: 3 Hours', align='L')
    pdf.cell(page_width / 2, 6, 'Max Marks: 100', align='R', ln=True)
    pdf.ln(2)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(4)

    section_meta = {
        "A": {"instruction": "Short Answer Questions (2 Marks Each)", "marks_label": "2"},
        "B": {"instruction": "Detailed Analytical Questions (7 Marks Each)", "marks_label": "7"},
        "C": {"instruction": "Comprehensive Essay/Problem Questions (14 Marks Each)", "marks_label": "14"},
    }

    for sec in ["A", "B", "C"]:
        qs = sections.get(sec, [])
        meta = section_meta.get(sec, {})
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 7, f'Section {sec}', ln=True)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, meta.get("instruction", ""), ln=True)
        pdf.ln(1)
        pdf.set_text_color(0, 0, 0)

        for i, q in enumerate(qs, start=1):
            text = q.get("text", "")
            diff = q.get("difficulty", "")
            tag = diff_tag.get(diff, "")
            pdf.set_font('Helvetica', '', 9)
            if tag:
                if diff == "Easy": pdf.set_text_color(6, 95, 70)
                elif diff == "Medium": pdf.set_text_color(146, 64, 14)
                else: pdf.set_text_color(153, 27, 27)
                pdf.cell(10, 6, tag)
            else: pdf.cell(10, 6, "")
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(page_width - 10, 6, f"Q{i}. {text}")
            pdf.ln(1)
        pdf.ln(3)
    return pdf
