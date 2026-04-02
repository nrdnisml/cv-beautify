import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.schemas import EnhanceCVRequest
from src.api.security import auth_guard
from src.api.limiter import limiter
from src.core.orchestrator import process_cv_enhancement
from src.utils.prompt_loader import PromptLoader

router = APIRouter()
logger = logging.getLogger("CVEnhancementController")


@router.post(
    "/api/v1/enhance-cv",
    dependencies=[Depends(auth_guard.verify)]
)
@limiter.limit("5/minute")
async def enhance_cv(request: Request, payload: EnhanceCVRequest):
    logger.info("Received CV request to enhance for role: %s", payload.role_assignment)

    loader = PromptLoader()
    project_specs = loader.sectorSelector(payload.project_sector)
    combined_role_context = (
        f"Target Role: {payload.role_assignment}\n"
        f"Specific User Intent/Instructions: {payload.user_intent}"
    )
    # role_prompt = await get_role_prompt(
    #     role_title=payload.role_assignment,
    #     sector=payload.project_sector,
    #     user_intent=payload.user_intent
    # )

    try:
        enhanced_cv = await process_cv_enhancement(
            raw_cv=payload.input_cv,
            project_specs=project_specs,
            role_assignment=combined_role_context,
            # role_assignment=role_prompt,
            chunk_size=3
        )
        return {
            "code": 200,
            "status": "success",
            "message": "CV enhancement completed successfully",
            "data": enhanced_cv
        }
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(ve)}")
    except RuntimeError as re:
        logger.error(f"Processing error: {str(re)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(re)}")
    except Exception as e:
        logger.error(f"Internal Server error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during CV enhancement."
        )


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