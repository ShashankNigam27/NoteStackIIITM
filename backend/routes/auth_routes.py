
import uuid
from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime
from services.firebase_service import get_user_by_email, save_user, get_firestore

auth_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    # naya account create 
    
    try:
        data = request.get_json(force=True) or {}

        full_name  = data.get('full_name',  '').strip()
        email      = data.get('email',      '').strip()
        password   = data.get('password',   '')
        university = data.get('university', '').strip()
        department = data.get('department', '').strip()

        if not full_name or not email or not password:
            return jsonify({"success": False, "error": "full_name, email, and password are required"}), 400

        # Check if user already exists
        existing_user = get_user_by_email(email)
        if existing_user:
            return jsonify({"success": False, "error": "Email already registered"}), 409

        # Create new user
        uid = str(uuid.uuid4().hex)
        user_data = {
            "full_name":  full_name,
            "email":      email,
            "password":   generate_password_hash(password, method='pbkdf2:sha256'),
            "university": university,
            "department": department,
            "scholar_id": f"SCH-{uid[:8]}", # Placeholder
            "created_at": datetime.utcnow()
        }

        success = save_user(uid, user_data)
        if not success:
            return jsonify({"success": False, "error": "Failed to save user"}), 500

        return jsonify({
            "success":   True,
            "user_id":   uid,
            "full_name": full_name,
        }), 201

    except Exception as e:
        print(f"[auth_routes] Registration error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    #return current logged-in
    try:
        return jsonify({
            "success": True,
            "user": {
                "id":         current_user.id,
                "full_name":  current_user.full_name,
                "email":      current_user.email,
                "university": getattr(current_user, 'university', '') or '',
                "department": getattr(current_user, 'department', '') or '',
                "scholar_id": getattr(current_user, 'scholar_id', '') or '',
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    #google sign in handle krta hai
    try:
        from firebase_admin import auth
        from models import User
        from services.firebase_service import get_user_by_id, save_user
        from extensions import login_manager

        data = request.get_json(force=True) or {}
        id_token = data.get('id_token')

        if not id_token:
            return jsonify({"success": False, "error": "id_token is required"}), 400

        # ID token verify krta hia
        # retry mechanism for clock skew
        import time
        decoded_token = None
        max_retries = 5  # Increased retries
        
        for attempt in range(max_retries):
            try:
                decoded_token = auth.verify_id_token(id_token)
                break
            except Exception as e:
                err_msg = str(e)
                if "Token used too early" in err_msg and attempt < max_retries - 1:
                    wait_sec = 5  # Wait longer per retry
                    print(f"[auth_routes] Token issued in future (skew: {err_msg}), retrying in {wait_sec}s... (attempt {attempt+1})")
                    time.sleep(wait_sec)
                    continue
                
                error_detail = err_msg
                if "Token used too early" in err_msg:
                    error_detail += " (Please check your computer's clock and click 'Sync now' in your system settings)"
                
                print(f"[auth_routes] Google Auth error: {err_msg}")
                return jsonify({"success": False, "error": error_detail}), 401
        
        if not decoded_token:
            return jsonify({"success": False, "error": "Token verification failed after multiple attempts due to clock skew."}), 401
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name', 'Google User')

        user_data = get_user_by_id(uid)
        
        if not user_data:
            user_data = {
                "full_name": name,
                "email": email,
                "password": "GOOGLE_AUTH", # Placeholder
                "university": "",
                "department": "",
                "scholar_id": f"SCH-{uid[:8]}",
                "created_at": datetime.utcnow()
            }
            save_user(uid, user_data)
        
        # Log the user in
        user = User.from_dict(user_data, uid)
        from flask_login import login_user
        login_user(user)

        return jsonify({
            "success": True,
            "user_id": uid,
            "full_name": name,
            "redirect_url": url_for('dashboard')
        }), 200

    except Exception as e:
        print(f"[auth_routes] Google Auth error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
