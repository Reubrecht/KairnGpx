import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from . import models, database
from .version import __version__ as app_version
from .routers import auth, pages, tracks, users, races, admin, strava_auth

# ... (lines omitted)

# Include Routers
app.include_router(auth.router)
app.include_router(strava_auth.router)
app.include_router(pages.router)
app.include_router(tracks.router)
app.include_router(users.router)
app.include_router(races.router)
app.include_router(admin.router)

# Note: Templates are configured in dependencies.py and used in routers
