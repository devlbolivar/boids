from pydantic import BaseModel, EmailStr

class TenantRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class RegisterResponse(BaseModel):
    tenant_id: str
    access_token: str

class Token(BaseModel):
    access_token: str
    token_type: str
