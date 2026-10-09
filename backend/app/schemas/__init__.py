import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Пароль слишком короткий — минимум 8 символов")
    if not re.search(r"[A-ZА-ЯЁ]", v):
        raise ValueError("В пароле обязательна хотя бы одна заглавная буква")
    if not re.search(r"[a-zа-яё]", v):
        raise ValueError("В пароле обязательна хотя бы одна строчная буква")
    if not re.search(r"[0-9!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|`~]", v):
        raise ValueError("В пароле обязательны цифра или специальный символ")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: str = Field(pattern="^(candidate|employer)$")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        return _validate_password(v)

class ConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern="^\\d{6}$")

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    role: str


class CandidateProfileIn(BaseModel):
    full_name: str = ""
    contacts: dict = {}
    summary: str = ""
    stack: list[str] = []
    experience_years: float = 0.0
    soft_skills: list[str] = []

class CandidateProfileOut(BaseModel):
    user_id: str = ""
    full_name: str
    contacts: dict = {}
    summary: str = ""
    specialization_code: str | None
    grade: str | None
    theta: float | None
    category: str | None = None
    stack: list[str]
    experience_years: float
    fsp_id: str | None = None
    has_fsp: bool = False
    photo_url: str | None = None
    is_public: bool = True
    consent_data_processing: bool = False

class EmployerProfileIn(BaseModel):
    company_name: str
    description: str = ""
    industry: str = ""
    contact_email: str = ""
    contact_phone: str = ""


class SurveyIn(BaseModel):
    specialization_code: str
    survey_answer: str
    target_grade: str = Field(pattern="^(junior|middle|senior|lead)$")
    code_language: str = Field(default="python",
                               pattern=r"^(python|javascript|c\+\+|c#|java)$")
    start_test: bool = True

class AnswerIn(BaseModel):
    item_id: str
    choice: int | None = None
    value: str | None = None
    time_spent_ms: int = 0
    away_ms: int = 0
    tab_switches: int = 0

    def payload(self) -> dict:
        if self.choice is not None:
            return {"choice": self.choice}
        return {"value": self.value}


class VacancyIn(BaseModel):
    title: str
    description: str
    specialization_code: str
    min_grade: str = Field(pattern="^(junior|middle|senior|lead)$")
    stack: list[str] = []
    code_language: str = Field(default="python",
                               pattern=r"^(python|javascript|c\+\+|c#|java)$")
    salary_min: int = Field(gt=0)
    salary_max: int = Field(gt=0)

class VacancyOut(BaseModel):
    id: str
    title: str
    description: str
    specialization_code: str
    min_grade: str
    stack: list[str]
    salary_min: int
    salary_max: int
    company_name: str
    is_active: bool = True
    code_language: str = "python"


class InvitationIn(BaseModel):
    candidate_id: str
    vacancy_id: str | None = None
    blueprint_id: str | None = None
    message: str
    salary_min: int = Field(gt=0)
    salary_max: int = Field(gt=0)

class NeedIn(BaseModel):
    raw_text: str
    specialization_code: str | None = None
    min_grade: str | None = Field(default=None, pattern="^(junior|middle|senior|lead)$")
    stack: list[str] = []
    only_fsp: bool = False

class ShortlistItem(BaseModel):
    candidate_id: str
    full_name: str
    category: str
    grade: str
    stack: list
    experience_years: float
    has_fsp: bool
    score: float
    rationale: str
    breakdown: dict
