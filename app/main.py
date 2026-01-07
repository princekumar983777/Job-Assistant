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
# Gemini Setup
# =======================
import google.generativeai as genai
genai.configure(api_key="YOUR_GEMINI_API_KEY")
model = genai.GenerativeModel("gemini-1.5-flash")

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
# # =======================
# def parse_pdf(path: str) -> str:
#     doc = fitz.open(path)
#     text = ""
#     for page in doc:
#         text += page.get_text()
#     return text

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

def parse_file(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx") or file_path.endswith(".doc"):
        return extract_text_from_doc(file_path)
    else:
        raise ValueError("Unsupported file format")

    """
    Send raw resume text to Gemini and get structured JSON back.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
    Convert the following resume text into a structured JSON format with fields:
    full_name, email, phone, location, linkedin, github, portfolio, summary,
    skills (programming_languages, frameworks, databases, tools),
    education (degree, institution, start_date, end_date, cgpa),
    experience (title, company, start_date, end_date, responsibilities),
    projects (name, description, technologies, link),
    certifications (name, issuer, date).

    Resume text:
    {raw_text}
    """

    response = model.generate_content(prompt)
    return response.text  # Gemini returns JSON string → parse if needed


@app.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user)  # email comes from validated token
):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[-1].lower()
    file_path = f"{UPLOAD_DIR}/{file_id}{ext}"

    # Save file locally
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Extract raw text (PDF/DOC parser)
    raw_text = parse_file(file_path)

    # Format with Gemini (structured JSON)
    structured_resume = format_resume_with_gemini(raw_text)

    # Create Resume object
    resume = Resume(
        email=user["email"],
        resume_text=structured_resume,
        file_id=file_id
    )

    # Insert into MongoDB
    result = resumes_collection.insert_one(resume.dict())

    users_collection.update_one(
        {"email": email},
        {"$push": {"resume": str(result.inserted_id)}}
    )

    return {"msg": "Resume uploaded successfully", "resume_id": str(result.inserted_id)}

# -----------------Job Scan -----------------------------
@app.post("/jobscan")
async def jobscan(
    response: Response,
    jobpost: JobModel,
    access_token: str | None = Cookie(None)
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Fetch user
    user = users_collection.find_one({"email": email}, {"hashed_password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch all resumes for this user
    resume_list = list(resumes_collection.find({"email": email}, {"_id": 0}))
    if not resume_list:
        raise HTTPException(status_code=404, detail="No resumes found")

    # Compile resumes into text format for AI
    compiled_resumes = []
    for idx, resume in enumerate(resume_list, start=1):
        compiled_resumes.append({
            "resume_id": resume.get("resume_id", f"resume_{idx}"),
            "tags": resume.get("tags", []),
            "resume_text": resume.get("resume_text", "")
        })

    # Prompt Gemini to score all resumes
    prompt = f"""
    You are an AI resume evaluator.
    Compare the following resumes against this job posting:

    Job Posting:
    {jobpost.json(indent=2)}

    Resumes:
    {compiled_resumes}

    Task:
    - For each resume, calculate a match percentage (0-100).
    - Return a JSON list with resume_id and match_percentage for all resumes.
    - Identify which resume has the highest score.
    - For ONLY that highest-scoring resume:
        * List missing skills or gaps.
        * Suggest improvements.
        * Provide an improved version of the resume in LaTeX format.

    Output strictly in JSON:
    {{
      "scores": [
        {{"resume_id": "...", "match_percentage": 75.0}},
        {{"resume_id": "...", "match_percentage": 82.0}}
      ],
      "best_resume": {{
        "resume_id": "...",
        "match_percentage": 82.0,
        "missing_skills": ["Docker", "React.js"],
        "suggestions": ["Add project experience with APIs"],
        "improved_resume_latex": "LaTeX formatted resume..."
      }}
    }}
    """

    ai_response = model.generate_content(prompt)
    result_text = ai_response.text

    return {"email": email, "jobscan_results": result_text}