from fastapi import APIRouter, Depends, HTTPException, Response, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service

router = APIRouter(tags=["auth"])

@router.api_route("/setup", methods=["GET", "HEAD"])
async def setup_page(auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = await auth_service.admin_exists()
    if not admin_exists:
        return FileResponse("app/frontend/dist/index.html")
    return RedirectResponse(url="/auth/login", status_code=307)

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
    response.set_cookie(key="session", value=token, httponly=True, secure=True)
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
    response.set_cookie(key="session", value=token, httponly=True, secure=True)
    return response

@router.api_route("/login", methods=["GET", "HEAD"])
async def login_page(auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = await auth_service.admin_exists()
    if not admin_exists:
        return RedirectResponse(url="/auth/setup", status_code=307)
    return FileResponse("app/frontend/dist/index.html")

@router.get("/check")
async def check_auth(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    session_token = request.cookies.get("session")
    if not session_token or not await auth_service.validate_session(session_token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse(content={"authenticated": True})