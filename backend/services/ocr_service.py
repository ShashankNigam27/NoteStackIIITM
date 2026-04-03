import pymupdf as fitz  # PyMuPDF
import io
import os

# ── Tesseract / Pillow are optional ─────────────────────────────
# Digital PDF jisme text ko copy paste krskte usme tesseract ki jarurat nhi hai. Lekin scanned PDF me text ko copy paste nhi krskte isliye tesseract ki jarurat hoti hai.

_TESSERACT_AVAILABLE = False
_TESSERACT_PATH      = ""

try:
    import pytesseract
    from PIL import Image, ImageFilter

    # in location me tesseract install krna hai jis laptop me display krenge project ko.
    _candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(
            os.environ.get("USERNAME", "")
        ),
    ]

    # Also check env override
    env_path = os.environ.get("TESSERACT_PATH", "")
    if env_path:
        _candidates.insert(0, env_path)

    for _path in _candidates:
        if os.path.exists(_path):
            pytesseract.pytesseract.tesseract_cmd = _path
            _TESSERACT_PATH = _path
            _TESSERACT_AVAILABLE = True
            break

    # If not found in standard paths, try calling it from PATH
    if not _TESSERACT_AVAILABLE:
        import subprocess
        try:
            subprocess.run(["tesseract", "--version"],
                           capture_output=True, check=True, timeout=3)
            _TESSERACT_AVAILABLE = True
            _TESSERACT_PATH = "tesseract (from PATH)"
        except Exception:
            pass

except ImportError:
    pass  # pytesseract not even installed

print(f"[OCR] Tesseract available: {_TESSERACT_AVAILABLE}"
      + (f" at {_TESSERACT_PATH}" if _TESSERACT_PATH else ""))

def extract_text(file_bytes, file_type):
    """
    Main entry point. Called by app.py

    Args:
        file_bytes (bytes): raw file data
        file_type  (str):  'pdf' or 'image'

    Returns:
        str: extracted clean text (or '' on failure)
    """
    try:
        if file_type == 'pdf':
            return _extract_from_pdf(file_bytes)
        else:
            return _extract_from_image(file_bytes)
    except Exception as e:
        print(f"[OCR] Extraction failed: {e}")
        return ""

#---------------------------------------------------------------------------------
# PDF

def _extract_from_pdf(file_bytes):
    """
    Handles both:
    - Digital PDFs (direct text via PyMuPDF — no Tesseract needed)
    - Scanned PDFs (OCR via Tesseract — only if installed)
    """
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    full_text = ""

    for page_num, page in enumerate(doc):
        # try direct text first (works for digital PDFs)
        text = page.get_text().strip()

        if len(text) >= 30:
            # Digital PDF page — text extracted directly
            full_text += text + "\n"
        elif _TESSERACT_AVAILABLE:
            # Scanned page — fall back to OCR
            print(f"[OCR] Page {page_num+1}: scanned, running Tesseract")
            ocr_text = _ocr_page(page)
            full_text += ocr_text + "\n"
        else:
            # Can't OCR without Tesseract — skip page
            print(f"[OCR] Page {page_num+1}: scanned but Tesseract not installed, skipping")

    return _clean_text(full_text)


def _ocr_page(page):
    """Converts a PDF page → image → Tesseract OCR text."""
    from PIL import Image, ImageFilter
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img = img.convert("L")           # grayscale
    img = img.filter(ImageFilter.SHARPEN)
    return pytesseract.image_to_string(img)



# IMAGE


def _extract_from_image(file_bytes):
    """
    OCR for image files (jpg, png).
    Requires Tesseract to be installed.
    """
    if not _TESSERACT_AVAILABLE:
        return (
            "[Tesseract not installed] Cannot extract text from images. "
            "Please upload a PDF with selectable text, or install Tesseract-OCR from: "
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )

    from PIL import Image, ImageFilter
    img = Image.open(io.BytesIO(file_bytes))
    img = img.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    return pytesseract.image_to_string(img)

#----------------------------------------------------------------------------------
#Cleaning

def _clean_text(text):
    """Basic cleanup to improve downstream ML quality."""
    if not text:
        return ""
    text = text.replace('\r', ' ').replace('\t', ' ')
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if len(line) > 2]  # skip noise lines
    return '\n'.join(lines)


# ----------------------------------------------------------------------------------
# STATUS CHECK (for debugging)


def get_status():
    return {
        "pymupdf":   True,  # always available (installed)
        "tesseract": _TESSERACT_AVAILABLE,
        "tesseract_path": _TESSERACT_PATH,
        "pdf_digital": True,
        "pdf_scanned": _TESSERACT_AVAILABLE,
        "images":    _TESSERACT_AVAILABLE,
    }
