from flask_login import UserMixin
from datetime import datetime
import json

# ═══════════════════════════════════════════════════════════════
# MODELS (Firestore Wrappers)
# ═══════════════════════════════════════════════════════════════

class User(UserMixin):
    """
    User class compatible with Flask-Login.
    Data is stored in Firestore 'users' collection.
    """
    def __init__(self, id, full_name, email, password, scholar_id=None, department=None, university=None):
        self.id         = str(id)
        self.full_name  = full_name
        self.email      = email
        self.password   = password
        self.scholar_id = scholar_id
        self.department = department
        self.university = university

    @staticmethod
    def from_dict(data, id):
        return User(
            id         = id,
            full_name  = data.get('full_name'),
            email      = data.get('email'),
            password   = data.get('password'),
            scholar_id = data.get('scholar_id'),
            department = data.get('department'),
            university = data.get('university')
        )

    def to_dict(self):
        return {
            "full_name":  self.full_name,
            "email":      self.email,
            "password":   self.password,
            "scholar_id": self.scholar_id,
            "department": self.department,
            "university": self.university,
        }


class Note:
    def __init__(self, data):
        self.id             = data.get('id')
        self.user_id        = data.get('uid') or data.get('user_id')
        self.title          = data.get('title')
        self.subject        = data.get('subject')
        self.university     = data.get('university')
        self.extracted_text = data.get('extracted_text')
        self.keywords       = data.get('keywords', []) # In Firestore it's a list
        self.summary        = data.get('summary')
        self.filename       = data.get('filename')
        
        # Ensure created_at is a datetime or a fallback
        self.created_at     = data.get('created_at')
        if not self.created_at:
            from datetime import datetime
            self.created_at = datetime.utcnow()
        elif hasattr(self.created_at, 'to_datetime'):
            self.created_at = self.created_at.to_datetime()

    @property
    def author(self):
        """Fetches and returns the author's user object from Firestore."""
        from services.firebase_service import get_user_by_id
        user_data = get_user_by_id(self.user_id)
        if user_data:
            from models import User
            return User.from_dict(user_data, user_data['id'])
        return type('Guest', (), {'full_name': 'Unknown Author'})()

    @property
    def keywords_list(self):
        if isinstance(self.keywords, list):
            return self.keywords
        try:
            return json.loads(self.keywords or '[]')
        except:
            return []

class GeneratedPaper:
    def __init__(self, data):
        self.id              = data.get('id')
        self.user_id         = data.get('uid') or data.get('user_id')
        self.note_id         = data.get('note_id')
        self.subject         = data.get('subject')
        self.university      = data.get('university')
        self.mode            = data.get('mode')
        self.questions       = data.get('questions', [])
        self.sections        = data.get('sections', {})
        self.stats           = data.get('stats', {})          # relevance stats
        self.priority_topics = data.get('priority_topics', [])
        self.created_at      = data.get('created_at')

    @property
    def sections_dict(self):
        if isinstance(self.sections, dict):
            return self.sections
        try:
            return json.loads(self.sections or '{}')
        except:
            return {}

    @property
    def questions_list(self):
        if isinstance(self.questions, list):
            return self.questions
        try:
            return json.loads(self.questions or '[]')
        except:
            return []



class TestResult:
    def __init__(self, data):
        self.id               = data.get('id')
        self.user_id          = data.get('uid') or data.get('user_id')
        self.subject          = data.get('subject')
        self.score            = data.get('score', 0)
        self.correct_answers  = data.get('correct') or data.get('correct_answers', 0)
        self.total_questions  = data.get('total') or data.get('total_questions', 0)
        self.time_taken       = data.get('time_taken', 0)
        self.created_at       = data.get('created_at')


class FAQ:
    def __init__(self, data):
        self.id         = data.get('id')
        self.user_id    = data.get('uid') or data.get('user_id')
        self.note_id    = data.get('note_id')
        self.subject    = data.get('subject')
        self.question   = data.get('question')
        self.answer     = data.get('answer')
        self.created_at = data.get('created_at')
        