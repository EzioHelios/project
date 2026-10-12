"""Authentication-related schemas."""

import re

import msgspec

from app.lib.schema import CamelizedBaseStruct
from app.lib.validation import validate_email, validate_name, validate_password, validate_username


class HumanVerification(CamelizedBaseStruct):
    provider: str
    payload: str


class AccountLogin(CamelizedBaseStruct):
    username: str
    password: str
    human_verification: HumanVerification | None = None

    def __post_init__(self) -> None:
        """Accept an email address or an existing account's username."""
        self.username = self.username.strip().lower()
        if "@" in self.username:
            self.username = validate_email(self.username)
        elif not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,29}", self.username):
            msg = "Enter a valid email address or username"
            raise ValueError(msg)


class AccountRegister(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None
    username: str | None = None
    initial_team_name: str | msgspec.UnsetType | None = msgspec.UNSET

    def __post_init__(self) -> None:
        """Validate fields."""
        self.email = validate_email(self.email)
        self.password = validate_password(self.password)
        if self.name is not None:
            self.name = validate_name(self.name)
        if self.username is not None:
            self.username = validate_username(self.username)


class PasswordUpdate(CamelizedBaseStruct):
    current_password: str
    new_password: str

    def __post_init__(self) -> None:
        """Validate new password strength."""
        self.new_password = validate_password(self.new_password)


class PasswordVerify(CamelizedBaseStruct):
    current_password: str
