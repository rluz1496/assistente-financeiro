# 🚀 GUIA DE DEPLOY COMPLETO

## 📋 PRÉ-REQUISITOS

1. ✅ Conta no GitHub
2. ✅ Conta no Railway (para backend)  
3. ✅ Conta no Vercel (para frontend - opcional)
4. ✅ Credenciais configuradas (Supabase, Redis, OpenAI, Evolution)

---

## 🔧 BACKEND - RAILWAY

### 1. Criar repositório no GitHub
```bash
cd assistente-financeiro-backend
git init
git add .
git commit -m "Initial backend commit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/assistente-financeiro-backend.git
git push -u origin main
```

### 2. Deploy no Railway
1. Acesse https://railway.app
2. Clique "Deploy from GitHub repo"
3. Selecione o repositório backend
4. Configure as variáveis de ambiente:

```env
SUPABASE_URL=sua_url_supabase
SUPABASE_ANON_KEY=sua_chave_supabase
DATABASE_URL=sua_url_postgres
REDIS_URL=sua_url_redis
OPENAI_API_KEY=sua_chave_openai
EVOLUTION_API_URL=sua_url_evolution
EVOLUTION_INSTANCE=sua_instancia
EVOLUTION_TOKEN=seu_token
BASE_URL=https://seu-backend.railway.app
```

### 3. Configurar webhook Evolution
Após deploy, atualize o webhook na Evolution API:

```bash
curl -X POST "https://evolution-evolution-api.tgss21.easypanel.host/webhook/set/teste_agente_fin" \
-H "Content-Type: application/json" \
-H "apikey: SEU_TOKEN" \
-d '{
  "url": "https://seu-backend.railway.app/webhook/evolution",
  "enabled": true,
  "events": ["MESSAGES_UPSERT"]
}'
```

---

## 🌐 OPÇÃO SIMPLES - APENAS BACKEND

**O sistema funciona completamente apenas com o backend!**

✅ **Vantagens:**
- Deploy mais simples (apenas 1 serviço)
- Formulário de onboarding integrado no backend
- Sem necessidade de configurar CORS
- URL única para tudo

📱 **Fluxo:**
1. Usuário envia mensagem no WhatsApp
2. Sistema detecta que não está cadastrado  
3. Envia link: `https://seu-backend.railway.app/onboarding?phone=48988379567`
4. Usuário preenche formulário
5. Cadastro salvo no banco
6. Retorna para WhatsApp
7. Já pode usar o assistente!

---

## 🌐 OPÇÃO AVANÇADA - FRONTEND SEPARADO (VERCEL)

### 1. Simplificar Frontend
Para usar frontend separado, você precisa:

1. **Converter HTML para React/Next.js**
2. **Configurar CORS no backend**
3. **Deploy no Vercel**

### 2. Estrutura simplificada do frontend:
```bash
cd assistente-financeiro-frontend
# Remover estrutura Next.js complexa
# Criar apenas index.html estático
# Configurar para chamar API do backend
```

### 3. Deploy no Vercel
```bash
git init
git add .
git commit -m "Initial frontend commit"
git push
# Conectar no Vercel dashboard
```

---

## ✅ **RECOMENDAÇÃO: USE APENAS O BACKEND**

Para simplificar o deploy e manutenção:

1. ✅ **Deploy apenas o backend** no Railway
2. ✅ **Formulário integrado** no endpoint `/onboarding`
3. ✅ **Sem necessidade** de frontend separado
4. ✅ **Menos configurações** e variáveis
5. ✅ **Mais estável** e fácil de manter

---

## 🔄 FLUXO DE ATUALIZAÇÃO

```bash
# Fazer mudanças no código
git add .
git commit -m "Update: descrição da mudança"
git push
# Railway faz deploy automático
```

---

## 🧪 VERIFICAÇÕES FINAIS

1. ✅ Backend funcionando: `https://seu-backend.railway.app/health`
2. ✅ Formulário funcionando: `https://seu-backend.railway.app/onboarding`
3. ✅ Webhook configurado na Evolution API
4. ✅ Todas as variáveis de ambiente definidas
5. ✅ Teste completo: enviar mensagem no WhatsApp

---

## 🆘 TROUBLESHOOTING

### Erro de CORS
- Certifique-se que `FRONTEND_URL` está configurado
- Ou use apenas backend sem frontend separado

### Webhook não funciona
- Verifique se URL do webhook está correta
- Teste endpoint `/webhook/evolution` manualmente

### Usuário não encontrado
- Verifique se telefone está sem o dígito 9
- Conferir dados no Supabase

### IA não responde
- Verificar `OPENAI_API_KEY`
- Testar endpoint `/health`

---

## 📞 SUPORTE

Para dúvidas:
1. Verificar logs no Railway
2. Testar endpoints individualmente
3. Conferir variáveis de ambiente
4. Validar integração Evolution API
