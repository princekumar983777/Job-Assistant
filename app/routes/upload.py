import fitz  # PyMuPDF
import os
from typing import List
from pydantic import EmailStr
from app.models.resume import Resume

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def parse_pdf(path: str) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

@app.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    email: str = Depends(get_current_user)
):
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/{file_id}.pdf"

    # Save file locally
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Parse PDF
    resume_text = parse_pdf(file_path)

    resume = Resume(
        email=email,
        tags=[],
        resume_text=resume_text,
        file_id=file_id
    )

    result = resumes_collection.insert_one(resume.dict())

    users_collection.update_one(
        {"email": email},
        {"$push": {"resume": str(result.inserted_id)}}
    )

    return {"msg": "Resume uploaded successfully"}
