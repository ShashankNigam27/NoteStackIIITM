# backend/services/model_manager.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MODEL_BASE_DIR

# FIREBASE STORAGE FOLDER STRUCTURE:
#   ml_models/
#     RGPV/
#       DataStructures/
#         v2.zip    ← zipped model folder
#       OperatingSystems/
#         v1.zip
#     MumbaiUniversity/
#       Mathematics/
#         v1.zip


# In-memory cache
# Format: { "RGPV_DataStructures": (model, tokenizer) }
_model_cache = {}


# ── Public API ─────────────────────────────────────────────────────────────────

def model_exists(university, subject):
    """
    Checks if a trained model exists ANYWHERE — disk or Firebase Storage.
    Returns True or False.

    Called by question_gen.py before deciding to use
    the university model or Gemini fallback.

    Checks in this order (fast to slow):
      1. Local disk  — instant
      2. Firebase Storage — one network call

    Args:
        university : string  e.g. "RGPV"
        subject    : string  e.g. "DataStructures"
    """
    # Check local disk first (fast)
    if _exists_on_disk(university, subject):
        return True

    # Check Firebase Storage (one network call)
    return _exists_in_storage(university, subject)


def load_model(university, subject):
    """
    Loads model and tokenizer for a university+subject pair.

    Order of attempts:
      1. Memory cache  — returns in microseconds
      2. Local disk    — returns in 30-60 seconds (first time)
      3. Firebase Storage → download → disk → load → cache

    Returns (model, tokenizer) tuple.
    Raises FileNotFoundError if model doesn't exist anywhere.

    Args:
        university : string  e.g. "RGPV"
        subject    : string  e.g. "DataStructures"
    """
    cache_key = _make_cache_key(university, subject)

    # ── Step 1: memory cache ──────────────────────────────────────────────────
    if cache_key in _model_cache:
        print(f"[model_manager] {cache_key}: serving from memory cache")
        return _model_cache[cache_key]

    # ── Step 2: local disk ────────────────────────────────────────────────────
    if not _exists_on_disk(university, subject):
        # Not on disk — try downloading from Firebase Storage
        print(f"[model_manager] {cache_key}: not on disk, checking Firebase Storage...")
        downloaded = _download_from_storage(university, subject)

        if not downloaded:
            raise FileNotFoundError(
                f"No trained model found for {university}/{subject}. "
                f"Not on disk and not in Firebase Storage. "
                f"The model hasn't been trained yet, Gemini fallback should be used."
            )
        print(f"[model_manager] {cache_key}: downloaded from Firebase Storage successfully")

    # ── Step 3: load from disk into memory ────────────────────────────────────
    model_path = _get_model_path(university, subject)
    print(f"[model_manager] {cache_key}: loading from disk at {model_path}")
    print("[model_manager] This takes 30-60 seconds on first load...")

    try:
        from transformers import T5ForConditionalGeneration, T5Tokenizer

        tokenizer = T5Tokenizer.from_pretrained(model_path)
        model     = T5ForConditionalGeneration.from_pretrained(model_path)
        model.eval()

        _model_cache[cache_key] = (model, tokenizer)
        print(f"[model_manager] {cache_key}: loaded and cached successfully")

        return model, tokenizer

    except Exception as e:
        raise Exception(f"[model_manager] Failed to load {cache_key} from disk: {str(e)}")


def upload_model_to_storage(university, subject):
    """
    Zips the trained model folder and uploads it to Firebase Storage.

    Call this from train.py right after training finishes.

    What it does:
      1. Finds the model folder on local disk  (e.g. models/RGPV/DataStructures/v1)
      2. Zips the entire folder into one file  (e.g. v1.zip)
      3. Uploads the zip to Firebase Storage   (e.g. ml_models/RGPV/DataStructures/v1.zip)
      4. Deletes the temporary zip file

    Args:
        university : string  e.g. "RGPV"
        subject    : string  e.g. "DataStructures"

    Returns:
        storage_path : string  the path inside Firebase Storage bucket
                       e.g. "ml_models/RGPV/DataStructures/v1.zip"

    Raises:
        FileNotFoundError if no trained model exists on disk to upload.

    Example (call this from train.py after trainer.train()):
        from services.model_manager import upload_model_to_storage
        upload_model_to_storage("RGPV", "DataStructures")
    """
    if not _exists_on_disk(university, subject):
        raise FileNotFoundError(
            f"Cannot upload — no model found on disk for {university}/{subject}. "
            f"Run training first."
        )

    model_path = _get_model_path(university, subject)
    version    = os.path.basename(model_path)          # "v1", "v2", or "v3"
    zip_name   = f"{version}.zip"
    zip_path   = os.path.join(MODEL_BASE_DIR, zip_name)  # temp zip location

    try:
        import zipfile
        from firebase_admin import storage

        # ── Step 1: zip the model folder ──────────────────────────────────────
        print(f"[model_manager] Zipping {model_path} ...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(model_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, model_path)
                    zf.write(full_path, arcname)

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"[model_manager] Zip created: {zip_size_mb:.1f} MB")

        # ── Step 2: upload to Firebase Storage ────────────────────────────────
        clean_subject = subject.replace(" ", "")
        storage_path  = f"ml_models/{university}/{clean_subject}/{zip_name}"

        print(f"[model_manager] Uploading to Firebase Storage: {storage_path} ...")
        bucket = storage.bucket()
        blob   = bucket.blob(storage_path)
        blob.upload_from_filename(zip_path, content_type="application/zip")

        print(f"[model_manager] Upload complete: {storage_path}")
        return storage_path

    finally:
        # Always clean up the temp zip, even if upload failed
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"[model_manager] Temp zip deleted")


def generate(university, subject, topics, pattern):
    """
    Generates questions using the university+subject trained model.

    Args:
        university : string  e.g. "RGPV"
        subject    : string  e.g. "DataStructures"
        topics     : list    e.g. ["binary tree", "BST"]
        pattern    : dict    section structure from Firestore

    Returns:
        list of question dicts with text, marks, section, topic
    """
    model, tokenizer = load_model(university, subject)
    questions        = []

    if not pattern:
        pattern = {
            "A": {"marks_per_q": 2,  "total_questions": 7},
            "B": {"marks_per_q": 7,  "total_questions": 7},
            "C": {"marks_per_q": 14, "total_questions": 6},
        }

    for section, spec in pattern.items():
        marks = spec.get("marks_per_q", 2)
        count = spec.get("total_questions", 5)

        for i in range(count):
            topic  = topics[i % len(topics)] if topics else subject
            prompt = f"generate {marks}-mark question about {topic}"

            try:
                inputs  = tokenizer(
                    prompt,
                    return_tensors="pt",
                    max_length=128,
                    truncation=True
                )
                outputs = model.generate(
                    **inputs,
                    max_length=256,
                    num_beams=4,
                    early_stopping=True,
                    no_repeat_ngram_size=2,
                )
                text = tokenizer.decode(outputs[0], skip_special_tokens=True)

                questions.append({
                    "text":    text,
                    "marks":   marks,
                    "section": section,
                    "topic":   topic,
                })

            except Exception as e:
                print(f"[model_manager] Generation failed for '{topic}': {str(e)}")
                questions.append({
                    "text":    f"Explain {topic} in detail. [{marks} marks]",
                    "marks":   marks,
                    "section": section,
                    "topic":   topic,
                })

    return questions


def clear_cache(university=None, subject=None):
    """
    Clears model(s) from memory cache.
    Call this after retraining so the new model is fetched fresh.

    Combinations:
        clear_cache("RGPV", "DataStructures")  → clears only that model
        clear_cache("RGPV")                    → clears all RGPV subjects
        clear_cache()                          → clears everything
    """
    global _model_cache

    if university and subject:
        cache_key = _make_cache_key(university, subject)
        _model_cache.pop(cache_key, None)
        print(f"[model_manager] Cache cleared for {cache_key}")

    elif university:
        prefix      = f"{university}_"
        keys_to_del = [k for k in _model_cache if k.startswith(prefix)]
        for k in keys_to_del:
            del _model_cache[k]
        print(f"[model_manager] Cache cleared for all {university} subjects: {keys_to_del}")

    else:
        _model_cache = {}
        print("[model_manager] All model cache cleared")


def list_available_models():
    """
    Returns all university+subject models available — checks BOTH disk and Storage.

    Returns:
        list of dicts, e.g.:
        [
            {"university": "RGPV", "subject": "DataStructures", "version": "v2", "location": "disk"},
            {"university": "RGPV", "subject": "OperatingSystems", "version": "v1", "location": "storage"},
        ]
    """
    available = []

    # ── From local disk ───────────────────────────────────────────────────────
    if os.path.isdir(MODEL_BASE_DIR):
        for university in os.listdir(MODEL_BASE_DIR):
            uni_path = os.path.join(MODEL_BASE_DIR, university)
            if not os.path.isdir(uni_path):
                continue
            for subject in os.listdir(uni_path):
                subj_path = os.path.join(uni_path, subject)
                if not os.path.isdir(subj_path):
                    continue
                for version in ["v3", "v2", "v1"]:
                    ver_path    = os.path.join(subj_path, version)
                    config_file = os.path.join(ver_path, "config.json")
                    if os.path.isdir(ver_path) and os.path.exists(config_file):
                        available.append({
                            "university": university,
                            "subject":    subject,
                            "version":    version,
                            "location":   "disk",
                        })
                        break

    # ── From Firebase Storage ─────────────────────────────────────────────────
    try:
        from firebase_admin import storage
        bucket = storage.bucket()
        blobs  = bucket.list_blobs(prefix="ml_models/")

        disk_keys = {f"{m['university']}_{m['subject']}" for m in available}

        for blob in blobs:
            # blob.name format: ml_models/RGPV/DataStructures/v1.zip
            parts = blob.name.split("/")
            if len(parts) != 4:
                continue
            _, university, subject, zip_file = parts
            version = zip_file.replace(".zip", "")

            cache_key = f"{university}_{subject}"
            if cache_key not in disk_keys:
                available.append({
                    "university": university,
                    "subject":    subject,
                    "version":    version,
                    "location":   "storage",
                })

    except Exception as e:
        print(f"[model_manager] Could not list Storage models: {e}")

    return available


# ── Private helpers ────────────────────────────────────────────────────────────

def _make_cache_key(university, subject):
    """
    e.g. _make_cache_key("RGPV", "Data Structures") → "RGPV_DataStructures"
    Spaces stripped so "Data Structures" and "DataStructures" hit the same key.
    """
    return f"{university}_{subject.replace(' ', '')}"


def _get_model_path(university, subject):
    """
    Returns local disk path to the model folder.
    Checks v3 → v2 → v1, returns first one that exists.
    Falls back to v1 path even if it doesn't exist yet.

    e.g. models/RGPV/DataStructures/v2
    """
    clean_subject = subject.replace(" ", "")

    for version in ["v3", "v2", "v1"]:
        path = os.path.join(MODEL_BASE_DIR, university, clean_subject, version)
        if os.path.isdir(path):
            return path

    return os.path.join(MODEL_BASE_DIR, university, clean_subject, "v1")


def _exists_on_disk(university, subject):
    """Returns True if the model folder + config.json exist on local disk."""
    model_path  = _get_model_path(university, subject)
    config_file = os.path.join(model_path, "config.json")
    return os.path.isdir(model_path) and os.path.exists(config_file)


def _exists_in_storage(university, subject):
    """
    Returns True if a zip for this university+subject exists in Firebase Storage.
    Makes one network call to check.
    """
    try:
        from firebase_admin import storage
        clean_subject = subject.replace(" ", "")
        bucket        = storage.bucket()

        for version in ["v3", "v2", "v1"]:
            storage_path = f"ml_models/{university}/{clean_subject}/{version}.zip"
            blob         = bucket.blob(storage_path)
            if blob.exists():
                return True

        return False

    except Exception as e:
        print(f"[model_manager] Storage existence check failed: {e}")
        return False


def _download_from_storage(university, subject):
    """
    Downloads the model zip from Firebase Storage and unzips it to local disk.

    Returns True if successful, False if not found or error.

    Rookie note on why we zip:
        A trained FLAN-T5-small model is ~10 files (config.json, tokenizer files,
        model weights, etc). Uploading/downloading 10 separate files is slow and
        error-prone. Zipping them into one file makes it one clean operation.
        If any file is missing, the whole zip fails clearly — no silent partial downloads.
    """
    zip_path = None
    try:
        import zipfile
        from firebase_admin import storage

        clean_subject = subject.replace(" ", "")
        bucket        = storage.bucket()

        # Find the latest version available in Storage
        version_found = None
        storage_path  = None

        for version in ["v3", "v2", "v1"]:
            candidate = f"ml_models/{university}/{clean_subject}/{version}.zip"
            blob      = bucket.blob(candidate)
            if blob.exists():
                version_found = version
                storage_path  = candidate
                break

        if not version_found:
            print(f"[model_manager] No model zip found in Storage for {university}/{clean_subject}")
            return False

        # ── Download zip to a temp file ───────────────────────────────────────
        zip_path = os.path.join(MODEL_BASE_DIR, f"_download_{university}_{clean_subject}.zip")
        os.makedirs(MODEL_BASE_DIR, exist_ok=True)

        print(f"[model_manager] Downloading {storage_path} from Firebase Storage...")
        blob = bucket.blob(storage_path)
        blob.download_to_filename(zip_path)

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"[model_manager] Downloaded: {zip_size_mb:.1f} MB")

        # ── Unzip to the correct local path ───────────────────────────────────
        extract_path = os.path.join(MODEL_BASE_DIR, university, clean_subject, version_found)
        os.makedirs(extract_path, exist_ok=True)

        print(f"[model_manager] Unzipping to {extract_path} ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_path)

        print(f"[model_manager] Model ready at {extract_path}")
        return True

    except Exception as e:
        print(f"[model_manager] Download failed for {university}/{subject}: {e}")
        return False

    finally:
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)