import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from . import models, database
from .version import __version__ as app_version
from .routers import auth, pages, tracks, users, races, admin

# Load local env (Local Dev)
if os.path.exists("local.env"):
    load_dotenv("local.env", override=True)

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Kairn Trail Platform", version=app_version)

# Mount static files
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount media files (User uploads)
os.makedirs("app/media", exist_ok=True)
app.mount("/media", StaticFiles(directory="app/media"), name="media")

# Include Routers
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(tracks.router)
app.include_router(users.router)
app.include_router(races.router)
app.include_router(admin.router)

# Note: Templates are configured in dependencies.py and used in routers
