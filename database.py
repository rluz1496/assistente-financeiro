from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Verificar se as variáveis estão definidas
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ AVISO: Variáveis SUPABASE_URL e SUPABASE_ANON_KEY não encontradas no .env")
    print("Usando modo mock para desenvolvimento local")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
