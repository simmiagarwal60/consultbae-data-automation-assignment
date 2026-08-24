from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.connection import SessionLocal
from src.database.models import Person
from src.ingestion.normalizers import (
    create_name_key,
    normalize_email,
    normalize_phone,
)
from src.matching.resolver import (
    find_people_by_name,
    find_person_by_email,
    find_person_by_phone,
)


app = FastAPI(
    title="ConsultBae Duplicate Check API",
    version="1.0.0",
)


class DuplicateCheckRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    @model_validator(mode="after")
    def require_identifier(self):
        if not any([self.name, self.email, self.phone]):
            raise ValueError(
                "At least one of name, email or phone is required"
            )

        return self


def person_data(person: Person) -> dict:
    return {
        "person_id": person.id,
        "full_name": person.full_name,
        "city": person.canonical_city,
        "emails": [
            item.email for item in person.emails
        ],
        "phones": [
            item.phone for item in person.phones
        ],
    }


def load_person(session, person_id: int) -> Person:
    statement = (
        select(Person)
        .where(Person.id == person_id)
        .options(
            selectinload(Person.emails),
            selectinload(Person.phones),
        )
    )

    return session.scalar(statement)


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "duplicate-check-api",
    }


@app.post("/api/duplicates/check")
def check_duplicate(
    request: DuplicateCheckRequest,
) -> dict:
    normalized_email = normalize_email(request.email)
    normalized_phone = normalize_phone(request.phone)
    name_key = create_name_key(request.name)

    with SessionLocal() as session:
        email_person = find_person_by_email(
            session,
            normalized_email,
        )

        phone_person = find_person_by_phone(
            session,
            normalized_phone,
        )

        if (
            email_person is not None
            and phone_person is not None
            and email_person.id != phone_person.id
        ):
            matches = []

            for person_id in {
                email_person.id,
                phone_person.id,
            }:
                person = load_person(session, person_id)
                matches.append(person_data(person))

            return {
                "duplicate": True,
                "requires_review": True,
                "match_type": "identifier_conflict",
                "confidence": 0.0,
                "message": (
                    "Email and phone belong to different people"
                ),
                "matches": matches,
            }

        matched_person = email_person or phone_person

        if matched_person is not None:
            person = load_person(
                session,
                matched_person.id,
            )

            if (
                email_person is not None
                and phone_person is not None
            ):
                match_type = "email_and_phone"
                confidence = 1.0
            elif email_person is not None:
                match_type = "email"
                confidence = 0.98
            else:
                match_type = "phone"
                confidence = 0.98

            return {
                "duplicate": True,
                "requires_review": False,
                "match_type": match_type,
                "confidence": confidence,
                "message": (
                    f"Duplicate found through {match_type}"
                ),
                "matches": [person_data(person)],
            }

        name_candidates = find_people_by_name(
            session,
            name_key,
        )

        if name_candidates:
            matches = [
                person_data(
                    load_person(session, candidate.id)
                )
                for candidate in name_candidates
            ]

            return {
                "duplicate": True,
                "requires_review": True,
                "match_type": "name_candidate",
                "confidence": 0.5,
                "message": (
                    "Matching name found, but no shared "
                    "email or phone"
                ),
                "matches": matches,
            }

        return {
            "duplicate": False,
            "requires_review": False,
            "match_type": "none",
            "confidence": 1.0,
            "message": "No duplicate found",
            "matches": [],
        }