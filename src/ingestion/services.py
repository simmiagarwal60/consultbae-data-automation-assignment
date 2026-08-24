import hashlib
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    Person,
    PersonSkill,
    Skill,
)
from src.ingestion.normalizers import normalize_skills


def serialize_raw_row(row: dict) -> str:
    """Serialize an original CSV row for audit storage."""
    return json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
    )


def create_record_hash(
    source_name: str,
    row: dict,
) -> str:
    """Create a deterministic SHA-256 hash for a source row."""
    serialized = serialize_raw_row(row)
    content = f"{source_name}:{serialized}"

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def parse_optional_float(value: object) -> Optional[float]:
    """Convert a value into a float without crashing ingestion."""
    if value is None:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def attach_skills(
    session: Session,
    *,
    person: Person,
    skills_value: object,
    source_name: str,
) -> None:
    """Attach normalized skills without creating duplicates."""
    skill_names = normalize_skills(skills_value)

    for skill_name in skill_names:
        skill = session.scalar(
            select(Skill).where(
                Skill.name == skill_name
            )
        )

        if skill is None:
            skill = Skill(name=skill_name)
            session.add(skill)
            session.flush()

        existing_link = session.scalar(
            select(PersonSkill).where(
                PersonSkill.person_id == person.id,
                PersonSkill.skill_id == skill.id,
            )
        )

        if existing_link is None:
            session.add(
                PersonSkill(
                    person_id=person.id,
                    skill_id=skill.id,
                    source_name=source_name,
                )
            )
def parse_optional_int(value: object) -> Optional[int]:
    """Convert a value into an integer without crashing ingestion."""
    if value is None:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None