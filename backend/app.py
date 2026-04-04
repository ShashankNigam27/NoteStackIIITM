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
from models     import User, Note,GeneratedPaper,TestResult,FAQ
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

@app.route('/library')
@login_required
def library():
    subject_filter = request.args.get('subject', '').strip()
    search_query   = request.args.get('q', '').strip()

    notes_data = search_notes(
        university=current_user.university or '',
        subject_filter=subject_filter,
        search_query=search_query,
        limit=30
    )
    all_notes = [Note(n) for n in notes_data]
    
    my_notes_data = get_notes_for_user(
        uid=str(current_user.id),
        subject=subject_filter,
        search_query=search_query
    )
    my_notes = [Note(n) for n in my_notes_data]
    
    subjects = get_all_subjects()
    
    return render_template('library.html',
                           notes=all_notes,
                           my_notes=my_notes,
                           subjects=subjects,
                           subject_filter=subject_filter,
                           search_query=search_query)


@app.route('/upload-note')
@login_required
def upload_note():
    return render_template('upload-note.html', user=current_user)


@app.route('/upload-pyq')
@login_required
def upload_pyq():
    return render_template('upload-pyq.html', user=current_user)


@app.route('/note-detail/<string:note_id>')
@app.route('/note-detail')
@login_required
def note_detail(note_id=None):
    note = None
    if note_id:
        n_data = get_note_by_id(note_id)
        if n_data:
            note = Note(n_data)
    return render_template('note-detail.html', note=note, user=current_user)


@app.route('/debug-db')
@login_required
def debug_db():
    from services.firebase_service import get_firestore, _convert_timestamp
    import json
    
    db = get_firestore()
    if not db:
        return "Firebase not initialized", 500
        
    uid = str(current_user.id)
    notes_ref = db.collection("notes").where("uid", "==", uid).limit(50).stream()
    
    notes = []
    for doc in notes_ref:
        d = doc.to_dict()
        d['id'] = doc.id
        notes.append(_convert_timestamp(d))
        
    user_data = {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "university": getattr(current_user, 'university', 'NONE'),
        "notes_found": len(notes)
    }
    
    # Return  plain text for easy read
    output = f"USER DATA:\n{json.dumps(user_data, indent=2)}\n\nNOTES FOUND:\n"
    for n in notes:
        output += f"- ID: {n['id']}, Title: {n.get('title')}, Univ: {n.get('university')}, Created: {n.get('created_at')}\n"
        
    
    return output, 200, {'Content-Type': 'text/plain'}

@app.route('/ai-tools')
@login_required
def ai_tools():
    my_notes_data = get_notes_for_user(str(current_user.id))
    my_notes = [Note(n) for n in my_notes_data]
    return render_template('ai-tools.html', my_notes=my_notes, user=current_user)


@app.route('/generated-paper')
@app.route('/generated-paper/<string:paper_id>')
@login_required
def generated_paper(paper_id=None):
    paper = None
    if paper_id:
        p_data = get_generated_paper(paper_id)
        if p_data and p_data.get('uid') == str(current_user.id):
            paper = GeneratedPaper(p_data)
    elif request.args.get('paper_id'):
        p_data = get_generated_paper(request.args.get('paper_id'))
        if p_data and p_data.get('uid') == str(current_user.id):
            paper = GeneratedPaper(p_data)
    else:
        # Get latest
        p_list = get_test_history(str(current_user.id), limit=1) # Using test history as proxy or add get_latest_paper
        if p_list:
            paper = GeneratedPaper(p_list[0]) # 
            
    return render_template('generated-paper.html', paper=paper, user=current_user)




@app.route('/analytics')
@login_required
def analytics():
    uid = str(current_user.id)
    note_count  = get_note_count(uid)
    paper_count = get_paper_count(uid)
    
    # Get all notes to count per subject
    all_notes_data = get_notes_for_user(uid)
    notes_per_subject = {}
    for n in all_notes_data:
        subj = n.get('subject', 'Untitled')
        notes_per_subject[subj] = notes_per_subject.get(subj, 0) + 1
        
    results_data = get_test_history(uid, limit=100)
    results = [TestResult(r) for r in results_data]
    
    total_tests = len(results)
    avg_score   = round(sum(r.score for r in results) / total_tests, 1) if total_tests > 0 else 0
    best_score  = round(max((r.score for r in results), default=0), 1)
    
    #Avg time taken (mins)
    avg_time = round(sum(r.time_taken for r in results) / (total_tests * 60), 1) if total_tests > 0 else 0
    
    # Subject Mastery Matrix
    subject_scores = {}
    for r in results:
        if r.subject not in subject_scores:
            subject_scores[r.subject] = []
        subject_scores[r.subject].append(r.score)
        
    subject_mastery = []
    # Combine subjects from notes and tests
    all_subjects = set(list(notes_per_subject.keys()) + list(subject_scores.keys()))
    
    for subj in all_subjects:
        n_count = notes_per_subject.get(subj, 0)
        scores = subject_scores.get(subj, [])
        s_avg = round(sum(scores) / len(scores), 1) if scores else 0
        t_count = len(scores)
        
        # Readiness Level: Based on notes (30%) and scores (70%)
        # 3 notes = 100% note score (weight 30), Score 100 = weight 70
        readiness = min(100, (min(n_count, 3) / 3 * 30) + (s_avg / 100 * 70)) if n_count > 0 or t_count > 0 else 0
        
        # Status labels
        status = "CRITICAL" if (t_count > 0 and s_avg < 40) else ("MASTERED" if s_avg > 85 else "IN PROGRESS")

        subject_mastery.append({
            'subject': subj,
            'note_count': n_count,
            'test_count': t_count,
            'avg_score': s_avg,
            'readiness': round(readiness, 1),
            'status': status
        })
    
    # Sort by readiness
    subject_mastery.sort(key=lambda x: x['readiness'])
    
    #Topics with scores below 60
    weak_topics = [s for s in subject_mastery if s['avg_score'] < 60 and s['test_count'] > 0]
    
    # Recent Scores for Chart
    recent_scores = [r.score for r in results[:10]]
    recent_scores.reverse() # Show chronological order
    if len(recent_scores) < 10:
        recent_scores = [0] * (10 - len(recent_scores)) + recent_scores

    return render_template('analytics.html', 
                           user=current_user,
                           note_count=note_count, 
                           paper_count=paper_count,
                           total_tests=total_tests,
                           avg_score=avg_score,
                           best_score=best_score,
                           avg_time=avg_time,
                           subject_mastery=subject_mastery,
                           weak_topics=weak_topics,
                           recent_scores=recent_scores)


@app.route('/test-mode/<string:note_id>')
@app.route('/test-mode')
@login_required
def test_mode(note_id=None):
    if not note_id:
        # If no note specified, redirect to library to pick one
        flash('Please select a note to start a test.')
        return redirect(url_for('library'))
    
    note_data = get_note_by_id(str(note_id))
    if not note_data:
        flash('Note not found.')
        return redirect(url_for('library'))
        
    return render_template('test-mode.html', note_id=note_id, subject=note_data.get('subject'), user=current_user)

if __name__ == '__main__':
    print("[NoteStack] Running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
