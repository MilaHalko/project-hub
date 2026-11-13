from fastapi import APIRouter

from project_hub.auth.dependencies import CurrentUser
from project_hub.users.schemas import UserResponse

router = APIRouter(tags=["users"])


@router.get("/users/me")
async def read_me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(user)
