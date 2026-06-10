from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PLACEHOLDER_VALUES = {
    "",
    "your.email@gmail.com",
    "your_google_app_password",
    "Your Name your.email@gmail.com",
}


class Settings(BaseSettings):
    telegram_bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    sec_user_agent: str = Field("Your Name your.email@gmail.com", alias="SEC_USER_AGENT")
    smtp_host: str = Field("smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("", alias="SMTP_FROM")
    report_email_to: str = Field("", alias="REPORT_EMAIL_TO")
    ollama_host: str = Field("http://host.docker.internal:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field("llama3.2:3b", alias="OLLAMA_MODEL")
    workspace_dir: Path = Field(Path("/workspace"), alias="WORKSPACE_DIR")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def reports_dir(self) -> Path:
        return self.workspace_dir / "reports"

    @property
    def audit_dir(self) -> Path:
        return self.workspace_dir / "audit"

    @property
    def runs_dir(self) -> Path:
        return self.workspace_dir / "runs"

    def smtp_configured(self) -> bool:
        values = [self.smtp_host, str(self.smtp_port), self.smtp_user, self.smtp_password, self.smtp_from, self.report_email_to]
        return all(v.strip() not in PLACEHOLDER_VALUES for v in values)

    def sec_user_agent_configured(self) -> bool:
        return self.sec_user_agent.strip() not in PLACEHOLDER_VALUES


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for directory in (settings.workspace_dir, settings.reports_dir, settings.audit_dir, settings.runs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return settings
