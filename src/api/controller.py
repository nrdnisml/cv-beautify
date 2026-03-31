import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.schemas import EnhanceCVRequest
from src.api.security import auth_guard
from src.api.limiter import limiter
from src.core.orchestrator import process_cv_enhancement
from src.utils.prompt_loader import PromptLoader

class CVEnhancementController:
    def __init__(self):
        self.router = APIRouter()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._register_routes()
        
    def _register_routes(self):
        self.router.add_api_route(
            path="api/v1/enhance-cv",
            endpoint=self.enhance_cv,
            methods=["POST"],
            dependencies=[Depends(auth_guard.verify)]
        )
        self.router.add_api_route(
            path="/api/v1/sectors",
            endpoint=self.get_sectors,
            methods=["GET"],
            tags=["Metadata"],
            summary="Get list of available sectors"
        )
        self.router.add_api_route(
            path="/health",
            endpoint=self.health_check,
            methods=["GET"]
        )
        
    @limiter.limit("5/minute")
    async def enhance_cv(self, request: Request, payload: EnhanceCVRequest):
        self.logger.info("Received CV request to enhance for role: %s", payload.role_assignment)
        combined_role_context = (
            f"Target Role: {payload.role_assignment}\n"
            f"Specific User Intent/Instructions: {payload.user_intent}"
        )
        loader = PromptLoader()
        project_specs = loader.sectorSelector(payload.project_sector)

        try:
            enhanced_cv = await process_cv_enhancement(
                raw_cv=payload.input_cv,
                project_specs=project_specs,
                role_assignment=combined_role_context,
                chunk_size=3
            )
            return {
                "code": 200,
                "status": "success",
                "message": "CV enhancement completed successfully",
                "data": enhanced_cv
            }
        except ValueError as ve:
            self.logger.error(f"Validation error: {str(ve)}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(ve)}")
        except RuntimeError as re:
            self.logger.error(f"Processing error: {str(re)}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(re)}")
        except Exception as e:
            self.logger.error(f"Internal Server error: {str(e)}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred during CV enhancement.")
    
    @limiter.exempt
    async def get_sectors(self, request: Request):
        """
        Endpoint to retrieve the supported industry sectors for CV enhancement.
        """
        self.logger.info("Fetching available industry sectors.")
        
        # These match the text files in src/prompts/domains/ directory
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
        
    @limiter.exempt
    async def health_check(self, request: Request):
        return {
            "code": 200,
            "status": "healthy",
            "message": "CV Enhancement API is up and running"
        }

cv_controller = CVEnhancementController()
router = cv_controller.router