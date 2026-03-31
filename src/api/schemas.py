from typing import Dict, Any
from pydantic import BaseModel, Field

class EnhanceCVRequest(BaseModel):
    input_cv: Dict[str, Any] = Field(..., description="The raw CV data to be enhanced")
    project_sector: str = Field(..., description="The industry sector of the projects (e.g., 'oil & gas', 'manufacturing', 'green energy')")
    role_assignment: str = Field(..., description="Details about the role for which the CV is being tailored")
    user_intent: str = Field(..., description="Additional context or specific instructions from the user")