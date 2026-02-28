from fastapi import APIRouter, HTTPException, status
from app.models import UserCreate, UserResponse
import uuid

router = APIRouter(prefix="/users", tags=["users"])

# In-memory store (sufficient for this task scope)
_users: dict[str, dict] = {}


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
def create_user(payload: UserCreate) -> UserResponse:
    for existing in _users.values():
        if existing["email"] == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )
    user_id = str(uuid.uuid4())
    user = {"id": user_id, "name": payload.name, "email": payload.email}
    _users[user_id] = user
    return UserResponse(**user)
