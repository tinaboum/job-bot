import requests
import json
import os
import re


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

TECH_QUERIES = [
    "embedded engineer UAE",
    "automation engineer UAE"
]

SALES_QUERIES = [
    "sales engineer UAE",
    "solutions engineer UAE"
]

BUSINESS_QUERIES = [
    "business development UAE",
    "operations coordinator UAE"
]


# =====================
# LOAD / SAVE SEEN
# =====================

def load_seen():

    if os.path.exists(SEEN_FILE):

        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))

    return set()



def save_seen(seen):

    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)



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


    response = requests.get(url, params=params)


    if response.status_code != 200:

        print(response.text)
        return []


    return response.json().get(
        "jobs_results",
        []
    )



# =====================
# NORMALIZATION
# =====================

def normalize(text):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9 ]",
        "",
        text
    )

    return " ".join(text.split())



def job_key(job):

    return (

        normalize(job.get("title",""))
        +
        "|"
        +
        normalize(job.get("company_name",""))
        +
        "|"
        +
        normalize(job.get("location",""))

    )



# =====================
# LINK EXTRACTION
# =====================

def extract_link(job):

    return (

        job.get("job_apply_link")
        or job.get("link")
        or "No link available"

    )



# =====================
# FILTERING
# =====================

REJECT_WORDS = [

    # senior
    "senior",
    "lead",
    "principal",
    "manager",
    "director",
    "head",

    # retail
    "cashier",
    "retail",
    "store",
    "promoter",
    "merchandiser",

    # hospitality
    "waiter",
    "barista",
    "cleaner",
    "driver",
    "security",
    "housekeeping",

    # unrelated
    "nurse",
    "doctor",
    "teacher"

]



def is_rejected(text):

    text = text.lower()

    return any(
        word in text
        for word in REJECT_WORDS
    )



# =====================
# CATEGORY
# =====================

def classify(title, desc):

    text = (
        title
        +
        " "
        +
        desc
    ).lower()



    if any(word in text for word in [

        "embedded",
        "firmware",
        "robotics",
        "automation",
        "electronics",
        "iot",
        "control"

    ]):

        return "TECH"



    if any(word in text for word in [

        "sales engineer",
        "technical sales",
        "solutions engineer",
        "presales"

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

    text = (
        title
        + " "
        + company
        + " "
        + desc
    ).lower()


    score = 0


    keywords = {

        # TECH
        "embedded": 30,
        "firmware": 30,
        "robotics": 25,
        "automation": 25,
        "electronics": 20,
        "electrical": 15,
        "iot": 20,
        "control": 20,
        "ros": 25,
        "stm32": 25,
        "lidar": 25,


        # SALES ENGINEERING
        "sales engineer": 30,
        "technical sales": 25,
        "solutions engineer": 30,
        "presales": 25,


        # BUSINESS
        "business development": 20,
        "customer success": 15,
        "operations coordinator": 20,
        "project coordinator": 15,


        # JUNIOR
        "junior": 20,
        "graduate": 20,
        "entry": 20

    }


    for word, points in keywords.items():

        if word in text:
            score += points



    # UAE boost

    if any(x in text for x in [

        "uae",
        "dubai",
        "abu dhabi",
        "emirates"

    ]):

        score += 10



    # Penalty for unwanted seniority

    if any(x in text for x in [

        "manager",
        "lead",
        "senior"

    ]):

        score -= 30



    return score




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


        text = (
            title
            + " "
            + company
            + " "
            + desc
        )


        key = job_key(job)



        # duplicate

        if key in seen:
            continue



        # reject unwanted jobs

        if is_rejected(text):
            continue



        seen.add(key)



        score = score_job(job)



        # keep only useful jobs

        if score < 30:
            continue



        results.append({

            "title": title,
            "company": company,
            "location": location,
            "link": extract_link(job),
            "score": score,
            "category": classify(title, desc)

        })



    # highest score first

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    return results




# =====================
# TELEGRAM REPORT
# =====================

def send_daily_report(tech, sales, business):


    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )


    message = (
        "🚀 UAE DAILY JOB REPORT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )



    sections = [

        ("🤖 TECH JOBS UAE", tech),

        ("💼 TECH SALES JOBS UAE", sales),

        ("📈 BUSINESS JOBS UAE", business)

    ]



    for title, jobs in sections:


        message += title + "\n\n"



        if not jobs:

            message += "⚠️ No jobs found\n\n"


        else:


            for job in jobs[:5]:

                message += (

                    f"📌 {job['title']}\n"
                    f"🏢 {job['company']}\n"
                    f"📍 {job['location']}\n"
                    f"⭐ Score: {job['score']}\n"
                    f"🔗 {job['link']}\n\n"

                )


        message += (
            "━━━━━━━━━━━━━━━━━━\n\n"
        )



    requests.post(

        url,

        json={

            "chat_id": CHAT_ID,
            "text": message

        }

    )





# =====================
# MAIN
# =====================

def main():


    seen = load_seen()


    all_jobs = []



    queries = (

        TECH_QUERIES
        +
        SALES_QUERIES
        +
        BUSINESS_QUERIES

    )



    for query in queries:

        print(
            "Searching:",
            query
        )


        jobs = fetch_jobs(query)


        all_jobs.extend(jobs)



    processed = process_jobs(

        all_jobs,
        seen

    )



    save_seen(seen)



    tech = [

        j for j in processed
        if j["category"] == "TECH"

    ]


    sales = [

        j for j in processed
        if j["category"] == "SALES"

    ]


    business = [

        j for j in processed
        if j["category"] == "BUSINESS"

    ]

    send_daily_report(

        tech,
        sales,
        business

    )

    print("Done!")

if __name__ == "__main__":

    main()
