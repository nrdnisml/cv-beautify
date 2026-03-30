from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field

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
    company: str
    project: str
    client: str
    date_start: str
    ongoing: bool
    date_end: Optional[str]
    role: str
    project_description: str
    responsibilities: str = Field(description="Tailored responsibilities highly matching project specs. Do NOT invent new facts.")
    sectors: List[str]
    DELETE: bool = False
    id: IDType = None  # Replaced Any with IDType
    cv: IDType = None  # Replaced Any with IDType

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

# This is the schema Azure OpenAI will be forced to return for each chunk
class CVChunkResponse(BaseModel):
    description: str = Field(description="Tailored professional summary focusing on the target role.")
    projects: List[Project]

# The full CV schema for API validation
class FullCV(BaseModel):
    name: str
    skills: List[str]
    description: str
    employee_id: str
    educations: List[Education]
    certifications: List[Certification]
    trainings: List[Training]
    projects: List[Project]
    languages: List[Language]
    memberships: List[Membership]