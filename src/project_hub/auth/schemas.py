from typing import Annotated, Self

from pydantic import BaseModel, Field, SecretStr, StringConstraints, model_validator

Login = Annotated[str, StringConstraints(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]
Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]


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
