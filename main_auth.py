"""
Arquivo principal para executar a API de autenticação
Para testar, execute: python main_auth.py
"""
import uvicorn
import asyncio
from web_auth_api import app

async def startup_tasks():
    """Tarefas de inicialização"""
    # Por enquanto, sem limpeza de tokens para evitar dependências
    print("📧 Sistema de email em modo simulação (configure SMTP no .env para envio real)")
    pass

@app.on_event("startup")
async def on_startup():
    """Executa na inicialização da aplicação"""
    await startup_tasks()
    print("🚀 Sistema de Autenticação iniciado!")
    print("🔐 Sistema JWT ativo")
    print("📊 API disponível em: http://localhost:8000")
    print("📖 Documentação em: http://localhost:8000/docs")

@app.on_event("shutdown")
async def on_shutdown():
    """Executa no encerramento da aplicação"""
    print("⏹️ Sistema de Autenticação encerrado")

if __name__ == "__main__":
    print("🏦 Iniciando Assistente Financeiro - Sistema de Autenticação")
    print("=" * 60)
    
    uvicorn.run(
        "main_auth:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )