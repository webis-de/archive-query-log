"""Hello World Router

Example router to demonstrate FastAPI routing structure.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/hello")
async def hello_world():
    """Simple Hello World endpoint"""
    return {"message": "Hello, World!"}


@router.get("/hello/{name}")
async def hello_name(name: str):
    """Personalized greeting endpoint

    Args:
        name: Name to greet

    Returns:
        Personalized greeting message
    """
    return {"message": f"Hello, {name}!"}
