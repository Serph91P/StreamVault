from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from typing import Optional

class AuthMiddleware:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.security = HTTPBearer()

    async def __call__(self, request: Request):
        credentials: Optional[HTTPAuthorizationCredentials] = await self.security(request)
        if not credentials:
            raise HTTPException(status_code=401, detail="Invalid authorization")
        
        try:
            payload = jwt.decode(credentials.credentials, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
