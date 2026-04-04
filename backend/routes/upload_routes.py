import json
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.firebase_service import (
    upload_to_storage, save_note, save_faq, save_pyq_paper, is_initialized
)

upload_bp = Blueprint('upload', __name__, url_prefix='/api/upload')

@upload_bp.route('/note', methods=['POST'])
@login_required
def upload_note():
    """
    Uploads a student note.
    OCR → TF-IDF → AI Summary → Knowledge Distillation (FAQs) → Save to Firestore.
    """
    try:
        from services.ocr_service   import extract_text
        from services.tfidf_service import analyze
        from services.summarizer    import summarize, extract_faqs

        file = request.files.get('file')
        if not file:
            return jsonify({"success": False, "error": "No file provided"}), 400

        subject    = request.form.get('subject', '').strip()
        if not subject:
            return jsonify({"success": False, "error": "subject is required"}), 400

        title      = request.form.get('title',      file.filename).strip()
        university = (
            request.form.get('university', '').strip()
            or getattr(current_user, 'university', '')
            or ''
        )
        branch     = request.form.get('branch',   '').strip()
        semester   = request.form.get('semester', '').strip()

        filename   = file.filename
        file_bytes = file.read()
        file_type  = 'pdf' if filename.lower().endswith('.pdf') else 'image'
        content_type = 'application/pdf' if file_type == 'pdf' else 'image/jpeg'

        #OCR
        raw_text = ""
        try:
            raw_text = extract_text(file_bytes, file_type)
        except Exception as e:
            print(f"[upload_note] OCR failed: {e}")

        #step-TF-IDF
        keywords, important_sentences = [], []
        try:
            if raw_text:
                keywords, important_sentences = analyze(raw_text, subject, university)
        except Exception as e:
            print(f"[upload_note] TF-IDF failed: {e}")

        #AI Summary
        summary = "No content extracted."
        try:
            if important_sentences:
                summary = summarize(important_sentences, subject, university)
        except Exception as e:
            print(f"[upload_note] Summarizer failed: {e}")
            summary = "Summary unavailable."

        #Firebase Storage + Firestore
        firestore_note_id = ""
        file_url = ""
        try:
            if is_initialized():
                file_url = upload_to_storage(file_bytes, filename, content_type, folder="notes")
                firestore_note_id = save_note(
                    uid                = str(current_user.id),
                    file_url           = file_url,
                    raw_text           = raw_text,
                    keywords           = keywords,
                    important_sentences= important_sentences,
                    metadata = {
                        "subject":    subject,
                        "university": university,
                        "filename":   filename,
                        "title":      title or filename,
                        "branch":     branch,
                        "semester":   semester,
                        "summary":    summary # Added summary to Firestore doc
                    }
                )
        except Exception as e:
            print(f"[upload_note] Firebase save failed: {e}")

        #firestore failed 
        if not firestore_note_id:
            return jsonify({"success": False, "error": "Failed to save note to Firestore"}), 500

        #extract FAQs 
        faq_count = 0
        try:
            faqs_data = extract_faqs(important_sentences, keywords, subject, university)
            for f in faqs_data:
                save_faq(
                    uid      = str(current_user.id),
                    note_id  = firestore_note_id,
                    subject  = subject,
                    question = f.get('q', 'No question'),
                    answer   = f.get('a', 'No answer'),
                )
            faq_count = len(faqs_data)
        except Exception as e:
            print(f"[upload_note] FAQ extraction failed: {e}")

        return jsonify({
            "success":      True,
            "note_id":      firestore_note_id,
            "keywords":     keywords,
            "summary":      summary,
            "faq_count":    faq_count,
            "char_count":   len(raw_text),
            "file_url":     file_url
        }), 200

    except Exception as e:
        print(f"[upload_note] Unexpected error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


#POST /api/upload/pyq

@upload_bp.route('/pyq', methods=['POST'])
@login_required
def upload_pyq():
    """
    Uploads a PYQ paper. OCR → store to Firestore pyq_papers (pending).
    """
    try:
        from services.ocr_service import extract_text

        file = request.files.get('file')
        if not file:
            return jsonify({"success": False, "error": "No file provided"}), 400

        subject    = request.form.get('subject', '').strip()
        if not subject:
            return jsonify({"success": False, "error": "subject is required"}), 400

        university = (
            request.form.get('university', '').strip()
            or getattr(current_user, 'university', '')
            or ''
        )
        year       = request.form.get('year', '').strip()
        filename   = file.filename
        file_bytes = file.read()
        file_type  = 'pdf' if filename.lower().endswith('.pdf') else 'image'
        content_type = 'application/pdf' if file_type == 'pdf' else 'image/jpeg'

        #OCR 
        raw_text = ""
        try:
            raw_text = extract_text(file_bytes, file_type)
        except Exception as e:
            print(f"[upload_pyq] OCR failed: {e}")

        #Firebase Storage + Firestore 
        pyq_id = ""
        file_url = ""
        try:
            if is_initialized():
                file_url = upload_to_storage(file_bytes, filename, content_type, folder="pyq")
                pyq_id   = save_pyq_paper(
                    uid        = str(current_user.id),
                    file_url   = file_url,
                    raw_text   = raw_text,
                    subject    = subject,
                    university = university,
                    year       = year,
                    filename   = filename,
                )
        except Exception as e:
            print(f"[upload_pyq] Firebase save failed: {e}")

        if not pyq_id:
            return jsonify({"success": False, "error": "Failed to save PYQ to Firestore"}), 500

        return jsonify({
            "success":    True,
            "paper_id":   pyq_id,
            "subject":    subject,
            "university": university,
            "year":       year,
            "status":     "pending_verification",
            "char_count": len(raw_text or ""),
        }), 200

    except Exception as e:
        print(f"[upload_pyq] Unexpected error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
