"""认证与授权工具：JWT 令牌、密码哈希、FastAPI 依赖注入。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select

from backend.settings import get_settings
from database.models import User
from database.session import SessionLocal

logger = logging.getLogger(__name__)

security = HTTPBearer()


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    """生成 JWT 访问令牌。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解码并验证 JWT 令牌。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI 依赖：从 JWT 中提取当前用户信息。"""
    payload = decode_token(credentials.credentials)
    user_id = int(payload["sub"])
    role = payload.get("role", "user")

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
        return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}
    finally:
        db.close()


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI 依赖：要求当前用户为管理员。"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def ensure_default_admin() -> None:
    """确保默认管理员账号存在，首次启动时自动创建。"""
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.username == settings.admin_username)
        ).scalar_one_or_none()
        if not existing:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                display_name="管理员",
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("已创建默认管理员账号: %s", settings.admin_username)
    finally:
        db.close()
