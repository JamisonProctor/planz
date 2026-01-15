from fastapi import APIRouter

router = APIRouter(prefix="/actions")


@router.post("/dismiss")
def dismiss_event() -> dict[str, str]:
    return {"status": "queued"}


@router.post("/disable-domain")
def disable_domain() -> dict[str, str]:
    return {"status": "queued"}
