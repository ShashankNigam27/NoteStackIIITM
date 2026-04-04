import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from config import GEMINI_API_KEY
import json
import re
import time

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# Model fallback chain - tried in order when quota/rate limit hit
MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def _call_gemini_with_retry(prompt, max_wait=90):
    """
    Calls Gemini with automatic retry across model variants.
    On 429 quota errors, waits the retryDelay Gemini specifies (up to max_wait),
    then tries the next model in MODEL_CHAIN.
    Raises the last exception if all models fail.
    """
    last_exc = None
    for model in MODEL_CHAIN:
        try:
            print(f"[question_gen] Trying model: {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            print(f"[question_gen] ✅ Model {model} succeeded.")
            return response
        except Exception as e:
            err_str = str(e)
            last_exc = e
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Parse retryDelay from the error message
                delay = 35  # default
                match = re.search(r"retry in ([\d.]+)s", err_str)
                if match:
                    delay = min(float(match.group(1)), max_wait)
                print(f"[question_gen] ⚠️ {model} quota exhausted. Waiting {delay:.0f}s then trying next model...")
                time.sleep(delay)
            else:
                # Non-quota error - don't retry this model, but still try next
                print(f"[question_gen] ⚠️ {model} failed with non-quota error: {e}")
    raise last_exc


def generate_paper(keywords, university, subject, user_id=0, target_count=20):
    """
    Main entry point. Called by ai_routes.py.
    Tries university model first, falls back to Gemini.
    """
    from services.model_manager  import model_exists, generate as model_generate
    from services.difficulty_clf import tag_questions

    counts = _get_section_counts(target_count)

    if model_exists(university, subject):
        print(f"Using trained model for {university}/{subject} (Target: {target_count})")
        pattern = {
            "A": {"marks_per_q": 2,  "total_questions": counts["A"]},
            "B": {"marks_per_q": 7,  "total_questions": counts["B"]},
            "C": {"marks_per_q": 14, "total_questions": counts["C"]},
        }
        questions = model_generate(university, subject, keywords, pattern)
        questions = tag_questions(questions)
        sections  = _build_sections(questions)
        return {
            "questions":       questions,
            "sections":        sections,
            "mode":            "university_model",
            "priority_topics": keywords[:5],
        }

    # No university model — use Gemini
    print(f"No model for {university} — using Gemini fallback (Target: {target_count})")
    return _generate_with_gemini(keywords, university, subject, user_id, target_count=target_count)


def _get_section_counts(target_count):
    """Calculates A,B,C distribution for 5, 10, 15, 20 questions."""
    if target_count <= 5:   return {"A": 2, "B": 2, "C": 1}
    if target_count <= 10:  return {"A": 4, "B": 3, "C": 3}
    if target_count <= 15:  return {"A": 5, "B": 5, "C": 5}
    return {"A": 7, "B": 7, "C": 6} # 20 questions


def _generate_with_gemini(keywords, university, subject, user_id=0, target_count=20):
    """
    Generates question paper using Gemini API.
    Called when no university-trained model exists.
    Includes per-question relevance validation — off-topic questions are filtered.
    """
    from services.firebase_service import get_firestore
    from services.difficulty_clf import tag_questions

    counts = _get_section_counts(target_count)

    # Knowledge Injection: Fetch distilled FAQs from Firestore to ground the generation
    # in the student's actual note content (Knowledge Distillation)
    faqs = []
    db = get_firestore()
    if db:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = db.collection("faqs").where(filter=FieldFilter("uid", "==", str(user_id))).where(filter=FieldFilter("subject", "==", subject)).limit(10).stream()
        for doc in docs:
            faqs.append(doc.to_dict())
    
    knowledge_str = ""
    if faqs:
        knowledge_str = "\n".join([f"Topic: {f.get('question')} | Key Concept: {f.get('answer')}" for f in faqs])

    # Build a numbered keyword list so Gemini knows exactly which keyword goes to which question
    kw_list = keywords[:15] if keywords else [subject]
    # Pad if we have fewer keywords than questions needed
    while len(kw_list) < (counts["A"] + counts["B"] + counts["C"]):
        kw_list.extend(kw_list)
    kw_list = kw_list[: counts["A"] + counts["B"] + counts["C"] ]

    # Split keyword slots per section
    kw_A = kw_list[: counts["A"]]
    kw_B = kw_list[counts["A"] : counts["A"] + counts["B"]]
    kw_C = kw_list[counts["A"] + counts["B"] :]

    kw_A_str = "\n".join([f"  Q{i+1}: MUST use keyword → \"{k}\"" for i, k in enumerate(kw_A)])
    kw_B_str = "\n".join([f"  Q{i+1}: MUST use keyword → \"{k}\"" for i, k in enumerate(kw_B)])
    kw_C_str = "\n".join([f"  Q{i+1}: MUST use keyword → \"{k}\"" for i, k in enumerate(kw_C)])

    prompt = f"""You are an academic examiner. Generate a formal exam paper for:

SUBJECT: {subject}
UNIVERSITY: {university}
{f'REFERENCE NOTE CONTENT:\n{knowledge_str}' if knowledge_str else ''}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEYWORD CONTRACT — THIS IS MANDATORY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every single question MUST be built around its assigned keyword below.
DO NOT write any question about a topic that is not in the keyword list.
DO NOT use generic subject knowledge. ONLY use the assigned keyword.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION A — {counts['A']} questions, 2 marks each
(Short, precise. Use: "Differentiate between...", "Contrast...", "Justify why...",
 "How does [keyword] affect...", "Identify the role of [keyword] in...")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{kw_A_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION B — {counts['B']} questions, 7 marks each
(Analytical with diagram/example. Use: "Illustrate with a diagram how [keyword]...",
 "Compare and contrast [keyword] with...", "Trace the step-by-step working of [keyword]...",
 "Apply [keyword] to solve the scenario: ...")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{kw_B_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION C — {counts['C']} questions, 14 marks each
(Comprehensive, multi-part. Use: "Critically evaluate [keyword]...",
 "Design a complete system using [keyword] and justify your decisions...",
 "Derive and prove [keyword]...", "Synthesize a solution for... using [keyword]...",
 "Formulate a framework based on [keyword] and evaluate its trade-offs.")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{kw_C_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORBIDDEN STARTERS (never use these):
Define, What is, What are, List, State, Name, Mention, Enumerate,
Write short note on, Give an example of, Explain briefly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No markdown. No explanation. No extra text.

JSON FORMAT (fill in EXACTLY {counts['A']} items in A, {counts['B']} in B, {counts['C']} in C):
{{
  "A": [
    {{"text": "<question text> [2 marks]", "marks": 2, "topic": "<keyword>", "relevant": true}},
    ...(exactly {counts['A']} items)
  ],
  "B": [
    {{"text": "<question text> [7 marks]", "marks": 7, "topic": "<keyword>", "relevant": true}},
    ...(exactly {counts['B']} items)
  ],
  "C": [
    {{"text": "<question text> [14 marks]", "marks": 14, "topic": "<keyword>", "relevant": true}},
    ...(exactly {counts['C']} items)
  ]
}}"""

    raw_text = ""
    try:
        response = _call_gemini_with_retry(prompt)

        raw_text = response.text.strip()
        print(f"[question_gen] Raw Gemini response (first 300 chars):\n{raw_text[:300]}")

        # ── Step 1: Strip markdown code fences ────────────────────
        text = re.sub(r'```json\s*', '', raw_text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*',     '', text)
        text = text.strip()

        # ── Step 2: Robustly extract JSON object by brace scanning ─
        # This handles any preamble/postamble text Gemini adds
        start = text.find('{')
        end   = text.rfind('}')
        if start == -1 or end == -1:
            raise json.JSONDecodeError("No JSON object found in response", text, 0)
        text = text[start : end + 1]

        # ── Step 3: Parse ──────────────────────────────────────────
        data      = json.loads(text)
        questions = []
        total_generated = 0
        total_filtered  = 0

        for section, count in counts.items():
            qs = data.get(section, [])
            total_generated += len(qs)

            # Relevance filter: keep only questions Gemini marked relevant
            relevant_qs  = [q for q in qs if q.get("relevant", True) is not False]
            filtered_out = len(qs) - len(relevant_qs)
            total_filtered += filtered_out
            if filtered_out:
                print(f"[relevance] Section {section}: filtered {filtered_out} off-topic question(s).")

            qs = relevant_qs

            # Safety Bridge: pad if relevance filter removed too many
            while len(qs) < count:
                idx   = len(qs)
                topic = keywords[idx % len(keywords)] if keywords else subject
                if section == "A":
                    qs.append({
                        "text":  f"Contrast the key properties of {topic} with an alternative approach used in {subject}. [2 marks]",
                        "marks": 2, "topic": topic, "relevant": True
                    })
                elif section == "B":
                    qs.append({
                        "text":  f"Illustrate with a suitable diagram and worked example how {topic} is applied in {subject}. Include at least one real-world use case. [7 marks]",
                        "marks": 7, "topic": topic, "relevant": True
                    })
                else:
                    qs.append({
                        "text":  f"Critically evaluate the role of {topic} in {subject}. Design a solution that leverages {topic}, derive its theoretical complexity, and justify your design decisions with a neat technical diagram. [14 marks]",
                        "marks": 14, "topic": topic, "relevant": True
                    })

            for q in qs[:count]:
                questions.append({
                    "text":    q.get("text",  ""),
                    "marks":   q.get("marks", 2 if section == "A" else (7 if section == "B" else 14)),
                    "section": section,
                    "topic":   q.get("topic", subject),
                })

        print(f"[question_gen] ✅ Generated: {total_generated} | Relevant: {len(questions)} | Filtered: {total_filtered}")

        questions            = tag_questions(questions)
        data_with_difficulty = _build_sections(questions)

        return {
            "questions":       questions,
            "sections":        data_with_difficulty,
            "mode":            "gemini_fallback",
            "priority_topics": keywords[:5],
            "stats": {
                "total_generated": total_generated,
                "total_relevant":  len(questions),
                "total_filtered":  total_filtered,
            }
        }

    except json.JSONDecodeError as e:
        print(f"[question_gen] ❌ JSON parse FAILED: {e}")
        print(f"[question_gen] Gemini raw output was:\n{raw_text}")
        return _fallback(subject, keywords)

    except Exception as e:
        import traceback
        print(f"[question_gen] ❌ Unexpected error: {e}")
        traceback.print_exc()
        return _fallback(subject, keywords)


def _build_sections(questions):
    """Groups flat question list into sections dict."""
    sections = {"A": [], "B": [], "C": []}
    for q in questions:
        sec = q.get("section", "A")
        if sec in sections:
            sections[sec].append(q)
    return sections


def _fallback(subject, keywords=None):
    """
    Safe fallback. App never crashes because of question generation.
    Uses high-quality question starters — never 'Define' or 'Explain'.
    """
    kw1 = keywords[0] if keywords and len(keywords) > 0 else subject
    kw2 = keywords[1] if keywords and len(keywords) > 1 else subject
    kw3 = keywords[2] if keywords and len(keywords) > 2 else subject
    return {
        "questions": [
            {"text": f"Contrast the fundamental characteristics of {kw1} with an alternative approach in {subject}. [2 marks]",
             "marks": 2,  "section": "A", "topic": kw1, "difficulty": "Easy"},
            {"text": f"Illustrate with a step-by-step worked example how {kw2} is applied within {subject}. Include a suitable diagram. [7 marks]",
             "marks": 7,  "section": "B", "topic": kw2, "difficulty": "Medium"},
            {"text": f"Critically evaluate the role of {kw3} in {subject}. Design a solution leveraging {kw3}, derive its theoretical complexity, and justify your design decisions with a neat diagram. [14 marks]",
             "marks": 14, "section": "C", "topic": kw3, "difficulty": "Hard"},
        ],
        "sections": {
            "A": [{"text": f"Contrast the fundamental characteristics of {kw1} with an alternative approach in {subject}. [2 marks]",
                   "marks": 2, "topic": kw1, "difficulty": "Easy"}],
            "B": [{"text": f"Illustrate with a step-by-step worked example how {kw2} is applied within {subject}. Include a suitable diagram. [7 marks]",
                   "marks": 7, "topic": kw2, "difficulty": "Medium"}],
            "C": [{"text": f"Critically evaluate the role of {kw3} in {subject}. Design a solution leveraging {kw3}, derive its theoretical complexity, and justify your design decisions with a neat diagram. [14 marks]",
                   "marks": 14, "topic": kw3, "difficulty": "Hard"}],
        },
        "mode":            "gemini_fallback",
        "priority_topics": keywords[:5] if keywords else [subject],
        "stats": {"total_generated": 3, "total_relevant": 3, "total_filtered": 0},
    }