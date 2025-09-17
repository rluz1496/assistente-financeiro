"""
Sistema de Reset de Senha Simplificado
Funciona sem configuração SMTP - simula envio de emails
"""
import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os

# Configurações de email (opcionais)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class EmailService:
    """Serviço simplificado para simulação de emails"""
    
    def __init__(self):
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        
    async def send_email_simple(self, to_email: str, subject: str, content: str):
        """Simula envio de email"""
        print("=" * 60)
        print(f"📧 EMAIL SIMULADO")
        print(f"Para: {to_email}")
        print(f"Assunto: {subject}")
        print("-" * 60)
        print(content)
        print("=" * 60)
        print("💡 Configure SMTP no .env para envio real de emails")
        return True
    
    async def send_password_reset_email(self, user_email: str, user_name: str, reset_token: str):
        """Envia email de reset de senha (simulado)"""
        reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
        
        content = f"""
Olá, {user_name}!

Você solicitou o reset da sua senha no Assistente Financeiro.

Acesse o link abaixo para criar uma nova senha:
{reset_url}

Este link é válido por apenas 1 hora.

Se você não solicitou este reset, ignore este email.

Atenciosamente,
Equipe Assistente Financeiro
        """
        
        return await self.send_email_simple(
            to_email=user_email,
            subject="Reset de Senha - Assistente Financeiro",
            content=content
        )
    
    async def send_welcome_email(self, user_email: str, user_name: str):
        """Envia email de boas-vindas (simulado)"""
        content = f"""
Olá, {user_name}!

Bem-vindo ao Assistente Financeiro! Sua conta foi criada com sucesso.

Você pode começar a usar o sistema agora mesmo.

Atenciosamente,
Equipe Assistente Financeiro
        """
        
        return await self.send_email_simple(
            to_email=user_email,
            subject="Bem-vindo ao Assistente Financeiro! 🎉",
            content=content
        )

# Instância global do serviço de email
email_service = EmailService()

# Classe para gestão de tokens de reset
class PasswordResetManager:
    """Gerenciador de tokens de reset de senha"""
    
    def __init__(self):
        # Em produção, use Redis ou banco de dados
        # Por simplicidade, usamos dicionário em memória
        self.reset_tokens = {}
    
    def generate_token(self, user_id: str, user_email: str) -> str:
        """Gera token de reset"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        self.reset_tokens[token] = {
            "user_id": user_id,
            "user_email": user_email,
            "expires_at": expires_at,
            "used": False
        }
        
        return token
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Valida token de reset"""
        token_data = self.reset_tokens.get(token)
        
        if not token_data:
            return None
        
        if token_data["used"]:
            return None
        
        if datetime.now(timezone.utc) > token_data["expires_at"]:
            # Token expirado, remove da memória
            del self.reset_tokens[token]
            return None
        
        return token_data
    
    def use_token(self, token: str) -> bool:
        """Marca token como usado"""
        if token in self.reset_tokens:
            self.reset_tokens[token]["used"] = True
            return True
        return False
    
    def cleanup_expired_tokens(self):
        """Remove tokens expirados (chamar periodicamente)"""
        now = datetime.now(timezone.utc)
        expired_tokens = [
            token for token, data in self.reset_tokens.items()
            if now > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self.reset_tokens[token]

# Instância global do gerenciador de reset
reset_manager = PasswordResetManager()

# Funções auxiliares para integração
async def send_password_reset_email_async(user_email: str, user_name: str, user_id: str) -> Optional[str]:
    """Envia email de reset e retorna token"""
    try:
        # Gera token
        reset_token = reset_manager.generate_token(user_id, user_email)
        
        # Envia email (simulado)
        success = await email_service.send_password_reset_email(
            user_email=user_email,
            user_name=user_name,
            reset_token=reset_token
        )
        
        if success:
            return reset_token
        else:
            return None
            
    except Exception as e:
        print(f"Erro ao enviar email de reset: {str(e)}")
        return None

async def send_welcome_email_async(user_email: str, user_name: str):
    """Envia email de boas-vindas de forma assíncrona"""
    try:
        await email_service.send_welcome_email(user_email, user_name)
    except Exception as e:
        print(f"Erro ao enviar email de boas-vindas: {str(e)}")

def validate_reset_token(token: str) -> Optional[str]:
    """Valida token e retorna user_id se válido"""
    token_data = reset_manager.validate_token(token)
    return token_data["user_id"] if token_data else None

def mark_token_as_used(token: str) -> bool:
    """Marca token como usado"""
    return reset_manager.use_token(token)

# Task para limpeza periódica de tokens
async def cleanup_tokens_periodically():
    """Task que roda periodicamente para limpar tokens expirados"""
    while True:
        reset_manager.cleanup_expired_tokens()
        await asyncio.sleep(3600)  # A cada hora