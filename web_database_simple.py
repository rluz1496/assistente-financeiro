"""
Funções de banco de dados para API REST do Frontend
Operações CRUD para todas as entidades do sistema
"""
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from database import supabase
import hashlib

class WebDatabaseService:
    def __init__(self):
        self.supabase = supabase
    
    # ======= USUÁRIOS =======
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar novo usuário"""
        try:
            # Gerar hash da senha (implementar depois)
            user_data['id'] = str(uuid.uuid4())
            user_data['created_at'] = datetime.now().isoformat()
            user_data['is_active'] = True
            user_data['role'] = 'user'
            user_data['onboarding_completed'] = False
            
            if not self.supabase:
                return {"error": "Database not available"}
                
            result = self.supabase.table("users").insert(user_data).execute()
            if result.data:
                return result.data[0]
            return {"error": "Failed to create user"}
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Buscar usuário por ID"""
        try:
            if not self.supabase:
                return None
                
            result = self.supabase.table("users").select("*").eq("id", user_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Database error: {str(e)}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Buscar usuário por email"""
        try:
            if not self.supabase:
                return None
                
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Database error: {str(e)}")
            return None
    
    # ======= CATEGORIAS =======
    
    def create_category(self, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar nova categoria"""
        try:
            category_data['id'] = str(uuid.uuid4())
            category_data['created_at'] = datetime.now().isoformat()
            
            if not self.supabase:
                return {"error": "Database not available"}
                
            result = self.supabase.table("categories").insert(category_data).execute()
            if result.data:
                return result.data[0]
            return {"error": "Failed to create category"}
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def get_categories_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Buscar categorias do usuário"""
        try:
            if not self.supabase:
                return []
                
            result = self.supabase.table("categories").select("*").eq("user_id", user_id).execute()
            return result.data or []
        except Exception as e:
            print(f"Database error: {str(e)}")
            return []
    
    # ======= CARTÕES DE CRÉDITO =======
    
    def create_credit_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar novo cartão de crédito"""
        try:
            card_data['id'] = str(uuid.uuid4())
            card_data['created_at'] = datetime.now().isoformat()
            
            if not self.supabase:
                return {"error": "Database not available"}
                
            result = self.supabase.table("credit_cards").insert(card_data).execute()
            if result.data:
                return result.data[0]
            return {"error": "Failed to create credit card"}
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def get_credit_cards_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Buscar cartões do usuário"""
        try:
            if not self.supabase:
                return []
                
            result = self.supabase.table("credit_cards").select("*").eq("user_id", user_id).execute()
            return result.data or []
        except Exception as e:
            print(f"Database error: {str(e)}")
            return []
    
    # ======= TRANSAÇÕES =======
    
    def create_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar nova transação"""
        try:
            transaction_data['id'] = str(uuid.uuid4())
            transaction_data['created_at'] = datetime.now().isoformat()
            
            if not self.supabase:
                return {"error": "Database not available"}
                
            result = self.supabase.table("transactions").insert(transaction_data).execute()
            if result.data:
                return result.data[0]
            return {"error": "Failed to create transaction"}
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def get_transactions_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Buscar transações do usuário"""
        try:
            if not self.supabase:
                return []
                
            result = self.supabase.table("transactions").select("*").eq("user_id", user_id).execute()
            return result.data or []
        except Exception as e:
            print(f"Database error: {str(e)}")
            return []
    
    # ======= ORÇAMENTOS =======
    
    def create_budget(self, budget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Criar novo orçamento"""
        try:
            budget_data['id'] = str(uuid.uuid4())
            budget_data['created_at'] = datetime.now().isoformat()
            budget_data['is_active'] = True
            
            if not self.supabase:
                return {"error": "Database not available"}
                
            result = self.supabase.table("budgets").insert(budget_data).execute()
            if result.data:
                return result.data[0]
            return {"error": "Failed to create budget"}
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def get_budgets_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Buscar orçamentos do usuário"""
        try:
            if not self.supabase:
                return []
                
            result = self.supabase.table("budgets").select("*").eq("user_id", user_id).execute()
            return result.data or []
        except Exception as e:
            print(f"Database error: {str(e)}")
            return []