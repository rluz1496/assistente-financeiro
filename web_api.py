"""
API REST para Frontend - Assistente Financeiro
Endpoints para gerenciar usuários, categorias, cartões, transações e orçamentos
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError
from typing import List, Optional
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Imports locais
from web_models import *
from web_database import WebDatabaseService

# Carregar variáveis de ambiente
load_dotenv()

# Configuração JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Inicializar FastAPI
app = FastAPI(
    title="Assistente Financeiro - API REST",
    description="API REST para gerenciamento financeiro pessoal",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite e outros frontends
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Segurança
security = HTTPBearer()

# Serviço de banco
db_service = WebDatabaseService()

# Utilitários JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(user_id: str = Depends(verify_token)):
    user = db_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    return user

# ENDPOINTS DE AUTENTICAÇÃO
@app.post("/auth/register", response_model=ApiResponse)
async def register_user(user_data: UserCreate):
    """Registra um novo usuário"""
    try:
        # Verificar se email já existe
        if user_data.email:
            existing_user = db_service.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email já cadastrado"
                )
        
        # Criar usuário
        user = db_service.create_user(user_data.dict())
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar usuário"
            )
        
        # Criar token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["id"])}, expires_delta=access_token_expires
        )
        
        return ApiResponse(
            success=True,
            message="Usuário criado com sucesso",
            data={
                "user": UserResponse(**user).dict(),
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.post("/auth/login", response_model=ApiResponse)
async def login_user(login_data: UserLogin):
    """Autentica um usuário"""
    try:
        if not login_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email é obrigatório"
            )
        
        # Autenticar usuário
        user = db_service.authenticate_user(login_data.email, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos"
            )
        
        # Criar token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["id"])}, expires_delta=access_token_expires
        )
        
        return ApiResponse(
            success=True,
            message="Login realizado com sucesso",
            data={
                "user": UserResponse(**user).dict(),
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.get("/auth/me", response_model=ApiResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Retorna informações do usuário autenticado"""
    return ApiResponse(
        success=True,
        message="Dados do usuário",
        data=UserResponse(**current_user).dict()
    )

# ENDPOINTS DE USUÁRIOS
@app.put("/users/profile", response_model=ApiResponse)
async def update_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza perfil do usuário"""
    try:
        updated_user = db_service.update_user(
            current_user["id"], 
            update_data.dict(exclude_unset=True)
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao atualizar perfil"
            )
        
        return ApiResponse(
            success=True,
            message="Perfil atualizado com sucesso",
            data=UserResponse(**updated_user).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINTS DE CATEGORIAS
@app.get("/categories", response_model=ApiResponse)
async def get_categories(
    category_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Lista categorias do usuário"""
    try:
        categories = db_service.get_user_categories(current_user["id"], category_type)
        
        return ApiResponse(
            success=True,
            message="Categorias listadas com sucesso",
            data={"categories": [CategoryResponse(**cat).dict() for cat in categories]}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.post("/categories", response_model=ApiResponse)
async def create_category(
    category_data: CategoryCreate,
    current_user: dict = Depends(get_current_user)
):
    """Cria uma nova categoria"""
    try:
        category = db_service.create_category(current_user["id"], category_data.dict())
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar categoria"
            )
        
        return ApiResponse(
            success=True,
            message="Categoria criada com sucesso",
            data=CategoryResponse(**category).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.put("/categories/{category_id}", response_model=ApiResponse)
async def update_category(
    category_id: str,
    update_data: CategoryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza uma categoria"""
    try:
        category = db_service.update_category(
            current_user["id"], 
            category_id, 
            update_data.dict(exclude_unset=True)
        )
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada"
            )
        
        return ApiResponse(
            success=True,
            message="Categoria atualizada com sucesso",
            data=CategoryResponse(**category).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.delete("/categories/{category_id}", response_model=ApiResponse)
async def delete_category(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deleta uma categoria"""
    try:
        success = db_service.delete_category(current_user["id"], category_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada"
            )
        
        return ApiResponse(
            success=True,
            message="Categoria deletada com sucesso"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINTS DE CARTÕES DE CRÉDITO
@app.get("/credit-cards", response_model=ApiResponse)
async def get_credit_cards(current_user: dict = Depends(get_current_user)):
    """Lista cartões de crédito do usuário"""
    try:
        cards = db_service.get_user_credit_cards(current_user["id"])
        
        return ApiResponse(
            success=True,
            message="Cartões listados com sucesso",
            data={"credit_cards": [CreditCardResponse(**card).dict() for card in cards]}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.post("/credit-cards", response_model=ApiResponse)
async def create_credit_card(
    card_data: CreditCardCreate,
    current_user: dict = Depends(get_current_user)
):
    """Cria um novo cartão de crédito"""
    try:
        card = db_service.create_credit_card(current_user["id"], card_data.dict())
        
        if not card:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar cartão"
            )
        
        return ApiResponse(
            success=True,
            message="Cartão criado com sucesso",
            data=CreditCardResponse(**card).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.put("/credit-cards/{card_id}", response_model=ApiResponse)
async def update_credit_card(
    card_id: str,
    update_data: CreditCardUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza um cartão de crédito"""
    try:
        card = db_service.update_credit_card(
            current_user["id"], 
            card_id, 
            update_data.dict(exclude_unset=True)
        )
        
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cartão não encontrado"
            )
        
        return ApiResponse(
            success=True,
            message="Cartão atualizado com sucesso",
            data=CreditCardResponse(**card).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.delete("/credit-cards/{card_id}", response_model=ApiResponse)
async def delete_credit_card(
    card_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deleta um cartão de crédito"""
    try:
        success = db_service.delete_credit_card(current_user["id"], card_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cartão não encontrado"
            )
        
        return ApiResponse(
            success=True,
            message="Cartão deletado com sucesso"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINTS DE TRANSAÇÕES
@app.get("/transactions", response_model=ApiResponse)
async def get_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    transaction_type: Optional[str] = None,
    credit_card_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Lista transações do usuário"""
    try:
        filters = {}
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        if category_id:
            filters['category_id'] = category_id
        if payment_method:
            filters['payment_method'] = payment_method
        if transaction_type:
            filters['transaction_type'] = transaction_type
        if credit_card_id:
            filters['credit_card_id'] = credit_card_id
        
        transactions = db_service.get_user_transactions(
            current_user["id"], filters, limit, offset
        )
        
        return ApiResponse(
            success=True,
            message="Transações listadas com sucesso",
            data={
                "transactions": [TransactionResponse(**t).dict() for t in transactions],
                "total": len(transactions),
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.post("/transactions", response_model=ApiResponse)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Cria uma nova transação"""
    try:
        transaction = db_service.create_transaction(current_user["id"], transaction_data.dict())
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar transação"
            )
        
        return ApiResponse(
            success=True,
            message="Transação criada com sucesso",
            data=TransactionResponse(**transaction).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.put("/transactions/{transaction_id}", response_model=ApiResponse)
async def update_transaction(
    transaction_id: str,
    update_data: TransactionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza uma transação"""
    try:
        transaction = db_service.update_transaction(
            current_user["id"], 
            transaction_id, 
            update_data.dict(exclude_unset=True)
        )
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transação não encontrada"
            )
        
        return ApiResponse(
            success=True,
            message="Transação atualizada com sucesso",
            data=TransactionResponse(**transaction).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.delete("/transactions/{transaction_id}", response_model=ApiResponse)
async def delete_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deleta uma transação"""
    try:
        success = db_service.delete_transaction(current_user["id"], transaction_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transação não encontrada"
            )
        
        return ApiResponse(
            success=True,
            message="Transação deletada com sucesso"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINTS DE ORÇAMENTOS
@app.get("/budgets", response_model=ApiResponse)
async def get_budgets(current_user: dict = Depends(get_current_user)):
    """Lista orçamentos do usuário"""
    try:
        budgets = db_service.get_user_budgets(current_user["id"])
        
        return ApiResponse(
            success=True,
            message="Orçamentos listados com sucesso",
            data={"budgets": [BudgetResponse(**budget).dict() for budget in budgets]}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@app.post("/budgets", response_model=ApiResponse)
async def create_budget(
    budget_data: BudgetCreate,
    current_user: dict = Depends(get_current_user)
):
    """Cria um novo orçamento"""
    try:
        budget = db_service.create_budget(current_user["id"], budget_data.dict())
        
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao criar orçamento"
            )
        
        return ApiResponse(
            success=True,
            message="Orçamento criado com sucesso",
            data=BudgetResponse(**budget).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINTS DE DASHBOARD
@app.get("/dashboard", response_model=ApiResponse)
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    """Retorna dados do dashboard"""
    try:
        dashboard_data = db_service.get_dashboard_data(current_user["id"])
        
        return ApiResponse(
            success=True,
            message="Dados do dashboard",
            data=dashboard_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

# ENDPOINT DE SAÚDE
@app.get("/health")
async def health_check():
    """Verifica se a API está funcionando"""
    return {"status": "ok", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Iniciando API REST do Assistente Financeiro...")
    print("📊 Endpoints disponíveis:")
    print("   - Autenticação: /auth/*")
    print("   - Usuários: /users/*")
    print("   - Categorias: /categories")
    print("   - Cartões: /credit-cards")
    print("   - Transações: /transactions")
    print("   - Orçamentos: /budgets")
    print("   - Dashboard: /dashboard")
    
    uvicorn.run(
        "web_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )