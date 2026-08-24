import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.connection import SessionLocal
from src.database.models import (
    MatchReview,
    Person,
    SourceRecord,
)


def format_person(person: Person) -> str:
    emails = [
        person_email.email
        for person_email in person.emails
    ]

    phones = [
        person_phone.phone
        for person_phone in person.phones
    ]

    return (
        f"Person ID: {person.id}\n"
        f"    Name: {person.full_name}\n"
        f"    City: {person.canonical_city}\n"
        f"    Emails: {emails or 'None'}\n"
        f"    Phones: {phones or 'None'}"
    )


def show_pending_reviews() -> None:
    with SessionLocal() as session:
        statement = (
            select(MatchReview)
            .where(MatchReview.status == "pending")
            .order_by(MatchReview.id)
        )

        reviews = list(session.scalars(statement).all())

        if not reviews:
            print("No pending match reviews.")
            return

        print("\nPENDING IDENTITY MATCH REVIEWS")
        print("=" * 70)
        print(f"Total pending reviews: {len(reviews)}")

        for review in reviews:
            source_record = session.get(
                SourceRecord,
                review.source_record_id,
            )

            if source_record is None:
                continue

            raw_data = json.loads(source_record.raw_data)
            candidate_ids = json.loads(
                review.candidate_person_ids or "[]"
            )

            print("\n" + "-" * 70)
            print(f"Review ID: {review.id}")
            print(f"Source: {source_record.source_name}")
            print(
                f"Original CSV row: "
                f"{source_record.source_row_number}"
            )
            print(f"Reason: {review.reason}")
            print("Original record:")
            print(
                json.dumps(
                    raw_data,
                    indent=4,
                    ensure_ascii=False,
                )
            )

            if not candidate_ids:
                print("Candidate people: None")
                continue

            print("Candidate people:")

            candidate_statement = (
                select(Person)
                .where(Person.id.in_(candidate_ids))
                .options(
                    selectinload(Person.emails),
                    selectinload(Person.phones),
                )
            )

            candidates = list(
                session.scalars(candidate_statement).all()
            )

            for candidate in candidates:
                print(format_person(candidate))


if __name__ == "__main__":
    show_pending_reviews()