import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.database.connection import SessionLocal
from src.database.models import (
    GigWorkerProfile,
    IngestionRun,
    MatchReview,
    Person,
    SourceRecord,
)
from src.ingestion.normalizers import (
    normalize_email,
    normalize_gig_rate,
    normalize_status,
)
from src.ingestion.services import (
    attach_skills,
    create_record_hash,
    serialize_raw_row,
)
from src.matching.resolver import (
    attach_missing_identifiers,
    create_person,
    resolve_person,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "source2_gig_workers.csv"
)

SOURCE_NAME = "gig_workers"


def ingest_gig_workers() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Gig Workers source file not found: {CSV_PATH}"
        )

    dataframe = pd.read_csv(
        CSV_PATH,
        dtype=str,
        keep_default_na=False,
    )

    with SessionLocal() as session:
        ingestion_run = IngestionRun(
            source_name=SOURCE_NAME,
            source_file=CSV_PATH.name,
            status="running",
            raw_row_count=len(dataframe),
        )

        session.add(ingestion_run)
        session.flush()

        accepted_count = 0
        rejected_count = 0
        created_people = 0
        matched_people = 0
        review_count = 0

        try:
            for dataframe_index, pandas_row in dataframe.iterrows():
                row = {
                    column: str(value).strip()
                    for column, value
                    in pandas_row.to_dict().items()
                }

                csv_row_number = dataframe_index + 2

                source_record = SourceRecord(
                    ingestion_run_id=ingestion_run.id,
                    source_name=SOURCE_NAME,
                    source_row_number=csv_row_number,
                    raw_data=serialize_raw_row(row),
                    record_hash=create_record_hash(
                        SOURCE_NAME,
                        row,
                    ),
                    processing_status="pending",
                )

                session.add(source_record)
                session.flush()

                full_name = row.get("worker_name")
                email = row.get("email_id")
                city = row.get("location")

                # The Gig Workers source requires both a name
                # and a structurally valid email.
                if not full_name:
                    source_record.processing_status = "rejected"
                    source_record.rejection_reason = (
                        "Completely blank or missing worker name"
                    )
                    rejected_count += 1
                    continue

                if normalize_email(email) is None:
                    source_record.processing_status = "rejected"
                    source_record.rejection_reason = (
                        "Invalid email structure; possible shifted "
                        "or corrupted CSV row"
                    )
                    rejected_count += 1
                    continue

                decision = resolve_person(
                    session,
                    full_name=full_name,
                    email=email,
                    city=city,
                )

                if decision.action == "review":
                    source_record.processing_status = "review"

                    session.add(
                        MatchReview(
                            source_record_id=source_record.id,
                            candidate_person_ids=json.dumps(
                                decision.candidate_person_ids
                            ),
                            reason=decision.reason,
                            status="pending",
                        )
                    )

                    review_count += 1
                    continue

                if decision.action == "new":
                    person = create_person(
                        session,
                        full_name=full_name,
                        email=email,
                        city=city,
                        source_name=SOURCE_NAME,
                    )

                    source_record.processing_status = "created"
                    created_people += 1

                else:
                    person = session.get(
                        Person,
                        decision.person_id,
                    )

                    if person is None:
                        raise RuntimeError(
                            "Matched person could not be loaded"
                        )

                    attach_missing_identifiers(
                        session,
                        person=person,
                        email=email,
                        source_name=SOURCE_NAME,
                    )

                    source_record.processing_status = "matched"
                    matched_people += 1

                source_record.person_id = person.id

                attach_skills(
                    session,
                    person=person,
                    skills_value=row.get("skill_tags"),
                    source_name=SOURCE_NAME,
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

                accepted_count += 1

            ingestion_run.accepted_row_count = accepted_count
            ingestion_run.rejected_row_count = rejected_count
            ingestion_run.status = "completed"
            ingestion_run.completed_at = datetime.now()

            session.commit()

        except Exception:
            session.rollback()
            raise

    print("\nGIG WORKERS INGESTION COMPLETE")
    print("=" * 50)
    print(f"Raw rows: {len(dataframe)}")
    print(f"Accepted rows: {accepted_count}")
    print(f"Rejected rows: {rejected_count}")
    print(f"Created people: {created_people}")
    print(f"Matched existing people: {matched_people}")
    print(f"Sent for review: {review_count}")


if __name__ == "__main__":
    ingest_gig_workers()