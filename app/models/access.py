from pydantic import BaseModel, EmailStr
from typing import List, Optional


class AccessData(BaseModel):
    email: EmailStr
    access_token: str
    refresh_token: str
