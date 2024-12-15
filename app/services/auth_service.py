from sqlalchemy.orm import Session
from app.models import User, Session
from passlib.context import CryptContext
import secrets
import logging

logger = logging.getLogger("streamvault")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    async def admin_exists(self) -> bool:
        return bool(self.db.query(User).filter_by(is_admin=True).first())

    async def create_admin(self, username: str, password: str) -> User:
        hashed_password = pwd_context.hash(password)
        admin = User(
            username=username,
            password=hashed_password,
            is_admin=True
        )
        self.db.add(admin)
        self.db.commit()
        return admin

    async def validate_login(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter_by(username=username).first()
        if user and pwd_context.verify(password, user.password):
            return user
        return None

    async def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        session = Session(user_id=user_id, token=token)
        self.db.add(session)
        self.db.commit()
        return token

    async def validate_session(self, token: str) -> bool:
        return bool(self.db.query(Session).filter_by(token=token).first())
