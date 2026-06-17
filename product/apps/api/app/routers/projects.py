from fastapi import APIRouter, HTTPException, Request, Response, status
from starlette.datastructures import UploadFile

from ..schemas import (
    ProjectCreate,
    ProjectDatabasePurgeRequest,
    ProjectDatabaseRead,
    ProjectRead,
    ProjectServiceEnvBundleRead,
    ProjectServiceEnvBundleWrite,
    ProjectUpdate,
)
from ..services import env_bundles, projects
from ..validation import bad_request

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _read_env_bundle_content(request: Request) -> str:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploaded = form.get("file")
        if not isinstance(uploaded, UploadFile):
            raise bad_request("Env bundle upload requires a file field.")
        raw_content = await uploaded.read()
        try:
            return raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise bad_request("Env bundle file must be UTF-8 text.") from exc

    if content_type.startswith("text/plain"):
        raw_content = await request.body()
        try:
            return raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise bad_request("Env bundle file must be UTF-8 text.") from exc

    try:
        payload = ProjectServiceEnvBundleWrite.model_validate(await request.json())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid env bundle request.") from exc
    return payload.content


@router.get("", response_model=list[ProjectRead])
def list_projects() -> list[ProjectRead]:
    return projects.list_projects()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> ProjectRead:
    return projects.create_project(payload)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str) -> ProjectRead:
    return projects.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdate) -> ProjectRead:
    return projects.update_project(project_id, payload)


@router.post("/{project_id}/database/retry", response_model=ProjectRead)
def retry_project_database(project_id: str) -> ProjectRead:
    return projects.retry_project_database(project_id)


@router.post("/{project_id}/database/purge", response_model=ProjectDatabaseRead)
def purge_project_database(project_id: str, payload: ProjectDatabasePurgeRequest) -> ProjectDatabaseRead:
    return projects.purge_project_database(project_id, payload)


@router.post(
    "/{project_id}/services/{service_id}/env-bundle",
    response_model=ProjectServiceEnvBundleRead,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_service_env_bundle(
    project_id: str,
    service_id: str,
    request: Request,
) -> ProjectServiceEnvBundleRead:
    content = await _read_env_bundle_content(request)
    return ProjectServiceEnvBundleRead(
        **env_bundles.upsert_service_env_bundle(project_id, service_id, content)
    )


@router.get("/{project_id}/services/{service_id}/env-bundle", response_model=ProjectServiceEnvBundleRead)
def get_service_env_bundle(project_id: str, service_id: str) -> ProjectServiceEnvBundleRead:
    return ProjectServiceEnvBundleRead(**env_bundles.get_service_env_bundle(project_id, service_id))


@router.delete("/{project_id}/services/{service_id}/env-bundle", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_env_bundle(project_id: str, service_id: str) -> Response:
    env_bundles.delete_service_env_bundle(project_id, service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> Response:
    projects.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
