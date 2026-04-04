
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.firebase_service import (
    save_test_result, get_test_history, is_initialized, get_generated_paper
)

test_bp = Blueprint('test', __name__, url_prefix='/api/test')


# ── POST /api/test/submit 

@test_bp.route('/submit', methods=['POST'])
@login_required
def submit_test():
    """
    Submits answers for a completed test session.
    Computes score, saves result to Firestore.
    """
    try:
        data      = request.get_json(force=True) or {}
        paper_id  = data.get('paper_id',  '')
        answers   = data.get('answers',   {})          
        correct_a = data.get('correct_answers', {})    
        questions = data.get('questions', [])
        time_taken= int(data.get('time_taken', data.get('time_taken_seconds', 0)))

        # Derive subject and university from the saved paper if possible
        subject    = "General"
        university = getattr(current_user, 'university', '') or ''

        try:
            if paper_id:
                p_data = get_generated_paper(str(paper_id))
                if p_data:
                    subject    = p_data.get('subject', subject)
                    university = p_data.get('university', university)
        except Exception as e:
            print(f"[submit_test] Could not fetch paper: {e}")

        # ── Grading 
        total_q = data.get('total')
        if not total_q:
            total_q = len(questions) if questions else len(answers)
            
        correct_count = data.get('correct', 0)

        if correct_a:
            for key in correct_a:
                student_ans = str(answers.get(key, '')).strip().lower()
                correct_ans = str(correct_a.get(key, '')).strip().lower()
                if student_ans and student_ans == correct_ans:
                    correct_count += 1
        else:
            pre_score = data.get('score')
            if pre_score is not None and not data.get('correct'):
                try:
                    score_perc = float(pre_score)
                    correct_count = round(score_perc / 100 * total_q) if total_q > 0 else 0
                except:
                    pass

        score_perc = round((correct_count / total_q * 100), 2) if total_q > 0 else 0.0

        # ── Save to Firestore 
        result_id = ""
        try:
            if is_initialized():
                result_id = save_test_result(
                    uid        = str(current_user.id),
                    subject    = subject,
                    university = university,
                    paper_id   = str(paper_id),
                    score      = score_perc,
                    correct    = correct_count,
                    total      = total_q,
                    time_taken = time_taken,
                )
        except Exception as e:
            print(f"[submit_test] Firestore save failed: {e}")
            return jsonify({"success": False, "error": "Failed to save test result"}), 500

        return jsonify({
            "success":   True,
            "score":     score_perc,
            "correct":   correct_count,
            "total":     total_q,
            "result_id": result_id,
            "subject":   subject,
        }), 200

    except Exception as e:
        print(f"[submit_test] Unexpected error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ── GET /api/test/history ───────────────────────────────────────

@test_bp.route('/history', methods=['GET'])
@login_required
def test_history():
    #Returns test history for the current user from Firestore.
    try:
        limit   = int(request.args.get('limit', 20))
        history = []

        if is_initialized():
            history = get_test_history(str(current_user.id), limit=limit)
        else:
            return jsonify({"success": False, "error": "Firebase not initialized"}), 503

        return jsonify({"success": True, "history": history}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
