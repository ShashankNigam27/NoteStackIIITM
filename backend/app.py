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

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    print("[NoteStack] Running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
