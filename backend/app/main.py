from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routes import health, customers, audience, campaigns, runs, media_upload, schedule
from .scheduler import start_scheduler
from contextlib import asynccontextmanager

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    
app = FastAPI(lifespan=lifespan)

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
app.include_router(schedule.router, prefix="/api")




