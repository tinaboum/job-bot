import requests
import json
import os
from datetime import datetime

# =====================
# CONFIG
# =====================

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SERPAPI_KEY = os.environ["SERPAPI_KEY"]

SEEN_FILE = "seen_jobs.json"

# =====================
# QUERIES BY CATEGORY
# =====================

TECH_QUERIES = [
    "embedded engineer UAE",
    "firmware engineer UAE",
    "robotics engineer UAE",
    "automation engineer UAE",
    "electronics engineer UAE",
    "electrical engineer UAE",
    "control engineer UAE",
    "iot engineer UAE",
    "application engineer UAE",
    "technical support engineer UAE",
    "junior engineer UAE"
]

SALES_QUERIES = [
    "sales engineer UAE",
    "technical sales engineer UAE",
    "pre sales engineer UAE",
    "solutions engineer UAE",
    "solutions consultant UAE",
    "business development engineer UAE",
    "inside sales engineer UAE",
    "account executive UAE",
    "sales coordinator UAE"
]

BUSINESS_QUERIES = [
    "business development executive UAE",
    "business development associate UAE",
    "B2B sales executive UAE",
    "customer success executive UAE",
    "operations coordinator UAE",
    "project coordinator UAE",
    "technical coordinator UAE"
]

# =====================
# LOAD / SAVE SEEN
# =====================

def load_seen():
    if os.path.exists(SEEN_FILE):
        return set(json.load(open(SEEN_FILE)))
    return set()

def save_seen(seen):
    json.dump(list(seen), open(SEEN_FILE, "w"))

# =====================
# FETCH JOBS
# =====================

def fetch_jobs(query):
    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": SERPAPI_KEY,
        "hl": "en"
    }

    r = requests.get(url, params=params)

    if r.status_code != 200:
        print("API ERROR:", r.text)
        return []

    return r.json().get("jobs_results", [])

# =====================
# LINK EXTRACTION
# =====================

def extract_link(job):
    return (
        job.get("job_apply_link")
        or job.get("link")
        or (job.get("apply_options")[0].get("link") if job.get("apply_options") else None)
        or "No link available"
    )

# =====================
# HARD REJECT (ONLY REAL UNWANTED JOBS)
# =====================

REJECT_WORDS = [
    "cashier", "retail", "sales associate", "store manager",
    "beauty advisor", "promoter", "merchandiser",
    "waiter", "barista", "cleaner", "security", "driver",
    "housekeeping", "restaurant", "hotel"
]

def is_rejected(text):
    text = text.lower()
    return any(w in text for w in REJECT_WORDS)

# =====================
# CATEGORY CLASSIFICATION
# =====================

def classify(title, desc):

    text = (title + " " + desc).lower()

    if any(x in text for x in [
        "embedded", "firmware", "robot", "automation",
        "electronics", "electrical", "iot", "control"
    ]):
        return "TECH"

    if any(x in text for x in [
        "sales engineer", "pre sales", "solutions engineer",
        "technical sales", "account executive"
    ]):
        return "SALES"

    return "BUSINESS"

# =====================
# SCORING SYSTEM
# =====================

def score_job(job):

    title = job.get("title", "")
    company = job.get("company_name", "")
    desc = job.get("description", "")

    text = (title + " " + company + " " + desc).lower()

    score = 0

    # -------- TECH BOOST --------
    tech_keywords = {
        "embedded": 25,
        "firmware": 25,
        "robot": 20,
        "automation": 15,
        "electronics": 15,
        "electrical": 10,
        "iot": 15,
        "ros": 25,
        "lidar": 25,
        "stm32": 25,
        "control": 15
    }

    # -------- SALES BOOST --------
    sales_keywords = {
        "sales engineer": 25,
        "technical sales": 25,
        "pre sales": 25,
        "solutions engineer": 25,
        "business development": 15,
        "account executive": 15,
        "b2b": 15
    }

    # -------- BUSINESS BOOST --------
    business_keywords = {
        "coordinator": 10,
        "operations": 10,
        "customer success": 10,
        "project": 10
    }

    for k, v in {**tech_keywords, **sales_keywords, **business_keywords}.items():
        if k in text:
            score += v

    # -------- JUNIOR BOOST --------
    if any(x in text for x in ["junior", "entry", "graduate", "associate"]):
        score += 20

    # -------- SENIOR PENALTY --------
    if any(x in text for x in ["senior", "lead", "manager", "director"]):
        score -= 20

    # -------- UAE BOOST --------
    if any(x in text for x in ["uae", "dubai", "abu dhabi", "emirates"]):
        score += 10

    # -------- SALARY BOOST --------
    full_text = str(job).lower()

    if "5000" in full_text:
        score += 10
    if "7000" in full_text:
        score += 20
    if "10000" in full_text:
        score += 30

    return score

# =====================
# SOFT FRESHNESS (IMPORTANT)
# =====================

def freshness_score(job):

    ext = job.get("detected_extensions", {})
    posted = str(ext.get("posted_at", "")).lower()

    if not posted:
        return 5  # KEEP UNKNOWN JOBS

    if "hour" in posted:
        return 30
    if "1 day" in posted:
        return 25
    if "2 day" in posted:
        return 22
    if "3 day" in posted:
        return 20

    if "week" in posted:
        try:
            w = int(posted.split()[0])
            if w <= 2:
                return 10
            return -5
        except:
            return 5

    return 5

# =====================
# PROCESS JOBS
# =====================

def process_jobs(jobs, seen):

    results = []

    for job in jobs:

        title = job.get("title", "")
        company = job.get("company_name", "")
        location = job.get("location", "")
        desc = job.get("description", "")

        key = f"{title}|{company}|{location}"

        if key in seen:
            continue

        text = (title + " " + company + " " + desc).lower()

        if is_rejected(text):
            continue

        seen.add(key)

        category = classify(title, desc)

        score = score_job(job)
        score += freshness_score(job)

        results.append({
            "title": title,
            "company": company,
            "location": location,
            "link": extract_link(job),
            "score": score,
            "category": category
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return results

# =====================
# TELEGRAM SENDER
# =====================

def send_to_telegram(title, jobs):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    if not jobs:
        message = f"{title}\n\n⚠️ No jobs found today."
    else:
        message = f"{title}\n\n"

        for job in jobs[:10]:
            message += (
                f"📌 {job['title']}\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"⭐ Score: {job['score']}\n"
                f"🔗 {job['link']}\n\n"
            )

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })

# =====================
# MAIN
# =====================

def main():

    seen = load_seen()

    all_jobs = []

    for q in TECH_QUERIES + SALES_QUERIES + BUSINESS_QUERIES:
        print("Searching:", q)
        jobs = fetch_jobs(q)
        all_jobs.extend(jobs)

    processed = process_jobs(all_jobs, seen)

    save_seen(seen)

    tech = [j for j in processed if j["category"] == "TECH"]
    sales = [j for j in processed if j["category"] == "SALES"]
    business = [j for j in processed if j["category"] == "BUSINESS"]

    send_to_telegram("🤖 TECH JOBS UAE", tech)
    send_to_telegram("💼 TECH SALES JOBS UAE", sales)
    send_to_telegram("📈 BUSINESS JOBS UAE", business)


if __name__ == "__main__":
    main()
