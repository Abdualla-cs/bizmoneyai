from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BizMoneyAI API"
    env: str = "development"
    database_url: str = "postgresql+psycopg2://bizmoney:bizmoney@localhost:5432/bizmoney"
    jwt_secret_key: str = Field(
        default="change_me",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool | None = None

    @property
    def use_secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.env == "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
