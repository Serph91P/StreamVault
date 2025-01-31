from sqlalchemy.orm import Session
from app.models import User, Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
import logging
from typing import Optional
from app.schemas.auth import UserCreate, UserResponse

logger = logging.getLogger("streamvault")

ph = PasswordHasher()

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    async def admin_exists(self) -> bool:
        return bool(self.db.query(User).filter_by(is_admin=True).first())

    async def create_admin(self, user_data: UserCreate) -> UserResponse:
        hashed_password = ph.hash(user_data.password)
        admin = User(
            username=user_data.username,
            password=hashed_password,
            is_admin=True
        )
        self.db.add(admin)
        self.db.commit()
        return UserResponse.model_validate(admin)

    async def validate_login(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter_by(username=username).first()
        if user:
            try:
                ph.verify(user.password, password)
                return user
            except VerifyMismatchError:
                return None
        return None

    async def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        session = Session(user_id=user_id, token=token)
        self.db.add(session)
        self.db.commit()
        return token

    async def validate_session(self, token: str) -> bool:
        return bool(self.db.query(Session).filter_by(token=token).first())
