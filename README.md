# AI-Powered Personalized Learning Recommendation System — V2

A semester-level Flask micro-project that learns from user behaviour and generates personalized course recommendations.

## What makes V2 stronger?

The recommendation system combines:

1. **Content-based similarity** using TF-IDF + cosine similarity.
2. **Behaviour signals** from views, searches, repeated activity, favourites, enrollments, ratings and completions.
3. **Time spent** on a course page.
4. **Course rating** as a small quality/tie-break signal.
5. **Popular-course fallback** for new users (cold start).
6. **Related-course similarity** on every course page.
7. **Explainable recommendations** showing why a course was suggested.

## Behaviour weights

- View = 1
- Favourite = 3
- Enroll = 4
- Rate = 2
- Complete = 6
- Time spent = a small capped bonus

The final recommendation score combines:

- 60% content similarity
- 30% user/category behaviour affinity
- 10% course rating

This is a transparent hybrid model suitable for a micro-project demonstration.

## Installation

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

Linux/macOS:
```bash
source venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
python seed_data.py
python app.py
```

Open:

`http://127.0.0.1:5000/`

## Demo admin

Email: `admin@learnhub.com`

Password: `admin123`

Change the demo password before real deployment.

## Suggested demonstration

1. Create a normal student account.
2. Search for **Python**.
3. Open **Python for Beginners**.
4. Open **Advanced Python**.
5. Save/favourite a Python course.
6. Enroll in a Python-related course.
7. Give it a 5-star rating.
8. Spend a little time on the course page.
9. Open **For You**.
10. Show the recommendation score and "Why recommended?" explanation.
11. Repeat with an AI & ML course and show how the user's interest profile changes.

## Project structure

- `app.py` — Flask routes, authentication, activity tracking and APIs
- `database.py` — SQLite schema and safe database upgrades
- `recommendation.py` — TF-IDF, cosine similarity, behaviour scoring and hybrid recommendations
- `seed_data.py` — sample courses and demo admin
- `make_admin.py` — enables admin access for the demo admin
- `templates/` — Jinja UI pages
- `static/style.css` — responsive UI styling

## Note

The recommendation model is intentionally lightweight and explainable so it can run locally without external ML services. It is an ML-style content recommendation component combined with explicit behavioural scoring, not a large neural-network recommender.
