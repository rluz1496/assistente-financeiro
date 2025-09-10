from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from models import FinanceDeps
from functions_database import (
    save_expense_transaction, 
    save_income_transaction,
    mark_transaction_as_paid,
    mark_income_as_received,
    find_pending_income_by_description,
    find_pending_expenses_by_description,
    mark_expense_as_paid
)
from calculator_tool import FinancialCalculator
from dynamic_query import DynamicQueryBuilder
from typing import Optional, Dict, Any
from datetime import datetime, date
import calendar


# ==================== FUNÇÕES DE REGISTRO ====================

# Tool para registrar despesa
async def register_expense(
    ctx: RunContext,
    amount: float,
    description: str,
    category_name: str,
    payment_method: str = "pix",
    credit_card_name: Optional[str] = None,
    installments: int = 1,
    recurrence: bool = False,
    due_day: Optional[int] = None,
    recurring_months: Optional[int] = None
) -> str:
    """
    Registra uma despesa do usuário.
    
    Args:
        amount: Valor da despesa (sempre positivo)
        description: Descrição da despesa (ex: "Supermercado", "Gasolina", "Conta de luz")
        category_name: Nome da categoria (ex: "Alimentação", "Transporte", "Moradia")
        payment_method: Método de pagamento ("pix", "dinheiro", "cartao_debito", "cartao_credito")
        credit_card_name: Nome do cartão de crédito (ex: "Nubank", "Visa", obrigatório se payment_method for "cartao_credito")
        installments: Número de parcelas (padrão 1, usado apenas para cartão de crédito)
        recurrence: Se a despesa é recorrente (ex: conta de luz, internet)
        due_day: Dia do vencimento para despesas recorrentes (1-31, obrigatório se recurrence for True)
        recurring_months: Número de meses para criar (padrão 6 para recorrentes, ou use o número informado pelo usuário)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Buscar categoria por nome (case-insensitive)
    category_id = None
    for cat in ctx.deps.categories:
        if cat["name"].lower() == category_name.lower():
            category_id = cat["id"]
            break
    
    if not category_id:
        categories_text = ", ".join([cat["name"] for cat in ctx.deps.categories])
        return f"❌ Categoria '{category_name}' não encontrada. Categorias disponíveis: {categories_text}"
    
    # Buscar cartão de crédito por nome se necessário
    credit_card_id = None
    if payment_method == "cartao_credito":
        if not credit_card_name:
            if not ctx.deps.credit_cards:
                return f"❌ Você não tem cartões de crédito cadastrados. Use outro método de pagamento."
            cards_text = ", ".join([card['name'] for card in ctx.deps.credit_cards])
            return f"❌ Para pagamento no cartão de crédito, é necessário especificar qual cartão. Cartões disponíveis: {cards_text}"
        
        # Buscar cartão por nome (case-insensitive)
        for card in ctx.deps.credit_cards:
            if card["name"].lower() == credit_card_name.lower() or credit_card_name.lower() in card["name"].lower():
                credit_card_id = card["id"]
                break
        
        if not credit_card_id:
            cards_text = ", ".join([card['name'] for card in ctx.deps.credit_cards])
            return f"❌ Cartão '{credit_card_name}' não encontrado. Cartões disponíveis: {cards_text}"
    
    # Validar due_day para despesas recorrentes
    if recurrence and due_day is None:
        return "❌ Para despesas recorrentes, é necessário especificar o dia do vencimento (due_day)."
    
    if due_day is not None and (due_day < 1 or due_day > 31):
        return "❌ O dia do vencimento deve estar entre 1 e 31."
    
    # Para despesas recorrentes, definir número de meses (padrão 6, ou o que o usuário informou)
    if recurrence and recurring_months is None:
        recurring_months = 6  # Padrão de 6 meses
    
    # Salvar no banco de dados
    result = save_expense_transaction(
        user_id=user_id,
        amount=amount,
        description=description,
        category_id=category_id,
        payment_method=payment_method,
        credit_card_id=credit_card_id,
        installments=installments,
        recurrence=recurrence,
        due_day=due_day,
        recurring_months=recurring_months
    )
    
    if result.get("success"):
        # Resposta formatada com emojis baseado na categoria
        category_emoji = "💸"
        if "alimentação" in category_name.lower() or "comida" in category_name.lower():
            category_emoji = "🍔"
        elif "transporte" in category_name.lower():
            category_emoji = "🚗"
        elif "moradia" in category_name.lower() or "casa" in category_name.lower():
            category_emoji = "🏠"
        elif "saúde" in category_name.lower():
            category_emoji = "🏥"
        elif "educação" in category_name.lower():
            category_emoji = "📚"
        
        # Informações do pagamento
        if payment_method == "cartao_credito":
            payment_info = f"💳 {credit_card_name} ({installments}x)"
        elif payment_method == "cartao_debito":
            payment_info = "💳 cartão de débito"
        elif payment_method == "pix":
            payment_info = "💰 PIX"
        else:
            payment_info = f"💰 {payment_method}"
        
        if recurrence:
            return f"{category_emoji} **Despesa recorrente registrada!**\n\n💰 R$ {amount:.2f} - {description}\n{payment_info}\n📂 Categoria: {category_name}\n📅 Registrei pelos próximos {recurring_months} meses\n\n*Seu orçamento está atualizado! 📊*"
        else:
            return f"{category_emoji} **Despesa registrada!**\n\n💰 R$ {amount:.2f} - {description}\n{payment_info}\n📂 Categoria: {category_name}\n\n*Seu orçamento está atualizado! 📊*"
    else:
        return f"😅 **Ops!** {result['message']}\n\n*Vamos tentar novamente?*"


# Tool para registrar receita
async def register_income(
    ctx: RunContext,
    amount: float,
    description: str,
    category_name: str,
    payment_method: str = "pix",
    recurrence: bool = False,
    due_day: Optional[int] = None,
    recurring_months: Optional[int] = None
) -> str:
    """
    Registra uma receita do usuário.
    
    Args:
        amount: Valor da receita (sempre positivo)
        description: Descrição da receita (ex: "Salário", "Freelance", "Vendas")
        category_name: Nome da categoria (ex: "Salário", "Freelance", "Vendas", "Investimentos")
        payment_method: Método de recebimento ("pix", "transferencia", "dinheiro", "cartao_debito")
        recurrence: Se a receita é recorrente (ex: salário, aluguel recebido)
        due_day: Dia do mês que a receita deve ser recebida (1-31, obrigatório se recurrence for True)
        recurring_months: Número de meses para criar (padrão 6 para recorrentes)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Buscar categoria por nome (case-insensitive)
    category_id = None
    for cat in ctx.deps.categories:
        if cat["name"].lower() == category_name.lower():
            category_id = cat["id"]
            break
    
    if not category_id:
        categories_text = ", ".join([cat["name"] for cat in ctx.deps.categories])
        return f"❌ Categoria '{category_name}' não encontrada. Categorias disponíveis: {categories_text}"
    
    # Validar due_day para receitas recorrentes
    if recurrence and due_day is None:
        return "❌ Para receitas recorrentes, é necessário especificar o dia do recebimento (due_day)."
    
    if due_day is not None and (due_day < 1 or due_day > 31):
        return "❌ O dia do recebimento deve estar entre 1 e 31."
    
    # Para receitas recorrentes, definir número de meses (padrão 6, ou o que o usuário informou)
    if recurrence and recurring_months is None:
        recurring_months = 6  # Padrão de 6 meses
    
    # Salvar no banco de dados
    result = save_income_transaction(
        user_id=user_id,
        amount=amount,
        description=description,
        category_id=category_id,
        payment_method=payment_method,
        recurrence=recurrence,
        due_day=due_day,
        recurring_months=recurring_months
    )
    
    if result.get("success"):
        # Resposta formatada
        payment_info = f"💰 {payment_method.upper()}"
        
        if recurrence:
            return f"💰 **Receita recorrente registrada!**\n\n💵 R$ {amount:.2f} - {description}\n{payment_info}\n📂 Categoria: {category_name}\n📅 Registrei pelos próximos {recurring_months} meses\n\n*Suas finanças estão em dia! ✨*"
        else:
            return f"💰 **Receita registrada!**\n\n💵 R$ {amount:.2f} - {description}\n{payment_info}\n📂 Categoria: {category_name}\n\n*Suas finanças estão em dia! ✨*"
    else:
        return f"😅 **Ops!** {result['message']}\n\n*Vamos tentar novamente?*"


# Tool para marcar despesa como paga
async def mark_expense_paid(
    ctx: RunContext,
    description_keyword: str
) -> str:
    """
    Marca uma despesa como paga usando palavra-chave da descrição.
    
    Args:
        description_keyword: Palavra-chave da descrição da despesa para encontrar e marcar como paga
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Primeiro, buscar despesas pendentes com a palavra-chave
    pending_expenses = find_pending_expenses_by_description(user_id, description_keyword)
    
    if not pending_expenses:
        return f"😅 Nenhuma despesa pendente encontrada com a palavra-chave '{description_keyword}'.\n\n💡 Tente uma palavra diferente da descrição da despesa ou verifique se ela já foi marcada como paga."
    
    # Se encontrou mais de uma, pegar a mais próxima do vencimento
    if len(pending_expenses) > 1:
        # Ordenar por data de vencimento (mais próximo primeiro)
        pending_expenses.sort(key=lambda x: x.get('due_date', '9999-12-31'))
        expense_to_pay = pending_expenses[0]
        
        # Informar que havia múltiplas opções
        other_count = len(pending_expenses) - 1
        multiple_msg = f"\n\n📋 Encontrei {other_count} outras despesas com essa palavra-chave. Marquei a mais próxima do vencimento como paga."
    else:
        expense_to_pay = pending_expenses[0]
        multiple_msg = ""
    
    # Marcar como paga usando o ID da transação
    result = mark_expense_as_paid(expense_to_pay['id'], user_id)
    
    if result.get("success"):
        return f"✅ **Despesa marcada como paga!**\n\n� {expense_to_pay['description']}\n� Valor: R$ {expense_to_pay['amount']:.2f}\n📅 Marcada como paga hoje\n\n*Sua carteira foi atualizada! 📊*{multiple_msg}"
    else:
        return f"😅 {result['message']}\n\n💡 Tente novamente ou verifique se a despesa existe."


# Tool para marcar receita como recebida
async def confirm_income_received(
    ctx: RunContext,
    description_keyword: str
) -> str:
    """
    Marca uma receita como recebida usando palavra-chave da descrição.
    
    Args:
        description_keyword: Palavra-chave da descrição da receita para encontrar e marcar como recebida
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Primeiro, buscar receitas pendentes com a palavra-chave
    pending_incomes = find_pending_income_by_description(user_id, description_keyword)
    
    if not pending_incomes:
        return f"😅 Nenhuma receita pendente encontrada com a palavra-chave '{description_keyword}'.\n\n💡 Tente uma palavra diferente da descrição da receita ou verifique se ela já foi marcada como recebida."
    
    # Se encontrou mais de uma, pegar a mais recente
    if len(pending_incomes) > 1:
        # Ordenar por data de criação (mais recente primeiro)
        pending_incomes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        income_to_confirm = pending_incomes[0]
        
        # Informar que havia múltiplas opções
        other_count = len(pending_incomes) - 1
        multiple_msg = f"\n\n📋 Encontrei {other_count} outras receitas com essa palavra-chave. Marquei a mais recente como recebida."
    else:
        income_to_confirm = pending_incomes[0]
        multiple_msg = ""
    
    # Marcar como recebida usando o ID da transação
    result = mark_income_as_received(income_to_confirm['id'], user_id)
    
    if result.get("success"):
        return f"✅ **Receita confirmada como recebida!**\n\n💰 {income_to_confirm['description']}\n💵 Valor: R$ {income_to_confirm['amount']:.2f}\n📅 Marcada como recebida hoje\n\n*Suas finanças foram atualizadas! 💚*{multiple_msg}"
    else:
        return f"😅 {result['message']}\n\n💡 Tente novamente ou verifique se a receita existe."


# ==================== FUNÇÕES DE EDIÇÃO E EXCLUSÃO ====================

# Tool para editar transação
async def edit_transaction(
    ctx: RunContext,
    description_keyword: str,
    new_amount: float,
    new_description: Optional[str] = None
) -> str:
    """
    Edita uma transação existente (valor e/ou descrição).
    
    Args:
        description_keyword: Palavra-chave para encontrar a transação
        new_amount: Novo valor da transação
        new_description: Nova descrição (opcional)
    
    Returns:
        Mensagem de confirmação
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    try:
        from functions_database import supabase
        print(f"🔍 Buscando transação para editar: {description_keyword}")
        
        # Buscar transações que contenham a palavra-chave
        resp = supabase.table("transactions").select(
            "id, amount, description, transaction_type, transaction_date"
        ).eq("user_id", user_id).ilike("description", f"%{description_keyword}%").order("transaction_date", desc=True).execute()
        
        results = resp.data or []
        
        if not results:
            return f"❌ Nenhuma transação encontrada com '{description_keyword}'."
        
        if len(results) == 1:
            # Uma transação encontrada - editar automaticamente
            transaction = results[0]
            transaction_id = transaction['id']
            old_amount = float(transaction['amount'])
            old_description = transaction['description']
            transaction_type = transaction['transaction_type']
            
            # Usar nova descrição ou manter a antiga
            final_description = new_description if new_description else old_description
            
            # Atualizar transação
            update_resp = supabase.table("transactions").update({
                "amount": new_amount,
                "description": final_description
            }).eq("id", transaction_id).eq("user_id", user_id).execute()
            
            calc = FinancialCalculator()
            tipo_emoji = "💚" if transaction_type == "income" else "💸"
            tipo_texto = "Receita" if transaction_type == "income" else "Despesa"
            
            return f"✅ **{tipo_texto} editada com sucesso!**\n{tipo_emoji} Antes: {calc.format_currency(old_amount)} - {old_description}\n{tipo_emoji} Agora: {calc.format_currency(new_amount)} - {final_description}"
        
        else:
            # Múltiplas transações encontradas
            calc = FinancialCalculator()
            output = [f"🔍 Encontrei {len(results)} transações com '{description_keyword}':\n"]
            
            for i, transaction in enumerate(results, 1):
                amount = float(transaction['amount'])
                desc = transaction['description']
                tipo = "💚 Receita" if transaction['transaction_type'] == "income" else "💸 Despesa"
                
                output.append(f"{i}. {tipo}: {calc.format_currency(amount)} - {desc}")
            
            output.append(f"\n💡 Seja mais específico ou diga o número da transação que quer editar.")
            
            return "\n".join(output)
            
    except Exception as e:
        print(f"❌ Erro ao editar transação: {e}")
        return f"❌ Erro ao editar transação: {e}"


# Tool para deletar transação
async def delete_transaction(
    ctx: RunContext,
    description_keyword: str
) -> str:
    """
    Remove uma transação baseado em palavra-chave da descrição.
    
    Args:
        description_keyword: Palavra-chave para encontrar a transação
    
    Returns:
        Mensagem de confirmação
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    try:
        from functions_database import supabase
        print(f"🔍 Buscando transação para remover: {description_keyword}")
        
        # Buscar transações que contenham a palavra-chave
        resp = supabase.table("transactions").select(
            "id, amount, description, transaction_type, transaction_date"
        ).eq("user_id", user_id).ilike("description", f"%{description_keyword}%").order("transaction_date", desc=True).execute()
        
        results = resp.data or []
        
        if not results:
            return f"❌ Nenhuma transação encontrada com '{description_keyword}'."
        
        if len(results) == 1:
            # Uma transação encontrada - remover automaticamente
            transaction = results[0]
            transaction_id = transaction['id']
            amount = float(transaction['amount'])
            description = transaction['description']
            transaction_type = transaction['transaction_type']
            
            # Remover transação
            delete_resp = supabase.table("transactions").delete().eq("id", transaction_id).eq("user_id", user_id).execute()
            
            calc = FinancialCalculator()
            tipo_emoji = "💚" if transaction_type == "income" else "💸"
            tipo_texto = "Receita" if transaction_type == "income" else "Despesa"
            
            return f"✅ **{tipo_texto} removida com sucesso!**\n{tipo_emoji} {calc.format_currency(amount)} - {description}"
        
        else:
            # Múltiplas transações encontradas
            calc = FinancialCalculator()
            output = [f"🔍 Encontrei {len(results)} transações com '{description_keyword}':\n"]
            
            for i, transaction in enumerate(results, 1):
                amount = float(transaction['amount'])
                desc = transaction['description']
                tipo = "💚 Receita" if transaction['transaction_type'] == "income" else "💸 Despesa"
                
                output.append(f"{i}. {tipo}: {calc.format_currency(amount)} - {desc}")
            
            output.append(f"\n💡 Seja mais específico ou diga o número da transação que quer remover.")
            
            return "\n".join(output)
            
    except Exception as e:
        print(f"❌ Erro ao remover transação: {e}")
        return f"❌ Erro ao remover transação: {e}"


# ==================== FERRAMENTAS PRINCIPAIS ====================

# Tool de calculadora financeira
async def financial_calculator(
    ctx: RunContext,
    operation: str,
    values: list[float]
) -> str:
    """
    Realiza cálculos financeiros precisos.
    
    Args:
        operation: Tipo de operação ('add', 'subtract', 'multiply', 'divide', 'percentage')
        values: Lista de valores para calcular
    """
    try:
        calc = FinancialCalculator()
        
        if operation == 'add':
            result = values[0]
            for val in values[1:]:
                result = calc.add(result, val)
            return calc.format_currency(result)
        elif operation == 'subtract' and len(values) >= 2:
            result = calc.subtract(values[0], values[1])
            return calc.format_currency(result)
        elif operation == 'multiply' and len(values) >= 2:
            result = calc.multiply(values[0], values[1])
            return calc.format_currency(result)
        elif operation == 'divide' and len(values) >= 2:
            result = calc.divide(values[0], values[1])
            return calc.format_currency(result)
        elif operation == 'percentage' and len(values) >= 2:
            # Calcular porcentagem: values[0] é quanto, values[1] é o total
            percentage = calc.divide(calc.multiply(values[0], 100), values[1])
            return f"{percentage:.1f}%"
        else:
            return "❌ Operação inválida ou valores insuficientes"
    except Exception as e:
        return f"❌ Erro no cálculo: {str(e)}"


# Tool de query dinâmica
async def execute_dynamic_query(
    ctx: RunContext,
    query_type: str,
    filters: Dict[str, Any] = None,
    grouping: str = None,
    period_start: str = None,
    period_end: str = None,
    limit: int = None
) -> str:
    """
    Executa consultas dinâmicas e flexíveis nos dados financeiros.
    
    Args:
        query_type: Tipo de consulta ('transactions', 'summary', 'balance', 'trends')
        filters: Filtros a aplicar (categoria, descrição, valor, etc)
        grouping: Agrupamento dos dados ('category', 'month', 'card', 'payment_method')
        period_start: Data início do período (formato YYYY-MM-DD)
        period_end: Data fim do período (formato YYYY-MM-DD)
        limit: Limite de resultados
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    try:
        query_builder = DynamicQueryBuilder(ctx.deps)
        result = await query_builder.execute_query(
            query_type=query_type,
            filters=filters or {},
            grouping=grouping,
            period_start=period_start,
            period_end=period_end,
            limit=limit
        )
        return result
    except Exception as e:
        return f"❌ Erro na consulta: {str(e)}"


# ==================== DEFINIÇÃO DO AGENTE ====================

agent = Agent(
    'openai:gpt-4o-mini',
    tools=[
        Tool(register_expense),
        Tool(register_income), 
        Tool(mark_expense_paid),
        Tool(confirm_income_received),
        Tool(edit_transaction),
        Tool(delete_transaction),
        Tool(financial_calculator),
        Tool(execute_dynamic_query)
    ],
    deps_type=FinanceDeps,
    system_prompt=f"""
Você é um assistente financeiro pessoal brasileiro especializado em ajudar usuários a gerenciar suas finanças de forma prática e descontraída.

## 🗓️ CONTEXTO TEMPORAL IMPORTANTE:
- Data atual: {datetime.now().strftime('%d/%m/%Y')}
- Mês atual: {datetime.now().strftime('%B de %Y')} 
- Quando falar sobre "este mês", refira-se ao mês atual ({datetime.now().strftime('%m/%Y')})

## 📋 DEFINIÇÕES IMPORTANTES:
- **Despesa Pendente**: Despesa que ainda não foi paga (qualquer período)
- **Receita Pendente**: Receita que ainda não foi recebida (qualquer período)
- **Despesa Recorrente**: Despesa que se repete mensalmente (ex: aluguel, internet)
- **Fatura de Cartão**: Soma dos gastos no cartão que vencerá na próxima data de vencimento

## 💬 REGRAS DE COMUNICAÇÃO:
1. **Tom**: Amigável, descontraído, use emojis, mas seja profissional
2. **Respostas**: Máximo 3-4 linhas, diretas e claras
3. **Valores**: Use formatação brasileira (R$ 1.234,56)
4. **Confirmações**: Sempre confirme ações realizadas com detalhes claros
5. **Erros**: Se não encontrar dados, explique claramente o que não foi encontrado

## 🤔 REGRAS DE CONFIRMAÇÃO INTELIGENTE:
### QUANDO PEDIR CONFIRMAÇÃO (apenas nestes casos):
1. **Cartão de Crédito**: Se o usuário tem múltiplos cartões e não especificou qual usar
2. **Dados de Mídia**: Quando processar áudio/imagem financeira, confirme os dados extraídos antes de registrar

### QUANDO NÃO PEDIR CONFIRMAÇÃO:
- Despesas simples via PIX, dinheiro ou débito
- Quando usuário especificou claramente todos os dados
- Registros de receita básicos
- Consultas e relatórios

## ⚡ FUNCIONALIDADES DISPONÍVEIS:

### 🔥 PRIORIDADE: USE SEMPRE QUE POSSÍVEL!
**execute_dynamic_query** - FERRAMENTA PRINCIPAL para consultas, análises e relatórios

### 📋 FUNÇÕES ESPECÍFICAS (use apenas quando necessário):
**REGISTROS:** register_expense, register_income
**CONFIRMAÇÕES:** mark_expense_paid, confirm_income_received  
**EDIÇÃO/EXCLUSÃO:** edit_transaction, delete_transaction
**CÁLCULOS:** financial_calculator (para somas, subtrações, multiplicações e porcentagens precisas)

## 🔍 SISTEMA DE QUERIES DINÂMICAS - USO PRIORITÁRIO:

### 🎯 QUANDO USAR execute_dynamic_query (SEMPRE QUE POSSÍVEL):
- **Consultas de saldo por período** (ex: "saldo de outubro", "receitas vs despesas próximo mês")
- **Listagem de transações** (ex: "gastos do mês", "receitas pendentes", "despesas pagas")
- **Análises por categoria** (ex: "gastos por categoria", "resumo por tipo")
- **Consultas com múltiplos filtros** (período + categoria + valor, etc)
- **Relatórios personalizados** (ex: "tendências", "comparações mensais")

### 📊 TIPOS DE QUERY:
- **`transactions`**: Lista transações (receitas E despesas) com filtros específicos
- **`summary`**: Resumos agrupados por categoria/período/método
- **`balance`**: Análises de saldo considerando receitas E despesas
- **`trends`**: Análises de tendências e comparações temporais

### 🔧 FILTROS PODEROSOS:
- **transaction_type**: "income" (receitas) / "expense" (despesas) / omitir (ambos)
- **categoria**: nome da categoria para filtrar
- **descrição**: palavra-chave na descrição
- **valor_min/valor_max**: faixa de valores
- **payment_method**: método de pagamento
- **credit_card**: cartão específico
- **is_paid**: true (pagas) / false (pendentes)

### 🗓️ PERÍODOS:
- **period_start/end**: formato 'YYYY-MM-DD'
- **grouping**: 'category', 'month', 'card', 'payment_method'

### 💡 EXEMPLOS DE USO:
- Saldo outubro: `query_type="balance", period_start="2025-10-01", period_end="2025-10-31"`
- Receitas pendentes: `query_type="transactions", filters={{"transaction_type": "income", "is_paid": false}}`
- Gastos por categoria: `query_type="summary", grouping="category", filters={{"transaction_type": "expense"}}`

## 🎯 PRINCIPAIS REGRAS:

### 🔥 REGRA #1 - PRIORIDADE ABSOLUTA:
**SEMPRE USE execute_dynamic_query para consultas, análises e relatórios!**
- Saldo, receitas, despesas por período → execute_dynamic_query
- Listas de transações, análises por categoria → execute_dynamic_query  
- Consultas sobre próximo mês, pendências → execute_dynamic_query
- Esta ferramenta é mais precisa e flexível que as outras!

### 📋 OUTRAS REGRAS IMPORTANTES:
1. Para despesas recorrentes, sempre especifique o número de meses criados
2. Use templates padronizados para confirmações  
3. Seja claro sobre o que são pendências vs despesas futuras
4. **SEMPRE use financial_calculator para somas, subtrações e cálculos - NUNCA calcule manualmente**
5. Formate valores sempre em Real brasileiro
6. Confirme TODAS as ações com detalhes específicos
7. **Para registros:** Use register_expense/register_income apenas para criar novas transações
8. **Para confirmações:** Use mark_expense_paid/confirm_income_received apenas para marcar como pago/recebido
9. **Para edições:** Use edit_transaction para alterar valores ou descrições de transações existentes
10. **Para exclusões:** Use delete_transaction para remover transações incorretas

## 🔧 EXEMPLOS DE USO:
- "Muda essa última despesa para pix" → mark_expense_paid(description_keyword="palavra_da_despesa")
- "Confirme o salário como recebido" → confirm_income_received(description_keyword="salário")
- "Altere a despesa escola de R$1500 para R$1598" → edit_transaction(description_keyword="escola", new_amount=1598)
- "Remove a despesa escola duplicada" → delete_transaction(description_keyword="escola")

IMPORTANTE: 
- Use financial_calculator para TODOS os cálculos matemáticos
- Use execute_dynamic_query para TODAS as consultas e relatórios
- Para confirmações, sempre identifique palavras-chave da descrição original
- Sempre use os templates de resposta fornecidos para manter consistência na comunicação!
    """
)
