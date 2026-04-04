import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from config import TFIDF_MAX_KEYWORDS, TFIDF_MAX_SENTENCES


def analyze(new_text, subject="", university=""):
    """
    Main function. Called after OCR extracts text from uploaded note.

    Args:
        new_text   : string — full text extracted from uploaded note
        subject    : string — e.g. "Data Structures and Algorithms"
        university : string — e.g. "RGPV"

    Returns:
        keywords          : list of top 10 important words
        important_sentences: list of top 5 important sentences
    """

    # existing notes fetch krlo if already in firestore
    existing_texts = _fetch_existing_notes(university, subject)

    # build corpus
    # New note is always the LAST document in the corpus
    corpus = existing_texts + [new_text]

    # If only one document exists (no existing notes yet)
    # add a placeholder so IDF does not become zero
    if len(corpus) < 2:
        corpus = [
            "this is a placeholder document for idf base calculation",
            new_text
        ]

    # Extract keywords
    keywords = _extract_keywords(corpus, new_text)

    # Score sentences
    sentences = _score_sentences(corpus, new_text)

    return keywords, sentences


def _fetch_existing_notes(university, subject):
    """
    Fetches extracted text from existing notes in Firestore.
    Returns list of text strings.
    If Firebase is not set up yet, returns empty list gracefully.
    """
    try:
        # Import here to avoid circular imports
        from firebase_admin import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
        db   = firestore.client()
        docs = (
            db.collection("notes")
            .where(filter=FieldFilter("university", "==", university))
            .where(filter=FieldFilter("subject", "==", subject))
            .where(filter=FieldFilter("status", "==", "active"))
            .limit(20)
            .stream()
        )
        texts = []
        for doc in docs:
            data = doc.to_dict()
            text = data.get("extracted_text", "")
            if text:
                texts.append(text)
        return texts

    except Exception:
        # Firebase not set up yet — return empty list
        # TF-IDF will still work with just the new note + placeholder
        return []


def _extract_keywords(corpus, target_text):
    """
    Fits TF-IDF on corpus.
    Returns top N meaningful keywords from target_text.
    """
    try:
        # Custom stopwords - bina mtlb ke common words jo har note me hote hain
        custom_stopwords = [
            
            "include", "includes", "including", "also", "used", "using", "use", "uses",
            "called", "known", "refers", "defined", "given", "based", "following",
            "example", "examples", "note", "notes", "shown", "figure", "table",
            "chapter", "section", "page", "left", "right", "child", "parent",
            "node", "nodes", "case", "cases", "set", "sets", "list", "element",
            "elements", "value", "values", "number", "numbers", "order", "type",
            "types", "way", "ways", "form", "forms", "parts", "point", "points",
            "step", "steps", "level", "levels", "size", "data", "function",
            "study", "student", "university", "subject", "topic", "topics", "lecture",
            "class", "classes", "provide", "provides", "provided", "different",
            "various", "important", "main", "key", "result", "results", "analysis",
            "team", "process", "process", "various", "multiple", "several", "each",
            "abstract", "introduction", "conclusion", "summary", "references", 
            "bibliography", "appendix", "acknowledgements", "acknowledges", "intro",
            "background", "future", "related", "work", "conclusion", "method", 
            "methodology", "theory", "theoretical", "principles", "overview",
            "scanned", "camscanner", "scanner", "resolution", "image", "document",
            "of", "total", "copyright", "rights", "reserved", "all", "reserved",
            "file", "upload", "download", "pdf", "docx", "txt", "link", "url",
            "analyze", "examine", "describe", "discuss", "show", "illustrates", 
            "represents", "indicates", "suggests", "considers", "compares", 
            "contrast", "evaluate", "justify", "synthesize", "formulate",
            "highly", "very", "extremely", "simply", "basic", "fundamental",
            "however", "therefore", "thus", "hence", "moreover", "furthermore",
            "similarly", "additionally", "consequently", "finally", "firstly", 
            "secondly", "thirdly", "next", "then", "last", "finally",
            "amount", "quantity", "degree", "extent", "level", "scale", "measure",
            "performance", "efficiency", "increase", "decrease", "high", "low",
            "large", "small", "greater", "smaller", "maximum", "minimum"
        ]

        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        all_stopwords = list(ENGLISH_STOP_WORDS) + custom_stopwords

        vectorizer = TfidfVectorizer(
            stop_words=all_stopwords,
            max_features=500,
            ngram_range=(1, 2),    # single words AND two-word phrases
            min_df=1,
            sublinear_tf=True,
            token_pattern=r'\b[a-zA-Z][a-zA-Z][a-zA-Z]+\b',  # min 3 chars
        )

        matrix        = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()

        # Target is always last document
        target_vec = matrix[-1].toarray()[0]

        # Get all words with scores above zero
        scored = [
            (feature_names[i], target_vec[i])
            for i in range(len(target_vec))
            if target_vec[i] > 0
        ]

        # Sort by score descending
        scored.sort(key=lambda x: -x[1])

        # Return top N keyword strings only
        keywords = [word for word, score in scored[:TFIDF_MAX_KEYWORDS]]

        return keywords

    except Exception as e:
        print(f"Keyword extraction failed: {str(e)}")
        return []
    
def _score_sentences(corpus, target_text):
    """
        Scores each sentence in target_text by TF-IDF importance.
        Returns top N most important sentences.
    """
    # Split text into sentences
    sentences = [
        s.strip()
        for s in target_text.replace("\n", ". ").split(".")
        if len(s.strip()) > 20     # ignore very short fragments
    ]

    if not sentences:
        return []

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=1000,
            min_df=1,
        )

        # Fit on full corpus for proper IDF
        vectorizer.fit_transform(corpus)

        # Transform only the sentences
        sent_matrix = vectorizer.transform(sentences).toarray()

        # Score each sentence = sum of all its word TF-IDF scores
        scores = sent_matrix.sum(axis=1)

        # Get top N sentence indices
        top_indices = scores.argsort()[-TFIDF_MAX_SENTENCES:][::-1]

        important = [sentences[i] for i in top_indices]
        return important

    except Exception as e:
        print(f"Sentence scoring failed: {str(e)}")
        return sentences[:TFIDF_MAX_SENTENCES]


def get_topic_frequency(university, subject):
    """
    Analyzes all verified PYQs for a university and subject.
    Returns topics ranked by how often they appear across papers.
    Used by the AI tools page to show students what to prioritize.
    """
    try:
        from firebase_admin import firestore
        from collections import Counter
        from google.cloud.firestore_v1.base_query import FieldFilter

        db   = firestore.client()
        docs = (
            db.collection("pyq_papers")
            .where(filter=FieldFilter("university", "==", university))
            .where(filter=FieldFilter("subject", "==", subject))
            .where(filter=FieldFilter("status", "==", "verified"))
            .stream()
        )

        topic_counter = Counter()
        total_papers  = 0

        for doc in docs:
            data = doc.to_dict()
            total_papers += 1
            for q in data.get("questions", []):
                topic = q.get("topic", "")
                if topic:
                    topic_counter[topic] += 1

        result = [
            {
                "topic":      topic,
                "count":      count,
                "percentage": round((count / total_papers) * 100)
                              if total_papers > 0 else 0
            }
            for topic, count in topic_counter.most_common(15)
        ]
        return result

    except Exception:
        return []