from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    runtime_dir = tmp_path / "runtime"
    database_path = tmp_path / "heimdall.db"
    monkeypatch.setenv("HEIMDALL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HEIMDALL_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("HEIMDALL_PREVIEW_HOST", "preview.local")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_START", "18000")
    monkeypatch.setenv("HEIMDALL_PREVIEW_PORT_END", "18010")
    for key in (
        "HEIMDALL_GITHUB_API_TOKEN",
        "GITHUB_API_TOKEN",
        "GITHUB_TOKEN",
        "HEIMDALL_GITHUB_WEBHOOK_SECRET",
        "GITHUB_WEBHOOK_SECRET",
        "GITHUB_SECRET",
        "HEIMDALL_GITLAB_BASE_URL",
        "GITLAB_BASE_URL",
        "HEIMDALL_GITLAB_API_TOKEN",
        "GITLAB_API_TOKEN",
        "GITLAB_TOKEN",
        "HEIMDALL_GITLAB_WEBHOOK_SECRET",
        "GITLAB_WEBHOOK_SECRET",
        "GITLAB_SYSTEM_HOOK_SECRET",
    ):
        monkeypatch.setenv(key, "")

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
