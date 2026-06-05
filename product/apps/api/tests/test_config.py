import os

from app.config import _load_dotenv_file


def test_dotenv_file_loads_provider_credentials(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GITHUB_API_TOKEN=github-local-token",
                "GITHUB_WEBHOOK_SECRET='github-local-secret'",
                'GITLAB_BASE_URL="https://gitlab.example.test"',
                "GITLAB_API_TOKEN=gitlab-local-token",
                "GITLAB_SYSTEM_HOOK_SECRET=gitlab-local-secret",
            ]
        ),
        encoding="utf-8",
    )

    for key in (
        "GITHUB_API_TOKEN",
        "GITHUB_WEBHOOK_SECRET",
        "GITLAB_BASE_URL",
        "GITLAB_API_TOKEN",
        "GITLAB_SYSTEM_HOOK_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    _load_dotenv_file(env_path)

    assert os.environ["GITHUB_API_TOKEN"] == "github-local-token"
    assert os.environ["GITHUB_WEBHOOK_SECRET"] == "github-local-secret"
    assert os.environ["GITLAB_BASE_URL"] == "https://gitlab.example.test"
    assert os.environ["GITLAB_API_TOKEN"] == "gitlab-local-token"
    assert os.environ["GITLAB_SYSTEM_HOOK_SECRET"] == "gitlab-local-secret"


def test_dotenv_file_does_not_override_process_environment(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("GITHUB_API_TOKEN=file-token", encoding="utf-8")
    monkeypatch.setenv("GITHUB_API_TOKEN", "process-token")

    _load_dotenv_file(env_path)

    assert os.environ["GITHUB_API_TOKEN"] == "process-token"


def test_settings_exposes_provider_credentials(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{tmp_path / 'heimdall.db'}")
    monkeypatch.setenv("HEIMDALL_GITHUB_API_TOKEN", "github-token")
    monkeypatch.setenv("HEIMDALL_GITHUB_WEBHOOK_SECRET", "github-secret")
    monkeypatch.setenv("HEIMDALL_GITLAB_BASE_URL", "https://gitlab.example.test")
    monkeypatch.setenv("HEIMDALL_GITLAB_API_TOKEN", "gitlab-token")
    monkeypatch.setenv("HEIMDALL_GITLAB_WEBHOOK_SECRET", "gitlab-secret")

    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.github_api_token == "github-token"
    assert settings.github_webhook_secret == "github-secret"
    assert settings.gitlab_base_url == "https://gitlab.example.test"
    assert settings.gitlab_api_token == "gitlab-token"
    assert settings.gitlab_webhook_secret == "gitlab-secret"
