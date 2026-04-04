import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle
from config import DIFFICULTY_CLF_PATH

TRAIN_X = [

    # ── EASY (contrast, differentiate, justify, identify significance) ────
    "Define binary tree",
    "What is time complexity",
    "What is recursion",
    "What is a stack",
    "What is a queue",
    "What is hashing",
    "What is dynamic programming",
    "What is an array",
    "What is a graph",
    "What is a linked list",
    "List any two sorting algorithms",
    "List the types of tree traversal",
    "List operations of a stack",
    "List two graph traversal algorithms",
    "List properties of AVL tree",
    "State the BST property",
    "State DeMorgan theorem",
    "State the properties of a heap",
    "Name two searching algorithms",
    "Name the types of linked list",
    "Define AVL tree",
    "Define hashing and hash function",
    "Define graph and its types",
    "Define pointer",
    "Define recursion",
    "Define sorting",
    "Define traversal",
    "Define spanning tree",
    "Define complexity",
    "Define adjacency matrix",
    # New easy starters
    "Contrast the key properties of stack with queue",
    "Contrast binary search tree with balanced tree",
    "Differentiate between BFS and DFS",
    "Differentiate between linear and binary search",
    "Differentiate between array and linked list",
    "Justify why quicksort is preferred over bubble sort",
    "Justify the use of recursion in tree traversal",
    "Identify the significance of hashing in databases",
    "Identify the significance of graph algorithms in networking",
    "How does dynamic programming affect time complexity",
    "How does hashing affect search performance",
    "In the context of data structures how is a heap applied",
    "In the context of algorithms how is memoization applied",


    # ── MEDIUM (explain, describe, illustrate, compare, apply, trace) ────
    "Explain binary search tree with a suitable example",
    "Explain AVL tree with example",
    "Explain insertion sort with suitable example",
    "Explain the concept of dynamic programming with example",
    "Explain depth first search with example",
    "Explain quick sort with suitable example",
    "Describe merge sort algorithm with steps",
    "Describe Prim algorithm for minimum spanning tree",
    "Describe hashing with collision resolution techniques",
    "Describe breadth first search with example",
    "Illustrate BFS traversal with a diagram",
    "Illustrate DFS traversal with a diagram",
    "Illustrate insertion in AVL tree",
    "Illustrate quick sort with example",
    "Illustrate binary search with example",
    "Compare stack and queue with suitable examples",
    "Compare DFS and BFS traversal",
    "Compare linear and binary search",
    "Compare array and linked list",
    "Compare BFS and DFS with examples",
    "Discuss the applications of stack",
    "Discuss collision resolution in hashing",
    "Discuss the properties of binary heap",
    "Discuss advantages of AVL tree",
    "Discuss applications of graph",
    "Show the steps of merge sort",
    "Show insertion in binary search tree",
    "Show deletion in AVL tree",
    "Show BFS traversal step by step",
    "Show working of hash function",
    # New medium starters
    "Illustrate with a suitable diagram and worked example how AVL rotations maintain balance",
    "Illustrate with a suitable diagram and worked example how heap sort operates",
    "Compare and contrast quicksort and mergesort with reference to their performance",
    "Compare and contrast stack and queue with reference to their use in algorithms",
    "Apply the concept of dynamic programming to solve the coin change problem",
    "Apply the concept of graph traversal to solve a path finding problem",
    "Trace through the step by step working of binary search when applied to a sorted array",
    "Trace through the step by step working of merge sort when applied to unsorted data",
    "With the help of a worked example demonstrate how hashing operates under collision",
    "With the help of a worked example demonstrate how AVL trees maintain height balance",
    "Illustrate with a suitable diagram and example how recursion solves tree traversal",
    "Compare and contrast greedy and dynamic programming with reference to efficiency",


    # ── HARD (derive, prove, critically analyze, design, synthesize, formulate) ────
    "Derive time complexity of quicksort for best worst and average case",
    "Derive time complexity of merge sort",
    "Derive the recurrence relation and solve using master theorem",
    "Derive and compare all cases for binary search tree operations",
    "Prove that heapsort runs in O n log n time",
    "Prove correctness of Dijkstra algorithm",
    "Prove that AVL tree height is O log n",
    "Prove that binary search runs in O log n",
    "Critically analyze and compare all sorting algorithms",
    "Critically evaluate divide and conquer strategy with examples",
    "Critically analyze space and time complexity of dynamic programming",
    "Critically analyze hashing techniques and collision resolution",
    "Design an algorithm for shortest path and prove its correctness",
    "Design a data structure for given problem and analyze complexity",
    "Design and implement sorting algorithm for linked list",
    "Design an efficient algorithm and prove its time complexity",
    "Design a hash function and analyze collision probability",
    "Design and implement graph algorithm for topological sort",
    "Analyze and compare time complexity of all tree operations",
    "Analyze best worst and average case of bubble sort",
    "Evaluate and compare greedy and dynamic programming approaches",
    "Evaluate time and space complexity of graph algorithms",
    "Implement and analyze binary search tree with all operations",
    "Implement AVL tree with all rotation cases and analyze",
    "Implement heap sort and derive its time complexity",
    "Compare and analyze all graph shortest path algorithms",
    "Compare sorting algorithms and derive their complexities",
    "Compare and prove efficiency of different hashing techniques",
    "Explain with neat diagram and derive time complexity of BST",
    "Explain AVL tree rotations with neat diagram and prove height",
    "Design a sorting algorithm",
    "Design algorithm for linked list",
    "Design sorting for linked list and analyze",
    # New hard starters
    "Critically evaluate the role of dynamic programming in optimization and justify its superiority",
    "Critically evaluate hashing techniques and evaluate their trade-offs in large scale systems",
    "Design a complete graph traversal framework and justify your design decisions with a neat diagram",
    "Design a complete sorting system and justify your design decisions including complexity proofs",
    "Derive and prove the correctness of Kruskal algorithm with a neat diagram",
    "Derive and prove time and space complexity of dynamic programming approach",
    "Construct and analyze a balanced binary search tree for an application",
    "Construct and analyze a hash table with open addressing and derive its performance",
    "Synthesize a solution for the shortest path problem using Dijkstra and evaluate its efficiency",
    "Synthesize a solution for the minimum spanning tree problem and prove its optimality",
    "Formulate a framework for cache friendly traversal and evaluate its trade offs",
    "Formulate a framework for adaptive sorting and evaluate its trade offs under different inputs",


]


TRAIN_Y = (
    ["Easy"]   * 43 +
    ["Medium"] * 42 +
    ["Hard"]   * 45
)


def train_and_save():
    """
    Trains the Naive Bayes classifier on hardcoded examples.
    Saves the model to DIFFICULTY_CLF_PATH as a pkl file.
    Called automatically on first run if pkl does not exist.
    """
    print("Training difficulty classifier...")

    clf = Pipeline([
        ("tfidf", TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
        )),
        ("nb", MultinomialNB()),
    ])

    clf.fit(TRAIN_X, TRAIN_Y)

    # Save to disk
    os.makedirs(os.path.dirname(DIFFICULTY_CLF_PATH), exist_ok=True)
    pickle.dump(clf, open(DIFFICULTY_CLF_PATH, "wb"))

    print(f"Classifier saved to {DIFFICULTY_CLF_PATH}")
    return clf

def _load_clf():
    """
    Loads classifier from disk.
    Trains and saves first if pkl does not exist.
    """
    if not os.path.exists(DIFFICULTY_CLF_PATH):
        return train_and_save()
    return pickle.load(open(DIFFICULTY_CLF_PATH, "rb"))


def predict(question_text):
    """
    Predicts difficulty of a single question.

    Args:
        question_text : string — the question text

    Returns:
        string — "Easy", "Medium", or "Hard"
    """
    clf = _load_clf()
    return clf.predict([question_text])[0]


def tag_questions(questions):
    """
    Tags a list of question dicts with difficulty.
    Each dict must have a "text" key.

    Args:
        questions : list of dicts e.g.
                    [{"text": "Define BST", "marks": 2, ...}]

    Returns:
        same list with "difficulty" key added to each dict
    """
    if not questions:
        return questions

    clf   = _load_clf()
    texts = [q.get("text", "") for q in questions]

    try:
        labels = clf.predict(texts)
        for q, label in zip(questions, labels):
            q["difficulty"] = label
    except Exception as e:
        # If prediction fails, default to Medium
        for q in questions:
            q["difficulty"] = "Medium"

    return questions


# ── Run directly to train and test ───────────────────────────
if __name__ == "__main__":

    # Train the model
    clf = train_and_save()

    # Test on new unseen examples
    test_questions = [
        "Define stack",
        "What is recursion",
        "Explain BFS with diagram",
        "Compare DFS and BFS",
        "Derive time complexity of merge sort",
        "Prove correctness of Dijkstra algorithm",
        "Critically analyze hashing techniques",
        "Design a sorting algorithm for linked list",
    ]

    print("\nTesting predictions:")
    print("=" * 60)
    for q in test_questions:
        label = predict(q)
        print(f"  {label:<8} ← {q}")
    print("=" * 60)