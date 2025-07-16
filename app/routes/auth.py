import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from app.services.auth_service import AuthService
from app.dependencies import get_auth_service
from app.schemas.auth import UserCreate, LoginResponse
from app.config.settings import get_settings

logger = logging.getLogger("streamvault")

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

@router.post("/setup")
async def setup_admin(
    request: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    if await auth_service.admin_exists():
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    admin = await auth_service.create_admin(request)
    token = await auth_service.create_session(admin.id)
    
    response = JSONResponse(content={"message": "Admin account created", "success": True})
    settings = get_settings()
    response.set_cookie(
        key="session", 
        value=token, 
        httponly=True, 
        secure=settings.USE_SECURE_COOKIES,  # Auto-configured for reverse proxy
        samesite="lax"
    )
    return response

@router.post("/login")
async def login(
    request: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        # Validate input
        if not request.username or not request.password:
            logger.warning(f"Login attempt with missing credentials: username={bool(request.username)}, password={bool(request.password)}")
            raise HTTPException(status_code=400, detail="Username and password are required")
        
        user = await auth_service.validate_login(request.username, request.password)
        if not user:
            logger.warning(f"Failed login attempt for username: {request.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = await auth_service.create_session(user.id)
        response = JSONResponse(content={"message": "Login successful", "success": True})
        # Set secure based on configuration, httponly=True for XSS protection
        settings = get_settings()
        response.set_cookie(
            key="session", 
            value=token, 
            httponly=True, 
            secure=settings.USE_SECURE_COOKIES,  # Auto-configured for reverse proxy
            samesite="lax"  # Allow cross-site requests for reverse proxy
        )
        logger.info(f"Successful login for user: {request.username}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.api_route("/login", methods=["GET", "HEAD"])
async def login_page(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    try:
        admin_exists = await auth_service.admin_exists()
        
        # For API requests (check for JSON accept header or XMLHttpRequest)
        if (request.headers.get("X-Requested-With") == "XMLHttpRequest" or 
            "application/json" in request.headers.get("accept", "")):
            if not admin_exists:
                return JSONResponse(content={"redirect": "/auth/setup"})
            return JSONResponse(content={"login_required": True})
        
        # For browser requests - always serve the SPA
        # The frontend will handle routing and redirects appropriately
        try:
            return FileResponse("app/frontend/dist/index.html")
        except Exception as file_error:
            logger.error(f"Error serving index.html: {file_error}")
            # If we can't serve the file, try to redirect to setup if no admin exists
            if not admin_exists:
                return RedirectResponse(url="/auth/setup", status_code=307)
            # Otherwise return a simple error response
            raise HTTPException(status_code=500, detail="Unable to serve login page")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login_page: {e}")
        # For error cases, try to serve the SPA or return appropriate response
        try:
            return FileResponse("app/frontend/dist/index.html")
        except:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
                return JSONResponse(
                    content={"error": "Internal server error"},
                    status_code=500
                )
            raise HTTPException(status_code=500, detail="Internal server error")

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

@router.post("/logout")
async def logout(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        session_token = request.cookies.get("session")
        if session_token:
            await auth_service.delete_session(session_token)
            logger.info("User logged out successfully")
        
        response = JSONResponse(content={"message": "Logout successful", "success": True})
        response.delete_cookie(key="session")
        return response
    except Exception as e:
        logger.error(f"Logout error: {e}")
        response = JSONResponse(content={"message": "Logout completed", "success": True})
        response.delete_cookie(key="session")
        return response
