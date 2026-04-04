import json
import re
import time
from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

# Model fallback chain — tried in order when quota/rate limit hit
MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def _call_gemini_with_retry(prompt, max_wait=60):
    """
    Calls Gemini with automatic retry across model variants.
    On 429 quota errors, waits the retryDelay then tries the next model.
    Returns parsed quiz JSON list.
    """
    last_exc = None
    for model in MODEL_CHAIN:
        try:
            print(f"[quiz_gen] Trying model: {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            print(f"[quiz_gen] ✅ {model} succeeded.")
            return _parse_quiz_json(response.text)
        except (ValueError, json.JSONDecodeError) as e:
            # agar JSON parse failed — same model won't help, try next
            print(f"[quiz_gen] ⚠️ {model} returned unparseable JSON: {e}")
            last_exc = e
        except Exception as e:
            err_str = str(e)
            last_exc = e
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay = 30
                match = re.search(r"retry in ([\d.]+)s", err_str)
                if match:
                    delay = min(float(match.group(1)), max_wait)
                print(f"[quiz_gen] ⚠️ {model} quota hit. Waiting {delay:.0f}s then trying next model...")
                time.sleep(delay)
            else:
                print(f"[quiz_gen] ⚠️ {model} failed: {e}")

    raise last_exc or RuntimeError("All models failed")

def generate_quiz(context, subject, university="", keywords=None, question_count=10):
    """
    Generates an interactive MCQ quiz based on the student's uploaded note content.

    - Uses university-trained model if one exists, converting to MCQs.
    - Falls back to Gemini with retry chain, grounding questions in the note's
      extracted_text and keywords.
    - Always returns exactly `question_count` distinct questions.
    """
    from services.model_manager import model_exists, generate as model_generate

    if university and model_exists(university, subject):
        print(f"[quiz_gen] Using trained model for {university}/{subject} (count={question_count})")
        pattern = {"A": {"marks_per_q": 2, "total_questions": question_count}}
        model_questions = model_generate(university, subject, keywords or [subject], pattern)
        return _mcq_ify(model_questions, subject, university, question_count)

    # ── Gemini Fallback ──────────────────────────────────────────────
    print(f"[quiz_gen] No trained model — using Gemini (count={question_count})")

    topics_str = ", ".join(keywords[:15]) if keywords else subject
    uni_str = f"at {university} university" if university else ""

    # Use the note's extracted text as the reference grounding material
    context_snippet = (context or "").strip()[:4500]

    prompt = f"""You are an expert academic examiner {uni_str}.
Generate EXACTLY {question_count} UNIQUE Multiple Choice Questions (MCQs) for the subject: {subject}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFERENCE MATERIAL (student's uploaded note — base ALL questions on this):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context_snippet}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY TOPICS TO COVER (from the student's notes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{topics_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Generate EXACTLY {question_count} questions — no more, no less.
2. Every question MUST be derived from the reference note material above.
3. Each question MUST test a COMPLETELY DIFFERENT concept — no duplicates.
4. NEVER start questions with: "What is", "Define", "Describe", "List", "Name", "State".
5. USE these academic starters: "Analyze...", "Evaluate the mechanism of...",
   "Synthesize the relationship between...", "Under what conditions would...",
   "Predict the outcome if...", "Critically examine...", "Compare and contrast...",
   "Justify the use of...", "Illustrate how...", "Formulate a solution for...".
6. Each question must have exactly 4 options (A, B, C, D).
7. Distractors (wrong options) must be plausible and technically nuanced.
8. Return ONLY a valid JSON array. No markdown, no preamble, no extra text.

9. DO NOT merge questions together. The JSON array MUST contain EXACTLY {question_count} separate objects! Failure to output discrete objects is unacceptable.

JSON FORMAT (exactly {question_count} independent objects):
[
    {{
        "question": "<question text>",
        "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "answer": "A",
        "explanation": "<why this answer is correct, referencing the note content>"
    }},
    {{
        "question": "<next question text>",
        "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "answer": "B",
        "explanation": "..."
    }}
]"""

    try:
        quiz_data = _call_gemini_with_retry(prompt)
        # Enforce exact count
        if len(quiz_data) < question_count:
            print(f"[quiz_gen] ⚠️ Got {len(quiz_data)} questions, needed {question_count}. Padding.")
            quiz_data.extend(_fallback_quiz(subject, keywords, question_count - len(quiz_data)))
        return quiz_data[:question_count]
    except Exception as e:
        print(f"[quiz_gen] ❌ All models failed: {e}")
        return _fallback_quiz(subject, keywords, question_count)


def _mcq_ify(model_questions, subject, university, question_count=10):
    """
    Uses Gemini to transform subjective university-model questions into MCQs.
    """
    questions_list = "\n".join([f"- {q.get('text', '')}" for q in model_questions])

    prompt = f"""You are an expert examiner at {university}.
Convert the following {subject} exam questions into exactly {question_count} distinct MCQs.

Source Questions:
{questions_list}

RULES:
- EXACTLY {question_count} MCQs. Each must test a different concept.
- 4 options per question (A, B, C, D). One correct answer.
- Distractors must be plausible.
- Return ONLY a valid JSON array. No markdown, no preamble.

- DO NOT merge questions. Output EXACTLY {question_count} independent objects inside the array.

JSON FORMAT (exactly {question_count} independent objects):
[
    {{
        "question": "...",
        "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "answer": "A",
        "explanation": "..."
    }},
    {{
        "question": "...",
        "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
        "answer": "B",
        "explanation": "..."
    }}
]"""

    try:
        quiz_data = _call_gemini_with_retry(prompt)
        if len(quiz_data) < question_count:
            quiz_data.extend(_fallback_quiz(subject, None, question_count - len(quiz_data)))
        return quiz_data[:question_count]
    except Exception as e:
        print(f"[quiz_gen] MCQ-ify failed: {e}")
        return _fallback_quiz(subject, None, question_count)


def _parse_quiz_json(text):
    """Helper to strip markdown fences and parse JSON array."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    # Find JSON array bounds robustly
    start = text.find('[')
    end   = text.rfind(']')
    if start == -1 or end == -1:
        raise json.JSONDecodeError("No JSON array found in response", text, 0)
    text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, list) or len(data) < 1:
        raise ValueError("Invalid quiz format — empty or non-list JSON")
    return data


def _fallback_quiz(subject, keywords=None, count=10):
    """
    Generates `count` distinct fallback questions when all AI calls fail.
    Each question covers a different aspect to avoid duplicates.
    """
    kws = list(keywords[:count]) if keywords and len(keywords) >= count else list(keywords or [])
    while len(kws) < count:
        kws.append(subject)

    # 10 rotating question templates with different correct answers
    templates = [
        ("Analyze the core operational mechanism of",          "A",
         "Its primary functional principle governing its behavior",
         "A storage concept unrelated to its core operation",
         "A networking protocol used for data transfer",
         "A UI rendering technique for visual output"),
        ("Evaluate the trade-offs when applying",              "B",
         "It amplifies latency while reducing throughput",
         "It balances speed and resource consumption optimally",
         "It eliminates all forms of system overhead",
         "It replaces hardware-level constraints entirely"),
        ("Under what conditions would",                        "C",
         "Only when operating in theoretical sandbox environments",
         "Only in legacy systems with no modern equivalent",
         "When system resources are constrained and efficiency is critical",
         "Exclusively in distributed cloud-native architectures"),
        ("Synthesize the relationship between",                "D",
         "They operate in completely isolated silos",
         "One is a strict subset of the other",
         "They share identical computational complexity",
         "They are interdependent, each enhancing the other's effectiveness"),
        ("Critically examine the architectural role of",       "A",
         "It acts as a foundational layer coordinating dependent subsystems",
         "It functions solely as a passive data repository",
         "It replaces the operating system in embedded scenarios",
         "It is redundant in modern microservices architectures"),
        ("Predict the system outcome if",                      "B",
         "Throughput doubles with no side effects",
         "Performance degrades due to increased contention and bottlenecks",
         "No measurable change occurs in system behavior",
         "The system self-optimizes and recovers automatically"),
        ("Compare and contrast the implementation of",         "C",
         "Both approaches yield identical runtime complexity",
         "The first approach fully supersedes the second in all scenarios",
         "They differ in scope, applicability, and computational overhead",
         "Neither approach has been validated in real-world deployments"),
        ("Justify the selection of",                           "A",
         "It optimizes resource utilization and scales with system demands",
         "It was the first historically documented solution",
         "It requires the least configuration effort of all alternatives",
         "It eliminates the need for any further system tuning"),
        ("Illustrate how",                                     "D",
         "Through a single monolithic pipeline with no modular boundaries",
         "By bypassing all intermediate processing layers",
         "Using a reactive event-driven model with no state management",
         "Via a layered modular architecture with clearly defined interfaces"),
        ("Formulate a solution that leverages",                "B",
         "A purely theoretical model with no implementation pathway",
         "A hybrid strategy combining modular design with adaptive optimization",
         "A brute-force enumeration without heuristic guidance",
         "An event-sourced approach independent of the underlying domain"),
    ]

    questions = []
    for i in range(count):
        kw  = kws[i]
        tmpl = templates[i % len(templates)]
        questions.append({
            "question":    f"{tmpl[0]} {kw} within the context of {subject}.",
            "options":     {"A": tmpl[2], "B": tmpl[3], "C": tmpl[4], "D": tmpl[5]},
            "answer":      tmpl[1],
            "explanation": (
                f"This question evaluates understanding of '{kw}' in {subject}. "
                f"Option {tmpl[1]} correctly reflects the fundamental principle as covered in the topic notes."
            )
        })
    return questions