from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.lectures import router as lecture_router

app = FastAPI(title="GenAI-ED Backend")

app.add_middleware(
    CORSMiddleware,
    # Allow ANY HTTPS origin (covers all vercel previews + bolt + webcontainer etc.)
    allow_origins=[],
    allow_origin_regex=r"^https:\/\/.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lecture_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "message": "GenAI-ED Backend running"}

@app.get("/health")
def health():
    return {"status": "healthy"}



# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from routes.lectures import router as lecture_router

# app = FastAPI(title="GenAI-ED Backend")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:3000",
#         "http://127.0.0.1:3000",
#         "https://frontend-genai-ed.vercel.app",
#     ],
#     # Bolt/WebContainer changing preview URLs (dynamic)
#     allow_origin_regex=r"^https?:\/\/.*\.webcontainer-api\.io$",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(lecture_router, prefix="/api")

# @app.get("/")
# def root():
#     return {"status": "ok", "message": "GenAI-ED Backend running"}

# @app.get("/health")
# def health():
#     return {"status": "healthy"}
