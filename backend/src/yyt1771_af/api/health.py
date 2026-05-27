from fastapi import APIRouter

from yyt1771_af import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, bool | str]:
    return {
        "ok": True,
        "app": "yyt1771-af-web-station",
        "version": __version__,
    }
