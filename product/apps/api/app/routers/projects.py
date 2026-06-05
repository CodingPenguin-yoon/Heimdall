from fastapi import APIRouter, Response, status

from ..schemas import ProjectCreate, ProjectRead, ProjectUpdate
from ..services import projects

router = APIRouter(prefix="/api/projects", tags=["projects"])


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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> Response:
    projects.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
