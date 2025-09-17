"""
Sistema de Reset de Senha via Email (Versão Simplificada)
Funciona sem configuração SMTP - simula envio de emails
"""
import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os

# Configurações de email
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Templates de email
PASSWORD_RESET_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset de Senha - Assistente Financeiro</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #4f46e5;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background-color: #f9fafb;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }
        .button {
            display: inline-block;
            background-color: #4f46e5;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #6b7280;
            font-size: 14px;
        }
        .warning {
            background-color: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏦 Assistente Financeiro</h1>
        <p>Reset de Senha</p>
    </div>
    
    <div class="content">
        <h2>Olá, {{ user_name }}!</h2>
        
        <p>Você solicitou o reset da sua senha. Clique no botão abaixo para criar uma nova senha:</p>
        
        <div style="text-align: center;">
            <a href="{{ reset_url }}" class="button">Resetar Senha</a>
        </div>
        
        <p>Ou copie e cole este link no seu navegador:</p>
        <p style="word-break: break-all; background-color: #e5e7eb; padding: 10px; border-radius: 4px;">
            {{ reset_url }}
        </p>
        
        <div class="warning">
            <strong>⚠️ Importante:</strong>
            <ul>
                <li>Este link é válido por apenas <strong>1 hora</strong></li>
                <li>Se você não solicitou este reset, ignore este email</li>
                <li>Nunca compartilhe este link com outras pessoas</li>
            </ul>
        </div>
        
        <p>Se você está com problemas para acessar o link, entre em contato conosco.</p>
        
        <p>Atenciosamente,<br>Equipe Assistente Financeiro</p>
    </div>
    
    <div class="footer">
        <p>Este é um email automático, não responda a esta mensagem.</p>
        <p>© 2025 Assistente Financeiro. Todos os direitos reservados.</p>
    </div>
</body>
</html>
"""

WELCOME_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bem-vindo - Assistente Financeiro</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #10b981;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background-color: #f9fafb;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }
        .button {
            display: inline-block;
            background-color: #10b981;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
        }
        .feature-list {
            background-color: white;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #10b981;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Bem-vindo!</h1>
        <p>Sua conta foi criada com sucesso</p>
    </div>
    
    <div class="content">
        <h2>Olá, {{ user_name }}!</h2>
        
        <p>É um prazer ter você conosco! Sua conta no <strong>Assistente Financeiro</strong> foi criada com sucesso.</p>
        
        <div class="feature-list">
            <h3>🚀 O que você pode fazer agora:</h3>
            <ul>
                <li>💳 Adicionar seus cartões e contas</li>
                <li>📊 Categorizar suas transações</li>
                <li>💰 Definir orçamentos mensais</li>
                <li>📈 Acompanhar seus gastos em tempo real</li>
                <li>🎯 Atingir suas metas financeiras</li>
            </ul>
        </div>
        
        <div style="text-align: center;">
            <a href="{{ app_url }}" class="button">Começar Agora</a>
        </div>
        
        <p>Se você tiver alguma dúvida, não hesite em entrar em contato conosco. Estamos aqui para ajudar!</p>
        
        <p>Atenciosamente,<br>Equipe Assistente Financeiro</p>
    </div>
</body>
</html>
"""

class EmailService:
    """Serviço para envio de emails"""
    
    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_email = FROM_EMAIL
        
    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None):
        """Envia email HTML - funciona sem SMTP configurado"""
        try:
            # Se não tem configuração SMTP, apenas simula o envio
            if not self.username or not self.password:
                print(f"📧 [SIMULANDO EMAIL] Para: {to_email}")
                print(f"📧 [SIMULANDO EMAIL] Assunto: {subject}")
                print(f"📧 [SIMULANDO EMAIL] Conteúdo: {html_content[:100]}...")
                print("💡 Configure SMTP_USERNAME e SMTP_PASSWORD no .env para envio real")
                return True
            
            # Criar mensagem
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Adicionar conteúdo texto (fallback)
            if text_content:
                text_part = MimeText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Adicionar conteúdo HTML
            html_part = MimeText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Enviar email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()
            
            print(f"📧 Email enviado com sucesso para: {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao enviar email: {str(e)}")
            print("💡 Configure SMTP no .env para funcionalidade completa")
            return False
    
    async def send_password_reset_email(self, user_email: str, user_name: str, reset_token: str):
        """Envia email de reset de senha"""
        try:
            reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
            
            # Renderizar template
            template = Template(PASSWORD_RESET_TEMPLATE)
            html_content = template.render(
                user_name=user_name,
                reset_url=reset_url
            )
            
            # Conteúdo texto (fallback)
            text_content = f"""
Olá, {user_name}!

Você solicitou o reset da sua senha no Assistente Financeiro.

Acesse o link abaixo para criar uma nova senha:
{reset_url}

Este link é válido por apenas 1 hora.

Se você não solicitou este reset, ignore este email.

Atenciosamente,
Equipe Assistente Financeiro
            """
            
            success = await self.send_email(
                to_email=user_email,
                subject="Reset de Senha - Assistente Financeiro",
                html_content=html_content,
                text_content=text_content
            )
            
            return success
            
        except Exception as e:
            print(f"Erro ao enviar email de reset: {str(e)}")
            return False
    
    async def send_welcome_email(self, user_email: str, user_name: str):
        """Envia email de boas-vindas"""
        try:
            app_url = FRONTEND_URL
            
            # Renderizar template
            template = Template(WELCOME_EMAIL_TEMPLATE)
            html_content = template.render(
                user_name=user_name,
                app_url=app_url
            )
            
            # Conteúdo texto (fallback)
            text_content = f"""
Olá, {user_name}!

Bem-vindo ao Assistente Financeiro! Sua conta foi criada com sucesso.

Acesse o aplicativo em: {app_url}

Atenciosamente,
Equipe Assistente Financeiro
            """
            
            success = await self.send_email(
                to_email=user_email,
                subject="Bem-vindo ao Assistente Financeiro! 🎉",
                html_content=html_content,
                text_content=text_content
            )
            
            return success
            
        except Exception as e:
            print(f"Erro ao enviar email de boas-vindas: {str(e)}")
            return False

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
        
        # Envia email
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