from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.connection import Base


class Person(Base):
    """
    Canonical person record.

    A person may have multiple source records, emails, phone numbers
    and skills, but only one row should exist in this table.
    """

    __tablename__ = "people"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    name_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    canonical_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    emails: Mapped[list["PersonEmail"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )

    phones: Mapped[list["PersonPhone"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )

    person_skills: Mapped[list["PersonSkill"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )


class PersonEmail(Base):
    """Every normalized email associated with a person."""

    __tablename__ = "person_emails"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    source_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    person: Mapped["Person"] = relationship(
        back_populates="emails",
    )


class PersonPhone(Base):
    """Every normalized phone number associated with a person."""

    __tablename__ = "person_phones"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    source_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    person: Mapped["Person"] = relationship(
        back_populates="phones",
    )


class Skill(Base):
    """Canonical skill such as Python, n8n or FastAPI."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    person_skills: Mapped[list["PersonSkill"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class PersonSkill(Base):
    """Many-to-many relationship between people and skills."""

    __tablename__ = "person_skills"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    person: Mapped["Person"] = relationship(
        back_populates="person_skills",
    )

    skill: Mapped["Skill"] = relationship(
        back_populates="person_skills",
    )

    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "skill_id",
            name="uq_person_skill",
        ),
    )
class IngestionRun(Base):
    """Audit information for each pipeline execution."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
    )

    raw_row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    accepted_row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    rejected_row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )


class SourceRecord(Base):
    """
    Original source row and its processing result.

    Keeping raw data makes the pipeline auditable and prevents
    accidental loss of information during cleaning.
    """

    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    raw_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint(
            "ingestion_run_id",
            "source_row_number",
            name="uq_run_source_row",
        ),
    )


class NaukriProfile(Base):
    """Naukri-specific applicant information."""

    __tablename__ = "naukri_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    experience_years: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    current_ctc_inr: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    applied_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )


class GigWorkerProfile(Base):
    """Gig-worker-specific information."""

    __tablename__ = "gig_worker_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rate_amount_inr: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    rate_unit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    worker_status: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )


class CBNexusProfile(Base):
    """CBNexus-specific contact information."""

    __tablename__ = "cbnexus_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    verified: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )

    projects_completed: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )


class MatchReview(Base):
    """Records that could not be merged safely without review."""

    __tablename__ = "match_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    candidate_person_ids: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )