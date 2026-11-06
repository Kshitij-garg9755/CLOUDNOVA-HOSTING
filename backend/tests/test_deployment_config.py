from app.core.config import Settings

def test_render_postgres_urls_use_psycopg_v3():
    assert Settings(database_url="postgres://user:pass@host/db").database_url_for_sqlalchemy == "postgresql+psycopg://user:pass@host/db"
    assert Settings(database_url="postgresql://user:pass@host/db").database_url_for_sqlalchemy == "postgresql+psycopg://user:pass@host/db"

def test_github_private_key_accepts_escaped_and_multiline_pem():
    escaped = Settings(github_private_key="-----BEGIN KEY-----\\nline\\n-----END KEY-----")
    multiline = Settings(github_private_key="-----BEGIN KEY-----\r\nline\r\n-----END KEY-----")
    assert escaped.github_private_key_pem == multiline.github_private_key_pem
    assert "\n" in escaped.github_private_key_pem
