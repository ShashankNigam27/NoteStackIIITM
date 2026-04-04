"""
backend/services/firebase_service.py

Firebase Admin SDK initializer + high-level helper functions.
All Firebase interactions go through this module.

If Firebase is not configured (no serviceAccountKey.json),
all functions degrade gracefully and return None / empty values.
"""

import os
import json
import uuid
import datetime
import logging

# Set up a dedicated debug logger for Firebase troubleshooting
debug_logger = logging.getLogger("firebase_debug")
debug_logger.setLevel(logging.DEBUG)
if not debug_logger.handlers:
    fh = logging.FileHandler("backend_debug.log")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    debug_logger.addHandler(fh)

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

_initialized = False


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def init_firebase():
    """
    Initializes Firebase Admin SDK.
    Safe to call multiple times — only initializes once.
    """
    global _initialized
    if _initialized:
        return

    # User mentioned serviceAccountKey.json is the correct key
    key_path = os.path.join(os.path.dirname(__file__), '..', 'serviceAccountKey.json')

    if not os.path.exists(key_path):
        print(f"[Firebase] {key_path} not found. Firebase features disabled.")
        return

    try:
        cred   = credentials.Certificate(key_path)
        # Firebase Storage bucket: try both naming conventions
        # Newer:  PROJECT_ID.appspot.com
        # Older: PROJECT_ID.firebasestorage.app
        bucket = os.getenv('FIREBASE_STORAGE_BUCKET', 'notestack-cad7d.appspot.com')

        firebase_admin.initialize_app(cred, {
            'storageBucket': bucket
        })

        _initialized = True
        print("[Firebase] Initialized successfully.")

    except Exception as e:
        print(f"[Firebase] Initialization failed: {e}")


def is_initialized():
    """Returns True if Firebase was successfully initialized."""
    return _initialized


def get_firestore():
    """Returns Firestore client. Returns None if Firebase not initialized."""
    if not _initialized:
        return None
    try:
        return firestore.client()
    except Exception as e:
        print(f"[Firebase] Firestore client error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# USER COLLECTION
# ═══════════════════════════════════════════════════════════════

def get_user_by_id(uid):
    """Fetches user from Firestore by ID."""
    db = get_firestore()
    if not db: return None
    try:
        doc = db.collection("users").document(str(uid)).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None
    except Exception as e:
        print(f"[Firebase] get_user_by_id error: {e}")
        return None


def get_user_by_email(email):
    """Fetches user from Firestore by email."""
    db = get_firestore()
    if not db: return None
    try:
        docs = db.collection("users").where(filter=FieldFilter("email", "==", email)).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None
    except Exception as e:
        print(f"[Firebase] get_user_by_email error: {e}")
        return None


def save_user(uid, data):
    """Saves or updates user data in Firestore."""
    db = get_firestore()
    if not db: return False
    try:
        db.collection("users").document(str(uid)).set(data, merge=True)
        return True
    except Exception as e:
        print(f"[Firebase] save_user error: {e}")
        return False


def get_storage():
    """Returns Firebase Storage bucket. Returns None if Firebase not initialized."""
    if not _initialized:
        return None
    try:
        return storage.bucket()
    except Exception as e:
        print(f"[Firebase] Storage bucket error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# STORAGE HELPERS
# ═══════════════════════════════════════════════════════════════

def upload_to_storage(file_bytes, filename, content_type, folder="notes"):
    """
    Uploads a file to Firebase Storage.

    Args:
        file_bytes   : bytes
        filename     : str  e.g. "lecture_notes.pdf"
        content_type : str  e.g. "application/pdf"
        folder       : str  storage folder prefix

    Returns:
        str — public download URL, or "" if Firebase not available
    """
    bucket = get_storage()
    if not bucket:
        return ""

    try:
        blob_name = f"{folder}/{uuid.uuid4().hex}_{filename}"
        blob      = bucket.blob(blob_name)
        blob.upload_from_string(file_bytes, content_type=content_type)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f"[Firebase] Storage upload failed: {e}")
        return ""


def _convert_timestamp(data):
    """
    Internal helper to convert Firestore Timestamps to Python datetime objects
    so templates can call .strftime().
    """
    if not data: return data
    for field in ["created_at", "verified_at"]:
        if field in data and hasattr(data[field], "to_datetime"):
            data[field] = data[field].to_datetime()
        elif field in data and hasattr(data[field], "isoformat"):
            # Fallback if somehow already a datetime or iso string
            pass 
    return data


# ═══════════════════════════════════════════════════════════════
# NOTES COLLECTION
# ═══════════════════════════════════════════════════════════════

def save_note(uid, file_url, raw_text, keywords, important_sentences, metadata):
    """
    Saves note document to Firestore notes collection.

    Args:
        uid                 : str  user ID
        file_url            : str  storage URL (can be "")
        raw_text            : str  extracted text
        keywords            : list of strings
        important_sentences : list of strings
        metadata            : dict with keys: subject, university, filename, title, branch, semester, summary

    Returns:
        str — document ID, or "" on failure
    """
    db = get_firestore()
    if not db:
        return ""

    try:
        doc_ref = db.collection("notes").document()
        doc_ref.set({
            "uid":                 uid,
            "file_url":            file_url,
            "extracted_text":      raw_text,
            "keywords":            keywords,
            "important_sentences": important_sentences,
            "subject":             metadata.get("subject", ""),
            "university":          metadata.get("university", ""),
            "filename":            metadata.get("filename", ""),
            "title":               metadata.get("title",    ""),
            "branch":              metadata.get("branch",   ""),
            "semester":            metadata.get("semester", ""),
            "summary":             metadata.get("summary",  ""), # Save summary to top level
            "status":              "active",
            "created_at":          firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[Firebase] save_note failed: {e}")
        return ""


def get_note_by_id(note_id):
    """
    Fetches a note document from Firestore by document ID.

    Returns:
        dict with note data, or None if not found
    """
    db = get_firestore()
    if not db:
        return None

    try:
        doc = db.collection("notes").document(note_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return _convert_timestamp(data)
        return None
    except Exception as e:
        print(f"[Firebase] get_note_by_id failed: {e}")
        return None


def get_notes_for_user(uid, university="", branch="", semester="", subject="", search_query=""):
    """
    Fetches both notes and uploaded PYQs for a given user with optional filters.
    """
    db = get_firestore()
    if not db: return []

    try:
        debug_logger.debug(f"[get_notes_for_user] Searching for UID: {uid}, Univ: {university}, Search: {search_query}")
        
        # 1. Fetch Notes
        q_notes = db.collection("notes").where(filter=FieldFilter("uid", "==", str(uid)))
        docs_notes = q_notes.limit(100).stream() 
        combined_list = []
        for doc in docs_notes:
            data = doc.to_dict()
            data["id"] = doc.id
            data["upload_type"] = "note"
            combined_list.append(data)
        
        # 2. Fetch PYQs
        q_pyqs = db.collection("pyq_papers").where(filter=FieldFilter("uid", "==", str(uid)))
        docs_pyqs = q_pyqs.limit(100).stream()
        for doc in docs_pyqs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["upload_type"] = "pyq"
            # Normalize fields for UI consistency
            if "title" not in data:
                data["title"] = f"PYQ: {data.get('subject')} ({data.get('year')})"
            combined_list.append(data)

        # Apply Filters in Python
        filtered = []
        for data in combined_list:
            note_univ = str(data.get("university", "")).lower()
            note_subj = str(data.get("subject", "")).lower()
            
            if university and university.lower() not in note_univ:
                continue
            if subject and subject.lower() not in note_subj:
                continue
            
            if search_query:
                sq = search_query.lower()
                title = str(data.get("title", "")).lower()
                kw    = " ".join(data.get("keywords", [])).lower()
                text  = str(data.get("extracted_text", "")).lower()
                
                if sq not in title and sq not in note_subj and sq not in kw and sq not in text:
                    continue

            filtered.append(_convert_timestamp(data))
        
        # Sort and Limit
        filtered.sort(key=lambda x: x.get("created_at") or datetime.datetime.min, reverse=True)
        return filtered[:60]

    except Exception as e:
        debug_logger.error(f"[get_notes_for_user] Error: {e}")
        return []

def delete_from_storage(file_url):
    """Deletes a file from Firebase Storage given its public URL."""
    bucket = get_storage()
    if not bucket or not file_url: return False
    try:
        from urllib.parse import unquote
        blob_path = unquote(file_url.split("/")[-1].split("?")[0])
        blob = bucket.blob(blob_path)
        if blob.exists():
            blob.delete()
            print(f"[Firebase] Deleted storage file: {blob_path}")
            return True
        return False
    except Exception as e:
        print(f"[Firebase] delete_from_storage error: {e}")
        return False

def delete_note(note_id, uid):
    """Deletes a note or PYQ from Firestore and Storage."""
    db = get_firestore()
    if not db: return False

    try:
        doc_ref = db.collection("notes").document(note_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            doc_ref = db.collection("pyq_papers").document(note_id)
            doc = doc_ref.get()
            
        if not doc.exists:
            return False

        data = doc.to_dict()
        if str(data.get("uid")) != str(uid):
            return False 

        file_url = data.get("file_url")
        doc_ref.delete()
        if file_url:
            delete_from_storage(file_url)
        return True
    except Exception as e:
        print(f"[Firebase] delete_note error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# PYQ PAPERS COLLECTION
# ═══════════════════════════════════════════════════════════════

def save_pyq_paper(uid, file_url, raw_text, subject, university, year, filename):
    """
    Saves an uploaded PYQ paper (pending verification) to Firestore.

    Returns:
        str — document ID, or "" on failure
    """
    db = get_firestore()
    if not db:
        return ""

    try:
        doc_ref = db.collection("pyq_papers").document()
        doc_ref.set({
            "uid":           uid,
            "file_url":      file_url,
            "extracted_text": raw_text,
            "subject":       subject,
            "university":    university,
            "year":          year,
            "filename":      filename,
            "status":        "pending",
            "questions":     [],
            "created_at":    firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[Firebase] save_pyq_paper failed: {e}")
        return ""

#Verify paper after mid evaluation.

# ═══════════════════════════════════════════════════════════════
# GENERATED PAPERS COLLECTION
# ═══════════════════════════════════════════════════════════════

def save_generated_paper(uid, subject, university, note_id, paper_json, mode, priority_topics, stats=None):
    """
    Saves a generated question paper to Firestore.

    Args:
        uid             : str
        subject         : str
        university      : str
        note_id         : str
        paper_json      : dict — the sections dict {"A": [...], "B": [...], "C": [...]}
        mode            : str — "university_model" or "gemini_fallback"
        priority_topics : list of strings
        stats           : dict — {total_generated, total_relevant, total_filtered}

    Returns:
        str — document ID, or "" on failure
    """
    db = get_firestore()
    if not db:
        return ""

    try:
        doc_ref = db.collection("generated_papers").document()
        doc_ref.set({
            "uid":             uid,
            "subject":         subject,
            "university":      university,
            "note_id":         note_id,
            "sections":        paper_json,
            "mode":            mode,
            "priority_topics": priority_topics,
            "stats":           stats or {},
            "created_at":      firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[Firebase] save_generated_paper failed: {e}")
        return ""


def get_generated_paper(paper_id):
    """
    Fetches a generated paper by document ID.

    Returns:
        dict or None
    """
    db = get_firestore()
    if not db:
        return None

    try:
        doc = db.collection("generated_papers").document(paper_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None
    except Exception as e:
        print(f"[Firebase] get_generated_paper failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# TEST RESULTS COLLECTION
# ═══════════════════════════════════════════════════════════════

def save_test_result(uid, subject, university, paper_id, score, correct, total, time_taken):
    """
    Saves a test result to Firestore.

    Returns:
        str — document ID, or "" on failure
    """
    db = get_firestore()
    if not db:
        return ""

    try:
        doc_ref = db.collection("test_results").document()
        doc_ref.set({
            "uid":          uid,
            "subject":      subject,
            "university":   university,
            "paper_id":     paper_id,
            "score":        score,
            "correct":      correct,
            "total":        total,
            "time_taken":   time_taken,
            "created_at":   firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[Firebase] save_test_result failed: {e}")
        return ""


def get_test_history(uid, limit=20):
    """
    Fetches test history for a user.
    Sorted in Python to avoid composite index requirements.
    """
    db = get_firestore()
    if not db:
        return []

    try:
        q = db.collection("test_results").where(filter=FieldFilter("uid", "==", uid))
        
        docs = q.limit(limit * 2).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(_convert_timestamp(data))
        
        # Sort in Python
        results.sort(key=lambda x: x.get("created_at") or datetime.datetime.min, reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"[Firebase] get_test_history failed: {e}")
        return []


def get_note_count(uid):
    """Returns number of notes for a user."""
    db = get_firestore()
    if not db: return 0
    try:
        # In Firestore, count() is available in some SDKs, otherwise we stream
        docs = db.collection("notes").where(filter=FieldFilter("uid", "==", str(uid))).stream()
        return sum(1 for _ in docs)
    except Exception:
        return 0


def get_paper_count(uid):
    """Returns number of generated papers for a user."""
    db = get_firestore()
    if not db: return 0
    try:
        docs = db.collection("generated_papers").where(filter=FieldFilter("uid", "==", str(uid))).stream()
        return sum(1 for _ in docs)
    except Exception:
        return 0


def get_all_subjects():
    """Returns list of distinct subjects from all notes."""
    db = get_firestore()
    if not db: return []
    try:
        docs = db.collection("notes").stream()
        subjects = set()
        for doc in docs:
            s = doc.to_dict().get("subject")
            if s: subjects.add(s)
        return sorted(list(subjects))
    except Exception:
        return []


def search_notes(university="", subject_filter="", search_query="", limit=30):
    """
    Searches notes across a university (or globally if searching).
    """
    db = get_firestore()
    if not db: return []
    try:
        debug_logger.debug(f"[search_notes] Univ: {university}, Search: {search_query}, Subject: {subject_filter}")
        
        q = db.collection("notes")
        docs = q.limit(500).stream() 
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            
            # University Filter (ignored if we're doing a global search/query)
            if not search_query and university:
                note_univ = str(data.get("university", "")).lower()
                if university.lower() not in note_univ:
                    continue

            # Subject Filter
            if subject_filter:
                note_subj = str(data.get("subject", "")).lower()
                if subject_filter.lower() not in note_subj:
                    continue
            
            if search_query:
                sq    = search_query.lower()
                title = str(data.get("title", "")).lower()
                subj  = str(data.get("subject", "")).lower()
                univ  = str(data.get("university", "")).lower()
                kw    = " ".join(data.get("keywords", [])).lower()
                text  = str(data.get("extracted_text", "")).lower()

                # Search in all relevant textual fields
                if sq not in title and sq not in subj and sq not in kw and sq not in text and sq not in univ:
                    continue
                    
            results.append(_convert_timestamp(data))
        
        debug_logger.debug(f"[search_notes] Found {len(results)} matches.")
        results.sort(key=lambda x: x.get("created_at") or datetime.datetime.min, reverse=True)
        return results[:limit]
    except Exception as e:
        debug_logger.error(f"[search_notes] Error: {e}")
        return []

def get_faqs_for_note(note_id):
    """Fetches FAQS associated with a note."""
    db = get_firestore()
    if not db: return []
    try:
        docs = db.collection("faqs").where(filter=FieldFilter("note_id", "==", str(note_id))).stream()
        faqs = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            faqs.append(data)
        return faqs
    except Exception:
        return []

def save_faq(uid, note_id, subject, question, answer):
    """Saves a single FAQ to Firestore."""
    db = get_firestore()
    if not db: return ""
    try:
        doc_ref = db.collection("faqs").document()
        doc_ref.set({
            "uid": uid,
            "note_id": note_id,
            "subject": subject,
            "question": question,
            "answer": answer,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return doc_ref.id
    except Exception:
        return ""

def save_quiz(uid, note_id, subject, quiz_data):
    """Saves generated MCQ quiz to Firestore."""
    db = get_firestore()
    if not db: return ""
    try:
        doc_ref = db.collection("quizzes").document()
        doc_ref.set({
            "uid": uid,
            "note_id": note_id,
            "subject": subject,
            "questions": quiz_data,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return doc_ref.id
    except Exception:
        return ""

def get_quiz(quiz_id):
    """Fetches a quiz by ID."""
    db = get_firestore()
    if not db: return None
    try:
        doc = db.collection("quizzes").document(quiz_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None
    except Exception:
        return None
def get_pyq_count(university, subject):
    """Returns number of uploaded PYQs for a university/subject pair."""
    db = get_firestore()
    if not db: return 0
    try:
        # Use simple filtering
        docs = db.collection("pyq_papers").where(filter=FieldFilter("university", "==", university)).where(filter=FieldFilter("subject", "==", subject)).stream()
        return sum(1 for _ in docs)
    except Exception:
        return 0

def get_all_pyq_text(university, subject):
    """Fetches text from all uploaded PYQs for training."""
    db = get_firestore()
    if not db: return []
    try:
        docs = db.collection("pyq_papers").where(filter=FieldFilter("university", "==", university)).where(filter=FieldFilter("subject", "==", subject)).stream()
        return [{"text": doc.to_dict().get("extracted_text", ""), "year": doc.to_dict().get("year", "Unknown")} for doc in docs]
    except Exception:
        return []

def is_model_training(university, subject):
    """Checks if a training job is already active in Firestore."""
    db = get_firestore()
    if not db: return False
    try:
        doc_id = f"{university}_{subject.replace(' ', '')}"
        doc = db.collection("model_training").document(doc_id).get()
        if doc.exists:
            return doc.to_dict().get("is_training", False)
        return False
    except Exception:
        return False

def set_model_training_status(university, subject, status):
    """Sets the training status flag."""
    db = get_firestore()
    if not db: return
    try:
        doc_id = f"{university}_{subject.replace(' ', '')}"
        db.collection("model_training").document(doc_id).set({
            "university": university,
            "subject": subject,
            "is_training": status,
            "updated_at": firestore.SERVER_TIMESTAMP
        }, merge=True)
    except Exception as e:
        print(f"[Firebase] set_model_training_status error: {e}")