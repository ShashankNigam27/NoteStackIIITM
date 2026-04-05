# backend/services/training_service.py

import os
import threading
import logging
from services.firebase_service import (
    get_note_count_by_subject, get_all_notes_text,
    is_model_training, set_model_training_status, is_initialized
)
from services.model_manager import model_exists, upload_model_to_storage, clear_cache
from config import MODEL_BASE_DIR, FLAN_T5_MODEL

# Set up logging for background training
training_logger = logging.getLogger("model_training")
training_logger.setLevel(logging.INFO)
if not training_logger.handlers:
    handler = logging.FileHandler("training_debug.log")
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    training_logger.addHandler(handler)

def auto_train_if_ready(university, subject):
    """
    Checks if conditions for automated training are met.
    If so, spawns a background thread to fine-tune the university model.
    """
    if not university or not subject:
        return
    
    # 1. Check if model already exists
    if model_exists(university, subject):
        return

    # 2. Check if already training
    if is_model_training(university, subject):
        training_logger.info(f"Training already in progress for {university}/{subject}")
        return

    # 3. Check note count (Threshold: 3 notes for this university+subject)
    count = get_note_count_by_subject(university, subject)
    if count < 3:
        training_logger.info(f"Insufficient notes for {university}/{subject}: {count}/3 notes")
        return

    # 4. Trigger background training
    training_logger.info(f"Triggering auto-train for {university}/{subject} (Notes: {count})")
    thread = threading.Thread(target=_background_train_task, args=(university, subject))
    thread.daemon = True
    thread.start()

def _background_train_task(university, subject):
    """
    The actual fine-tuning process. Runs in a separate thread.
    """
    try:
        # Firebase is a process-level singleton — safe to use from threads
        # but only if init_firebase() succeeded at startup
        if not is_initialized():
            training_logger.error(
                f"Firebase not initialized — cannot run training for {university}/{subject}. "
                f"Check serviceAccountKey.json exists in backend/."
            )
            return

        set_model_training_status(university, subject, True)
        training_logger.info(f"Background task STARTED for {university}/{subject}")

        # ── Step 1: Fetch note text ────────────────────────────────
        notes = get_all_notes_text(university, subject)
        if not notes:
            training_logger.error("No note text retrieved from Firestore")
            return
        training_logger.info(f"Fetched {len(notes)} note(s) for {university}/{subject}")

        from training.data_prep import parse_questions_from_text
        
        all_examples = []
        for note in notes:
            text = note.get('text', '')
            if text:
                examples = parse_questions_from_text(text, university, subject)
                all_examples.extend(examples)
        training_logger.info(f"Extracted {len(all_examples)} training example(s) from notes")
        
        if len(all_examples) < 10: # Minimum examples needed for any meaningful T5 flux
            training_logger.warning(f"Too few extracted questions ({len(all_examples)}) to train.")
            return

        # ── Step 2: Fine-Tuning (Logic from train.py) ──────────────────
        import torch
        from transformers import T5ForConditionalGeneration, T5Tokenizer
        
        training_logger.info(f"Loading base {FLAN_T5_MODEL} for fine-tuning...")
        tokenizer  = T5Tokenizer.from_pretrained(FLAN_T5_MODEL)
        model      = T5ForConditionalGeneration.from_pretrained(FLAN_T5_MODEL)
        
        optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
        batch_size = 4
        epochs = 3

        model.train()
        for epoch in range(epochs):
            total_loss = 0
            for i in range(0, len(all_examples), batch_size):
                batch = all_examples[i:i + batch_size]
                inputs  = tokenizer([ex['prompt'] for ex in batch], 
                                  return_tensors='pt', padding=True, truncation=True, max_length=128)
                targets = tokenizer([ex['completion'] for ex in batch], 
                                  return_tensors='pt', padding=True, truncation=True, max_length=256)

                labels = targets['input_ids']
                labels[labels == tokenizer.pad_token_id] = -100
                
                outputs = model(**inputs, labels=labels)
                loss = outputs.loss
                total_loss += loss.item()
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            training_logger.info(f"Epoch {epoch+1}/{epochs} Loss: {total_loss/len(all_examples):.4f}")

        # ── Step 3: Save & Sync ──────────────────────────────
        clean_subject = subject.replace(' ', '')
        out_dir = os.path.join(MODEL_BASE_DIR, university, clean_subject, 'v1')
        os.makedirs(out_dir, exist_ok=True)
        
        model.save_pretrained(out_dir)
        tokenizer.save_pretrained(out_dir)
        
        training_logger.info(f"Model saved locally to {out_dir}. Syncing to Storage...")
        
        # Guard storage upload — firebase_admin must still be initialized in this thread
        try:
            import firebase_admin
            firebase_admin.get_app()          # raises ValueError if not initialized
            upload_model_to_storage(university, subject)
            training_logger.info(f"Model synced to Firebase Storage successfully.")
        except ValueError:
            training_logger.warning(
                "Firebase app not available in training thread — skipping Storage upload. "
                "Model is saved locally and will be used from disk."
            )
        except Exception as upload_err:
            training_logger.warning(f"Storage upload failed (non-fatal): {upload_err}")

        clear_cache(university, subject)
        training_logger.info(f"Background task SUCCESSFULLY COMPLETED for {university}/{subject}")

    except Exception as e:
        training_logger.error(f"Background training FAILED for {university}/{subject}: {str(e)}")
    
    finally:
        set_model_training_status(university, subject, False)