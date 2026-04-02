import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.schemas import EnhanceCVRequest
from src.api.security import auth_guard
from src.api.limiter import limiter
from src.core.orchestrator import process_cv_enhancement_stream
from src.utils.prompt_loader import PromptLoader

router = APIRouter()
logger = logging.getLogger("CVEnhancementController")


@router.post(
    "/api/v1/enhance-cv/stream",
    dependencies=[Depends(auth_guard.verify)]
)
@limiter.limit("5/minute")
async def enhance_cv_stream(request: Request, payload: EnhanceCVRequest):
    logger.info("Received CV streaming request to enhance for role: %s", payload.role_assignment)

    loader = PromptLoader()
    project_specs = loader.sectorSelector(payload.project_sector)
    combined_role_context = (
        f"Target Role: {payload.role_assignment}\n"
        f"Specific User Intent/Instructions: {payload.user_intent}"
    )

    async def event_generator():
        try:
            # Consume the orchestrator stream
            async for update in process_cv_enhancement_stream(
                raw_cv=payload.input_cv,
                project_specs=project_specs,
                role_assignment=combined_role_context,
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

    sectors_map = {
        "green": "Green Energy",
        "minerals": "Minerals",
        "oil_and_gas": "Oil and Gas",
        "petrochemical": "Petrochemical",
        "power": "Power",
        "telecommunication": "Telecommunication"
    }

    return {
        "code": 200,
        "status": "success",
        "data": sectors_map
    }


@router.get("/health")
@limiter.limit("5/second")
async def health_check(request: Request):
    return {
        "code": 200,
        "status": "healthy",
        "message": "CV Enhancement API is up and running"
    }