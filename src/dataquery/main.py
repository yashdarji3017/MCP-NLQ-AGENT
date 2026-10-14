"""Application entrypoints and FastAPI factory for DataQuery AI."""

import os
import subprocess
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dataquery.api.routes import router
from dataquery.config import get_settings


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="DataQuery AI API Gateway",
        description="Enterprise NLQ to PostgreSQL Assistant powered by PydanticAI, Gemini, and MCP.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()


def start_api() -> None:
    """Run the FastAPI application via uvicorn."""
    import uvicorn

    settings = get_settings()
    print(f"Starting DataQuery AI API on http://{settings.API_HOST}:{settings.API_PORT}...")
    uvicorn.run("dataquery.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)


def start_ui() -> None:
    """Launch the Streamlit dashboard."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "app.py")
    print(f"Launching Streamlit UI from {app_path}...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path], check=True)


if __name__ == "__main__":
    start_api()
