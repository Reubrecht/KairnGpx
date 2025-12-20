import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from . import models, database
from .version import __version__ as app_version
from .routers import auth, pages, tracks, users, races, admin, strava_auth, webhooks, event_manager

if os.path.exists("local.env"):
    load_dotenv("local.env")
load_dotenv()

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Kairn", version=app_version)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="app/media"), name="media")

# Include Routers
app.include_router(auth.router)
app.include_router(strava_auth.router)
app.include_router(pages.router)
app.include_router(tracks.router)
app.include_router(users.router)
app.include_router(races.router)
app.include_router(admin.router)
app.include_router(event_manager.router)
app.include_router(webhooks.router)

# Note: Templates are configured in dependencies.py and used in routers
