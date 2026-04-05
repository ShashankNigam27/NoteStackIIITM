# backend/training/data_prep.py
#
# Converts raw PYQ paper text into (prompt, completion) pairs
# that flan-t5-small can be fine-tuned on.
#
# Called exclusively by training_service._background_train_task().

import re


def parse_questions_from_text(text, university, subject):
    """
    Extracts individual exam questions from raw OCR/text of a PYQ paper
    and converts them into prompt→completion training pairs.

    Each example dict has:
        prompt     : the T5 input   e.g. "generate 2-mark question about binary tree"
        completion : the T5 target  e.g. "Contrast the properties of a binary tree..."

    Args:
        text       : str   full raw text of one PYQ paper
        university : str   e.g. "RGPV"
        subject    : str   e.g. "DataStructures"

    Returns:
        list of {"prompt": str, "completion": str}
    """
    if not text or not text.strip():
        return []

    examples = []

    # ── Step 1: split into candidate sentences / lines ─────────────────────
    # Split on newlines and sentence boundaries to isolate individual questions.
    raw_chunks = re.split(r'\n{1,}|(?<=[.?])\s+(?=[A-Z0-9(])', text)

    # ── Step 2: simple heuristic to detect question lines ──────────────────
    # A line is treated as a question if it:
    #   - is between 20 and 500 characters long
    #   - starts with a question number OR contains a question word
    question_patterns = [
        r'^\(?\d+[\).\s]',          # (1), 1., 1)
        r'^[Qq]\.?\s*\d+',          # Q1, Q. 1
        r'^[A-Z]\.\s+',             # A. B. C.
        r'\?',                       # ends with ?
        r'\b(explain|derive|discuss|compare|contrast|analyze|evaluate|'
        r'differentiate|illustrate|design|justify|describe|formulate|'
        r'synthesize|critically)\b', # imperative verbs common in exam Qs
    ]
    question_re = re.compile('|'.join(question_patterns), re.IGNORECASE)

    raw_questions = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if 20 <= len(chunk) <= 500 and question_re.search(chunk):
            raw_questions.append(chunk)

    # ── Step 3: infer marks per question from marks tags ───────────────────
    # e.g. "[2 marks]", "(7 M)", "(14 marks)"
    marks_re = re.compile(r'\[?\(?(\d+)\s*(?:marks?|m)\)?\]?', re.IGNORECASE)

    for q in raw_questions:
        q_clean = q.strip()
        if not q_clean:
            continue

        marks = 2  # default
        m = marks_re.search(q_clean)
        if m:
            detected = int(m.group(1))
            if detected in (2, 7, 14):
                marks = detected

        # Build prompt in the same format used by model_manager.generate()
        # so training distribution matches inference distribution exactly.
        prompt = f"generate {marks}-mark question about {subject}"

        examples.append({
            "prompt":     prompt,
            "completion": q_clean,
        })

    return examples
