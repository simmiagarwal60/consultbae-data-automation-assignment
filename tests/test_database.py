from sqlalchemy import inspect

from src.database.connection import Base, engine
from src.database import models  # noqa: F401


EXPECTED_TABLES = {
    "people",
    "person_emails",
    "person_phones",
    "skills",
    "person_skills",
    "ingestion_runs",
    "source_records",
    "naukri_profiles",
    "gig_worker_profiles",
    "cbnexus_profiles",
    "match_reviews",
    "audio_submissions",
}


def test_database_tables_exist():
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())

    assert EXPECTED_TABLES.issubset(actual_tables)