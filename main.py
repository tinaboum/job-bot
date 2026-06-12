import requests
import json
import os

# =====================
# CONFIG
# =====================

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SERPAPI_KEY = os.environ["SERPAPI_KEY"]


SEEN_FILE = "seen_jobs.json"

# =====================
# SEARCH QUERIES
# =====================
QUERIES = [
    "engineer UAE",
    "embedded engineer Dubai",
    "robotics engineer UAE",
    "automation engineer UAE",
    "electrical engineer UAE",
    "software engineer UAE"
]

# =====================
# LOAD / SAVE SEEN JOBS
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
# SAFE LINK EXTRACTION
# =====================
def extract_link(job):
    return (
        job.get("job_apply_link")
        or job.get("link")
        or (job.get("apply_options")[0].get("link") if job.get("apply_options") else None)
        or "No link available"
    )

# =====================
# SAFE SCORING (NO ZERO BUG)
# =====================
def score_job(job):

    text = " ".join([
        job.get("title") or "",
        job.get("company_name") or "",
        job.get("description") or ""
    ]).lower()

    score = 0

    # ENGINEERING CORE
    if "engineer" in text: score += 2
    if "electrical" in text: score += 4
    if "electronics" in text: score += 4
    if "software" in text: score += 3

    # EMBEDDED / ROBOTICS
    if "embedded" in text: score += 10
    if "robot" in text: score += 9
    if "automation" in text: score += 8
    if "firmware" in text: score += 9
    if "mechatronics" in text: score += 8
    if "control" in text: score += 7
    if "iot" in text: score += 6

    # UAE BOOST
    if any(x in text for x in ["uae", "dubai", "abu dhabi", "emirates"]):
        score += 5

    # NEGATIVE FILTERS
    if any(x in text for x in ["cashier", "waiter", "retail", "cleaner"]):
        score -= 10

    return score

# =====================
# PROCESS JOBS
# =====================
def process_jobs(jobs, seen):

    results = []

    for job in jobs:

        title = job.get("title", "")
        company = job.get("company_name", "")

        key = title + company

        if key in seen:
            continue

        seen.add(key)

        score = score_job(job)

        # IMPORTANT: LOWER THRESHOLD (FIX EMPTY RESULTS)
        if score < 2:
            continue

        results.append({
            "title": title,
            "company": company,
            "location": job.get("location", ""),
            "score": score,
            "link": extract_link(job)
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return results

# =====================
# TELEGRAM SEND
# =====================
def send_to_telegram(jobs):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    if not jobs:
        message = "⚠️ No jobs found today (filters too strict or API issue)."
    else:
        message = "🔥 UAE JOB RADAR\n\n"

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

    for q in QUERIES:
        print("Searching:", q)
        jobs = fetch_jobs(q)
        print("Found:", len(jobs))
        all_jobs.extend(jobs)

    print("TOTAL RAW JOBS:", len(all_jobs))

    processed = process_jobs(all_jobs, seen)

    save_seen(seen)

    print("PROCESSED JOBS:", len(processed))

    send_to_telegram(processed)


if __name__ == "__main__":
    main()
