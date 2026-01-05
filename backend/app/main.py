from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routes import health, customers, audience, campaigns, runs, media_upload

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CPA_Panel Backend")

# Frontend dev server will run on localhost:5173 (Vite default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"name": "CPA_Panel Backend", "ok": True}

app.include_router(health.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(audience.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(media_upload.router, prefix="/api")