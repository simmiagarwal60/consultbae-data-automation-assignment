import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.database.connection import SessionLocal
from src.database.models import (
    CBNexusProfile,
    IngestionRun,
    MatchReview,
    Person,
    SourceRecord,
)
from src.ingestion.normalizers import (
    normalize_boolean,
    normalize_phone,
)
from src.ingestion.services import (
    create_record_hash,
    parse_optional_int,
    serialize_raw_row,
)
from src.matching.resolver import (
    attach_missing_identifiers,
    resolve_person,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "source3_cbnexus_contacts.csv"
)

SOURCE_NAME = "cbnexus"


def ingest_cbnexus() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CBNexus source file not found: {CSV_PATH}"
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

                full_name = row.get("Name")
                phone = row.get("Phone Number")
                city = row.get("City")

                # This catches the repeated CSV header row.
                is_repeated_header = (
                    str(full_name).strip().lower() == "name"
                    and str(phone).strip().lower()
                    == "phone number"
                )

                if is_repeated_header:
                    source_record.processing_status = "rejected"
                    source_record.rejection_reason = (
                        "Repeated CSV header found inside data"
                    )
                    rejected_count += 1
                    continue

                if not full_name:
                    source_record.processing_status = "rejected"
                    source_record.rejection_reason = (
                        "Missing required contact name"
                    )
                    rejected_count += 1
                    continue

                if normalize_phone(phone) is None:
                    source_record.processing_status = "rejected"
                    source_record.rejection_reason = (
                        "Invalid or missing Indian phone number"
                    )
                    rejected_count += 1
                    continue

                decision = resolve_person(
                    session,
                    full_name=full_name,
                    phone=phone,
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

                # Every valid CBNexus row should either match by
                # phone or go to review because it has no email.
                if decision.action == "new":
                    source_record.processing_status = "review"

                    session.add(
                        MatchReview(
                            source_record_id=source_record.id,
                            candidate_person_ids="[]",
                            reason=(
                                "Valid CBNexus contact has no "
                                "existing identifier match"
                            ),
                            status="pending",
                        )
                    )

                    review_count += 1
                    continue

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
                    phone=phone,
                    source_name=SOURCE_NAME,
                )

                source_record.person_id = person.id
                source_record.processing_status = "matched"

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

                accepted_count += 1
                matched_people += 1

            ingestion_run.accepted_row_count = accepted_count
            ingestion_run.rejected_row_count = rejected_count
            ingestion_run.status = "completed"
            ingestion_run.completed_at = datetime.now()

            session.commit()

        except Exception:
            session.rollback()
            raise

    print("\nCBNEXUS INGESTION COMPLETE")
    print("=" * 50)
    print(f"Raw rows: {len(dataframe)}")
    print(f"Accepted rows: {accepted_count}")
    print(f"Rejected rows: {rejected_count}")
    print(f"Matched existing people: {matched_people}")
    print(f"Sent for review: {review_count}")


if __name__ == "__main__":
    ingest_cbnexus()