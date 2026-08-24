import argparse

from sqlalchemy import func, select

from scripts.ingest_cbnexus import ingest_cbnexus
from scripts.ingest_gig_workers import ingest_gig_workers
from scripts.ingest_naukri import ingest_naukri
from scripts.resolve_match_reviews import apply_review_decisions
from src.database import models  # noqa: F401
from src.database.connection import (
    Base,
    DATABASE_PATH,
    SessionLocal,
    engine,
)
from src.database.models import (
    CBNexusProfile,
    GigWorkerProfile,
    MatchReview,
    NaukriProfile,
    Person,
    SourceRecord,
)


def reset_database() -> None:
    """Delete only the generated project SQLite database."""
    engine.dispose()

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print(f"Removed old database: {DATABASE_PATH}")

    Base.metadata.create_all(bind=engine)
    print(f"Created clean database: {DATABASE_PATH}")


def print_final_summary() -> None:
    with SessionLocal() as session:
        people_count = session.scalar(
            select(func.count()).select_from(Person)
        )

        naukri_count = session.scalar(
            select(func.count()).select_from(NaukriProfile)
        )

        gig_count = session.scalar(
            select(func.count()).select_from(GigWorkerProfile)
        )

        cbnexus_count = session.scalar(
            select(func.count()).select_from(CBNexusProfile)
        )

        pending_reviews = session.scalar(
            select(func.count())
            .select_from(MatchReview)
            .where(MatchReview.status == "pending")
        )

        rejected_count = session.scalar(
            select(func.count())
            .select_from(SourceRecord)
            .where(
                SourceRecord.processing_status == "rejected"
            )
        )

    print("\nFINAL PIPELINE SUMMARY")
    print("=" * 50)
    print(f"Canonical people: {people_count}")
    print(f"Naukri profiles: {naukri_count}")
    print(f"Gig Worker profiles: {gig_count}")
    print(f"CBNexus profiles: {cbnexus_count}")
    print(f"Pending match reviews: {pending_reviews}")
    print(f"Rejected source rows: {rejected_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the ConsultBae database and ingest "
            "all three source files."
        )
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Delete the generated SQLite database before ingestion."
        ),
    )

    arguments = parser.parse_args()

    if not arguments.reset:
        parser.error(
            "Use --reset to confirm rebuilding the generated database."
        )

    print("\nCONSULTBAE MERGE PIPELINE")
    print("=" * 50)

    reset_database()

    print("\n[1/4] Ingesting Naukri applicants...")
    ingest_naukri()

    print("\n[2/4] Ingesting Gig Workers...")
    ingest_gig_workers()

    print("\n[3/4] Ingesting CBNexus contacts...")
    ingest_cbnexus()

    print("\n[4/4] Applying reviewed match decisions...")
    apply_review_decisions()

    print_final_summary()


if __name__ == "__main__":
    main()