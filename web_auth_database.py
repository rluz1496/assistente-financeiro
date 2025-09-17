"""
Sistema completo de banco de dados para autenticação
Inclui hash de senhas, JWT tokens, reset de senha e validações
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import jwt
from web_models import *

# Carrega variáveis de ambiente
load_dotenv()

# Configuração Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")  # Corrigido para usar a variável correta

# Configuração JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class DatabaseError(Exception):
    """Exceção customizada para erros de banco de dados"""
    pass

class AuthenticationError(Exception):
    """Exceção customizada para erros de autenticação"""
    pass

# Utilidades de hash e criptografia
def hash_password(password: str) -> str:
    """Hash seguro da senha usando SHA-256 com salt"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha está correta"""
    try:
        salt, stored_hash = password_hash.split(':')
        calculated_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return secrets.compare_digest(calculated_hash, stored_hash)
    except ValueError:
        return False

def generate_reset_token() -> str:
    """Gera token seguro para reset de senha"""
    return secrets.token_urlsafe(32)

# Funções JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Cria token de acesso JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict):
    """Cria token de refresh JWT"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """Verifica e decodifica token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.PyJWTError:
        return None

# Operações de usuário
async def create_user(user_data: UserCreate) -> Optional[Dict[str, Any]]:
    """Cria novo usuário no banco de dados"""
    try:
        # Verifica se email já existe
        existing_user = await get_user_by_email(user_data.email)
        if existing_user:
            raise DatabaseError("Email já cadastrado")
        
        # Verifica se phone já existe
        existing_phone = await get_user_by_phone(user_data.phone_number)
        if existing_phone:
            raise DatabaseError("Telefone já cadastrado")
        
        # Verifica se CPF já existe
        existing_cpf = await get_user_by_cpf(user_data.cpf)
        if existing_cpf:
            raise DatabaseError("CPF já cadastrado")
        
        # Hash da senha
        password_hash = hash_password(user_data.password)
        
        # Dados do usuário
        user_dict = {
            "name": user_data.name,
            "email": user_data.email,
            "phone_number": user_data.phone_number,
            "cpf": user_data.cpf,
            "password_hash": password_hash,
            "is_active": True,
            "role": "user",
            "onboarding_completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table("users").insert(user_dict).execute()
        
        if result.data:
            user_data = result.data[0]
            
            # Envia email de boas-vindas de forma assíncrona
            try:
                from email_service_simple import send_welcome_email_async
                import asyncio
                asyncio.create_task(send_welcome_email_async(user_data["email"], user_data["name"]))
            except Exception as e:
                # Não falha se o email não for enviado
                print(f"Erro ao enviar email de boas-vindas: {str(e)}")
            
            return user_data
        else:
            raise DatabaseError("Erro ao criar usuário")
            
    except Exception as e:
        raise DatabaseError(f"Erro ao criar usuário: {str(e)}")

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Busca usuário por ID"""
    try:
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        raise DatabaseError(f"Erro ao buscar usuário: {str(e)}")

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca usuário por email"""
    try:
        result = supabase.table("users").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        raise DatabaseError(f"Erro ao buscar usuário por email: {str(e)}")

async def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Busca usuário por telefone"""
    try:
        result = supabase.table("users").select("*").eq("phone_number", phone).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        raise DatabaseError(f"Erro ao buscar usuário por telefone: {str(e)}")

async def get_user_by_cpf(cpf: str) -> Optional[Dict[str, Any]]:
    """Busca usuário por CPF"""
    try:
        result = supabase.table("users").select("*").eq("cpf", cpf).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        raise DatabaseError(f"Erro ao buscar usuário por CPF: {str(e)}")

async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Autentica usuário com email e senha"""
    try:
        user = await get_user_by_email(email)
        if not user:
            return None
        
        if not user.get("is_active", False):
            raise AuthenticationError("Conta desativada")
        
        if not verify_password(password, user["password_hash"]):
            return None
        
        # Atualiza último login
        await update_last_login(user["id"])
        
        return user
        
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise e
        raise DatabaseError(f"Erro na autenticação: {str(e)}")

async def update_last_login(user_id: str):
    """Atualiza timestamp do último login"""
    try:
        supabase.table("users").update({
            "last_login": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
    except Exception as e:
        # Não falha se não conseguir atualizar o último login
        pass

async def update_user(user_id: str, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
    """Atualiza dados do usuário"""
    try:
        update_dict = {}
        
        # Verifica campos a serem atualizados
        if user_data.name is not None:
            update_dict["name"] = user_data.name
        
        if user_data.email is not None:
            # Verifica se novo email já está em uso
            existing_user = await get_user_by_email(user_data.email)
            if existing_user and existing_user["id"] != user_id:
                raise DatabaseError("Email já está em uso")
            update_dict["email"] = user_data.email
        
        if user_data.phone_number is not None:
            # Verifica se novo telefone já está em uso
            existing_phone = await get_user_by_phone(user_data.phone_number)
            if existing_phone and existing_phone["id"] != user_id:
                raise DatabaseError("Telefone já está em uso")
            update_dict["phone_number"] = user_data.phone_number
        
        if not update_dict:
            return await get_user_by_id(user_id)
        
        update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = supabase.table("users").update(update_dict).eq("id", user_id).execute()
        
        if result.data:
            return result.data[0]
        else:
            raise DatabaseError("Erro ao atualizar usuário")
            
    except Exception as e:
        if isinstance(e, DatabaseError):
            raise e
        raise DatabaseError(f"Erro ao atualizar usuário: {str(e)}")

async def change_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Altera senha do usuário"""
    try:
        user = await get_user_by_id(user_id)
        if not user:
            raise DatabaseError("Usuário não encontrado")
        
        if not verify_password(current_password, user["password_hash"]):
            raise AuthenticationError("Senha atual incorreta")
        
        new_password_hash = hash_password(new_password)
        
        result = supabase.table("users").update({
            "password_hash": new_password_hash,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return bool(result.data)
        
    except Exception as e:
        if isinstance(e, (DatabaseError, AuthenticationError)):
            raise e
        raise DatabaseError(f"Erro ao alterar senha: {str(e)}")

# Sistema de reset de senha
async def create_password_reset_token(email: str) -> Optional[str]:
    """Cria token para reset de senha"""
    try:
        from email_service_simple import send_password_reset_email_async
        
        user = await get_user_by_email(email)
        if not user:
            return None  # Não revelamos se o email existe
        
        # Envia email e obtém token
        token = await send_password_reset_email_async(
            user_email=user["email"],
            user_name=user["name"],
            user_id=user["id"]
        )
        
        return token
        
    except Exception as e:
        raise DatabaseError(f"Erro ao criar token de reset: {str(e)}")

async def reset_password_with_token(token: str, new_password: str) -> bool:
    """Reseta senha usando token"""
    try:
        from email_service_simple import validate_reset_token, mark_token_as_used
        
        # Valida token
        user_id = validate_reset_token(token)
        if not user_id:
            return False
        
        # Marca token como usado
        if not mark_token_as_used(token):
            return False
        
        # Atualiza senha
        new_password_hash = hash_password(new_password)
        
        result = supabase.table("users").update({
            "password_hash": new_password_hash,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return bool(result.data)
        
    except Exception as e:
        raise DatabaseError(f"Erro ao resetar senha: {str(e)}")

# Funções de token management
async def create_token_pair(user: Dict[str, Any]) -> Dict[str, Any]:
    """Cria par de tokens (access + refresh)"""
    try:
        access_token = create_access_token(
            data={"user_id": user["id"], "email": user["email"]}
        )
        refresh_token = create_refresh_token(
            data={"user_id": user["id"], "email": user["email"]}
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    except Exception as e:
        raise DatabaseError(f"Erro ao criar tokens: {str(e)}")

async def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """Renova token de acesso usando refresh token"""
    try:
        payload = verify_token(refresh_token, "refresh")
        if not payload:
            return None
        
        user = await get_user_by_id(payload["user_id"])
        if not user or not user.get("is_active", False):
            return None
        
        new_access_token = create_access_token(
            data={"user_id": user["id"], "email": user["email"]}
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except Exception as e:
        raise DatabaseError(f"Erro ao renovar token: {str(e)}")

# Funções auxiliares
async def deactivate_user(user_id: str) -> bool:
    """Desativa usuário"""
    try:
        result = supabase.table("users").update({
            "is_active": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return bool(result.data)
    except Exception as e:
        raise DatabaseError(f"Erro ao desativar usuário: {str(e)}")

async def activate_user(user_id: str) -> bool:
    """Ativa usuário"""
    try:
        result = supabase.table("users").update({
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return bool(result.data)
    except Exception as e:
        raise DatabaseError(f"Erro ao ativar usuário: {str(e)}")

async def complete_onboarding(user_id: str) -> bool:
    """Marca onboarding como completo"""
    try:
        result = supabase.table("users").update({
            "onboarding_completed": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return bool(result.data)
    except Exception as e:
        raise DatabaseError(f"Erro ao completar onboarding: {str(e)}")