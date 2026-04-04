from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.firebase_service import (
    get_notes_for_user, get_note_by_id, rate_note as fb_rate, 
    verify_pyq_paper, is_initialized, search_notes, delete_note
)

notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')

@notes_bp.route('/<note_id>', methods=['DELETE'])
@login_required
def delete_user_note(note_id):
    """
    Deletes a note or PYQ belonging to the user.
    """
    try:
        if is_initialized():
            success = delete_note(note_id, str(current_user.id))
            if not success:
                return jsonify({"success": False, "error": "Note not found or permission denied"}), 404
        else:
            return jsonify({"success": False, "error": "Firebase not initialized"}), 503

        return jsonify({"success": True, "message": "Note deleted successfully"}), 200

    except Exception as e:
        print(f"[notes_routes] delete_note error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@notes_bp.route('/list', methods=['GET'])
@login_required
def list_notes():
    """
    Returns notes for the current user with optional filters.
    """
    try:
        university = request.args.get('university', getattr(current_user, 'university', '') or '')
        branch     = request.args.get('branch',   '')
        semester   = request.args.get('semester', '')
        subject    = request.args.get('subject',  '')

        notes = []
        if is_initialized():
            notes = get_notes_for_user(
                uid        = str(current_user.id),
                university = university,
                branch     = branch,
                semester   = semester,
                subject    = subject,
            )
        else:
            return jsonify({"success": False, "error": "Firebase not initialized"}), 503

        return jsonify({"success": True, "notes": notes}), 200

    except Exception as e:
        print(f"[notes_routes] list_notes error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@notes_bp.route('/<note_id>', methods=['GET'])
@login_required
def get_note(note_id):
    """
    Returns full detail of a single note from Firestore.
    """
    try:
        note_data = None
        if is_initialized():
            note_data = get_note_by_id(note_id)
        
        if not note_data:
            return jsonify({"success": False, "error": "Note not found"}), 404

        return jsonify({"success": True, "note": note_data}), 200

    except Exception as e:
        print(f"[notes_routes] get_note error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@notes_bp.route('/<note_id>/rate', methods=['POST'])
@login_required
def rate_note(note_id):
    """
    Saves a user's rating on a note.
    """
    try:
        data   = request.get_json(force=True) or {}
        rating = data.get('rating')

        if rating is None or not (1 <= int(rating) <= 5):
            return jsonify({"success": False, "error": "rating must be an integer 1-5"}), 400

        rating = int(rating)

        if is_initialized():
            success = fb_rate(note_id, str(current_user.id), rating)
            if not success:
               return jsonify({"success": False, "error": "Failed to rate note"}), 500
        else:
            return jsonify({"success": False, "error": "Firebase not initialized"}), 503

        return jsonify({"success": True, "rating": rating}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@notes_bp.route('/pyq/verify/<paper_id>', methods=['POST'])
@login_required
def verify_pyq(paper_id):
    """
    Marks a PYQ paper as verified in Firestore.
    """
    try:
        if is_initialized():
            ok = verify_pyq_paper(paper_id)
            if not ok:
                return jsonify({"success": False, "error": "Failed to verify paper"}), 500
        else:
            return jsonify({"success": False, "error": "Firebase not initialized"}), 503

        return jsonify({"success": True, "paper_id": paper_id}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
