import logging
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from src.api.schemas import (
    EnhanceCVRequest,
    SSEProcessingResponse,
    SSEFinalResponse,
    SSEErrorResponse
)
from src.utils.prompt_loader import PromptLoader
from src.api.security import auth_guard
from src.api.limiter import limiter
from src.core.orchestrator import process_cv_enhancement_stream

router = APIRouter()
logger = logging.getLogger("CVEnhancementController")


@router.post(
    "/api/v1/enhance-cv/stream",
    dependencies=[Depends(auth_guard.verify)],
    responses={
        200: {
            "description": "SSE Stream. Yields 'processing' updates, followed by either a 'completed' payload or a 'failed' error state.",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "oneOf": [
                            SSEProcessingResponse.model_json_schema(),
                            SSEFinalResponse.model_json_schema(),
                            SSEErrorResponse.model_json_schema()
                        ]
                    }
                }
            }
        }
    }
)
@limiter.limit("5/minute")
async def enhance_cv_stream(request: Request, payload: EnhanceCVRequest):
    logger.info("Received CV streaming request to enhance for role: %s", payload.role_assignment)

    async def event_generator():
        try:
            # Consume the orchestrator stream
            async for update in process_cv_enhancement_stream(
                raw_cv=payload.input_cv,
                project_sector=payload.project_sector,
                role_assignment=payload.role_assignment,
                user_intent=payload.user_intent,
                chunk_size=2
            ):
                # Format payload according to SSE standards: "data: <json>\n\n"
                yield f"data: {json.dumps(update)}\n\n"
                
        except Exception as e:
            logger.error(f"Unexpected streaming error: {str(e)}")
            error_payload = {
                "status": "failed", 
                "progress": 100, 
                "message": f"Server encountered a critical error: {str(e)}"
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get(
    "/api/v1/sectors",
    tags=["Metadata"],
    summary="Get list of available sectors"
)
@limiter.limit("10/second")
async def get_sectors(request: Request):
    logger.info("Fetching available industry sectors.")

    loader = PromptLoader()
    sectors = loader.get_available_sectors()

    return {
        "code": 200,
        "status": "success",
        "data": sectors
    }


@router.get("/health")
@limiter.limit("5/second")
async def health_check(request: Request):
    return {
        "code": 200,
        "status": "healthy",
        "message": "CV Enhancement API is up and running"
    }