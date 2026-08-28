import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv
from flask import Flask, make_response, redirect, render_template, request, url_for

from translations import DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS

load_dotenv()

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

ADZUNA_COUNTRY = "in"  # India
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
REQUEST_TIMEOUT = 10  # seconds

RESULTS_PER_PAGE = 10
MAX_PAGES = 20  # keep pagination simple and bounded

app = Flask(__name__)


# ----- Interface language (job data from Adzuna is never translated) -----

def get_language():
    """Chosen language: ?lang= wins, then the saved cookie, then the default."""
    lang = request.args.get("lang") or request.cookies.get("lang")
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def translate(key):
    """Look up an interface string for the current language."""
    strings = TRANSLATIONS.get(get_language(), TRANSLATIONS[DEFAULT_LANGUAGE])
    return strings.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)


@app.context_processor
def inject_i18n():
    return {"t": translate, "languages": LANGUAGES, "current_lang": get_language()}


@app.route("/set-language")
def set_language():
    """Remember the chosen language in a cookie and return to the last page."""
    lang = request.args.get("lang", DEFAULT_LANGUAGE)
    next_url = request.args.get("next", "") or url_for("index")
    if not next_url.startswith("/"):  # only allow internal paths
        next_url = url_for("index")

    response = make_response(redirect(next_url))
    if lang in LANGUAGES:
        response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response


class AdzunaError(Exception):
    """Raised when the Adzuna API call cannot be completed successfully."""


def _clean(value):
    """Return a trimmed string, or None if there is nothing meaningful to show."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _prettify(value):
    """Turn Adzuna codes like 'full_time' into 'Full time'."""
    text = _clean(value)
    if not text:
        return None
    return text.replace("_", " ").capitalize()


def _safe_url(raw):
    """Return the job link with any credential-bearing query param removed.

    Adzuna's redirect_url includes the public App ID as `utm_source`, so we
    drop any parameter whose name or value contains one of our credentials.
    """
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
    """Build a readable salary range string, or None if no salary data."""
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
    """Map one raw Adzuna job into a safe, display-ready dict."""
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


def search_adzuna_jobs(profession, location, page=1):
    """Call the Adzuna jobs API and return clean, display-ready results.

    Returns a dict: {"count", "jobs", "page", "total_pages"}.
    Raises AdzunaError with a friendly message on any failure.
    Credentials are read from the environment and never returned to the caller.
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise AdzunaError("Job search is not configured. Please try again later.")

    page = max(1, min(page, MAX_PAGES))
    url = ADZUNA_URL.format(country=ADZUNA_COUNTRY, page=page)
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": profession,
        "where": location,
        "results_per_page": RESULTS_PER_PAGE,
    }

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    profession = (request.args.get("profession") or "").strip()
    location = (request.args.get("location") or "").strip()

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    if not profession:
        return render_template("results.html", error=translate("err_no_profession"),
                               profession=profession, location=location), 400
    if not location:
        return render_template("results.html", error=translate("err_no_location"),
                               profession=profession, location=location), 400

    try:
        result = search_adzuna_jobs(profession, location, page=page)
    except AdzunaError as exc:
        return render_template("results.html", error=str(exc),
                               profession=profession, location=location), 502

    return render_template(
        "results.html",
        jobs=result["jobs"],
        count=result["count"],
        page=result["page"],
        total_pages=result["total_pages"],
        profession=profession,
        location=location,
    )


@app.route("/job/<job_id>")
def job_details(job_id):
    """Show one opportunity.

    Adzuna's free API has no "fetch by id" endpoint, so we re-run the same
    search (carried in the query string) and pick out the matching job.
    No database needed.
    """
    profession = (request.args.get("profession") or "").strip()
    location = (request.args.get("location") or "").strip()

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
        result = search_adzuna_jobs(profession, location, page=page)
    except AdzunaError as exc:
        return render_template("job.html", error=str(exc),
                               profession=profession, location=location, page=page), 502

    job = next((j for j in result["jobs"] if j["id"] and j["id"] == job_id), None)

    if job is None:
        return render_template(
            "job.html",
            error="Sorry, we couldn't find that opportunity. It may have expired.",
            profession=profession, location=location, page=page,
        ), 404

    return render_template("job.html", job=job,
                           profession=profession, location=location, page=page)


if __name__ == "__main__":
    app.run(debug=True)
