from datetime import date

from src.ingestion.normalizers import (
    create_name_key,
    normalize_boolean,
    normalize_city,
    normalize_ctc,
    normalize_date,
    normalize_email,
    normalize_gig_rate,
    normalize_name,
    normalize_phone,
    normalize_skills,
    normalize_status,
)


def test_normalize_email():
    assert (
        normalize_email(" ISHA.CHOPRA95@EXAMPLE.COM ")
        == "isha.chopra95@example.com"
    )
    assert normalize_email("not-an-email") is None
    assert normalize_email("") is None


def test_normalize_phone():
    expected = "+919000000131"

    assert normalize_phone("9000000131") == expected
    assert normalize_phone("09000000131") == expected
    assert normalize_phone("919000000131") == expected
    assert normalize_phone("+91-9000000131") == expected
    assert normalize_phone("12345") is None


def test_normalize_name():
    assert normalize_name(" RAHUL   MALHOTRA ") == "Rahul Malhotra"
    assert create_name_key("Rohit Verma") == "rohitverma"
    assert create_name_key("R. Verma") == "rverma"


def test_normalize_city():
    assert normalize_city("GURGAON") == "Gurugram"
    assert normalize_city("gurugram ") == "Gurugram"
    assert normalize_city("bangalore") == "Bengaluru"
    assert normalize_city("PUNE") == "Pune"
    assert normalize_city("Delhi NCR") == "Delhi NCR"


def test_normalize_status():
    assert normalize_status("ACTIVE") == "active"
    assert normalize_status("Inactive") == "inactive"
    assert normalize_status("paused") == "paused"
    assert normalize_status("unknown") is None


def test_normalize_boolean():
    assert normalize_boolean("Y") is True
    assert normalize_boolean("yes") is True
    assert normalize_boolean("N") is False
    assert normalize_boolean("No") is False
    assert normalize_boolean("unknown") is None


def test_normalize_skills():
    result = normalize_skills(
        "python, SQL, fastapi, Python, rest apis"
    )

    assert result == [
        "Python",
        "SQL",
        "FastAPI",
        "REST APIs",
    ]


def test_normalize_date():
    assert normalize_date("24-07-2026") == date(2026, 7, 24)
    assert normalize_date("7 Jul 2026") == date(2026, 7, 7)
    assert normalize_date("2026-08-02") == date(2026, 8, 2)
    assert normalize_date("invalid") is None


def test_normalize_ctc():
    assert normalize_ctc("4.2") == 420_000
    assert normalize_ctc("10.0") == 1_000_000
    assert normalize_ctc("417964") == 417_964
    assert normalize_ctc("invalid") is None


def test_normalize_gig_rate():
    assert normalize_gig_rate("1415/hr") == (1415, "hour")
    assert normalize_gig_rate("15k/month") == (15000, "month")
    assert normalize_gig_rate("invalid") == (None, None)