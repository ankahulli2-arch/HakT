import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import Encrypted
from app.core.db import Base

def uid() -> Mapped[str]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

def now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    candidate = "candidate"
    employer = "employer"

class Grade(str, enum.Enum):
    junior = "junior"
    middle = "middle"
    senior = "senior"
    lead = "lead"

class ItemKind(str, enum.Enum):
    quiz = "quiz"
    code = "code"

class TestStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"

class InteractionStatus(str, enum.Enum):
    sent = "sent"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"

class MicrotaskStatus(str, enum.Enum):
    pending = "pending"
    solved = "solved"
    approach = "approach"
    expired = "expired"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uid()
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirm_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    full_name: Mapped[str] = mapped_column(Encrypted("candidate_profiles.full_name"), default="")

    contacts: Mapped[dict] = mapped_column(Encrypted("candidate_profiles.contacts", json_field=True), default=dict)
    summary: Mapped[str] = mapped_column(Encrypted("candidate_profiles.summary"), default="")
    stack: Mapped[list] = mapped_column(JSON, default=list)
    experience_years: Mapped[float] = mapped_column(Float, default=0.0)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)


    specialization_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[Grade | None] = mapped_column(Enum(Grade), nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_se: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_history: Mapped[list] = mapped_column(JSON, default=list)
    last_grade_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    integrity: Mapped[float] = mapped_column(Float, default=1.0)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)


    fsp_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    fsp_history: Mapped[list | None] = mapped_column(JSON, nullable=True)


    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_data_processing: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship()

class EmployerProfile(Base):
    __tablename__ = "employer_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    company_name: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String, default="")
    contact_email: Mapped[str] = mapped_column(Encrypted("employer_profiles.contact_email"), default="")
    contact_phone: Mapped[str] = mapped_column(Encrypted("employer_profiles.contact_phone"), default="")
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    blind_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship()


class Specialization(Base):
    __tablename__ = "specializations"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    survey_options: Mapped[list] = mapped_column(JSON, default=list)


class ItemTemplate(Base):
    __tablename__ = "item_templates"

    id: Mapped[str] = uid()
    specialization_code: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    template_params: Mapped[dict] = mapped_column(JSON, default=dict)

    a: Mapped[float] = mapped_column(Float, default=1.5)
    b: Mapped[float] = mapped_column(Float, default=0.0)
    c: Mapped[float] = mapped_column(Float, default=0.15)
    exposure_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[str] = uid()
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.user_id"), index=True)
    specialization_code: Mapped[str] = mapped_column(String(32))
    target_grade: Mapped[Grade] = mapped_column(Enum(Grade))
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[TestStatus] = mapped_column(Enum(TestStatus), default=TestStatus.in_progress)

    theta: Mapped[float] = mapped_column(Float, default=0.0)
    se: Mapped[float] = mapped_column(Float, default=1.5)
    administered: Mapped[list] = mapped_column(JSON, default=list)

    measured_grade: Mapped[Grade | None] = mapped_column(Enum(Grade), nullable=True)
    applied_grade: Mapped[Grade | None] = mapped_column(Enum(Grade), nullable=True)
    blueprint_id: Mapped[str | None] = mapped_column(ForeignKey("test_blueprints.id"), nullable=True)
    code_language: Mapped[str] = mapped_column(String(16), default="python")
    integrity: Mapped[float] = mapped_column(Float, default=1.0)
    away_total_ms: Mapped[int] = mapped_column(Integer, default=0)
    tab_switches: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class TestAnswer(Base):
    __tablename__ = "test_answers"
    __table_args__ = (UniqueConstraint("session_id", "item_id"),)

    id: Mapped[str] = uid()
    session_id: Mapped[str] = mapped_column(ForeignKey("test_sessions.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    answer: Mapped[dict] = mapped_column(JSON)
    correct: Mapped[bool] = mapped_column(Boolean)
    variant: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    time_spent_ms: Mapped[int] = mapped_column(Integer, default=0)
    away_ms: Mapped[int] = mapped_column(Integer, default=0)
    tab_switches: Mapped[int] = mapped_column(Integer, default=0)
    cheat_signals: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FspAchievement(Base):
    __tablename__ = "fsp_achievements"

    id: Mapped[str] = uid()
    fsp_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    level: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, default=0.0)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[str] = uid()
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    specialization_code: Mapped[str] = mapped_column(String(32))
    min_grade: Mapped[Grade] = mapped_column(Enum(Grade))
    stack: Mapped[list] = mapped_column(JSON, default=list)
    salary_min: Mapped[int] = mapped_column(Integer)
    salary_max: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    code_language: Mapped[str] = mapped_column(String(16), default="python")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    employer: Mapped["EmployerProfile"] = relationship()

class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = uid()
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.user_id"), index=True)
    vacancy_id: Mapped[str | None] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    blueprint_id: Mapped[str | None] = mapped_column(ForeignKey("test_blueprints.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    salary_min: Mapped[int] = mapped_column(Integer)
    salary_max: Mapped[int] = mapped_column(Integer)
    status: Mapped[InteractionStatus] = mapped_column(Enum(InteractionStatus), default=InteractionStatus.sent)
    contact_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    employer: Mapped["EmployerProfile"] = relationship()
    vacancy: Mapped["Vacancy | None"] = relationship()

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = uid()
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.user_id"), index=True)
    vacancy_id: Mapped[str] = mapped_column(ForeignKey("vacancies.id"), index=True)
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[InteractionStatus] = mapped_column(Enum(InteractionStatus), default=InteractionStatus.sent)
    contact_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    vacancy: Mapped["Vacancy"] = relationship()

class EmployerNeed(Base):
    __tablename__ = "employer_needs"

    id: Mapped[str] = uid()
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    specialization_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    min_grade: Mapped[Grade | None] = mapped_column(Enum(Grade), nullable=True)
    stack: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Microtask(Base):
    __tablename__ = "microtasks"

    id: Mapped[str] = uid()
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.user_id"), index=True)
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[MicrotaskStatus] = mapped_column(Enum(MicrotaskStatus), default=MicrotaskStatus.pending)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmployerCustomItem(Base):
    __tablename__ = "employer_custom_items"

    id: Mapped[str] = uid()
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    correct: Mapped[str] = mapped_column(String)
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind), default=ItemKind.quiz)

    a: Mapped[float] = mapped_column(Float, default=1.5)
    b: Mapped[float] = mapped_column(Float, default=0.0)
    c: Mapped[float] = mapped_column(Float, default=0.25)

class TestBlueprint(Base):
    __tablename__ = "test_blueprints"

    id: Mapped[str] = uid()
    employer_id: Mapped[str] = mapped_column(ForeignKey("employer_profiles.user_id"), index=True)
    vacancy_id: Mapped[str | None] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    specialization_code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String, default="Тест по потребности")
    researched_skills: Mapped[list] = mapped_column(JSON, default=list)
    items_json: Mapped[list] = mapped_column(JSON, default=list)


    status: Mapped[str] = mapped_column(String(16), default="draft")
    code_language: Mapped[str] = mapped_column(String(16), default="python")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


GRADE_ORDER = [g.value for g in Grade]


class CandidateCategory(Base):
    __tablename__ = "candidate_categories"
    __table_args__ = (UniqueConstraint("candidate_id", "specialization_code"),)

    id: Mapped[str] = uid()
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.user_id"), index=True)
    specialization_code: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade] = mapped_column(Enum(Grade))
    theta: Mapped[float] = mapped_column(Float)
    theta_se: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
