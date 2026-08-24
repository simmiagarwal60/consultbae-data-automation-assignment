import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
from src.database import models  # noqa: F401
from src.matching.resolver import (
    create_person,
    resolve_person,
)


@pytest.fixture()
def session():
    test_engine = create_engine(
        "sqlite:///:memory:",
    )

    Base.metadata.create_all(test_engine)

    TestSession = sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )

    with TestSession() as test_session:
        yield test_session


def test_match_by_email(session):
    person = create_person(
        session,
        full_name="Isha Chopra",
        email="isha.chopra@example.com",
        source_name="naukri",
    )

    decision = resolve_person(
        session,
        full_name="ISHA CHOPRA",
        email=" ISHA.CHOPRA@EXAMPLE.COM ",
    )

    assert decision.action == "match"
    assert decision.person_id == person.id
    assert decision.confidence == 0.98


def test_match_by_phone(session):
    person = create_person(
        session,
        full_name="Tanvi Gupta",
        phone="+91-9000000254",
        source_name="naukri",
    )

    decision = resolve_person(
        session,
        full_name="Tanvi Gupta",
        phone="9000000254",
    )

    assert decision.action == "match"
    assert decision.person_id == person.id


def test_email_and_phone_match_same_person(session):
    person = create_person(
        session,
        full_name="Varun Jain",
        email="varun@example.com",
        phone="9000000263",
        source_name="naukri",
    )

    decision = resolve_person(
        session,
        full_name="Varun Jain",
        email="VARUN@EXAMPLE.COM",
        phone="919000000263",
    )

    assert decision.action == "match"
    assert decision.person_id == person.id
    assert decision.confidence == 1.0


def test_conflicting_identifiers_require_review(session):
    email_person = create_person(
        session,
        full_name="Person One",
        email="shared@example.com",
    )

    phone_person = create_person(
        session,
        full_name="Person Two",
        phone="9000000999",
    )

    decision = resolve_person(
        session,
        full_name="Conflicting Person",
        email="shared@example.com",
        phone="9000000999",
    )

    assert decision.action == "review"
    assert set(decision.candidate_person_ids) == {
        email_person.id,
        phone_person.id,
    }


def test_name_only_match_requires_review(session):
    person = create_person(
        session,
        full_name="Arjun Mehta",
        email="first.arjun@example.com",
        city="Noida",
    )

    decision = resolve_person(
        session,
        full_name="ARJUN MEHTA",
        email="different.arjun@example.com",
        city="NOIDA",
    )

    assert decision.action == "review"
    assert decision.candidate_person_ids == [person.id]


def test_new_person_decision(session):
    decision = resolve_person(
        session,
        full_name="Completely New Person",
        email="new.person@example.com",
        phone="9000000888",
        city="Pune",
    )

    assert decision.action == "new"
    assert decision.person_id is None
    assert decision.candidate_person_ids == []