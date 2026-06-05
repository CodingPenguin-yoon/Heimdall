def project_payload(**overrides):
    payload = {
        "name": "Preview API",
        "provider": "github",
        "repo_url": "https://github.com/example/preview-api.git",
        "tracked_branch": "main",
        "deploy_mode": "dockerfile",
        "build_context_path": ".",
        "dockerfile_path": "Dockerfile",
        "container_port": 8080,
        "health_check_path": "/health",
        "auto_deploy_enabled": True,
    }
    payload.update(overrides)
    return payload


def multi_service_payload(**overrides):
    payload = project_payload(
        name="Portfolio",
        repo_url="https://github.com/example/portfolio.git",
        deploy_mode="multi_service_dockerfile",
        build_context_path=".",
        dockerfile_path="Dockerfile",
        container_port=None,
        health_check_path=None,
        services=[
            {
                "name": "frontend",
                "build_context_path": "frontend",
                "dockerfile_path": "frontend/Dockerfile",
                "container_port": 3000,
                "public": True,
                "health_check_path": "/",
                "startup_order": 20,
                "build_env": {"VITE_API_BASE_URL": "/api"},
                "runtime_env": {},
                "required_secrets": [],
            },
            {
                "name": "backend",
                "build_context_path": "backend",
                "dockerfile_path": "backend/Dockerfile",
                "container_port": 8000,
                "public": False,
                "health_check_path": "/health",
                "startup_order": 10,
                "build_env": {},
                "runtime_env": {"PORT": "8000"},
                "required_secrets": ["DATABASE_URL", "JWT_SECRET"],
            },
        ],
    )
    payload.update(overrides)
    return payload


def test_create_and_list_project(client):
    create_response = client.post("/api/projects", json=project_payload())
    assert create_response.status_code == 201, create_response.text

    created = create_response.json()
    assert created["slug"] == "preview-api"
    assert created["preview_port"] == 18000
    assert created["preview_url"] == "http://preview.local:18000"
    assert created["has_real_preview"] is False

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]


def test_create_second_project_auto_allocates_next_preview_port(client):
    first_response = client.post("/api/projects", json=project_payload(name="Preview API"))
    assert first_response.status_code == 201, first_response.text

    second_response = client.post(
        "/api/projects",
        json=project_payload(name="Portfolio", repo_url="https://github.com/example/portfolio.git"),
    )

    assert second_response.status_code == 201, second_response.text
    assert first_response.json()["preview_port"] == 18000
    assert second_response.json()["preview_port"] == 18001


def test_create_gitlab_project(client):
    response = client.post(
        "/api/projects",
        json=project_payload(
            name="GitLab Preview",
            provider="gitlab",
            repo_url="https://gitlab.com/example/preview-api.git",
        ),
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["provider"] == "gitlab"
    assert created["repo_url"] == "https://gitlab.com/example/preview-api.git"


def test_rejects_embedded_repo_credentials(client):
    response = client.post(
        "/api/projects",
        json=project_payload(repo_url="https://token:secret@github.com/example/private-repo.git"),
    )
    assert response.status_code == 422
    assert "Embedded repository credentials" in response.json()["detail"]


def test_rejects_path_traversal(client):
    response = client.post(
        "/api/projects",
        json=project_payload(build_context_path="../outside"),
    )
    assert response.status_code == 422
    assert "path traversal" in response.json()["detail"]


def test_compose_mode_is_explicitly_unsupported(client):
    response = client.post(
        "/api/projects",
        json=project_payload(deploy_mode="compose", compose_file_path="docker-compose.yml"),
    )
    assert response.status_code == 422
    assert "unsupported" in response.json()["detail"].lower()


def test_create_multi_service_project(client):
    response = client.post("/api/projects", json=multi_service_payload())

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["deploy_mode"] == "multi_service_dockerfile"
    assert created["build_context_path"] == "frontend"
    assert created["dockerfile_path"] == "frontend/Dockerfile"
    assert created["container_port"] == 3000
    assert created["health_check_path"] == "/"
    assert [service["name"] for service in created["services"]] == ["backend", "frontend"]
    backend = next(service for service in created["services"] if service["name"] == "backend")
    assert backend["public"] is False
    assert backend["required_secrets"] == ["DATABASE_URL", "JWT_SECRET"]
    assert "DATABASE_URL" in response.text
    assert "postgres://" not in response.text


def test_rejects_duplicate_multi_service_names(client):
    payload = multi_service_payload()
    payload["services"][0]["name"] = "backend"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Duplicate service name" in response.json()["detail"]


def test_rejects_invalid_multi_service_name(client):
    payload = multi_service_payload()
    payload["services"][0]["name"] = "Front End"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Service name" in response.json()["detail"]


def test_rejects_zero_public_multi_services(client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["public"] = False

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "exactly one public service" in response.json()["detail"]


def test_rejects_multiple_public_multi_services(client):
    payload = multi_service_payload()
    for service in payload["services"]:
        service["public"] = True

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "exactly one public service" in response.json()["detail"]


def test_rejects_invalid_multi_service_path(client):
    payload = multi_service_payload()
    payload["services"][0]["dockerfile_path"] = "../Dockerfile"

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "path traversal" in response.json()["detail"]


def test_rejects_invalid_env_name_and_secret_looking_env_value(client):
    invalid_name = multi_service_payload()
    invalid_name["services"][0]["build_env"] = {"1BAD": "value"}
    invalid_name_response = client.post("/api/projects", json=invalid_name)
    assert invalid_name_response.status_code == 422
    assert "invalid environment variable name" in invalid_name_response.json()["detail"]

    secret_value = multi_service_payload()
    secret_value["services"][0]["runtime_env"] = {"PUBLIC_VALUE": "super-secret-token"}
    secret_value_response = client.post("/api/projects", json=secret_value)
    assert secret_value_response.status_code == 422
    assert "secret value" in secret_value_response.json()["detail"]


def test_rejects_invalid_required_secret_name(client):
    payload = multi_service_payload()
    payload["services"][1]["required_secrets"] = ["jwt-secret"]

    response = client.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert "Required secret names" in response.json()["detail"]
