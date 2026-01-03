from fastapi import (
    FastAPI, Depends, HTTPException, status,
    UploadFile, File, Response, Cookie, Request
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from pymongo import MongoClient
import hashlib
import bcrypt
import base64
import uuid
import os
import fitz  # PyMuPDF

# =======================
# CONFIG
# =======================
SECRET_KEY = "abc123xyz456"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# =======================
# APP
# =======================
app = FastAPI()

# =======================
# DATABASE
# =======================
client = MongoClient("mongodb://localhost:27017/")
db = client["Lamina"]
users_collection = db["users"]
access_collection = db["access"]
resumes_collection = db["resumes"]

# =======================
# PASSWORD HASHING
# =======================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    # Encode the password to bytes, then hash with SHA-256, then base64 encode
    password_bytes = password.encode('utf-8')
    sha256_hash = hashlib.sha256(password_bytes).digest()
    prehashed = base64.b64encode(sha256_hash)
    # Hash with bcrypt and return as string
    return bcrypt.hashpw(prehashed, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed: str) -> bool:
    # Encode the password to bytes, then hash with SHA-256, then base64 encode
    password_bytes = plain_password.encode('utf-8')
    sha256_hash = hashlib.sha256(password_bytes).digest()
    prehashed = base64.b64encode(sha256_hash)
    # Verify using bcrypt
    try:
        return bcrypt.checkpw(prehashed, hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False
# =======================
# MODELS
# =======================
from app.models.user import User , UserLogin
# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str
    
# class UserCreate(UserLogin):
#     username: str
#     full_name: str

# class UserInDB(BaseModel):
#     username: str
#     full_name: str
#     email: EmailStr
#     hashed_password: str
#     resume: List[str] = Field(default_factory=list)
from app.models.resume import Resume
# class Resume(BaseModel):
#     email: EmailStr
#     tags: List[str] = []
#     resume_text: Optional[str]
#     file_id: Optional[str]
from app.models.access import AccessData
# class AccessData(BaseModel):
#     email: EmailStr
#     access_token: str
#     refresh_token: str

from app.models.job import JobModel
# =======================
# JWT UTILS
# =======================
def create_access_token(email: str, expires_delta: timedelta):
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + expires_delta
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(email: str):
    payload = {
        "sub": email,
        "token_type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# =======================
# AUTH DEPENDENCY (COOKIE)
# =======================
def get_current_user(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# =======================
# PDF PARSER
# =======================
def parse_pdf(path: str) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# =======================
# ROUTES
# =======================
@app.get("/")
async def home(
        request: Request, 
        access_token: str | None = Cookie(None), 
        refresh_token: str | None = Cookie(None)
    ):
    response = {
        "message": "Welcome to JobFit AI",
        "is_authenticated": False,
        "user": None
    }

    # Check access token first
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                user = users_collection.find_one({"email": email}, {"hashed_password": 0})
                if user:
                    response.update({
                        "is_authenticated": True,
                        "user": {
                            "email": user.get("email"),
                            "username": user.get("username"),
                            "full_name": user.get("full_name")
                        }
                    })
                    return response
        except JWTError:
            pass  # Token is invalid or expired

    # If access token is invalid/expired, try refresh token
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                # Check if refresh token exists in the database
                stored_token = access_collection.find_one({
                    "email": email,
                    "refresh_token": refresh_token
                })
                
                if stored_token:
                    # Create new access token
                    new_access = create_access_token(
                        email,
                        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                    )
                    # Update the accesstoken in access_collection
                    access_collection.update_one(
                        {"email": email, "refresh_token": refresh_token},
                        {"$set": {"access_token": new_access}}
                    )
                    # Update response with new access token
                    response["access_token"] = new_access
                    response["is_authenticated"] = True
                    
                    # Get user data
                    user = users_collection.find_one({"email": email}, {"hashed_password": 0})
                    if user:
                        response["user"] = {
                            "email": user.get("email"),
                            "username": user.get("username"),
                            "full_name": user.get("full_name")
                        }
                    
                    # Set the new access token in a cookie
                    response_obj = JSONResponse(content=response)
                    response_obj.set_cookie(
                        key="access_token",
                        value=new_access,
                        httponly=True,
                        samesite="lax"
                    )
                    return response_obj
                    
        except JWTError:
            pass  # Refresh token is invalid or expired

    return response
# ---------- SIGNUP ----------
@app.post("/signup")
def signup(user: User, response: Response):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    user_doc = {
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "hashed_password": hash_password(user.password),
        "resume": []
    }
    users_collection.insert_one(user_doc)

    access = create_access_token(
        user.email,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh = create_refresh_token(user.email)

    access_collection.insert_one({
        "email": user.email,
        "access_token": access,
        "refresh_token": refresh
    })

    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")

    return {"msg": "Signup successful"}

# ---------- LOGIN ----------
@app.post("/login")
def login(
    response: Response,
    user_data: UserLogin,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None)
):
    # Already logged in
    if access_token:
        try:
            jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            return {"msg": "Already logged in"}
        except JWTError:
            pass

    # Refresh token
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload["sub"]

            new_access = create_access_token(
                email,
                timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            )

            response.set_cookie("access_token", new_access, httponly=True, samesite="lax")
            return {"msg": "Token refreshed"}
        except JWTError:
            pass

    # Normal login
    user = users_collection.find_one({"email": user_data.email})
    print("User data from Mongo Db : " , user)
    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # print(f"Loging password match : {user["email"]}____________________________________________________________")
    access = create_access_token(
        user["email"],
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh = create_refresh_token(user["email"])

    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")

    return {"msg": "Login successful"}

# ---------- LOGOUT ----------
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"msg": "Logged out"}

# ---------- UPLOAD RESUME ----------
@app.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    email: str = Depends(get_current_user)
):
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/{file_id}.pdf"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    resume_text = parse_pdf(file_path)
    # use llm to change the parase text , 
    resume = Resume(
        email=email,
        resume_text=resume_text,
        file_id=file_id
    )

    result = resumes_collection.insert_one(resume.dict())

    users_collection.update_one(
        {"email": email},
        {"$push": {"resume": str(result.inserted_id)}}
    )

    return {"msg": "Resume uploaded successfully"}

@app.post("/jobscan")
async def jobscan(
    response : Response,
    jobpost : JobModel,
    access_token: str | None = Cookie(None)
):
    if access_token :
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload["sub"]

            if email:
                user = users_collection.find_one({"email": email}, {"hashed_password": 0})
            resume_list = user["resume"]

            for resume in resume_list :
                pass
            #  make a string of all resume and send it to gemini , aspecting the finidng the which one is best suited and and how much is it score 
            # in return we expact the few things 
    pass