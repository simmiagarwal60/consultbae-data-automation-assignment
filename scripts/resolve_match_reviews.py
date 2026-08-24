import csv
import json
from pathlib import Path

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    CBNexusProfile,
    GigWorkerProfile,
    IngestionRun,
    MatchReview,
    Person,
    SourceRecord,
)
from src.ingestion.normalizers import (
    normalize_boolean,
    normalize_gig_rate,
    normalize_status,
)
from src.ingestion.services import (
    attach_skills,
    parse_optional_int,
)
from src.matching.resolver import (
    attach_missing_identifiers,
    create_person,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DECISIONS_PATH = (
    PROJECT_ROOT
    / "data"
    / "review_decisions.csv"
)


def get_source_record(
    session,
    source_name: str,
    row_number: int,
) -> SourceRecord:
    statement = select(SourceRecord).where(
        SourceRecord.source_name == source_name,
        SourceRecord.source_row_number == row_number,
    )

    records = list(session.scalars(statement).all())

    if not records:
        raise ValueError(
            f"Source record not found: "
            f"{source_name} row {row_number}"
        )

    # Select the latest record if the pipeline was run more than once.
    return records[-1]


def get_review(
    session,
    source_record: SourceRecord,
) -> MatchReview:
    review = session.scalar(
        select(MatchReview).where(
            MatchReview.source_record_id == source_record.id
        )
    )

    if review is None:
        raise ValueError(
            f"Review not found for source record "
            f"{source_record.id}"
        )

    return review


def mark_record_resolved(
    session,
    source_record: SourceRecord,
    resolution_reason: str,
) -> None:
    review = get_review(session, source_record)

    # Prevent count inflation if the script is run twice.
    if review.status == "resolved":
        return

    review.status = "resolved"
    review.reason = (
        f"{review.reason} | Resolution: {resolution_reason}"
    )

    ingestion_run = session.get(
        IngestionRun,
        source_record.ingestion_run_id,
    )

    if ingestion_run is not None:
        ingestion_run.accepted_row_count += 1


def create_gig_profile(
    session,
    source_record: SourceRecord,
    person: Person,
) -> None:
    existing_profile = session.scalar(
        select(GigWorkerProfile).where(
            GigWorkerProfile.source_record_id
            == source_record.id
        )
    )

    if existing_profile is not None:
        return

    row = json.loads(source_record.raw_data)

    attach_missing_identifiers(
        session,
        person=person,
        email=row.get("email_id"),
        source_name="gig_workers",
    )

    attach_skills(
        session,
        person=person,
        skills_value=row.get("skill_tags"),
        source_name="gig_workers",
    )

    rate_amount, rate_unit = normalize_gig_rate(
        row.get("rate")
    )

    session.add(
        GigWorkerProfile(
            source_record_id=source_record.id,
            person_id=person.id,
            rate_amount_inr=rate_amount,
            rate_unit=rate_unit,
            worker_status=normalize_status(
                row.get("status")
            ),
        )
    )

    source_record.person_id = person.id
    source_record.processing_status = "manually_resolved"


def create_cbnexus_profile(
    session,
    source_record: SourceRecord,
    person: Person,
) -> None:
    existing_profile = session.scalar(
        select(CBNexusProfile).where(
            CBNexusProfile.source_record_id
            == source_record.id
        )
    )

    if existing_profile is not None:
        return

    row = json.loads(source_record.raw_data)

    attach_missing_identifiers(
        session,
        person=person,
        phone=row.get("Phone Number"),
        source_name="cbnexus",
    )

    session.add(
        CBNexusProfile(
            source_record_id=source_record.id,
            person_id=person.id,
            verified=normalize_boolean(
                row.get("Verified")
            ),
            projects_completed=parse_optional_int(
                row.get("Projects Completed")
            ),
        )
    )

    source_record.person_id = person.id
    source_record.processing_status = "manually_resolved"


def resolve_create_new(
    session,
    source_record: SourceRecord,
    reason: str,
) -> None:
    row = json.loads(source_record.raw_data)

    if source_record.source_name != "gig_workers":
        raise ValueError(
            "create_new currently supports Gig Worker reviews"
        )

    person = create_person(
        session,
        full_name=row.get("worker_name"),
        email=row.get("email_id"),
        city=row.get("location"),
        source_name="gig_workers",
    )

    create_gig_profile(
        session,
        source_record,
        person,
    )

    mark_record_resolved(
        session,
        source_record,
        reason,
    )


def resolve_match_source(
    session,
    source_record: SourceRecord,
    target_record: SourceRecord,
    reason: str,
) -> None:
    if target_record.person_id is None:
        raise ValueError(
            "Target source record has no canonical person"
        )

    person = session.get(
        Person,
        target_record.person_id,
    )

    if person is None:
        raise ValueError(
            "Target canonical person could not be loaded"
        )

    if source_record.source_name == "cbnexus":
        create_cbnexus_profile(
            session,
            source_record,
            person,
        )
    elif source_record.source_name == "gig_workers":
        create_gig_profile(
            session,
            source_record,
            person,
        )
    else:
        raise ValueError(
            f"Unsupported source: {source_record.source_name}"
        )

    mark_record_resolved(
        session,
        source_record,
        reason,
    )


def resolve_pair(
    session,
    gig_record: SourceRecord,
    cbnexus_record: SourceRecord,
    reason: str,
) -> None:
    gig_row = json.loads(gig_record.raw_data)
    cbnexus_row = json.loads(cbnexus_record.raw_data)

    person = create_person(
        session,
        full_name=gig_row.get("worker_name"),
        email=gig_row.get("email_id"),
        phone=cbnexus_row.get("Phone Number"),
        city=gig_row.get("location"),
        source_name="manual_review",
    )

    create_gig_profile(
        session,
        gig_record,
        person,
    )

    create_cbnexus_profile(
        session,
        cbnexus_record,
        person,
    )

    mark_record_resolved(
        session,
        gig_record,
        reason,
    )

    mark_record_resolved(
        session,
        cbnexus_record,
        reason,
    )


def apply_review_decisions() -> None:
    if not DECISIONS_PATH.exists():
        raise FileNotFoundError(
            f"Decision file not found: {DECISIONS_PATH}"
        )

    resolved_count = 0

    with DECISIONS_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as decision_file:
        decisions = list(
            csv.DictReader(decision_file)
        )

    with SessionLocal() as session:
        try:
            for decision in decisions:
                source_record = get_source_record(
                    session,
                    decision["source_name"],
                    int(decision["source_row_number"]),
                )

                action = decision["decision"].strip()
                reason = decision["reason"].strip()

                review = get_review(
                    session,
                    source_record,
                )

                if review.status == "resolved":
                    print(
                        f"Skipping already resolved record: "
                        f"{source_record.source_name} "
                        f"row {source_record.source_row_number}"
                    )
                    continue

                if action == "create_new":
                    resolve_create_new(
                        session,
                        source_record,
                        reason,
                    )
                    resolved_count += 1

                elif action in {
                    "match_source",
                    "pair_with_source",
                }:
                    target_record = get_source_record(
                        session,
                        decision["target_source_name"],
                        int(
                            decision[
                                "target_source_row_number"
                            ]
                        ),
                    )

                    if action == "match_source":
                        resolve_match_source(
                            session,
                            source_record,
                            target_record,
                            reason,
                        )
                        resolved_count += 1

                    else:
                        resolve_pair(
                            session,
                            source_record,
                            target_record,
                            reason,
                        )

                        # One decision resolves two review records.
                        resolved_count += 2

                else:
                    raise ValueError(
                        f"Unsupported decision: {action}"
                    )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print("\nMATCH REVIEW RESOLUTION COMPLETE")
    print("=" * 50)
    print(f"Resolved review records: {resolved_count}")


if __name__ == "__main__":
    apply_review_decisions()