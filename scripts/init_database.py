from sqlalchemy import inspect

from src.database.connection import Base, DATABASE_PATH, engine

# Importing models registers them with SQLAlchemy metadata.
from src.database import models  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("\nDATABASE INITIALIZED")
    print("=" * 50)
    print(f"Database path: {DATABASE_PATH}")
    print("Created tables:")

    for table in tables:
        print(f"  - {table}")


if __name__ == "__main__":
    main()