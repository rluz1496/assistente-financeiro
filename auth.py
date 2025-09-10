"""
Sistema de autenticação simples usando sessions no Redis
"""
import secrets
import bcrypt
import json
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functions_database import supabase
from chat_redis import ChatRedisDatabase


class AuthUtils:
    """Utilitários para autenticação"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash da senha usando bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifica se a senha confere com o hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """
        Valida força da senha
        
        Returns:
            Dict com 'valid' (bool) e 'errors' (list)
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Senha deve ter pelo menos 8 caracteres")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Senha deve conter pelo menos uma letra maiúscula")
        
        if not re.search(r'[a-z]', password):
            errors.append("Senha deve conter pelo menos uma letra minúscula")
        
        if not re.search(r'\d', password):
            errors.append("Senha deve conter pelo menos um número")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Valida formato de email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Valida formato de telefone brasileiro"""
        clean_phone = re.sub(r'[^\d]', '', phone)
        return len(clean_phone) in [10, 11] and clean_phone.isdigit()
    
    @staticmethod
    def clean_phone(phone: str) -> str:
        """Remove formatação do telefone"""
        return re.sub(r'[^\d]', '', phone)


class SessionAuth:
    """Sistema de autenticação com sessions no Redis"""
    
    def __init__(self):
        self.redis_db = ChatRedisDatabase()
        self.session_prefix = "auth_session:"
        self.user_session_prefix = "user_sessions:"
        self.session_duration = 24 * 3600  # 24 horas
    
    def create_session(self, user_id: str, user_data: Dict) -> str:
        """
        Cria sessão do usuário
        
        Args:
            user_id: ID do usuário
            user_data: Dados do usuário para armazenar na sessão
            
        Returns:
            session_token: Token da sessão
        """
        try:
            # Gerar token único
            session_token = secrets.token_urlsafe(32)
            
            # Dados da sessão
            session_data = {
                "user_id": user_id,
                "user_data": user_data,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(seconds=self.session_duration)).isoformat()
            }
            
            # Salvar no Redis
            if self.redis_db.redis_client:
                session_key = f"{self.session_prefix}{session_token}"
                self.redis_db.redis_client.setex(
                    session_key, 
                    self.session_duration, 
                    json.dumps(session_data, ensure_ascii=False)
                )
                
                # Mapear usuário -> sessões (para logout múltiplas sessões)
                user_session_key = f"{self.user_session_prefix}{user_id}"
                self.redis_db.redis_client.sadd(user_session_key, session_token)
                self.redis_db.redis_client.expire(user_session_key, self.session_duration)
                
                # Atualizar último login
                self._update_last_login(user_id)
                
                print(f"✅ Sessão criada para usuário {user_id}")
                return session_token
            else:
                print("❌ Redis não disponível para criar sessão")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao criar sessão: {e}")
            return None
    
    def get_session(self, session_token: str) -> Optional[Dict]:
        """
        Recupera dados da sessão
        
        Args:
            session_token: Token da sessão
            
        Returns:
            Dados da sessão ou None se inválida
        """
        try:
            if not self.redis_db.redis_client:
                return None
            
            session_key = f"{self.session_prefix}{session_token}"
            session_data = self.redis_db.redis_client.get(session_key)
            
            if session_data:
                data = json.loads(session_data)
                
                # Verificar se não expirou
                expires_at = datetime.fromisoformat(data["expires_at"])
                if datetime.now() > expires_at:
                    self.delete_session(session_token)
                    return None
                
                # Atualizar última atividade e estender sessão
                data["last_activity"] = datetime.now().isoformat()
                data["expires_at"] = (datetime.now() + timedelta(seconds=self.session_duration)).isoformat()
                
                self.redis_db.redis_client.setex(
                    session_key, 
                    self.session_duration, 
                    json.dumps(data, ensure_ascii=False)
                )
                
                return data
            
            return None
            
        except Exception as e:
            print(f"❌ Erro ao recuperar sessão: {e}")
            return None
    
    def delete_session(self, session_token: str) -> bool:
        """
        Remove sessão (logout)
        
        Args:
            session_token: Token da sessão
            
        Returns:
            True se removida com sucesso
        """
        try:
            if not self.redis_db.redis_client:
                return False
            
            session_key = f"{self.session_prefix}{session_token}"
            
            # Recuperar dados da sessão antes de deletar
            session_data = self.redis_db.redis_client.get(session_key)
            if session_data:
                data = json.loads(session_data)
                user_id = data.get("user_id")
                
                # Remover da lista de sessões do usuário
                if user_id:
                    user_session_key = f"{self.user_session_prefix}{user_id}"
                    self.redis_db.redis_client.srem(user_session_key, session_token)
            
            # Deletar sessão
            result = self.redis_db.redis_client.delete(session_key) > 0
            print(f"✅ Sessão {session_token[:8]}... removida")
            return result
            
        except Exception as e:
            print(f"❌ Erro ao deletar sessão: {e}")
            return False
    
    def delete_all_user_sessions(self, user_id: str) -> int:
        """
        Remove todas as sessões do usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Número de sessões removidas
        """
        try:
            if not self.redis_db.redis_client:
                return 0
            
            user_session_key = f"{self.user_session_prefix}{user_id}"
            session_tokens = self.redis_db.redis_client.smembers(user_session_key)
            
            count = 0
            for token in session_tokens:
                session_key = f"{self.session_prefix}{token}"
                if self.redis_db.redis_client.delete(session_key):
                    count += 1
            
            # Limpar lista de sessões do usuário
            self.redis_db.redis_client.delete(user_session_key)
            
            print(f"✅ {count} sessões removidas para usuário {user_id}")
            return count
            
        except Exception as e:
            print(f"❌ Erro ao deletar sessões do usuário: {e}")
            return 0
    
    def get_user_sessions(self, user_id: str) -> list:
        """
        Lista todas as sessões ativas de um usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Lista com informações das sessões ativas
        """
        try:
            if not self.redis_db.redis_client:
                return []
            
            user_session_key = f"{self.user_session_prefix}{user_id}"
            session_tokens = self.redis_db.redis_client.smembers(user_session_key)
            
            sessions = []
            for token in session_tokens:
                session_data = self.get_session(token)
                if session_data:
                    sessions.append({
                        "token": token[:8] + "...",  # Mascarar token
                        "created_at": session_data["created_at"],
                        "last_activity": session_data["last_activity"],
                        "expires_at": session_data["expires_at"]
                    })
            
            return sessions
            
        except Exception as e:
            print(f"❌ Erro ao listar sessões: {e}")
            return []
    
    def _update_last_login(self, user_id: str):
        """Atualiza último login do usuário no banco"""
        try:
            if supabase:
                supabase.table("users").update({
                    "last_login": datetime.now().isoformat()
                }).eq("id", user_id).execute()
        except Exception as e:
            print(f"⚠️ Erro ao atualizar último login: {e}")


# Instância global do sistema de autenticação
auth_system = SessionAuth()
