from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool


class LoginResponse(BaseModel):
    message: str
    success: bool
