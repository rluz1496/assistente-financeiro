# 🏦 Assistente Financeiro - Backend

API FastAPI integrada com WhatsApp Evolution para assistente financeiro inteligente usando Pydantic-AI.

## 🚀 **Funcionalidades**

- 🤖 **Assistente IA** com 13 ferramentas financeiras
- 💬 **Integração WhatsApp** via Evolution API  
- 💾 **Redis Cloud** para histórico de conversas
- 🗄️ **Supabase** para dados financeiros
- 📊 **Análises financeiras** avançadas
- 🔄 **Sistema de onboarding** automático

## 🛠️ **Tecnologias**

- **FastAPI** - API REST moderna
- **Pydantic-AI** - Framework de IA com OpenAI
- **Supabase** - Banco PostgreSQL
- **Redis Cloud** - Cache e sessões
- **Evolution API** - Integração WhatsApp
- **Uvicorn** - Servidor ASGI

## ⚙️ **Configuração Local**

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/assistente-financeiro-backend.git
cd assistente-financeiro-backend
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente
```bash
cp .env.example .env
# Edite o arquivo .env com suas credenciais
```

### 4. Execute a aplicação
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 🌐 **Deploy Railway**

### 1. Conecte seu repositório GitHub ao Railway
### 2. Configure as variáveis de ambiente no painel Railway
### 3. Deploy automático a cada push na branch main

## 📋 **Variáveis de Ambiente**

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
DATABASE_URL=your_postgres_url

# Redis
REDIS_URL=your_redis_url

# OpenAI
OPENAI_API_KEY=your_openai_key

# Evolution API
EVOLUTION_API_URL=your_evolution_url
EVOLUTION_INSTANCE=your_instance
EVOLUTION_TOKEN=your_token

# Base URL
BASE_URL=https://your-backend.railway.app
```

## 🔗 **Endpoints Principais**

- `GET /` - Status da API
- `GET /health` - Health check
- `POST /webhook/evolution` - Webhook WhatsApp
- `GET /onboarding` - Formulário de cadastro
- `POST /onboarding/complete` - Processar cadastro
- `GET /docs` - Documentação Swagger

## 📁 **Estrutura do Projeto**

```
assistente-financeiro-backend/
├── main.py                 # Aplicação principal
├── api.py                 # Rotas FastAPI
├── agent.py               # Agente IA
├── models.py              # Modelos Pydantic
├── database.py            # Conexão Supabase
├── functions_database.py  # Funções do banco
├── onboarding.py          # Sistema de cadastro
├── chat_redis.py          # Gerenciamento Redis
├── templates/             # Templates HTML
├── requirements.txt       # Dependências
├── railway.json          # Configuração Railway
├── .env.example          # Exemplo variáveis
└── README.md             # Este arquivo
```

## 🤝 **Contribuição**

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 **Licença**

Este projeto está sob a licença MIT.
