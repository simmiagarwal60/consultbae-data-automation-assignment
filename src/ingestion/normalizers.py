import re
from datetime import date
from typing import Optional

from dateutil import parser as date_parser


CITY_MAPPING = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "noida": "Noida",
    "pune": "Pune",
    "delhi": "Delhi",
    "new delhi": "New Delhi",
    "delhi ncr": "Delhi NCR",
}

SKILL_MAPPING = {
    "fastapi": "FastAPI",
    "javascript": "JavaScript",
    "langchain": "LangChain",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "n8n": "n8n",
    "pandas": "Pandas",
    "python": "Python",
    "react": "React",
    "rest apis": "REST APIs",
    "selenium": "Selenium",
    "sql": "SQL",
    "web scraping": "Web Scraping",
    "zapier": "Zapier",
    "docker": "Docker",
}


def clean_text(value: object) -> Optional[str]:
    """Trim whitespace and convert empty values to None."""
    if value is None:
        return None

    cleaned = re.sub(r"\s+", " ", str(value)).strip()

    if not cleaned:
        return None

    return cleaned


def normalize_email(value: object) -> Optional[str]:
    """Normalize email casing and surrounding whitespace."""
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    normalized = cleaned.lower()

    email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    if not re.match(email_pattern, normalized):
        return None

    return normalized


def normalize_phone(value: object) -> Optional[str]:
    """
    Normalize Indian phone numbers to E.164 format.

    Examples:
    9000000131      -> +919000000131
    09000000131     -> +919000000131
    919000000131    -> +919000000131
    +91-9000000131  -> +919000000131
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    digits = re.sub(r"\D", "", cleaned)

    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    if len(digits) != 10:
        return None

    return f"+91{digits}"


def normalize_name(value: object) -> Optional[str]:
    """Create a readable canonical name."""
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    return cleaned.title()


def create_name_key(value: object) -> Optional[str]:
    """
    Create a comparison key for matching names.

    'Rohit Verma' -> 'rohitverma'
    'ROHIT VERMA' -> 'rohitverma'
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    key = re.sub(r"[^a-z0-9]", "", cleaned.lower())
    return key or None


def normalize_city(value: object) -> Optional[str]:
    """Normalize city casing, spaces and known aliases."""
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    city_key = cleaned.lower()
    return CITY_MAPPING.get(city_key, cleaned.title())


def normalize_status(value: object) -> Optional[str]:
    """Normalize gig-worker status."""
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    status = cleaned.lower()

    allowed_statuses = {
        "active": "active",
        "inactive": "inactive",
        "paused": "paused",
    }

    return allowed_statuses.get(status)


def normalize_boolean(value: object) -> Optional[bool]:
    """Normalize values such as Y, yes, N and No."""
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    normalized = cleaned.lower()

    if normalized in {"y", "yes", "true", "1"}:
        return True

    if normalized in {"n", "no", "false", "0"}:
        return False

    return None


def normalize_skills(value: object) -> list[str]:
    """Split, standardize and deduplicate comma-separated skills."""
    cleaned = clean_text(value)

    if cleaned is None:
        return []

    normalized_skills = []
    seen = set()

    for skill in cleaned.split(","):
        skill_key = clean_text(skill)

        if skill_key is None:
            continue

        skill_key = skill_key.lower()
        canonical_skill = SKILL_MAPPING.get(
            skill_key,
            skill_key.title(),
        )

        if canonical_skill.lower() not in seen:
            normalized_skills.append(canonical_skill)
            seen.add(canonical_skill.lower())

    return normalized_skills


def normalize_date(value: object) -> Optional[date]:
    """
    Convert mixed date formats into a Python date.

    ISO dates are parsed separately because dayfirst=True can
    incorrectly interpret 2026-08-02 as 8 February 2026.
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    try:
        # Handle ISO format explicitly: YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
            return date.fromisoformat(cleaned)

        # Handle formats such as 24-07-2026 and 7 Jul 2026
        return date_parser.parse(
            cleaned,
            dayfirst=True,
        ).date()

    except (ValueError, TypeError, OverflowError):
        return None


def normalize_ctc(value: object) -> Optional[int]:
    """
    Convert annual CTC to INR.

    Values under 100 are treated as lakhs:
    4.2    -> 420000
    10.0   -> 1000000
    417964 -> 417964
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    cleaned = cleaned.replace(",", "").replace("₹", "")

    try:
        numeric_value = float(cleaned)
    except ValueError:
        return None

    if numeric_value < 0:
        return None

    if numeric_value <= 100:
        numeric_value *= 100_000

    return round(numeric_value)


def normalize_gig_rate(
    value: object,
) -> tuple[Optional[int], Optional[str]]:
    """
    Separate rate amount and unit.

    1415/hr    -> (1415, 'hour')
    15k/month  -> (15000, 'month')
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None, None

    normalized = cleaned.lower().replace(" ", "")

    hourly_match = re.fullmatch(r"(\d+(?:\.\d+)?)/hr", normalized)

    if hourly_match:
        return round(float(hourly_match.group(1))), "hour"

    monthly_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)k/month",
        normalized,
    )

    if monthly_match:
        amount = float(monthly_match.group(1)) * 1_000
        return round(amount), "month"

    return None, None