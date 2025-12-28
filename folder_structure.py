import os

folders = [
    "app",
    "app/models",
    "app/routes",
    "app/services",
    "app/utils"
]

files = [
    "app/main.py",
    "app/config.py",
    "app/database.py",

    "app/models/user.py",
    "app/models/resume.py",
    "app/models/job.py",
    "app/models/analysis.py",

    "app/routes/auth.py",
    "app/routes/resume.py",
    "app/routes/job.py",
    "app/routes/analysis.py",

    "app/services/resume_parser.py",
    "app/services/job_scraper.py",
    "app/services/embeddings.py",
    "app/services/llm.py",

    "app/utils/scoring.py",
    "app/utils/text_cleaner.py",

    "requirements.txt",
    "run.py"
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

for file in files:
    with open(file, "w") as f:
        pass

print("✅ JobFit AI folder structure created successfully!")

