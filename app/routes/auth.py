from fastapi import APIRouter, Depends, HTTPException, Response, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service

router = APIRouter(tags=["auth"])

@router.api_route("/setup", methods=["GET", "HEAD"])
async def setup_page(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = await auth_service.admin_exists()
    
    # Always return JSON for XHR/fetch requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            content={"setup_required": not admin_exists},
            headers={"Content-Type": "application/json"}
        )
    
    # Handle browser requests
    if admin_exists:
        return RedirectResponse(url="/auth/login", status_code=307)
    return FileResponse("app/frontend/dist/index.html")
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
    
    response = JSONResponse(content={"message": "Admin account created", "success": True})
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
    response = JSONResponse(content={"message": "Login successful", "success": True})
    response.set_cookie(key="session", value=token, httponly=True, secure=True)
    return response

@router.api_route("/login", methods=["GET", "HEAD"])
async def login_page(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    admin_exists = await auth_service.admin_exists()
    
    # For API requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not admin_exists:
            return JSONResponse(content={"redirect": "/auth/setup"})
        return JSONResponse(content={"login_required": True})
    
    # For browser requests
    if not admin_exists:
        return RedirectResponse(url="/auth/setup", status_code=307)
    return FileResponse("app/frontend/dist/index.html")

@router.get("/check")
async def check_auth(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    admin_exists = await auth_service.admin_exists()
    if not admin_exists:
        return JSONResponse(content={"setup_required": True})
    
    session_token = request.cookies.get("session")
    if not session_token or not await auth_service.validate_session(session_token):
        return JSONResponse(content={"authenticated": False})
    return JSONResponse(content={"authenticated": True})
