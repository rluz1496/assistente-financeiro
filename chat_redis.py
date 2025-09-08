import json
import redis
from typing import List, Optional
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
import os
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
    
    def add_messages(self, user_id: str, messages: bytes):
        """
        Adiciona mensagens ao histórico do usuário
        
        Args:
            user_id: ID único do usuário  
            messages: Mensagens serializadas em bytes
        """
        try:
            chat_key = self._get_chat_key(user_id)
            message_data = messages.decode('utf-8')
            
            if self.redis_client:
                # Usar Redis
                # Adicionar à lista com timestamp
                import time
                timestamp = int(time.time())
                
                # Usar lista Redis para manter ordem cronológica
                self.redis_client.lpush(chat_key, json.dumps({
                    "timestamp": timestamp,
                    "data": message_data
                }))
                
                # Manter apenas últimas 100 mensagens por usuário
                self.redis_client.ltrim(chat_key, 0, 99)
                
                # Definir expiração de 7 dias para chaves inativas
                self.redis_client.expire(chat_key, 7 * 24 * 3600)
                
            else:
                # Fallback: memória local
                if user_id not in self._local_cache:
                    self._local_cache[user_id] = []
                
                self._local_cache[user_id].insert(0, message_data)
                
                # Manter apenas últimas 100 mensagens
                if len(self._local_cache[user_id]) > 100:
                    self._local_cache[user_id] = self._local_cache[user_id][:100]
                
        except Exception as e:
            print(f"❌ Erro ao salvar mensagens: {e}")
    
    def get_messages(self, user_id: str, limit: int = 50) -> List[ModelMessage]:
        """
        Recupera mensagens do histórico do usuário
        
        Args:
            user_id: ID único do usuário
            limit: Número máximo de mensagens (padrão 50)
            
        Returns:
            Lista de mensagens do modelo
        """
        try:
            chat_key = self._get_chat_key(user_id)
            
            if self.redis_client:
                # Usar Redis
                raw_messages = self.redis_client.lrange(chat_key, 0, limit - 1)
                
                messages = []
                for raw_msg in reversed(raw_messages):  # Reverter para ordem cronológica
                    try:
                        msg_obj = json.loads(raw_msg)
                        message_data = msg_obj["data"]
                        messages.extend(ModelMessagesTypeAdapter.validate_json(message_data))
                    except Exception as e:
                        print(f"⚠️ Erro ao processar mensagem: {e}")
                        continue
                
                return messages
                
            else:
                # Fallback: memória local
                if user_id not in self._local_cache:
                    return []
                
                messages = []
                for message_data in reversed(self._local_cache[user_id][:limit]):
                    try:
                        messages.extend(ModelMessagesTypeAdapter.validate_json(message_data))
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
