"""
FastAPI para integração com Evolution API (WhatsApp)
Recebe mensagens do WhatsApp e responde através do assistente financeiro
"""
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import asyncio
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from agent import agent
from functions_database import get_user_by_phone
from models import FinanceDeps
from onboarding import complete_onboarding, check_user_exists

# Configurações
app = FastAPI(
    title="Assistente Financeiro WhatsApp API",
    description="API para integração entre Evolution API e o Assistente Financeiro",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações Evolution API
EVOLUTION_BASE_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_TOKEN", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "assistente-financeiro")

# Models para webhooks
class EvolutionMessage(BaseModel):
    """Modelo para mensagens recebidas da Evolution API"""
    key: Dict[str, Any]
    message: Dict[str, Any]
    messageTimestamp: int
    pushName: Optional[str] = None
    messageType: Optional[str] = None
    instanceId: Optional[str] = None
    source: Optional[str] = None

class EvolutionWebhook(BaseModel):
    """Modelo para webhook da Evolution API"""
    event: str
    instance: str
    data: EvolutionMessage
    destination: Optional[str] = None
    date_time: Optional[str] = None
    sender: Optional[str] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None

class WhatsAppResponse(BaseModel):
    """Modelo para resposta do WhatsApp"""
    number: str
    text: str

class CategoryData(BaseModel):
    """Modelo para categoria de onboarding"""
    name: str
    type: str = "expense"
    color: str = "#007bff"

class CreditCardData(BaseModel):
    """Modelo para cartão de crédito de onboarding"""
    name: str
    closing_day: int
    due_day: int
    limit: float = 0.0

class OnboardingData(BaseModel):
    """Modelo para dados de onboarding"""
    name: str
    phone: str
    cpf: Optional[str] = None
    categories: List[CategoryData] = []
    credit_cards: List[CreditCardData] = []

# Cache para evitar processamento duplicado
processed_messages = set()

async def send_whatsapp_message(phone_number: str, message: str) -> bool:
    """Envia mensagem via Evolution API"""
    try:
        # Limpar número para formato internacional
        clean_phone = phone_number.replace("+", "").replace("-", "").replace(" ", "")
        if not clean_phone.startswith("55"):
            clean_phone = f"55{clean_phone}"
        
        url = f"{EVOLUTION_BASE_URL}/message/sendText/{EVOLUTION_INSTANCE}"
        
        payload = {
            "number": clean_phone,
            "text": message
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": EVOLUTION_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ Mensagem enviada para {phone_number}")
                return True
            else:
                print(f"❌ Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem WhatsApp: {e}")
        return False

async def process_user_message(phone_number: str, message_text: str, user_name: str = None):
    """Processa mensagem do usuário através do assistente"""
    try:
        # Verificar se usuário existe
        user_data = get_user_by_phone(phone_number)
        
        if not user_data:
            # Usuário não cadastrado - enviar para onboarding
            # Obter URL base dinamicamente (será o ngrok URL)
            base_url = os.getenv("BASE_URL", "http://localhost:8001")
            onboarding_url = f"{base_url}/onboarding?phone={phone_number}"
            
            onboarding_message = (
                f"👋 Olá{f' {user_name}' if user_name else ''}! \n\n"
                "Ainda não temos você cadastrado no nosso sistema financeiro. "
                "Para usar o assistente, você precisa fazer um cadastro rápido.\n\n"
                f"🔗 Acesse: {onboarding_url}\n\n"
                "Após o cadastro, você poderá:\n"
                "💰 Registrar receitas e despesas\n"
                "💳 Gerenciar cartões de crédito\n"
                "📊 Ver relatórios financeiros\n"
                "📈 Acompanhar seu saldo"
            )
            
            await send_whatsapp_message(phone_number, onboarding_message)
            return
        
        # Usuário cadastrado - processar com o agente
        user_id = user_data["id"]
        user_name = user_data["name"]
        
        # Criar dependências para o agente
        deps = FinanceDeps(user_id=user_id)
        
        # Executar o agente
        result = await agent.run(message_text, deps=deps)
        
        # Enviar resposta
        response_text = result.data if hasattr(result, 'data') else str(result)
        await send_whatsapp_message(phone_number, response_text)
        
        print(f"✅ Mensagem processada para {user_name} ({phone_number})")
        
    except Exception as e:
        print(f"❌ Erro ao processar mensagem: {e}")
        error_message = (
            "😔 Ops! Ocorreu um erro ao processar sua mensagem. "
            "Tente novamente em alguns instantes."
        )
        await send_whatsapp_message(phone_number, error_message)

@app.get("/")
async def root():
    """Endpoint de status da API"""
    return {
        "message": "Assistente Financeiro WhatsApp API",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "evolution_configured": bool(EVOLUTION_API_KEY),
        "instance": EVOLUTION_INSTANCE
    }

@app.get("/health")
async def health_check():
    """Health check da API"""
    return {
        "api_status": "healthy",
        "evolution_configured": bool(EVOLUTION_API_KEY),
        "instance": EVOLUTION_INSTANCE,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/webhook/evolution")
async def evolution_webhook(webhook: EvolutionWebhook, background_tasks: BackgroundTasks):
    """Webhook para receber mensagens da Evolution API"""
    try:
        # Verificar se é uma mensagem recebida
        if webhook.event != "messages.upsert":
            return {"status": "ignored", "reason": "not a message event"}
        
        message_data = webhook.data
        
        # Verificar se é uma mensagem de texto recebida (não enviada por nós)
        if not message_data.message.get("conversation") and not message_data.message.get("extendedTextMessage"):
            return {"status": "ignored", "reason": "not a text message"}
        
        # Extrair informações da mensagem
        phone_number = message_data.key.get("remoteJid", "").replace("@s.whatsapp.net", "")
        
        # Verificar se a mensagem é de nós mesmos (fromMe: true)
        if message_data.key.get("fromMe", False):
            return {"status": "ignored", "reason": "message from bot"}
        
        message_text = (
            message_data.message.get("conversation") or 
            message_data.message.get("extendedTextMessage", {}).get("text", "")
        )
        user_name = message_data.pushName
        message_id = message_data.key.get("id", "")
        
        # Limpar número de telefone para formato padrão
        clean_phone = phone_number.replace("55", "", 1) if phone_number.startswith("55") else phone_number
        
        # Evitar processamento duplicado
        if message_id in processed_messages:
            return {"status": "ignored", "reason": "already processed"}
        
        processed_messages.add(message_id)
        
        # Limpar cache se ficar muito grande
        if len(processed_messages) > 1000:
            processed_messages.clear()
        
        # Verificar se temos dados suficientes
        if not phone_number or not message_text:
            return {"status": "ignored", "reason": "insufficient data"}
        
        # Processar mensagem em background
        background_tasks.add_task(
            process_user_message, 
            clean_phone, 
            message_text, 
            user_name
        )
        
        return {
            "status": "accepted",
            "phone": clean_phone,
            "original_phone": phone_number,
            "message_preview": message_text[:50] + "..." if len(message_text) > 50 else message_text
        }
        
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")

@app.post("/send-message")
async def send_message_endpoint(response: WhatsAppResponse):
    """Endpoint para enviar mensagens via WhatsApp (para testes)"""
    try:
        success = await send_whatsapp_message(response.number, response.text)
        
        if success:
            return {"status": "sent", "number": response.number}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{phone_number}")
async def get_user_info(phone_number: str):
    """Endpoint para verificar informações do usuário"""
    try:
        user_data = get_user_by_phone(phone_number)
        
        if user_data:
            return {
                "registered": True,
                "user": {
                    "id": user_data["id"],
                    "name": user_data["name"],
                    "phone": user_data["phone_number"],
                    "created_at": user_data["created_at"]
                }
            }
        else:
            return {"registered": False}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_form(phone: str = None):
    """Página de onboarding para novos usuários"""
    try:
        with open("templates/onboarding.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Se telefone fornecido, pré-preencher no formulário
        if phone:
            html_content = html_content.replace(
                'placeholder="48988379567"',
                f'value="{phone}" placeholder="48988379567"'
            )
        
        return HTMLResponse(content=html_content)
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Página de onboarding não encontrada")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/onboarding/complete")
async def complete_user_onboarding(data: OnboardingData):
    """Completa o processo de onboarding do usuário"""
    try:
        # Verificar se usuário já existe
        if check_user_exists(data.phone):
            return {
                "success": False,
                "message": "Usuário já cadastrado! Você pode usar o assistente normalmente."
            }
        
        # Converter dados para formato esperado pela função
        categories = [
            {
                "name": cat.name,
                "type": cat.type,
                "color": cat.color
            } for cat in data.categories
        ]
        
        credit_cards = [
            {
                "name": card.name,
                "closing_day": card.closing_day,
                "due_day": card.due_day,
                "limit": card.limit
            } for card in data.credit_cards
        ]
        
        # Completar onboarding
        result = complete_onboarding(
            phone_number=data.phone,
            name=data.name,
            cpf=data.cpf,
            categories=categories,
            credit_cards=credit_cards
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"🎉 Cadastro concluído com sucesso! Bem-vindo(a), {data.name}!",
                "details": {
                    "categories_created": result["categories_created"],
                    "cards_created": result["cards_created"]
                }
            }
        else:
            return {
                "success": False,
                "message": result["message"]
            }
            
    except Exception as e:
        print(f"❌ Erro no onboarding: {e}")
        return {
            "success": False,
            "message": "Erro interno do servidor. Tente novamente."
        }

@app.get("/onboarding/check/{phone_number}")
async def check_onboarding_status(phone_number: str):
    """Verifica se o usuário já completou o onboarding"""
    try:
        user_exists = check_user_exists(phone_number)
        
        return {
            "registered": user_exists,
            "phone": phone_number,
            "needs_onboarding": not user_exists
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Iniciando Assistente Financeiro WhatsApp API...")
    print(f"📱 Evolution Instance: {EVOLUTION_INSTANCE}")
    print(f"🔗 Evolution URL: {EVOLUTION_BASE_URL}")
    print(f"🔑 API Key configurada: {'Sim' if EVOLUTION_API_KEY else 'Não'}")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
