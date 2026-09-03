import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, make_response, redirect, render_template, request, url_for

from translations import DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS

load_dotenv()

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

ADZUNA_COUNTRY = "in"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
REQUEST_TIMEOUT = 10

RESULTS_PER_PAGE = 10
MAX_PAGES = 20

FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback_data.json")
MAX_FEEDBACK_SHOWN = 6

PROFESSIONS = [
    ("Software / IT", "it-jobs", None),
    ("Engineering", "engineering-jobs", None),
    ("Data Science", "it-jobs", "data scientist"),
    ("Marketing", "pr-advertising-marketing-jobs", None),
    ("Finance", "accounting-finance-jobs", None),
    ("Human Resources", "hr-jobs", None),
    ("Design", "creative-design-jobs", None),
    ("Research", "scientific-qa-jobs", None),
    ("Sales", "sales-jobs", None),
    ("Operations", None, "operations manager"),
    ("Customer Support", "customer-services-jobs", None),
    ("Healthcare", "healthcare-nursing-jobs", None),
    ("Education", "teaching-jobs", None),
    ("Legal", "legal-jobs", None),
    ("Manufacturing", "manufacturing-jobs", None),
    ("Logistics & Supply Chain", "logistics-warehouse-jobs", None),
    ("Hospitality", "hospitality-catering-jobs", None),
    ("Retail", "retail-jobs", None),
    ("Construction", "trade-construction-jobs", None),
    ("Consulting", "consultancy-jobs", None),
    ("Media & Journalism", None, "journalist"),
    ("Government / Public Sector", "admin-jobs", None),
    ("Policy", None, "policy analyst"),
]

PROFESSION_LABELS = [label for label, _category, _what in PROFESSIONS]
PROFESSION_LOOKUP = {label: (category, what) for label, category, what in PROFESSIONS}

JOB_TYPES = ["full_time", "part_time", "internship"]

ASSET_VERSION = "5"

# Initialize Sentry
sentry_sdk.init(
    dsn="https://63d29ce67291fe3cc18796f135d0b8b0@o4512005380636672.ingest.us.sentry.io/4512005387976704",
    send_default_pii=True,
    traces_sample_rate=1.0,
)

app = Flask(__name__)


# ----- Interface language -----

def get_language():
    lang = request.args.get("lang") or request.cookies.get("lang")
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def translate(key):
    strings = TRANSLATIONS.get(get_language(), TRANSLATIONS[DEFAULT_LANGUAGE])
    return strings.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)


@app.context_processor
def inject_i18n():
    return {
        "t": translate,
        "languages": LANGUAGES,
        "current_lang": get_language(),
        "asset_version": ASSET_VERSION,
    }


@app.route("/set-language")
def set_language():
    lang = request.args.get("lang", DEFAULT_LANGUAGE)
    next_url = request.args.get("next", "") or url_for("index")
    if not next_url.startswith("/"):
        next_url = url_for("index")

    response = make_response(redirect(next_url))
    if lang in LANGUAGES:
        response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response


class AdzunaError(Exception):
    pass


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _prettify(value):
    text = _clean(value)
    if not text:
        return None
    return text.replace("_", " ").capitalize()


def _safe_url(raw):
    url = _clean(raw)
    if not url:
        return None
    creds = [c for c in (ADZUNA_APP_ID, ADZUNA_APP_KEY) if c]
    parts = urlsplit(url)
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not any(c in key or c in value for c in creds)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


def _format_salary(job):
    low = job.get("salary_min")
    high = job.get("salary_max")
    if not low and not high:
        return None

    def money(amount):
        return "₹{:,.0f}".format(float(amount))

    if low and high and low != high:
        text = "{} – {} a year".format(money(low), money(high))
    else:
        text = "{} a year".format(money(low or high))

    if job.get("salary_is_predicted") in (1, "1", True):
        text += " (estimated)"
    return text


def _build_job(job):
    return {
        "id": _clean(job.get("id")),
        "title": _clean(job.get("title")) or "Untitled role",
        "company": _clean((job.get("company") or {}).get("display_name")),
        "location": _clean((job.get("location") or {}).get("display_name")),
        "category": _clean((job.get("category") or {}).get("label")),
        "contract_type": _prettify(job.get("contract_type")),
        "contract_time": _prettify(job.get("contract_time")),
        "salary": _format_salary(job),
        "description": _clean(job.get("description")),
        "url": _safe_url(job.get("redirect_url")),
    }


def search_adzuna_jobs(profession, location, page=1, min_salary=None, job_type=None):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise AdzunaError("Job search is not configured. Please try again later.")

    page = max(1, min(page, MAX_PAGES))
    url = ADZUNA_URL.format(country=ADZUNA_COUNTRY, page=page)
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "where": location,
        "results_per_page": RESULTS_PER_PAGE,
    }

    category, what_terms = PROFESSION_LOOKUP.get(profession, (None, None))
    if category:
        params["category"] = category
    if what_terms:
        params["what"] = what_terms
    if min_salary is not None:
        params["salary_min"] = min_salary
    if job_type == "full_time":
        params["full_time"] = 1
    elif job_type == "part_time":
        params["part_time"] = 1
    elif job_type == "internship":
        params["what"] = "internship"

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise AdzunaError("The job search timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise AdzunaError("Could not connect to the job search service.")
    except requests.exceptions.HTTPError:
        raise AdzunaError("The job search service returned an error. Please try again later.")
    except requests.exceptions.RequestException:
        raise AdzunaError("Something went wrong while searching for jobs.")

    try:
        data = response.json()
        raw_jobs = data["results"]
    except (ValueError, KeyError, TypeError):
        raise AdzunaError("Received an unexpected response from the job search service.")

    jobs = [_build_job(job) for job in raw_jobs]

    count = data.get("count", len(jobs)) or 0
    total_pages = min(MAX_PAGES, max(1, -(-count // RESULTS_PER_PAGE))) if count else 1

    return {"count": count, "jobs": jobs, "page": page, "total_pages": total_pages}


def _parse_min_salary(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = int(str(raw).replace(",", "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_job_type(raw):
    value = (raw or "").strip()
    return value if value in JOB_TYPES else None


@app.route("/")
def index():
    with sentry_sdk.start_transaction(op="page_load", name="landing_page"):
        sentry_sdk.set_tag("page", "index")
    return render_template("index.html", professions=PROFESSION_LABELS, job_types=JOB_TYPES)


@app.route("/search")
def search():
    profession = (request.args.get("profession") or "").strip()
    location = (request.args.get("location") or "").strip()
    min_salary = _parse_min_salary(request.args.get("min_salary"))
    job_type = _parse_job_type(request.args.get("job_type"))

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    # Start Sentry transaction for time-to-task
    print(f"🔍 Starting job_search transaction for {profession} in {location}")
    with sentry_sdk.start_transaction(op="http.server", name="job_search") as txn:
        print(f"✅ Transaction started: {txn.name}")
        sentry_sdk.set_tag("profession", profession)
        sentry_sdk.set_tag("location", location)
        sentry_sdk.set_tag("page", page)

        if not profession:
            sentry_sdk.set_tag("error_type", "missing_profession")
            sentry_sdk.set_measurement("search_success", 0, "boolean")
            return render_template("results.html", error=translate("err_no_profession"),
                                   profession=profession, location=location,
                                   min_salary=min_salary, job_type=job_type), 400

        if not location:
            sentry_sdk.set_tag("error_type", "missing_location")
            sentry_sdk.set_measurement("search_success", 0, "boolean")
            return render_template("results.html", error=translate("err_no_location"),
                                   profession=profession, location=location,
                                   min_salary=min_salary, job_type=job_type), 400

        try:
            result = search_adzuna_jobs(profession, location, page=page,
                                        min_salary=min_salary, job_type=job_type)
        except AdzunaError as exc:
            sentry_sdk.set_tag("error_type", "api_error")
            sentry_sdk.set_measurement("search_success", 0, "boolean")
            sentry_sdk.capture_exception(exc)
            return render_template("results.html", error=str(exc),
                                   profession=profession, location=location,
                                   min_salary=min_salary, job_type=job_type), 502

        # SUCCESS - track metrics
        sentry_sdk.set_measurement("search_success", 1, "boolean")
        sentry_sdk.set_measurement("results_count", result["count"], "integer")
        sentry_sdk.set_tag("results_found", "yes" if result["count"] > 0 else "no")

    return render_template(
        "results.html",
        jobs=result["jobs"],
        count=result["count"],
        page=result["page"],
        total_pages=result["total_pages"],
        profession=profession,
        location=location,
        min_salary=min_salary,
        job_type=job_type,
    )


@app.route("/job/<job_id>")
def job_details(job_id):
    sentry_sdk.set_tag("interaction", "job_click")
    sentry_sdk.set_tag("job_id", job_id)

    profession = (request.args.get("profession") or "").strip()
    location = (request.args.get("location") or "").strip()
    min_salary = _parse_min_salary(request.args.get("min_salary"))
    job_type = _parse_job_type(request.args.get("job_type"))

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    if not profession or not location:
        return render_template(
            "job.html",
            error="We couldn't load this opportunity. Please run your search again.",
        ), 400

    try:
        result = search_adzuna_jobs(profession, location, page=page,
                                    min_salary=min_salary, job_type=job_type)
    except AdzunaError as exc:
        sentry_sdk.capture_exception(exc)
        return render_template("job.html", error=str(exc),
                               profession=profession, location=location, page=page,
                               min_salary=min_salary, job_type=job_type), 502

    job = next((j for j in result["jobs"] if j["id"] and j["id"] == job_id), None)

    if job is None:
        sentry_sdk.set_tag("job_not_found", "yes")
        return render_template(
            "job.html",
            error="Sorry, we couldn't find that opportunity. It may have expired.",
            profession=profession, location=location, page=page,
            min_salary=min_salary, job_type=job_type,
        ), 404

    return render_template("job.html", job=job,
                           profession=profession, location=location, page=page,
                           min_salary=min_salary, job_type=job_type)


# ----- Company feedback ----

def _load_feedback():
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_feedback(entries):
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)


def _company_feedback(entries, company):
    key = company.strip().lower()
    return [e for e in entries if (e.get("company") or "").strip().lower() == key]


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    company = (request.args.get("company") or "").strip()
    locked = bool(company)
    submitted = False
    error = None
    posted_rating = 0
    posted_text = ""

    if request.method == "POST":
        company = (request.form.get("company") or "").strip()
        locked = bool((request.args.get("company") or "").strip())
        try:
            posted_rating = int(request.form.get("rating", "0"))
        except ValueError:
            posted_rating = 0
        posted_text = (request.form.get("text") or "").strip()

        if not company:
            error = translate("feedback_err_company")
        elif posted_rating < 1 or posted_rating > 5:
            error = translate("feedback_err_rating")
        else:
            entries = _load_feedback()
            entries.append({
                "company": company,
                "rating": posted_rating,
                "text": posted_text,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            })
            _save_feedback(entries)

            # Track feedback to Sentry
            sentry_sdk.set_tag("interaction", "feedback_submit")
            sentry_sdk.set_tag("company", company)
            sentry_sdk.set_measurement("feedback_rating", posted_rating, "integer")

            submitted = True
            posted_rating = 0
            posted_text = ""

    all_entries = _load_feedback()
    matching = _company_feedback(all_entries, company) if company else []
    average = round(sum(e["rating"] for e in matching) / len(matching), 1) if matching else None
    recent = list(reversed(matching))[:MAX_FEEDBACK_SHOWN]

    return render_template(
        "feedback.html",
        company=company,
        locked=locked,
        submitted=submitted,
        error=error,
        recent=recent,
        review_count=len(matching),
        average=average,
        posted_rating=posted_rating,
        posted_text=posted_text,
    )


if __name__ == "__main__":
    app.run(debug=True)
