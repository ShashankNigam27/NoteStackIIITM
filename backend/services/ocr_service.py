import fitz # PyMuPDF — opens PDFs
import pytesseract # reads text from images
from PIL import Image, ImageFilter
import io

def extract_text(file_bytes, file_type):
    if file_type == 'pdf':
        return _from_pdf(file_bytes)
    else:
        return _from_image(file_bytes)
    
def _from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    text = ''

    for page in doc:
        page_text = page.get_text()

        if len(page_text.strip()) < 30:  # Scanned page, use OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes('png')))
            ocr_text = pytesseract.image_to_string(img)
            text += ocr_text.strip() + '\n'
        else:
            text += page_text.strip() + '\n'

    return text.strip()
    
def _from_image(file_bytes):
    img = Image.open(io.BytesIO(file_bytes))
    gray = img.convert('L') # grayscale improves accuracy
    sharp= gray.filter(ImageFilter.SHARPEN)
    return pytesseract.image_to_string(sharp)
