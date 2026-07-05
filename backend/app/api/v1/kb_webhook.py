"""KB service webhook routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.v1.dependencies import KBDocumentWebhookServiceDep
from app.schemas.kb_documents import KBWebhookPayload, KBWebhookResponse

router = APIRouter(prefix="/kb", tags=["KB Webhooks"])


@router.post("/webhook", response_model=KBWebhookResponse)
async def kb_webhook(
    payload: KBWebhookPayload,
    request: Request,
    service: KBDocumentWebhookServiceDep,
    signature: Annotated[str | None, Header(alias="X-KB-Signature")] = None,
) -> KBWebhookResponse:
    """Process a signed KB service status webhook."""
    return await service.process(
        payload=payload,
        raw_body=await request.body(),
        signature=signature,
    )
