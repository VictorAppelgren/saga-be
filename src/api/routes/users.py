"""User & Authentication Routes"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List

from src.storage.user_manager import UserManager

router = APIRouter(prefix="/api", tags=["users"])
user_manager = UserManager()


# Models
class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str
    accessible_topics: List[str]


# Routes
@router.post("/login")
def login(request: LoginRequest):
    """Authenticate user"""
    user = user_manager.authenticate(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


@router.get("/users/{username}")
def get_user(username: str):
    """Get user info (without password)"""
    user = user_manager.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
