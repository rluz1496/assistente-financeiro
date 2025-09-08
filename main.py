"""
Ponto de entrada principal da aplicação para Railway
Importa e executa a API FastAPI
"""
import os
from api import app

# Railway define a porta via variável PORT
port = int(os.getenv("PORT", 8000))

if __name__ == "__main__":
    import uvicorn
    
    print(f"🚀 Iniciando Assistente Financeiro na porta {port}...")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0", 
        port=port,
        reload=False  # Desabilitado em produção
    )
