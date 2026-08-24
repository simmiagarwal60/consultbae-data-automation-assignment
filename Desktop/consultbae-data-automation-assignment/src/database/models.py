from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
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
