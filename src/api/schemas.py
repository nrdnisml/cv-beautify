from typing import Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class EnhanceCVRequest(BaseModel):
    input_cv: Dict[str, Any] = Field(..., description="The raw CV data to be enhanced")
    project_sector: str = Field(..., description="The industry sector of the projects (e.g., 'oil & gas', 'manufacturing', 'green energy')")
    role_assignment: str = Field(..., description="Details about the role for which the CV is being tailored")
    user_intent: str = Field(..., description="Additional context or specific instructions from the user")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input_cv": {
                    "name": "TAVIP SUNANDI",
                    "description": "Senior Project Manager...",
                    "employee_id": "23444",
                    "projects": [
                        {
                            "id": "ProjectExperience object (3477)",
                            "cv": "CurriculumVitae object (25215)",
                            "company": "PT. TRIPATRA",
                            "project": "Medco DFO Project",
                            "client": "PT. Medco...",
                            "date_start": "2023-07-01",
                            "date_end": "2023-08-01",
                            "ongoing": True,
                            "role": "Project Manager",
                            "project_description": "EPCC of facility optimizations...",
                            "responsibilities": "Develop Project Management Plan...",
                            "sectors": ["Oil and Gas"],
                            "DELETE": False
                        }
                    ]
                },
                "project_sector": "oil_and_gas",
                "role_assignment": "civil engineer",
                "user_intent": "civil engineer with technical skills"
            }
        }
    )
    
# --- SSE Response Schemas ---

class SSEProcessingResponse(BaseModel):
    status: str = Field("processing", example="processing")
    progress: int = Field(..., ge=0, le=100, example=5)
    message: str = Field(..., example="Validating CV data and extracting history...")

class SSEFinalResponse(BaseModel):
    status: str = Field("completed", example="completed")
    tokens: int = Field(..., example=16375)
    progress: int = Field(100, example=100)
    message: str = Field("CV Enhancement Complete!", example="CV Enhancement Complete!")
    data: Dict[str, Any] = Field(..., description="The fully enhanced CV payload")

class SSEErrorResponse(BaseModel):
    status: str = Field("failed", example="failed")
    progress: int = Field(100, example=100)
    message: str = Field(..., example="Server encountered a critical error: [Error Details]")