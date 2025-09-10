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
from functions_database import get_user_by_phone, get_user_categories, get_user_credit_cards
from models import FinanceDeps
from onboarding import complete_onboarding, check_user_exists
from media_processor import MediaProcessor, detect_media_type, extract_message_id
from chat_redis import ChatRedisDatabase

# Configurações
app = FastAPI(
    title="Assistente Financeiro WhatsApp API",
    description="API para integração entre Evolution API e o Assistente Financeiro",
    version="1.0.0"
)

# Inicializar Redis para confirmações
redis_db = ChatRedisDatabase()

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
            
            # 200 e 201 são códigos de sucesso
            if response.status_code in [200, 201]:
                print(f"✅ Mensagem enviada para {phone_number}")
                return True
            else:
                print(f"❌ Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem WhatsApp: {e}")
        return False

async def process_media_message(phone_number: str, message_data: dict, user_name: str = None, instance: str = None):
    """Processa mensagem de mídia (áudio ou imagem) do usuário"""
    print(f"🚀 INICIANDO PROCESSAMENTO DE MÍDIA - Usuário: {phone_number}, Instância: {instance}")
    try:
        media_type = detect_media_type(message_data)
        message_id = extract_message_id(message_data)
        
        if not message_id:
            await send_whatsapp_message(phone_number, "❌ Não consegui processar a mídia enviada.")
            return
        
        # Verificar se usuário existe
        user_data = get_user_by_phone(phone_number)
        if not user_data:
            # Mesmo fluxo de onboarding para usuários não cadastrados
            base_url = os.getenv("BASE_URL", "http://localhost:8001")
            onboarding_url = f"{base_url}/onboarding?phone={phone_number}"
            onboarding_message = (
                f"👋 Olá{f' {user_name}' if user_name else ''}!\n\n"
                "Para processar suas mídias financeiras, você precisa fazer um cadastro rápido.\n\n"
                f"🔗 Acesse: {onboarding_url}"
            )
            await send_whatsapp_message(phone_number, onboarding_message)
            return
        
        if media_type == "audio":
            # Processar áudio
            await send_whatsapp_message(phone_number, "🎧 Processando seu áudio...")
            
            # Baixar áudio
            base64_audio = await MediaProcessor.get_media_from_evolution(message_id, instance, False)
            if not base64_audio:
                await send_whatsapp_message(phone_number, "❌ Não consegui baixar o áudio.")
                return
            
            # Transcrever áudio
            transcription = await MediaProcessor.transcribe_audio(base64_audio)
            if not transcription:
                await send_whatsapp_message(phone_number, "❌ Não consegui transcrever o áudio.")
                return
            
            # Processar transcrição como mensagem de texto
            await process_user_message(phone_number, transcription, user_name)
            
        elif media_type == "image":
            # Processar imagem
            await send_whatsapp_message(phone_number, "📸 Analisando sua imagem...")
            
            # Baixar imagem
            base64_image = await MediaProcessor.get_media_from_evolution(message_id, instance, False)
            if not base64_image:
                await send_whatsapp_message(phone_number, "❌ Não consegui baixar a imagem.")
                return
            
            # Extrair dados do comprovante
            receipt_data = await MediaProcessor.extract_receipt_data(base64_image)
            if not receipt_data:
                await send_whatsapp_message(phone_number, "❌ Não consegui analisar a imagem.")
                return
            
            # Verificar se foi identificado como comprovante
            if "erro" in receipt_data:
                await send_whatsapp_message(phone_number, "📷 Não consegui identificar um comprovante financeiro nesta imagem. Tente enviar uma foto mais clara do comprovante.")
                return
            
            # Sempre pedir confirmação para dados extraídos de mídia
            valor = receipt_data.get('valor')
            descricao = receipt_data.get('descricao') or receipt_data.get('estabelecimento', 'Comprovante')
            categoria = receipt_data.get('categoria_sugerida', 'Outras despesas')
            metodo = receipt_data.get('metodo_pagamento', 'pix')
            confidence = receipt_data.get("confianca", 0)
            
            if valor and valor > 0:
                # Salvar dados de confirmação temporariamente
                confirmation_data = {
                    "tipo": "despesa_comprovante",
                    "valor": valor,
                    "descricao": descricao,
                    "categoria": categoria,
                    "metodo_pagamento": metodo,
                    "confianca": confidence,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Salvar no Redis por 5 minutos
                redis_db.save_pending_confirmation(phone_number, confirmation_data, expires_in=300)
                
                # Montar mensagem de confirmação inteligente
                confidence_emoji = "🎯" if confidence > 0.8 else "⚠️" if confidence > 0.5 else "❓"
                
                confirmation_message = (
                    f"✅ **Dados extraídos do comprovante:**\n"
                    f"💰 R$ {valor:.2f} - {descricao}\n"
                    f"💳 {metodo.replace('_', ' ').title()}\n"
                    f"📂 {categoria}\n"
                    f"{confidence_emoji} Confiança: {confidence*100:.0f}%\n\n"
                    f"Responda 'sim' para confirmar ou me diga o que ajustar.\n"
                    f"Ex: 'muda para cartão' ou 'categoria alimentação'"
                )
                
                await send_whatsapp_message(phone_number, confirmation_message)
                return
            else:
                await send_whatsapp_message(phone_number, "❌ Não consegui identificar o valor no comprovante.")
                return
        
    except Exception as e:
        print(f"❌ Erro ao processar mídia: {e}")
        await send_whatsapp_message(phone_number, "❌ Erro ao processar sua mídia. Tente novamente.")

async def process_confirmed_data(phone_number: str, pending_data: dict, user_name: str = None):
    """Processa dados confirmados pelo usuário"""
    try:
        tipo = pending_data.get("tipo")
        
        if tipo == "despesa_comprovante":
            # Construir comando para registrar despesa
            valor = pending_data.get("valor")
            descricao = pending_data.get("descricao")
            categoria = pending_data.get("categoria")
            metodo = pending_data.get("metodo_pagamento")
            
            comando = f"Registra uma despesa de R$ {valor:.2f} para {descricao} na categoria {categoria} via {metodo}"
            
            # Processar através do agente
            await process_user_message(phone_number, comando, user_name)
            
            # Enviar confirmação adicional
            await send_whatsapp_message(phone_number, f"✅ **Comprovante confirmado e registrado!**\n🎯 Transação processada com sucesso!")
            
    except Exception as e:
        print(f"❌ Erro ao processar confirmação: {e}")
        await send_whatsapp_message(phone_number, "❌ Erro ao processar confirmação. Tente novamente.")

async def process_user_message(phone_number: str, message_text: str, user_name: str = None):
    """Processa mensagem de texto do usuário através do assistente"""
    print(f"🚀 INICIANDO PROCESSAMENTO DE TEXTO - Usuário: {phone_number}, Mensagem: {message_text[:50]}...")
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
        
        # Verificar se há dados pendentes de confirmação
        pending_data = redis_db.get_pending_confirmation(phone_number)
        
        if pending_data:
            # Verificar se é confirmação simples
            message_lower = message_text.lower().strip()
            if message_lower in ['sim', 'confirma', 'confirmar', 'ok', 'certo', 'correto', 'confirmo']:
                # Processar confirmação
                await process_confirmed_data(phone_number, pending_data, user_name)
                # Limpar dados pendentes
                redis_db.clear_pending_confirmation(phone_number)
                return
            
            # Verificar se o usuário quer alterar algum dado
            elif any(word in message_lower for word in ['muda', 'altera', 'troca', 'categoria', 'cartao', 'pix', 'dinheiro']):
                # Processar alteração nos dados pendentes
                await process_data_modification(phone_number, pending_data, message_text, user_name)
                return
        
        # Se não há dados pendentes e é uma confirmação simples
        message_lower = message_text.lower().strip()
        if message_lower in ['sim', 'confirma', 'confirmar', 'ok', 'certo', 'correto', 'confirmo']:
            await send_whatsapp_message(phone_number, "❌ Não tenho dados pendentes para confirmar. Tente enviar novamente a mídia ou digite o registro manualmente.")
            return
        
        # Buscar categorias e cartões do usuário para criar as dependências
        categories = get_user_categories(user_id)
        credit_cards = get_user_credit_cards(user_id)
        
        # Criar dependências para o agente
        deps = FinanceDeps(
            user_id=user_id,
            user_name=user_name,
            phone_number=phone_number,
            categories=categories,
            credit_cards=credit_cards
        )
        
        # Executar o agente
        result = await agent.run(message_text, deps=deps)
        
        # Extrair o texto da resposta do AgentRunResult
        if hasattr(result, 'output'):
            # Se tiver o campo output, usa ele (formato mais comum)
            response_text = result.output
        elif hasattr(result, 'data'):
            # Caso tenha o campo data
            response_text = result.data
        else:
            # Último caso, converte para string mas remove o prefixo AgentRunResult
            result_str = str(result)
            if result_str.startswith("AgentRunResult"):
                # Extrai apenas o conteúdo entre aspas simples
                import re
                match = re.search(r"output='([^']*)'", result_str)
                if match:
                    response_text = match.group(1)
                else:
                    response_text = result_str
            else:
                response_text = result_str
                
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
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook para receber mensagens da Evolution API"""
    print(f"🔔 WEBHOOK RECEBIDO!")
    try:
        # Receber dados como JSON
        webhook_data = await request.json()
        print(f"📦 Dados brutos: {webhook_data}")
        
        # Extrair evento e instância
        event = webhook_data.get("event")
        instance = webhook_data.get("instance")
        print(f"🎯 Evento: {event}, Instância: {instance}")
        
        # Verificar se é uma mensagem recebida
        if event != "messages.upsert":
            print(f"❌ Evento ignorado: {event}")
            return {"status": "ignored", "reason": "not a message event"}
        
        # Acessar dados da mensagem
        message_data = webhook_data.get("data")
        if not message_data:
            print(f"❌ Dados da mensagem não encontrados")
            return {"status": "ignored", "reason": "no message data"}
        print(f"📱 Message data recebido")
        
        # Extrair informações básicas
        key_data = message_data.get('key', {})
        phone_number = key_data.get('remoteJid', "").replace("@s.whatsapp.net", "")
        from_me = key_data.get('fromMe', False)
        user_name = message_data.get('pushName', 'Usuário')
        print(f"📞 Telefone: {phone_number}, FromMe: {from_me}, Nome: {user_name}")
        
        # Verificar se não é mensagem nossa
        if from_me:
            return {"status": "ignored", "reason": "message from bot"}
        
        # Limpar número de telefone
        clean_phone = phone_number.replace("55", "", 1) if phone_number.startswith("55") else phone_number
        
        # Detectar tipo de mensagem e extrair conteúdo
        message_text = None
        
        # Verificar se é texto
        message_content = message_data.get('message', {})
        conversation = message_content.get('conversation')
        extended_text = message_content.get('extendedTextMessage', {})
        
        if conversation:
            message_text = conversation
        elif extended_text and extended_text.get('text'):
            message_text = extended_text.get('text')
        
        # Se tem texto, processar como mensagem de texto (fluxo original)
        if message_text:
            background_tasks.add_task(process_user_message, clean_phone, message_text, user_name)
            return {"status": "accepted", "type": "text", "preview": message_text[:50]}
        
        # Se não tem texto, verificar se é mídia (áudio ou imagem)
        # Verificar se tem áudio
        if message_content.get('audioMessage'):
            background_tasks.add_task(process_media_message, clean_phone, message_data, user_name, instance)
            return {"status": "accepted", "type": "audio"}
        
        # Verificar se tem imagem
        if message_content.get('imageMessage'):
            background_tasks.add_task(process_media_message, clean_phone, message_data, user_name, instance)
            return {"status": "accepted", "type": "image"}
        
        # Caso contrário, ignorar
        return {"status": "ignored", "reason": "unsupported message type"}
        
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
