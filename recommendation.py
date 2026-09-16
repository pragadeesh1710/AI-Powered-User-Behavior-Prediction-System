import math
import re
from collections import Counter, defaultdict
from database import get_connection

# Behaviour weights used by the recommendation model.
ACTIVITY_WEIGHTS = {
    "view": 1,
    "enroll": 4,
    "complete": 6,
    "favorite": 3,
    "rate": 2,
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "this", "that", "learn",
    "course", "courses", "using", "your", "you", "about", "basic", "basics",
    "fundamentals", "introduction", "to", "of", "in", "on", "a", "an"
}


def tokenize(text):
    words = re.findall(r"[a-zA-Z0-9+#]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def build_course_text(course):
    return " ".join([
        course["name"] or "",
        course["category"] or "",
        course["description"] or "",
       course["difficulty"] if "difficulty" in course.keys() else ""
    ])


def tfidf_vectors(documents):
    tokenized = [tokenize(d) for d in documents]
    df = Counter()
    for tokens in tokenized:
        df.update(set(tokens))

    n = max(len(documents), 1)
    vectors = []
    for tokens in tokenized:
        counts = Counter(tokens)
        total = max(len(tokens), 1)
        vector = {}
        for term, count in counts.items():
            idf = math.log((1 + n) / (1 + df[term])) + 1
            vector[term] = (count / total) * idf
        vectors.append(vector)
    return vectors


def cosine_similarity(a, b):
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def get_user_profile(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT ua.course_id, ua.activity_type, ua.timestamp,
               c.category, c.name, c.description
        FROM user_activity ua
        JOIN courses c ON c.course_id = ua.course_id
        WHERE ua.user_id = ?
        ORDER BY ua.timestamp DESC
    """, (user_id,))
    activity = cursor.fetchall()

    cursor.execute("""
        SELECT query FROM search_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 30
    """, (user_id,))
    searches = [r["query"] for r in cursor.fetchall()]

    cursor.execute("""
        SELECT course_id, seconds FROM course_time
        WHERE user_id = ?
    """, (user_id,))
    time_rows = cursor.fetchall()

    cursor.execute("""
        SELECT course_id, rating FROM ratings
        WHERE user_id = ?
    """, (user_id,))
    ratings = {r["course_id"]: r["rating"] for r in cursor.fetchall()}

    cursor.execute("""
        SELECT course_id FROM favorites
        WHERE user_id = ?
    """, (user_id,))
    favorites = {r["course_id"] for r in cursor.fetchall()}

    connection.close()

    category_scores = defaultdict(float)
    interacted = set()
    course_interest = defaultdict(float)

    for row in activity:
        weight = ACTIVITY_WEIGHTS.get(row["activity_type"], 1)
        category_scores[row["category"]] += weight
        course_interest[row["course_id"]] += weight
        interacted.add(row["course_id"])

    for row in time_rows:
        # Time is intentionally capped so a long inactive browser tab
        # does not overwhelm explicit actions.
        minutes = min(row["seconds"], 30 * 60) / 60
        bonus = min(minutes / 2, 5)
        course_interest[row["course_id"]] += bonus

        for activity_row in activity:
            if activity_row["course_id"] == row["course_id"]:
                category_scores[activity_row["category"]] += bonus
                break

    for course_id in favorites:
        course_interest[course_id] += ACTIVITY_WEIGHTS["favorite"]

    for course_id, rating in ratings.items():
        course_interest[course_id] += rating * 0.6

    return {
        "activity": activity,
        "searches": searches,
        "time": {r["course_id"]: r["seconds"] for r in time_rows},
        "ratings": ratings,
        "favorites": favorites,
        "category_scores": dict(category_scores),
        "course_interest": dict(course_interest),
        "interacted": interacted,
    }


def get_user_interest_summary(user_id):
    profile = get_user_profile(user_id)
    rows = []
    for category, score in sorted(
        profile["category_scores"].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        views = sum(
            1 for row in profile["activity"]
            if row["category"] == category and row["activity_type"] == "view"
        )
        rows.append({
            "category": category,
            "score": round(score, 1),
            "views": views
        })
    return rows


def get_popular_courses(limit=5, exclude_ids=None):
    exclude_ids = exclude_ids or set()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT c.*, COUNT(ua.activity_id) AS popularity
        FROM courses c
        LEFT JOIN user_activity ua ON c.course_id = ua.course_id
        GROUP BY c.course_id
        ORDER BY popularity DESC, c.rating DESC, c.name
    """)
    rows = cursor.fetchall()
    connection.close()

    return [
        dict(r) for r in rows
        if r["course_id"] not in exclude_ids
    ][:limit]


def recommend_courses(user_id, limit=10):
    profile = get_user_profile(user_id)

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM courses ORDER BY name")
    courses = [dict(r) for r in cursor.fetchall()]
    connection.close()

    if not profile["activity"] and not profile["searches"]:
        result = get_popular_courses(limit)
        for course in result:
            course["recommendation_score"] = 0
            course["recommendation_reason"] = "Popular among learners."
        return result

    # Build a user document from viewed/enrolled/completed/favourited courses
    # plus search queries, then compare it with every candidate course.
    course_docs = [build_course_text(course) for course in courses]
    user_terms = []

    for row in profile["activity"]:
        weight = ACTIVITY_WEIGHTS.get(row["activity_type"], 1)
        user_terms.extend([build_course_text(row)] * max(1, min(weight, 6)))

    user_terms.extend(profile["searches"])
    user_doc = " ".join(user_terms)

    vectors = tfidf_vectors(course_docs + [user_doc])
    user_vector = vectors[-1]

    candidates = []
    for course, vector in zip(courses, vectors[:-1]):
        course_id = course["course_id"]
        if course_id in profile["interacted"]:
            continue

        content_score = cosine_similarity(user_vector, vector)
        category_score = profile["category_scores"].get(course["category"], 0)
        normalized_category = min(category_score / 12.0, 1.0)

        # Hybrid score: content similarity is primary, behaviour affinity
        # is a strong secondary signal, while rating breaks close ties.
        hybrid_score = (
            content_score * 0.60 +
            normalized_category * 0.30 +
            (float(course["rating"] or 0) / 5.0) * 0.10
        )

        if hybrid_score <= 0:
            continue

        if content_score >= 0.35:
            reason = "Similar to topics and courses you explored."
        elif category_score > 0:
            reason = f"Matches your interest in {course['category']}."
        else:
            reason = "A highly rated course related to your interests."

        course["recommendation_score"] = round(hybrid_score * 100, 1)
        course["content_similarity"] = round(content_score * 100, 1)
        course["recommendation_reason"] = reason
        candidates.append(course)

    candidates.sort(
        key=lambda c: (c["recommendation_score"], c["rating"] or 0),
        reverse=True
    )

    if len(candidates) < limit:
        shown = {c["course_id"] for c in candidates} | profile["interacted"]
        fallback = get_popular_courses(limit - len(candidates), shown)
        for course in fallback:
            course["recommendation_score"] = 0
            course["content_similarity"] = 0
            course["recommendation_reason"] = "Popular among learners."
        candidates.extend(fallback)

    return candidates[:limit]


def get_related_courses(course_id, limit=6):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,))
    target = cursor.fetchone()
    cursor.execute("SELECT * FROM courses WHERE course_id != ?", (course_id,))
    others = [dict(r) for r in cursor.fetchall()]
    connection.close()

    if not target:
        return []

    documents = [build_course_text(target)] + [build_course_text(c) for c in others]
    vectors = tfidf_vectors(documents)
    target_vector = vectors[0]

    scored = []
    for course, vector in zip(others, vectors[1:]):
        score = cosine_similarity(target_vector, vector)
        if course["category"] == target["category"]:
            score += 0.12
        course["similarity"] = round(score * 100, 1)
        scored.append(course)

    scored.sort(key=lambda c: c["similarity"], reverse=True)
    return scored[:limit]
