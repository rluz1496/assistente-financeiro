"""
Funções para o sistema de onboarding
Cadastro de novos usuários com categorias e cartões
"""
from supabase import create_client, Client
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

load_dotenv()

# Configuração Supabase
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)

def create_user_onboarding(phone_number: str, name: str, cpf: str = None) -> str:
    """
    Cria um novo usuário no sistema durante o onboarding
    
    Args:
        phone_number: Número de telefone (sem o 9)
        name: Nome completo do usuário
        cpf: CPF do usuário (opcional)
        
    Returns:
        str: ID do usuário criado
    """
    try:
        user_data = {
            "id": str(uuid.uuid4()),
            "phone_number": phone_number,
            "name": name,
            "cpf": cpf,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("users").insert(user_data).execute()
        
        if result.data:
            print(f"✅ Usuário criado: {name} ({phone_number})")
            return result.data[0]["id"]
        else:
            raise Exception("Erro ao criar usuário")
            
    except Exception as e:
        print(f"❌ Erro ao criar usuário: {e}")
        raise e

def create_user_categories(user_id: str, categories: List[Dict[str, str]]) -> List[str]:
    """
    Cria categorias personalizadas do usuário
    
    Args:
        user_id: ID do usuário
        categories: Lista de categorias [{"name": "Nome", "type": "expense|income", "color": "#hex"}]
        
    Returns:
        List[str]: IDs das categorias criadas
    """
    try:
        category_ids = []
        
        for category in categories:
            category_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": category["name"],
                "type": category.get("type", "expense"),
                "color": category.get("color", "#007bff"),
                "created_at": datetime.now().isoformat()
            }
            
            result = supabase.table("categories").insert(category_data).execute()
            
            if result.data:
                category_ids.append(result.data[0]["id"])
                print(f"✅ Categoria criada: {category['name']}")
            else:
                print(f"❌ Erro ao criar categoria: {category['name']}")
        
        return category_ids
        
    except Exception as e:
        print(f"❌ Erro ao criar categorias: {e}")
        raise e

def create_user_credit_cards(user_id: str, credit_cards: List[Dict[str, Any]]) -> List[str]:
    """
    Cria cartões de crédito do usuário
    
    Args:
        user_id: ID do usuário
        credit_cards: Lista de cartões [{"name": "Nome", "closing_day": int, "due_day": int, "limit": float}]
        
    Returns:
        List[str]: IDs dos cartões criados
    """
    try:
        card_ids = []
        
        for card in credit_cards:
            card_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": card["name"],
                "closing_day": int(card["closing_day"]),
                "due_day": int(card["due_day"]),
                "credit_limit": float(card.get("limit", 0)),
                "created_at": datetime.now().isoformat()
            }
            
            result = supabase.table("credit_cards").insert(card_data).execute()
            
            if result.data:
                card_ids.append(result.data[0]["id"])
                print(f"✅ Cartão criado: {card['name']}")
            else:
                print(f"❌ Erro ao criar cartão: {card['name']}")
        
        return card_ids
        
    except Exception as e:
        print(f"❌ Erro ao criar cartões: {e}")
        raise e

def complete_onboarding(phone_number: str, name: str, cpf: str, 
                       categories: List[Dict[str, str]], 
                       credit_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Completa todo o processo de onboarding
    
    Args:
        phone_number: Telefone do usuário
        name: Nome completo
        cpf: CPF
        categories: Lista de categorias
        credit_cards: Lista de cartões
        
    Returns:
        Dict com resultado do onboarding
    """
    try:
        # 1. Criar usuário
        user_id = create_user_onboarding(phone_number, name, cpf)
        
        # 2. Criar categorias padrão + personalizadas
        default_categories = [
            {"name": "Alimentação", "type": "expense", "color": "#ff6b6b"},
            {"name": "Transporte", "type": "expense", "color": "#4ecdc4"},
            {"name": "Moradia", "type": "expense", "color": "#45b7d1"},
            {"name": "Saúde", "type": "expense", "color": "#96ceb4"},
            {"name": "Educação", "type": "expense", "color": "#ffeaa7"},
            {"name": "Lazer", "type": "expense", "color": "#dda0dd"},
            {"name": "Salário", "type": "income", "color": "#00b894"},
            {"name": "Freelance", "type": "income", "color": "#00cec9"},
            {"name": "Investimentos", "type": "income", "color": "#6c5ce7"}
        ]
        
        all_categories = default_categories + categories
        category_ids = create_user_categories(user_id, all_categories)
        
        # 3. Criar cartões de crédito
        card_ids = create_user_credit_cards(user_id, credit_cards)
        
        return {
            "success": True,
            "user_id": user_id,
            "categories_created": len(category_ids),
            "cards_created": len(card_ids),
            "message": f"Onboarding concluído para {name}!"
        }
        
    except Exception as e:
        print(f"❌ Erro no onboarding: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Erro ao completar cadastro"
        }

def check_user_exists(phone_number: str) -> bool:
    """
    Verifica se usuário já existe pelo telefone
    
    Args:
        phone_number: Número de telefone
        
    Returns:
        bool: True se usuário existe
    """
    try:
        result = supabase.table("users").select("id").eq("phone_number", phone_number).execute()
        return len(result.data) > 0
    except:
        return False
