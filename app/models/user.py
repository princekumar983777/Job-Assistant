from pydantic import BaseModel, EmailStr , Field
from typing import List, Optional 

class User(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    hashed_password: str
    resume: List[str] = []

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
