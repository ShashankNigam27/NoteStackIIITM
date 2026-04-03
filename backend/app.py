import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from services.firebase_service import (
    init_firebase)


#extensions and models
from extensions import login_manager
from models     import User, Note, GeneratedPaper, TestResult, FAQ
from services.firebase_service import (
    init_firebase, get_user_by_id, get_note_count, get_paper_count, 
    get_notes_for_user, search_notes, get_all_subjects, get_generated_paper,
    get_test_history, get_note_by_id
)

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

#FIREBASE ININTIALISE
init_firebase()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, '..', 'frontend', 'pages'),
    static_folder=os.path.join(BASE_DIR, '..', 'frontend'),
    static_url_path=''
)

# SECRET KEY
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'notestack-secret-radical-key-123')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB

# CORS
CORS(app,
     origins="*",
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


login_manager.login_view    = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data:
        return User.from_dict(user_data, user_data['id'])
    return None

@app.context_processor
def inject_globals():
    # Convert UTC to IST (+5:30)
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return {'now_hour': ist_now.hour}

#api blueprints
from routes.auth_routes   import auth_bp
from routes.upload_routes import upload_bp
from routes.notes_routes  import notes_bp
from routes.ai_routes     import ai_bp
from routes.test_routes   import test_bp

app.register_blueprint(auth_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(test_bp)

#page routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('college-email', '').strip()
        password = request.form.get('password', '')
        
        from services.firebase_service import get_user_by_email
        user_data = get_user_by_email(email)
        
        if user_data and check_password_hash(user_data.get('password', ''), password):
            user = User.from_dict(user_data, user_data['id'])
            login_user(user)
            return redirect(url_for('dashboard'))
            
        flash('Invalid email or password. Please try again.')
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        from services.firebase_service import get_user_by_email, save_user
        import uuid
        
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        university = request.form.get('university', '').strip()
        department = request.form.get('department', '').strip()
        
        if not full_name or not email or not password:
            flash('All fields are required.')
            return render_template('register.html')
            
        if get_user_by_email(email):
            flash('Email already registered.')
            return render_template('register.html')
            
        uid = str(uuid.uuid4().hex)
        user_data = {
            "full_name": full_name,
            "email": email,
            "password": generate_password_hash(password, method='pbkdf2:sha256'),
            "university": university,
            "department": department,
            "scholar_id": f"SCH-{uid[:8]}",
            "created_at": datetime.utcnow()
        }
        
        if save_user(uid, user_data):
            user = User.from_dict(user_data, uid)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Registration failed. Please try again.')
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    note_count   = get_note_count(current_user.id)
    paper_count  = get_paper_count(current_user.id)
    recent_notes_data = get_notes_for_user(str(current_user.id))[:4]
    recent_notes = [Note(n) for n in recent_notes_data]
    
    return render_template('dashboard.html',
                           user=current_user,
                           note_count=note_count,
                           paper_count=paper_count,
                           recent_notes=recent_notes)

if __name__ == '__main__':
    print("[NoteStack] Running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
