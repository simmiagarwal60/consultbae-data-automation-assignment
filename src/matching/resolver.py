from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    Person,
    PersonEmail,
    PersonPhone,
)
from src.ingestion.normalizers import (
    create_name_key,
    normalize_city,
    normalize_email,
    normalize_name,
    normalize_phone,
)


@dataclass
class MatchDecision:
    """
    Result returned by the identity-resolution engine.

    action:
    - match: safely matched an existing person
    - new: no existing candidate was found
    - review: an ambiguous or conflicting match requires review
    """

    action: str
    person_id: Optional[int] = None
    candidate_person_ids: list[int] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0


def find_person_by_email(
    session: Session,
    email: Optional[str],
) -> Optional[Person]:
    if email is None:
        return None

    statement = (
        select(Person)
        .join(PersonEmail)
        .where(PersonEmail.email == email)
    )

    return session.scalar(statement)


def find_person_by_phone(
    session: Session,
    phone: Optional[str],
) -> Optional[Person]:
    if phone is None:
        return None

    statement = (
        select(Person)
        .join(PersonPhone)
        .where(PersonPhone.phone == phone)
    )

    return session.scalar(statement)


def find_people_by_name(
    session: Session,
    name_key: Optional[str],
) -> list[Person]:
    if name_key is None:
        return []

    statement = select(Person).where(
        Person.name_key == name_key
    )

    return list(session.scalars(statement).all())


def resolve_person(
    session: Session,
    *,
    full_name: object,
    email: object = None,
    phone: object = None,
    city: object = None,
) -> MatchDecision:
    """
    Resolve an incoming source record to a canonical person.

    Name-only candidates are never automatically merged because
    multiple people may share the same name and city.
    """
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    normalized_name_key = create_name_key(full_name)
    normalized_city = normalize_city(city)

    email_person = find_person_by_email(
        session,
        normalized_email,
    )

    phone_person = find_person_by_phone(
        session,
        normalized_phone,
    )

    # Both identifiers match the same person.
    if (
        email_person is not None
        and phone_person is not None
        and email_person.id == phone_person.id
    ):
        return MatchDecision(
            action="match",
            person_id=email_person.id,
            reason="Exact normalized email and phone match",
            confidence=1.0,
        )

    # Email and phone point to different people.
    if (
        email_person is not None
        and phone_person is not None
        and email_person.id != phone_person.id
    ):
        return MatchDecision(
            action="review",
            candidate_person_ids=[
                email_person.id,
                phone_person.id,
            ],
            reason=(
                "Email and phone match different existing people"
            ),
            confidence=0.0,
        )

    # Email is considered a strong unique identifier.
    if email_person is not None:
        return MatchDecision(
            action="match",
            person_id=email_person.id,
            reason="Exact normalized email match",
            confidence=0.98,
        )

    # Phone is also considered a strong unique identifier.
    if phone_person is not None:
        return MatchDecision(
            action="match",
            person_id=phone_person.id,
            reason="Exact normalized phone match",
            confidence=0.98,
        )

    name_candidates = find_people_by_name(
        session,
        normalized_name_key,
    )

    if name_candidates:
        same_city_candidates = [
            person
            for person in name_candidates
            if (
                normalized_city is not None
                and person.canonical_city == normalized_city
            )
        ]

        candidates = same_city_candidates or name_candidates

        return MatchDecision(
            action="review",
            candidate_person_ids=[
                person.id for person in candidates
            ],
            reason=(
                "Name-based candidate found without a shared "
                "email or phone; automatic merge rejected"
            ),
            confidence=0.5,
        )

    return MatchDecision(
        action="new",
        reason="No existing identifier or name candidate found",
        confidence=1.0,
    )


def create_person(
    session: Session,
    *,
    full_name: object,
    email: object = None,
    phone: object = None,
    city: object = None,
    source_name: Optional[str] = None,
) -> Person:
    """Create one canonical person with normalized identifiers."""
    canonical_name = normalize_name(full_name)
    name_key = create_name_key(full_name)

    if canonical_name is None or name_key is None:
        raise ValueError("A valid full name is required")

    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    person = Person(
        full_name=canonical_name,
        name_key=name_key,
        canonical_city=normalize_city(city),
    )

    session.add(person)
    session.flush()

    if normalized_email is not None:
        session.add(
            PersonEmail(
                person_id=person.id,
                email=normalized_email,
                is_primary=True,
                source_name=source_name,
            )
        )

    if normalized_phone is not None:
        session.add(
            PersonPhone(
                person_id=person.id,
                phone=normalized_phone,
                is_primary=True,
                source_name=source_name,
            )
        )

    session.flush()
    return person


def attach_missing_identifiers(
    session: Session,
    *,
    person: Person,
    email: object = None,
    phone: object = None,
    source_name: Optional[str] = None,
) -> None:
    """
    Attach a newly discovered email or phone to an existing person.

    This is only called after a strong match has already been made.
    """
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    if normalized_email is not None:
        existing_email = session.scalar(
            select(PersonEmail).where(
                PersonEmail.email == normalized_email
            )
        )

        if existing_email is None:
            session.add(
                PersonEmail(
                    person_id=person.id,
                    email=normalized_email,
                    is_primary=False,
                    source_name=source_name,
                )
            )

    if normalized_phone is not None:
        existing_phone = session.scalar(
            select(PersonPhone).where(
                PersonPhone.phone == normalized_phone
            )
        )

        if existing_phone is None:
            session.add(
                PersonPhone(
                    person_id=person.id,
                    phone=normalized_phone,
                    is_primary=False,
                    source_name=source_name,
                )
            )

    session.flush()