from fastapi import APIRouter, Request

from ..schemas import WebhookResponse
from ..services import webhooks

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(request: Request) -> WebhookResponse:
    return await webhooks.handle_github_webhook(request)


@router.post("/gitlab", response_model=WebhookResponse)
async def gitlab_webhook(request: Request) -> WebhookResponse:
    return await webhooks.handle_gitlab_webhook(request)
