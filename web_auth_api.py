"""
API de Autenticação Completa
Endpoints para registro, login, logout, reset de senha e gestão de tokens
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import asyncio

# Importa modelos e banco de dados
from web_models import *
from web_auth_database import *

app = FastAPI(
    title="Sistema de Gestão Financeira",
    description="API completa com autenticação JWT, reset de senha e gestão de usuários",
    version="1.0.0"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração de segurança
security = HTTPBearer()

# Dependency para extrair usuário atual do token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Extrai usuário atual do token JWT"""
    try:
        token = credentials.credentials
        payload = verify_token(token, "access")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await get_user_by_id(payload["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Conta desativada",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro na autenticação",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Dependency opcional para usuário (não obrigatório)
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Extrai usuário atual do token JWT (opcional)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

# ENDPOINTS DE AUTENTICAÇÃO

@app.post("/api/auth/register", response_model=ApiResponse)
async def register_user(user_data: UserCreate):
    """Registra novo usuário"""
    try:
        user = await create_user(user_data)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao criar usuário"
            )
        
        # Remove senha do retorno
        user_response = {k: v for k, v in user.items() if k != "password_hash"}
        
        return ApiResponse(
            success=True,
            message="Usuário criado com sucesso",
            data={"user": user_response}
        )
        
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@app.post("/api/auth/login", response_model=ApiResponse)
async def login_user(login_data: UserLogin):
    """Realiza login do usuário"""
    try:
        user = await authenticate_user(login_data.email, login_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos"
            )
        
        # Cria tokens
        tokens = await create_token_pair(user)
        
        # Remove senha do retorno
        user_response = {k: v for k, v in user.items() if k != "password_hash"}
        
        return ApiResponse(
            success=True,
            message="Login realizado com sucesso",
            data={
                "user": user_response,
                "tokens": tokens
            }
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@app.post("/api/auth/refresh", response_model=ApiResponse)
async def refresh_token(refresh_data: RefreshToken):
    """Renova token de acesso"""
    try:
        new_token = await refresh_access_token(refresh_data.refresh_token)
        
        if not new_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresh inválido"
            )
        
        return ApiResponse(
            success=True,
            message="Token renovado com sucesso",
            data={"tokens": new_token}
        )
        
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@app.post("/api/auth/logout", response_model=ApiResponse)
async def logout_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Realiza logout do usuário"""
    # Em uma implementação completa, você invalidaria o token
    # Por simplicidade, apenas retornamos sucesso
    return ApiResponse(
        success=True,
        message="Logout realizado com sucesso"
    )

# ENDPOINTS DE GESTÃO DE USUÁRIO

@app.get("/api/auth/me", response_model=ApiResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna informações do usuário atual"""
    user_response = {k: v for k, v in current_user.items() if k != "password_hash"}
    
    return ApiResponse(
        success=True,
        message="Informações do usuário",
        data={"user": user_response}
    )

@app.put("/api/auth/me", response_model=ApiResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Atualiza informações do usuário atual"""
    try:
        updated_user = await update_user(current_user["id"], user_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao atualizar usuário"
            )
        
        user_response = {k: v for k, v in updated_user.items() if k != "password_hash"}
        
        return ApiResponse(
            success=True,
            message="Usuário atualizado com sucesso",
            data={"user": user_response}
        )
        
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

# ENDPOINTS DE GESTÃO DE SENHA

@app.post("/api/auth/change-password", response_model=ApiResponse)
async def change_user_password(
    password_data: PasswordChange,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Altera senha do usuário"""
    try:
        success = await change_password(
            current_user["id"],
            password_data.current_password,
            password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao alterar senha"
            )
        
        return ApiResponse(
            success=True,
            message="Senha alterada com sucesso"
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

@app.post("/api/auth/forgot-password", response_model=ApiResponse)
async def forgot_password(reset_request: PasswordResetRequest):
    """Solicita reset de senha"""
    try:
        token = await create_password_reset_token(reset_request.email)
        
        # Sempre retorna sucesso para não revelar se o email existe
        return ApiResponse(
            success=True,
            message="Se o email existir, você receberá um link para reset de senha"
        )
        
    except Exception as e:
        # Log do erro internamente, mas não revela para o usuário
        return ApiResponse(
            success=True,
            message="Se o email existir, você receberá um link para reset de senha"
        )

@app.post("/api/auth/reset-password", response_model=ApiResponse)
async def reset_password(reset_data: PasswordReset):
    """Reseta senha com token"""
    try:
        success = await reset_password_with_token(reset_data.token, reset_data.new_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido ou expirado"
            )
        
        return ApiResponse(
            success=True,
            message="Senha resetada com sucesso"
        )
        
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

# ENDPOINTS ADMINISTRATIVOS

@app.post("/api/auth/complete-onboarding", response_model=ApiResponse)
async def complete_user_onboarding(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Marca onboarding como completo"""
    try:
        success = await complete_onboarding(current_user["id"])
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao completar onboarding"
            )
        
        return ApiResponse(
            success=True,
            message="Onboarding completado com sucesso"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

# ENDPOINT DE HEALTH CHECK

@app.get("/api/health")
async def health_check():
    """Endpoint para verificar saúde da API"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# MIDDLEWARE PARA LOGS (opcional)
@app.middleware("http")
async def log_requests(request, call_next):
    """Middleware para log de requisições"""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    
    # Aqui você pode adicionar logs mais elaborados
    print(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)