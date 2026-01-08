from fastapi import FastAPI
from routes.lectures import router as lecture_router

app = FastAPI(title="GenAI-ED Backend")

app.include_router(lecture_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "message": "GenAI-ED Backend running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
