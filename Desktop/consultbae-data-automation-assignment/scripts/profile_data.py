import json
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

CSV_FILES = [
    "source1_naukri_applicants.csv",
    "source2_gig_workers.csv",
    "source3_cbnexus_contacts.csv",
]


def is_valid_email(value: str) -> bool:
    """Perform a basic structural email check."""
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, value.strip(), re.IGNORECASE))


def find_repeated_header_rows(df: pd.DataFrame) -> list[int]:
    """Find rows containing the CSV column names instead of real data."""
    normalized_columns = {
        str(column).strip().lower() for column in df.columns
    }

    repeated_rows = []

    for index, row in df.iterrows():
        normalized_values = {
            str(value).strip().lower()
            for value in row.tolist()
            if str(value).strip()
        }

        overlap = normalized_columns.intersection(normalized_values)

        if len(overlap) >= max(2, len(df.columns) // 2):
            repeated_rows.append(int(index))

    return repeated_rows


def profile_csv(file_path: Path) -> dict:
    df = pd.read_csv(
        file_path,
        dtype=str,
        keep_default_na=False,
    )

    # Remove spaces around every text value for profiling only.
    stripped_df = df.apply(lambda column: column.str.strip())

    empty_counts = {
        column: int((stripped_df[column] == "").sum())
        for column in stripped_df.columns
    }

    unique_counts = {
        column: int(stripped_df[column].nunique())
        for column in stripped_df.columns
    }

    fully_blank_rows = stripped_df.index[
        (stripped_df == "").all(axis=1)
    ].tolist()

    email_columns = [
        column
        for column in df.columns
        if "email" in column.lower()
    ]

    invalid_email_rows = {}

    for column in email_columns:
        invalid_indexes = []

        for index, value in stripped_df[column].items():
            if value and not is_valid_email(value):
                invalid_indexes.append(int(index))

        invalid_email_rows[column] = invalid_indexes

    return {
        "file_name": file_path.name,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": list(df.columns),
        "empty_value_counts": empty_counts,
        "unique_value_counts": unique_counts,
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "fully_blank_row_indexes": fully_blank_rows,
        "repeated_header_row_indexes": find_repeated_header_rows(df),
        "invalid_email_row_indexes": invalid_email_rows,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    complete_report = {
        "files": [],
        "total_raw_rows": 0,
    }

    for file_name in CSV_FILES:
        file_path = RAW_DATA_DIR / file_name

        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing file: {file_path}\n"
                "Place all three CSV files inside data/raw."
            )

        report = profile_csv(file_path)
        complete_report["files"].append(report)
        complete_report["total_raw_rows"] += report["row_count"]

    output_path = OUTPUT_DIR / "profile_report.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            complete_report,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nDATA PROFILING COMPLETE")
    print("=" * 50)

    for report in complete_report["files"]:
        print(f"\nFile: {report['file_name']}")
        print(f"Rows: {report['row_count']}")
        print(f"Columns: {report['column_count']}")
        print(
            "Blank rows:",
            report["fully_blank_row_indexes"],
        )
        print(
            "Repeated header rows:",
            report["repeated_header_row_indexes"],
        )
        print(
            "Invalid email rows:",
            report["invalid_email_row_indexes"],
        )

    print(f"\nFull report saved to: {output_path}")


if __name__ == "__main__":
    main()