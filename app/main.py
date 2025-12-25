import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from . import models, database
from .version import __version__ as app_version

from .routers import auth, pages, tracks, users, races, admin, strava_auth, webhooks, event_manager, strategy, club

if os.path.exists("local.env"):
    load_dotenv("local.env")
load_dotenv()

# Exception Handlers
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from .dependencies import templates

async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

async def generic_exception_handler(request: Request, exc: Exception):
    print(f"INTERNAL ERROR: {exc}") # Log for debugging
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "detail": "Internal Server Error"
    }, status_code=500)

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Kairn", version=app_version)

# Register Handlers
app.add_exception_handler(HTTPException, custom_http_exception_handler)
app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler)
app.add_exception_handler(500, generic_exception_handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/.well-known", StaticFiles(directory="app/static/.well-known"), name="well-known")
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
app.include_router(strategy.router)
app.include_router(club.router)

# Note: Templates are configured in dependencies.py and used in routers
