"""用户认证路由：登录、注册、用户管理。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from database.models import User
from database.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- 请求/响应模型 ----------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    display_name: str = Field(default="", max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: int
    created_at: str


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


# ---------- 端点 ----------

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """用户登录，返回 JWT 令牌。"""
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

        token = create_access_token(user.id, user.role)
        logger.info("用户登录: %s (role=%s)", user.username, user.role)
        return TokenResponse(
            access_token=token,
            user={"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
        )
    finally:
        db.close()


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """用户自行注册。"""
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            display_name=req.display_name or req.username,
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id, user.role)
        logger.info("新用户注册: %s", user.username)
        return TokenResponse(
            access_token=token,
            user={"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
        )
    finally:
        db.close()


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return current_user


@router.get("/users", response_model=list[UserInfo])
def list_users(_admin: dict = Depends(require_admin)):
    """[管理员] 获取所有用户列表。"""
    db = SessionLocal()
    try:
        users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
        return [
            UserInfo(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in users
        ]
    finally:
        db.close()


@router.put("/users/{user_id}/role")
def update_role(user_id: int, req: RoleUpdateRequest, admin: dict = Depends(require_admin)):
    """[管理员] 修改用户角色。"""
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        if user.id == admin["id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的角色")
        user.role = req.role
        db.commit()
        logger.info("管理员 %s 修改用户 %s 角色为 %s", admin["username"], user.username, req.role)
        return {"message": "角色已更新"}
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """[管理员] 禁用用户（软删除）。"""
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        if user.id == admin["id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
        user.is_active = 0
        db.commit()
        logger.info("管理员 %s 禁用用户 %s", admin["username"], user.username)
        return {"message": "用户已禁用"}
    finally:
        db.close()
