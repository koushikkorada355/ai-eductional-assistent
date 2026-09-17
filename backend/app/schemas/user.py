from pydantic import BaseModel, field_validator
from uuid import UUID
import re

# RFC 5322 simplified - requires @ and domain with dot, no spaces
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def _validate_email(v: str) -> str:
    v = v.strip()
    if not EMAIL_REGEX.fullmatch(v):
        raise ValueError("Invalid email address")
    # extra checks: no consecutive dots, domain has at least one dot, TLD >=2
    if ".." in v or v.startswith(".") or v.startswith("@") or "@." in v:
        raise ValueError("Invalid email address")
    domain = v.split("@")[-1]
    if "." not in domain or len(domain.split(".")[-1]) < 2:
        raise ValueError("Invalid email address")
    return v.lower()

class UserCreate(BaseModel):
    email: str
    password: str
    name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 120:
            raise ValueError("Name must be 120 characters or fewer")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email(v)

class UserOut(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role: str
    is_active: bool

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email(v)

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str