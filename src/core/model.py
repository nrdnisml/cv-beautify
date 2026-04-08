from typing import List, Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field

IDType = Union[str, int, None]
class Education(BaseModel):
    institution: str
    major: str
    degree: str
    year_end: Optional[str]
    gpa: Optional[str]
    category: str
    file_link: Optional[str]
    diploma_scan: Optional[str]
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType

class Certification(BaseModel):
    certificate: str
    issuer: str
    year_issued: Optional[str]
    year_expired: Optional[str]
    file: Optional[str]
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType

class Training(BaseModel):
    training: str
    year_issued: Optional[str]
    issuer: str
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType

class Project(BaseModel):
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType
    company: str
    project: str
    client: str
    date_start: str
    ongoing: bool
    date_end: Optional[str]
    role: str
    project_description: str = Field(description="Brief overview of the PROJECT itself (e.g., scale, objective, technology used). ""Focus on the project as an object, NOT the candidate's personal tasks.")
    responsibilities: str = Field(description="Tailored responsibilities and personal contributions of the CANDIDATE. Do NOT invent new facts.")
    sectors: List[str]
    DELETE: bool = False

class Language(BaseModel):
    language: str
    proficiency: str
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType

class Membership(BaseModel):
    membership: str
    year_issued: Optional[int]
    issuer: str
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType
    
class Description(BaseModel):
    description: str

# This is the schema Azure OpenAI will be forced to return for each chunk
class CVChunkResponse(BaseModel):
    description: str = Field(description="Tailored professional summary focusing on the target role.")
    projects: List[Project]

# The full CV schema for API validation
class FullCV(BaseModel):
    employee_id: str
    name: str
    description: str
    projects: List[Project]
    # skills: List[str]
    # educations: List[Education]
    # certifications: List[Certification]
    # trainings: List[Training]
    # languages: List[Language]
    # memberships: List[Membership]
    