# NoteStackIIITM
An AI-powered academic tool that helps university students upload notes, get smart summaries, and generate university-style exam papers.

---

## Project Structure

```
NoteStack/
├── frontend/              ← Static HTML/CSS/JS (served by Flask)
│   ├── pages/             ← All HTML pages
│   ├── components/        ← Reusable sidebar, navbar components
│   ├── css/               ← Global CSS + per-page CSS
│   ├── js/                ← Firebase, API client, page scripts
│   └── assets/            ← Logo, icons
│
├── backend/               ← Flask API + ML services
│   ├── app.py             ← Entry point (Flask app + blueprint registration)
│   ├── config.py          ← All configuration from .env
│   ├── routes/            ← API blueprints (auth, upload, notes, ai, test)
│   ├── services/          ← ML services (OCR, TF-IDF, Gemini, difficulty clf)
│   ├── models/            ← Trained ML models (pkl + T5 checkpoints)
│   └── training/          ← Data prep + model training scripts
│
└── docs/                  ← SRS and Developer Guide PDFs
```

---

## Getting Started

### 1. Set up the virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

For ML model training (optional):

```bash
pip install torch transformers sentencepiece
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your GEMINI_API_KEY
```

### 4. Run the app

```bash
cd backend
python app.py
```

Visit: [http://localhost:5000](http://localhost:5000)

---

## ML Services

| Service        | File                        | Description                                   |
|----------------|-----------------------------|-----------------------------------------------|
| OCR            | `services/ocr_service.py`   | Extracts text from PDF/image notes            |
| TF-IDF         | `services/tfidf_service.py` | Extracts keywords & key sentences             |
| Summarizer     | `services/summarizer.py`    | Gemini-powered exam-focused summary           |
| Question Gen   | `services/question_gen.py`  | Generates paper (university model → Gemini fallback) |
| Difficulty Clf | `services/difficulty_clf.py`| Naive Bayes: Easy / Medium / Hard             |
| Model Manager  | `services/model_manager.py` | Loads / caches T5 university models           |

---

## Training a University Model

1. Add question paper PDFs to `backend/training/raw_papers/`  
   Filename format: `RGPV_DSA_2023.pdf`

2. Run data prep:
   ```bash
   python training/data_prep.py
   ```

3. Train:
   ```bash
   python training/train.py --university RGPV --subject DSA
   ```

4. Evaluate:
   ```bash
   python training/evaluate.py --university RGPV
   ```

---

## Environment Variables

| Variable                | Required | Description                  |
|--------------------------|----------|------------------------------|
| `GEMINI_API_KEY`         | Yes      | Google Gemini API key        |
| `SECRET_KEY`             | Yes      | Flask session secret         |
| `FIREBASE_STORAGE_BUCKET`| Optional | Firebase storage bucket      |

---

## Virtual Environment

**Single shared venv: `frontend/venv/`** — this is the only active venv for the entire project.  
The old `backend/venv/` was broken and has been deleted.

| Task                  | Command                                                                 |
|-----------------------|-------------------------------------------------------------------------|
| Start app (Windows)   | Double-click `run.bat` OR run `frontend\venv\Scripts\python backend\app.py` |
| Install new package   | `frontend\venv\Scripts\pip install <package>`                           |
| Start app (Mac/Linux) | `source frontend/venv/bin/activate && cd backend && python app.py`      |

---

## Team

| Developer | Contribution                                                                 |
|-----------|-------------------------------------------------------------------------------|
| Dev 1     | Frontend HTML/CSS/Tailwind, Flask auth, SQLite, base routes                   |
| Dev 2     | ML services (OCR, TF-IDF, Gemini AI, difficulty classifier, model manager)    |

---

## License

This project is intended for academic and research purposes.  
Please ensure compliance with your institution’s guidelines before use.
```

---

Would you like me to also add a **"Features" section** (highlighting capabilities like smart summaries, exam paper generation, OCR, etc.) so the README doubles as a project showcase for GitHub?
