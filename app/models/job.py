from typing import List, Optional, Union
from pydantic import BaseModel

class Eligibility(BaseModel):
    education_levels: List[str]
    preferred_backgrounds: List[str]

class JobDetails(BaseModel):
    duration: Optional[str] = None
    salary_range: Optional[str] = None
    work_mode: Optional[str] = None  # Onsite / Remote / Hybrid

class RequiredSkills(BaseModel):
    programming_languages: List[str]
    web_technologies: List[str]
    tools: List[str]
    soft_skills: List[str]

class Experience(BaseModel):
    years: Union[str, int]  # can be "0-1" or integer
    type: Optional[str] = None

class ExpectedOutcomes(BaseModel):
    resume_match_percentage: float
    missing_skills: List[str]
    suggested_resume_changes: List[str]

class JobModel(BaseModel):
    job_title: str
    company: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    eligibility: Eligibility
    details: JobDetails
    key_responsibilities: List[str]
    required_skills: RequiredSkills
    preferred_skills: List[str] = []
    experience: Experience
    certifications: List[str] = []
    expected_outcomes: Optional[ExpectedOutcomes] = None