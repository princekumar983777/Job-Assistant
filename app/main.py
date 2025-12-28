from fastapi import FastAPI

# from app.routes import auth, resume, job, analysis


app = FastAPI()

# app.include_router(auth.router)
# app.include_router(resume.router)
# app.include_router(job.router)
# app.include_router(analysis.router)


@app.get("/")
def root():
    return {"message": "Welcome to JobFit AI!"}