from fastapi import FastAPI

from yyt1771_af import __version__
from yyt1771_af.api.camera import router as camera_router
from yyt1771_af.api.health import router as health_router
from yyt1771_af.api.offline_playback import router as offline_playback_router
from yyt1771_af.api.offline_run import router as offline_run_router
from yyt1771_af.api.runs import router as runs_router
from yyt1771_af.api.setup import router as setup_router
from yyt1771_af.api.temperature import router as temperature_router


def create_app() -> FastAPI:
    app = FastAPI(title="YYT1771 AF Web Station", version=__version__)
    app.include_router(camera_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(offline_playback_router, prefix="/api")
    app.include_router(offline_run_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(setup_router, prefix="/api")
    app.include_router(temperature_router, prefix="/api")
    return app


app = create_app()
