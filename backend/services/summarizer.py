import sys
import os
import json
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GEMINI_API_KEY

# ── Initialize Gemini client ─────────────────────────────────────
_client = None

def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env file")
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def summarize(important_sentences, subject, university=""):
    """
    Takes key sentences extracted from a note (via TF-IDF).
    Returns a clean structured exam-focused summary using Gemini.

    """
    if not important_sentences:
        return "Not enough content to summarize. Please upload a clearer note with more readable text."

    # Cap context to avoid token limit issues
    context = " ".join(important_sentences[:15])
    if len(context) > 4000:
        context = context[:4000]

    uni_str = f"at {university} university" if university else ""

    prompt = f"""You are an expert exam preparation assistant {uni_str}.
Your task is to distill messy, OCR-extracted lecture notes into a high-yield revision summary.

Subject: {subject}
Raw Extracted Text:
{context}

Based ONLY on the text above, provide a structured exam-revision summary in exactly this format:

- [Key Concept 1: Clear, concise explanation]
- [Key Concept 2: Clear, concise explanation]
- [Key Concept 3: Clear, concise explanation]
- [Key Concept 4: Clear, concise explanation]
- [Key Concept 5: Clear, concise explanation]

Definition: [The single most important technical definition found in the text]

Most likely exam topics: [Comma-separated list of 3 specific topics]

Strict Rules:
1. Ignore any OCR noise (like partial words, page numbers, or symbols).
2. If the text is too messy to extract 5 concepts, provide as many as possible (min 3).
3. Do NOT include any preamble, introduction, or "Here is your summary".
4. Focus on "High-Yield" topics that are likely to appear in a university exam.
5. Use professional, academic tone."""

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()

    except RuntimeError as e:
        # API key missing
        return f"[Config Error] {e}"

    except Exception as e:
        err = str(e)
        print(f"[Summarizer] Gemini API error: {err}")
        # Return a basic extractive summary as fallback
        return _extractive_fallback(important_sentences, subject)


def _extractive_fallback(sentences, subject):
    """
    Pure local fallback no API needed.
    Just formats the key sentences into bullet points.
    """
    bullets = []
    for s in sentences[:6]:
        s = s.strip()
        if len(s) > 20:
            bullets.append(f"- {s}")

    if not bullets:
        return f"Summary unavailable. Subject: {subject}. Please check your GEMINI_API_KEY in backend/.env"

    return "\n".join(bullets) + f"\n\nMost likely exam topics: {subject}"


def extract_faqs(important_sentences, keywords, subject, university=""):
    """
    Knowledge Distillation: Extracts high-yield FAQ pairs from the note skeleton.
    This 'trains' the system on specific note content for better future generation.
    """
    if not important_sentences:
        return []

    # Use sentences and keywords as the 'skeleton' context
    context = " ".join(important_sentences[:15])
    uni_str = f"at {university} university" if university else ""

    prompt = f"""You are an expert exam preparation assistant {uni_str}.
Subject: {subject}
Keywords: {", ".join(keywords)}
Key Content extracted from student notes:
{context}

Based on this 'skeleton' of knowledge, generate exactly 3 Question and Answer pairs that are most likely to appear in a university exam. 
Make the questions sound like real university exam questions.

Return ONLY a valid JSON list of objects in exactly this format:
[
  {{"q": "What is the primary difference between X and Y?", "a": "X is... while Y is..."}},
  {{"q": "Define Z and its significance in {subject}.", "a": "Z is defined as... it is significant because..."}}
]
Do not include markdown code blocks. Return ONLY the raw JSON."""

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        raw = response.text.strip()
        # Clean up possible markdown or garbage
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*',     '', raw)
        
        return json.loads(raw)
    except Exception as e:
        print(f"[Distiller] Failed to extract FAQs: {e}")
        return []