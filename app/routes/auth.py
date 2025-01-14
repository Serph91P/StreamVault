from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service

router = APIRouter(tags=["auth"])

@router.get("/setup")
async def setup_page(auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = await auth_service.admin_exists()
    return JSONResponse(content={"setup_required": not admin_exists})

class SetupRequest(BaseModel):
    username: str
    password: str

@router.post("/setup")
async def setup_admin(
    request: SetupRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    if await auth_service.admin_exists():
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    admin = await auth_service.create_admin(request.username, request.password)
    token = await auth_service.create_session(admin.id)
    
    response = JSONResponse(content={"message": "Admin account created"})
    response.set_cookie(key="session", value=token, httponly=True)
    return response

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    user = await auth_service.validate_login(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = await auth_service.create_session(user.id)
    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(key="session", value=token, httponly=True)
    return response

@router.get("/auth/check")
async def check_auth(auth_service: AuthService = Depends(get_auth_service)):
    session_token = request.cookies.get("session")
    if not session_token or not await auth_service.validate_session(session_token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse(content={"authenticated": True})
