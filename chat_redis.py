import json
import redis
from typing import List, Optional
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class ChatRedisDatabase:
    """
    Gerenciador de histórico de chat usando Redis para melhor performance
    """
    def __init__(self, redis_url: str = None, key_prefix: str = "chat:"):
        """
        Inicializa conexão com Redis
        
        Args:
            redis_url: URL de conexão Redis (padrão: local)
            key_prefix: Prefixo para chaves no Redis
        """
        self.key_prefix = key_prefix
        
        # Configuração do Redis
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Testar conexão
            self.redis_client.ping()
            print("✅ Conectado ao Redis com sucesso!")
            
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Erro ao conectar Redis: {e}")
            print("🔄 Usando modo fallback (memória local)")
            self.redis_client = None
            self._local_cache = {}  # Fallback para memória local
    
    def _get_chat_key(self, user_id: str) -> str:
        """Gera chave única para o chat do usuário"""
        return f"{self.key_prefix}{user_id}"
    
    def _get_confirmation_key(self, user_id: str) -> str:
        """Gera chave única para dados de confirmação do usuário"""
        return f"confirmation:{user_id}"
    
    def save_pending_confirmation(self, user_id: str, data: dict, expires_in: int = 300) -> bool:
        """
        Salva dados pendentes de confirmação (válidos por 5 minutos)
        
        Args:
            user_id: ID do usuário
            data: Dados da transação pendente 
            expires_in: Tempo de expiração em segundos (padrão: 300s = 5min)
        """
        try:
            key = self._get_confirmation_key(user_id)
            
            if self.redis_client:
                # Salvar no Redis com expiração
                self.redis_client.setex(
                    key,
                    expires_in,
                    json.dumps(data, ensure_ascii=False)
                )
                return True
            else:
                # Fallback: salvar em memória local (sem expiração automática)
                self._local_cache[key] = data
                return True
                
        except Exception as e:
            print(f"❌ Erro ao salvar confirmação pendente: {e}")
            return False
    
    def get_pending_confirmation(self, user_id: str) -> Optional[dict]:
        """
        Recupera dados pendentes de confirmação
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Dados da transação pendente ou None se não existir
        """
        try:
            key = self._get_confirmation_key(user_id)
            
            if self.redis_client:
                # Buscar no Redis
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
                return None
            else:
                # Fallback: buscar em memória local
                return self._local_cache.get(key)
                
        except Exception as e:
            print(f"❌ Erro ao recuperar confirmação pendente: {e}")
            return None
    
    def clear_pending_confirmation(self, user_id: str) -> bool:
        """
        Remove dados pendentes de confirmação
        
        Args:
            user_id: ID do usuário
        """
        try:
            key = self._get_confirmation_key(user_id)
            
            if self.redis_client:
                # Remover do Redis
                self.redis_client.delete(key)
                return True
            else:
                # Fallback: remover da memória local
                if key in self._local_cache:
                    del self._local_cache[key]
                return True
                
        except Exception as e:
            print(f"❌ Erro ao limpar confirmação pendente: {e}")
            return False
    
    def add_messages(self, user_id: str, messages_json: bytes):
        """
        Adiciona novas mensagens ao histórico do usuário no Redis.
        
        Args:
            user_id: ID do usuário
            messages_json: Mensagens em formato JSON bytes (do Pydantic AI)
        """
        try:
            chat_key = self._get_chat_key(user_id)
            
            # Converter bytes para string se necessário
            if isinstance(messages_json, bytes):
                messages_str = messages_json.decode('utf-8')
            else:
                messages_str = json.dumps(messages_json) if not isinstance(messages_json, str) else messages_json
            
            # Parse das mensagens
            messages_list = json.loads(messages_str)
            
            # Filtrar mensagens válidas (evita problemas com tool calls órfãs)
            valid_messages = []
            for message in messages_list:
                # Não salvar mensagens de tool sem contexto adequado
                if isinstance(message, dict):
                    # Verificar se é mensagem de tool órfã
                    parts = message.get('parts', [])
                    if parts and isinstance(parts[0], dict) and parts[0].get('role') == 'tool':
                        print(f"⚠️ Pulando mensagem de tool órfã")
                        continue  # Pular mensagens de tool órfãs
                    
                valid_messages.append(message)
            
            if self.redis_client:
                # Adicionar apenas mensagens válidas ao Redis
                for message in valid_messages:
                    message_with_timestamp = {
                        "timestamp": datetime.now().isoformat(),
                        "data": message
                    }
                    
                    # Adicionar mensagem ao início da lista (LPUSH)
                    self.redis_client.lpush(chat_key, json.dumps(message_with_timestamp))
                
                # Manter apenas as últimas 100 mensagens
                self.redis_client.ltrim(chat_key, 0, 99)
                
                # Definir expiração de 7 dias
                self.redis_client.expire(chat_key, 7 * 24 * 3600)
                
                print(f"💾 {len(valid_messages)} mensagens válidas adicionadas ao Redis para usuário {user_id}")
                
            else:
                # Fallback: memória local
                if user_id not in self._local_cache:
                    self._local_cache[user_id] = []
                
                for message in valid_messages:
                    self._local_cache[user_id].insert(0, json.dumps(message))
                
                # Manter apenas últimas 100 mensagens
                if len(self._local_cache[user_id]) > 100:
                    self._local_cache[user_id] = self._local_cache[user_id][:100]
                
        except Exception as e:
            print(f"❌ Erro ao adicionar mensagens no Redis: {e}")
            raise e
    
    def get_messages(self, user_id: str, limit: int = 50) -> List[ModelMessage]:
        """
        Recupera mensagens do histórico do usuário.
        
        Args:
            user_id: ID do usuário
            limit: Número máximo de mensagens para retornar
            
        Returns:
            Lista de mensagens no formato do Pydantic AI
        """
        try:
            chat_key = self._get_chat_key(user_id)
            
            if self.redis_client:
                # Buscar mensagens do Redis (LRANGE pega da mais recente para mais antiga)
                raw_messages = self.redis_client.lrange(chat_key, 0, limit - 1)
                
                if not raw_messages:
                    return []
                
                # Converter de volta para objetos de mensagem do Pydantic AI
                messages = []
                for raw_msg in reversed(raw_messages):  # Reverter para ordem cronológica
                    try:
                        msg_data = json.loads(raw_msg)
                        message_content = msg_data.get("data")
                        
                        # Usar o ModelMessagesTypeAdapter para deserializar
                        if isinstance(message_content, str):
                            parsed_message = ModelMessagesTypeAdapter.validate_json(message_content)[0]
                        else:
                            parsed_message = ModelMessagesTypeAdapter.validate_python([message_content])[0]
                        messages.append(parsed_message)
                        
                    except Exception as parse_error:
                        print(f"⚠️ Erro ao processar mensagem: {parse_error}")
                        continue
                
                print(f"📚 {len(messages)} mensagens recuperadas do Redis para usuário {user_id}")
                return messages
                
            else:
                # Fallback: memória local
                if user_id not in self._local_cache:
                    return []
                
                messages = []
                for message_data in reversed(self._local_cache[user_id][:limit]):
                    try:
                        if isinstance(message_data, str):
                            parsed_message = ModelMessagesTypeAdapter.validate_json(message_data)[0]
                        else:
                            parsed_message = ModelMessagesTypeAdapter.validate_python([message_data])[0]
                        messages.append(parsed_message)
                    except Exception as e:
                        print(f"⚠️ Erro ao processar mensagem: {e}")
                        continue
                
                return messages
                
        except Exception as e:
            print(f"❌ Erro ao carregar mensagens: {e}")
            return []
    
    def clear_chat(self, user_id: str):
        """
        Limpa histórico de chat de um usuário específico
        
        Args:
            user_id: ID único do usuário
        """
        try:
            chat_key = self._get_chat_key(user_id)
            
            if self.redis_client:
                self.redis_client.delete(chat_key)
                print(f"✅ Histórico do usuário {user_id} limpo do Redis")
            else:
                if user_id in self._local_cache:
                    del self._local_cache[user_id]
                print(f"✅ Histórico do usuário {user_id} limpo da memória local")
                
        except Exception as e:
            print(f"❌ Erro ao limpar chat: {e}")
    
    def get_chat_stats(self, user_id: str) -> dict:
        """
        Retorna estatísticas do chat do usuário
        
        Args:
            user_id: ID único do usuário
            
        Returns:
            Dicionário com estatísticas
        """
        try:
            chat_key = self._get_chat_key(user_id)
            
            if self.redis_client:
                message_count = self.redis_client.llen(chat_key)
                ttl = self.redis_client.ttl(chat_key)
                
                return {
                    "message_count": message_count,
                    "ttl_seconds": ttl,
                    "storage": "redis"
                }
            else:
                message_count = len(self._local_cache.get(user_id, []))
                
                return {
                    "message_count": message_count,
                    "ttl_seconds": -1,
                    "storage": "local_memory"
                }
                
        except Exception as e:
            print(f"❌ Erro ao obter estatísticas: {e}")
            return {"message_count": 0, "ttl_seconds": -1, "storage": "error"}
    
    def close(self):
        """Fecha conexão com Redis"""
        if self.redis_client:
            try:
                self.redis_client.close()
                print("✅ Conexão Redis fechada")
            except Exception as e:
                print(f"⚠️ Erro ao fechar Redis: {e}")


# Manter compatibilidade com código existente
class ChatDatabase(ChatRedisDatabase):
    """
    Classe de compatibilidade que mantém a interface original
    mas usa Redis internamente
    """
    def __init__(self, file_path: str = None):
        # Ignorar file_path e usar Redis
        super().__init__()
        self._default_user = "default_user"  # Para compatibilidade
    
    def add_messages(self, messages: bytes):
        """Compatibilidade: usa usuário padrão"""
        super().add_messages(self._default_user, messages)
    
    def get_messages(self) -> List[ModelMessage]:
        """Compatibilidade: usa usuário padrão"""
        return super().get_messages(self._default_user)
