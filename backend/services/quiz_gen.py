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


