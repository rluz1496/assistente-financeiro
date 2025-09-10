"""
Processador de mídia para áudio e imagens usando OpenAI APIs
"""
import httpx
import base64
import io
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuração OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configurações Evolution API
EVOLUTION_BASE_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_TOKEN", "")

class MediaProcessor:
    """Processador de mídia para áudio e imagem"""
    
    @staticmethod
    async def get_media_from_evolution(message_id: str, instance: str, convert_to_mp4: str) -> Optional[str]:
        """
        Baixa mídia da Evolution API e retorna como base64
        
        Args:
            message_id: ID da mensagem
            instance: Nome da instância
            convert_to_mp4: Se deve converter áudio para MP4 (para áudio usar False para MP3)
            
        Returns:
            String base64 do arquivo ou None se houver erro
        """
        try:
            print(f"🔍 INICIANDO DOWNLOAD DE MÍDIA:")
            print(f"   📧 Message ID: {message_id}")
            print(f"   🏢 Instance: {instance}")
            print(f"   🎬 Convert to MP4: {convert_to_mp4}")
            
            # Usar o formato correto do endpoint
            url = f"{EVOLUTION_BASE_URL}chat/getBase64FromMediaMessage/{instance}"
            
            payload = {
                "convertToMp4": "false",
                "message": {
                    "key": {
                        "id": message_id
                    }
                }
            }
            
            headers = {
                "apikey": "429683C4C977415CAAFCCE10F7D57E11"
            }
            
            print(f"📥 Baixando mídia - URL: {url}")
            print(f"📦 Payload: {payload}")
            print(f"🔑 Headers: {headers}")
            print(f"🏢 Instance: {instance}")
            print(f"🆔 Message ID: {message_id}")
            
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.post(url, json=payload, headers=headers)
                
                print(f"📋 Response status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"📄 Response data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                    
                    # A Evolution API geralmente retorna {"base64": "data:audio/mp3;base64,xxxxx"}
                    if "base64" in data:
                        base64_data = data["base64"]
                        # Remove o prefixo se existir (data:audio/mp3;base64,)
                        if "," in base64_data:
                            base64_data = base64_data.split(",")[1]
                        return base64_data
                    return None
                else:
                    print(f"❌ Erro ao baixar mídia: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Erro ao baixar mídia da Evolution: {e}")
            return None
    
    @staticmethod
    async def transcribe_audio(base64_audio: str) -> Optional[str]:
        """
        Transcreve áudio usando OpenAI Whisper
        
        Args:
            base64_audio: Áudio em base64
            
        Returns:
            Texto transcrito ou None se houver erro
        """
        try:
            # Decodificar base64 para bytes
            audio_bytes = base64.b64decode(base64_audio)
            
            # Criar um arquivo temporário em memória
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"  # Whisper precisa do nome com extensão
            
            # Transcrever usando Whisper
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="pt"  # Português
            )
            
            return transcript.text
            
        except Exception as e:
            print(f"❌ Erro ao transcrever áudio: {e}")
            return None
    
    @staticmethod
    async def extract_receipt_data(base64_image: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados de comprovante usando OpenAI Vision
        
        Args:
            base64_image: Imagem em base64
            
        Returns:
            Dicionário com dados extraídos ou None se houver erro
        """
        try:
            # Prompt específico para extrair dados de comprovantes
            prompt = """
            Analise esta imagem de comprovante/recibo financeiro e extraia as seguintes informações em formato JSON:

            {
                "valor": número (apenas o valor numérico, ex: 50.75),
                "descricao": "string (nome do estabelecimento ou descrição da compra)",
                "data": "YYYY-MM-DD (data da transação, se não encontrar use a data atual)",
                "metodo_pagamento": "pix|cartao_credito|cartao_debito|dinheiro (tente identificar pelo comprovante)",
                "categoria_sugerida": "string (categoria que melhor se encaixa: Alimentação, Transporte, Saúde, Lazer, Moradia, etc)",
                "estabelecimento": "string (nome do estabelecimento/loja)",
                "tipo_comprovante": "string (pix, ted, compra_cartao, etc)",
                "confianca": número de 0 a 1 (quão confiante está na extração)
            }

            Se não conseguir identificar algum campo, coloque null.
            Se a imagem não for um comprovante financeiro, retorne {"erro": "Não é um comprovante financeiro"}.
            
            IMPORTANTE: Retorne APENAS o JSON, sem texto adicional.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo com capacidade de visão
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            # Extrair e parsear resposta JSON
            response_text = response.choices[0].message.content.strip()
            
            # Tentar fazer parse do JSON
            import json
            try:
                data = json.loads(response_text)
                return data
            except json.JSONDecodeError:
                # Se não conseguir fazer parse, tentar extrair JSON da resposta
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    print(f"❌ Resposta não é JSON válido: {response_text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Erro ao extrair dados do comprovante: {e}")
            return None

# Função auxiliar para detectar tipo de mídia
def detect_media_type(message_data) -> Optional[str]:
    """
    Detecta o tipo de mídia na mensagem
    
    Returns:
        "audio", "image", "text" ou None
    """
    # Se for um objeto Pydantic, usar atributos diretos
    if hasattr(message_data, 'message'):
        message = message_data.message
    else:
        # Se for um dict, usar get()
        message = message_data.get("message", {})
    
    # Verificar atributos do objeto Pydantic ou chaves do dict
    if hasattr(message, 'audioMessage') or (isinstance(message, dict) and "audioMessage" in message):
        return "audio"
    elif hasattr(message, 'imageMessage') or (isinstance(message, dict) and "imageMessage" in message):
        return "image"
    elif hasattr(message, 'conversation') or hasattr(message, 'extendedTextMessage') or \
         (isinstance(message, dict) and ("conversation" in message or "extendedTextMessage" in message)):
        return "text"
    else:
        return None

# Função para extrair ID da mensagem
def extract_message_id(message_data) -> Optional[str]:
    """Extrai o ID da mensagem para download de mídia"""
    print(f"📧 Extraindo message_id de: {type(message_data)}")
    
    # Se for um objeto Pydantic, usar atributos diretos
    if hasattr(message_data, 'key'):
        key = message_data.key
        if hasattr(key, 'id'):
            print(f"✅ ID encontrado (Pydantic): {key.id}")
            return key.id
    else:
        # Se for um dict, usar get()
        key = message_data.get("key", {})
        message_id = key.get("id")
        print(f"✅ ID encontrado (dict): {message_id}")
        print(f"📋 Estrutura key: {key}")
        return message_id
    
    print(f"❌ ID não encontrado")
    return None
