from fastapi import APIRouter

router = APIRouter(prefix="/admin")


@router.get("/events")
def list_events() -> list[dict[str, str]]:
    return []


@router.get("/sources")
def list_sources() -> list[dict[str, str]]:
    return []
