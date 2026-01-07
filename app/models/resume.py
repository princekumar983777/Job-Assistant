from pydantic import BaseModel, EmailStr
from typing import List, Optional

class Resume(BaseModel):
    email: EmailStr
    tags: List[str] = []
    resume_text: str | None
    file_id: str | None

