from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "notice": "AI-generated draft for advocate review. Not legal advice.",
    }
