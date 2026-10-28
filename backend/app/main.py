from contextlib import asynccontextmanager
from pathlib import Path
import ssl
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .config import Settings, get_settings
from .database import get_db
from .models import TasteProfile, UserProfile
from .onboarding import router as onboarding_router
from .analysis import router as analysis_router
from .enrichment import router as enrichment_router
from .qloo import QlooClient
from .catalog import ProductCatalog
from .shopping import router as shopping_router, SearchLimiter
from .extension import router as extension_router
from .analytics import router as analytics_router
from .culture import router as culture_router
from .discovery import router as discovery_router
from .cultural_analytics import router as cultural_analytics_router
from .myntra_shopping import router as myntra_shopping_router
from .shopping_agent import router as shopping_agent_router
from .retailer_images import RetailerImages
from .outfits import router as outfits_router

Style = Literal["romantic", "classic", "casual", "chic"]


class TasteAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_styles: list[Style] = Field(min_length=1, max_length=4)

    @field_validator("selected_styles")
    @classmethod
    def unique_styles(cls, styles: list[Style]) -> list[Style]:
        if len(styles) != len(set(styles)):
            raise ValueError("Choose each style only once.")
        return styles


def create_app(settings: Settings | None = None, *, auth_transport=None, public_directory: Path | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tls = ssl.create_default_context()
        async with httpx.AsyncClient(timeout=10, transport=auth_transport, verify=tls) as client:
            with httpx.Client(timeout=60, transport=auth_transport, verify=tls) as storage_client:
                with httpx.Client(timeout=120, verify=tls) as analysis_client:
                    with httpx.Client(timeout=8, follow_redirects=False, verify=tls) as qloo_client:
                        with httpx.Client(timeout=10, follow_redirects=False, verify=tls, headers={'User-Agent': 'Muselly/0.1 (product search)'}) as catalog_client:
                            app.state.catalog = ProductCatalog(catalog_client)
                            app.state.retailer_images = RetailerImages(catalog_client)
                            app.state.search_limiter = SearchLimiter()
                            app.state.qloo = QlooClient(qloo_client)
                            app.state.analysis_client = analysis_client
                            app.state.storage_client = storage_client
                            app.state.auth_client = client
                            try:
                                yield
                            finally:
                                app.state.catalog.close()

    app = FastAPI(title="Muselly API", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=[settings.app_origin], allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Filename"])
    app.include_router(onboarding_router)
    app.include_router(analysis_router)
    app.include_router(enrichment_router)
    app.include_router(shopping_router)
    app.include_router(extension_router)
    app.include_router(analytics_router)
    app.include_router(culture_router)
    app.include_router(discovery_router)
    app.include_router(cultural_analytics_router)
    app.include_router(myntra_shopping_router)
    app.include_router(shopping_agent_router)
    app.include_router(outfits_router)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request, error):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"detail": "Unable to access your taste profile. Please try again."})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/auth/me", response_model=AuthUser)
    def me(user: AuthUser = Depends(get_current_user)):
        return user

    @app.get("/api/taste-test")
    def get_taste(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
        profile = db.get(TasteProfile, user.id)
        return {"selected_styles": profile.selected_styles if profile else []}

    @app.put("/api/taste-test")
    def save_taste(answers: TasteAnswers, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        profile = insert(UserProfile).values(id=user.id, email=user.email, display_name=user.display_name)
        db.execute(profile.on_conflict_do_update(index_elements=[UserProfile.id], set_={"email": user.email, "display_name": user.display_name, "updated_at": func.now()}))
        taste = insert(TasteProfile).values(user_id=user.id, selected_styles=answers.selected_styles)
        db.execute(taste.on_conflict_do_update(index_elements=[TasteProfile.user_id], set_={"selected_styles": answers.selected_styles, "updated_at": func.now()}))
        db.commit()
        return {"selected_styles": answers.selected_styles}

    public = public_directory or Path(__file__).resolve().parents[2] / "frontend" / "dist"

    def entry_page():
        if not (public / "index.html").is_file():
            raise HTTPException(503, "Frontend build not found. Run npm run build in frontend first.")
        return FileResponse(public / "index.html", headers={"Cache-Control": "no-cache"})

    # The React route guard verifies bearer tokens before showing the taste UI;
    # every taste/onboarding API independently verifies authentication server-side.
    for route in ("/", "/sign-in", "/taste-test", "/dashboard", "/explore", "/shop", "/auth/callback"):
        app.add_api_route(route, entry_page, methods=["GET"], include_in_schema=False)
    for name in ("assets", "images"):
        if (public / name).is_dir():
            app.mount(f"/{name}", StaticFiles(directory=public / name), name=name)
    if (public / "favicon.svg").is_file():
        app.add_api_route("/favicon.svg", lambda: FileResponse(public / "favicon.svg"), include_in_schema=False)
    return app


app = create_app()
