import re
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

_PRINTABLE_ASCII = re.compile(r"[\x20-\x7E]*")


def _check_printable_ascii(value: SecretStr) -> SecretStr:
    if _PRINTABLE_ASCII.fullmatch(value.get_secret_value()) is None:
        raise ValueError(
            "Password may contain only English letters, digits, keyboard symbols and spaces"
        )
    return value


Login = Annotated[str, StringConstraints(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]
Password = Annotated[
    SecretStr, Field(min_length=8, max_length=128), AfterValidator(_check_printable_ascii)
]


class RegisterRequest(BaseModel):
    login: Login
    password: Password
    repeat_password: SecretStr

    @model_validator(mode="after")
    def _check_passwords(self) -> Self:
        if self.password.get_secret_value() != self.repeat_password.get_secret_value():
            raise ValueError("Passwords do not match")
        if self.password.get_secret_value() == self.login:
            raise ValueError("Password must not equal the login")
        return self


class LoginRequest(BaseModel):
    # No login pattern or password minimum here, so a wrong but well-sized login or password is a
    # 401; only an empty or oversized value (login over 32, password over 128) is a 422.
    login: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 3600


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    new_password: Password
    repeat_new_password: SecretStr

    @model_validator(mode="after")
    def _check_passwords(self) -> Self:
        new = self.new_password.get_secret_value()
        if new != self.repeat_new_password.get_secret_value():
            raise ValueError("Passwords do not match")
        if new == self.current_password.get_secret_value():
            raise ValueError("New password must differ from the current one")
        return self
