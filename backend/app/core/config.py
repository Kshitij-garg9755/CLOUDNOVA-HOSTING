from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./cloudnova.db"
    secret_key: str = "development-only-change-this-secret-key"
    access_token_minutes: int = 45
    frontend_origins: str = "http://localhost:5173"
    allowed_hosts: str = "*"
    environment: str = "development"
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payment_demo_mode: bool = True
    github_app_id: str = ""
    github_app_slug: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_private_key: str = ""
    github_webhook_secret: str = ""
    github_callback_url: str = "http://localhost:8000/api/github/callback"
    public_base_domain: str = ""
    deployment_worker_enabled: bool = False
    deployment_isolation_runtime: str = ""
    redis_url: str = "redis://localhost:6379/0"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def github_private_key_pem(self) -> str:
        """Normalize Render secrets whether entered as multiline PEM or escaped newlines."""
        return self.github_private_key.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n").strip()

    @property
    def database_url_for_sqlalchemy(self) -> str:
        """Render may provide postgres:// or postgresql://; use the installed psycopg v3 driver."""
        value = self.database_url
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

settings = Settings()
def origins() -> list[str]:
    values = [x.strip().rstrip("/") for x in settings.frontend_origins.split(",") if x.strip()]
    if "*" in values:
        raise ValueError("FRONTEND_ORIGINS must list explicit origins when CORS credentials are enabled")
    return values
def allowed_hosts() -> list[str]: return [x.strip() for x in settings.allowed_hosts.split(",") if x.strip()]
