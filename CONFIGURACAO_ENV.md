# 🔧 Configuração Rápida do .env

## ✅ Status Atual
- ✅ Servidor principal funcionando na porta 8001
- ✅ Frontend funcionando na porta 8080
- ✅ Supabase configurado
- ✅ Redis configurado
- ✅ OpenAI configurado

## 🔑 Configurações Necessárias para Sistema de Autenticação

### 1. JWT (já está configurado)
```env
JWT_SECRET_KEY=assistente-financeiro-jwt-secret-key-super-seguro-2024
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 2. SMTP para Email (configure no .env)

#### Para Gmail:
1. **Ative a autenticação de 2 fatores** na sua conta Google
2. **Gere uma senha de app**: https://myaccount.google.com/apppasswords
3. **Configure no .env**:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app_de_16_caracteres
FROM_EMAIL=seu_email@gmail.com
```

#### Para Outlook/Hotmail:
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=seu_email@outlook.com
SMTP_PASSWORD=sua_senha
FROM_EMAIL=seu_email@outlook.com
```

#### Para outros provedores:
- **Yahoo**: smtp.mail.yahoo.com:587
- **SendGrid**: smtp.sendgrid.net:587
- **Mailgun**: smtp.mailgun.org:587

### 3. URLs (já configuradas)
```env
FRONTEND_URL=http://localhost:8080
BACKEND_URL=http://localhost:8000
```

## 🚀 Como Testar

### 1. Servidores Rodando
- **Backend**: http://localhost:8001 ✅
- **Frontend**: http://localhost:8080 ✅

### 2. Para usar o sistema de autenticação completo:
1. Configure o email no .env
2. Execute: `python main_auth.py` (porta 8000)
3. Acesse: http://localhost:8000/docs para ver a documentação

### 3. APIs Disponíveis
- **Servidor atual (8001)**: APIs originais do projeto
- **Servidor auth (8000)**: Sistema completo de autenticação

## 📧 Exemplo de Configuração Gmail

1. Vá em: https://myaccount.google.com/apppasswords
2. Selecione "App": Mail
3. Selecione "Device": Other (custom name) → digite "Assistente Financeiro"
4. Copie a senha de 16 caracteres gerada
5. Cole no .env:

```env
SMTP_USERNAME=seuemail@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
FROM_EMAIL=seuemail@gmail.com
```

## 🔐 Segurança
- ✅ JWT secret configurado
- ✅ Senhas com hash SHA-256 + salt
- ✅ Tokens com expiração
- ✅ Refresh tokens
- ⚠️ Configure email para reset de senha

## 🎯 Próximos Passos
1. Configure o email no .env
2. Teste o registro de usuário
3. Teste o reset de senha
4. Integre com o frontend existente