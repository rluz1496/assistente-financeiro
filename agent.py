from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from models import FinanceDeps
from functions_database import (
    save_expense_transaction, 
    search_transactions, 
    mark_transaction_as_paid,
    find_unpaid_transactions_by_description,
    get_current_invoice,
    get_next_invoice,
    get_credit_card_transactions_by_period,
    save_income_transaction,
    search_income_transactions,
    mark_income_as_received,
    find_pending_income_by_description,
    calculate_user_balance,
    get_category_analysis,
    get_monthly_trend,
    get_pending_commitments
)
from typing import Optional, Dict, Any
from datetime import datetime, date
import calendar


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
        description: Descrição da despesa
        category_name: Nome da categoria (ex: "Alimentação", "Transporte")
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
    
    # Salvar a despesa
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
    
    if result["success"]:
        # Emojis por categoria
        category_emojis = {
            "alimentação": "🍽️",
            "transporte": "🚗",
            "supermercado": "🛒", 
            "aluguel e depesas de casa": "🏠",
            "escola": "📚",
            "empréstimos": "💳",
            "lazer": "🎉",
            "saúde": "⚕️"
        }
        
        category_emoji = category_emojis.get(category_name.lower(), "💰")
        
        # Mensagens personalizadas por método de pagamento
        if payment_method == "cartao_credito":
            if installments > 1:
                payment_info = f"💳 Parcelado em {installments}x no {credit_card_name or 'cartão'}"
            else:
                payment_info = f"💳 No {credit_card_name or 'cartão de crédito'}"
        elif payment_method == "pix":
            payment_info = "⚡ Via PIX - já era! 💸"
        elif payment_method == "dinheiro":
            payment_info = "💵 No dinheiro vivo"
        elif payment_method == "cartao_debito":
            payment_info = "💳 No débito - saiu na hora!"
        else:
            payment_info = f"💰 Via {payment_method}"
        
        # Mensagem principal com estilo descontraído
        if recurrence:
            months_count = result.get('recurring_count', 6)
            return f"{category_emoji} **Conta fixa registrada!**\n\n💰 R$ {amount:.2f} - {description}\n{payment_info}\n📅 Todo dia {due_day} pelos próximos {months_count} meses\n\n*Agora é só aguardar os lembretes! 📲*"
        else:
            return f"{category_emoji} **Gasto registrado!**\n\n💰 R$ {amount:.2f} - {description}\n{payment_info}\n📂 Categoria: {category_name}\n\n*Seu orçamento está sempre atualizado! 📊*"
    else:
        return f"😅 **Ops!** {result['message']}\n\n*Vamos tentar novamente?*"

# Tool para consultar despesas
async def search_expenses(
    ctx: RunContext,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_name: Optional[str] = None,
    payment_method: Optional[str] = None,
    is_paid: Optional[bool] = None,
    due_day: Optional[int] = None,
    due_month: Optional[int] = None,
    credit_card_name: Optional[str] = None,
    description_contains: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> str:
    """
    Busca despesas do usuário com filtros específicos.
    
    Args:
        start_date: Data de início (formato YYYY-MM-DD)
        end_date: Data de fim (formato YYYY-MM-DD)
        category_name: Nome da categoria para filtrar
        payment_method: Método de pagamento para filtrar
        is_paid: True para apenas pagas, False para apenas não pagas
        due_day: Dia do vencimento (1-31)
        due_month: Mês do vencimento (1-12)
        credit_card_name: Nome do cartão de crédito
        description_contains: Palavra ou frase que deve estar na descrição
        min_amount: Valor mínimo
        max_amount: Valor máximo
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Monta filtros
    filters = {}
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date
    if category_name:
        filters["category_name"] = category_name
    if payment_method:
        filters["payment_method"] = payment_method
    if is_paid is not None:
        filters["is_paid"] = is_paid
    if due_day:
        filters["due_day"] = due_day
    if due_month:
        filters["due_month"] = due_month
    if credit_card_name:
        filters["credit_card_name"] = credit_card_name
    if description_contains:
        filters["description_contains"] = description_contains
    if min_amount:
        filters["min_amount"] = min_amount
    if max_amount:
        filters["max_amount"] = max_amount
    
    transactions = search_transactions(user_id, filters)
    
    if not transactions:
        return "� Ops! Não encontrei nenhuma despesa com esses filtros. Que tal tentar uma busca mais ampla? 🔍"
    
    # Formatar resultado
    total_amount = sum(t["amount"] for t in transactions)
    paid_count = sum(1 for t in transactions if t.get("paid_date"))
    unpaid_count = len(transactions) - paid_count
    
    result = f"� **Aqui estão suas {len(transactions)} despesa(s)!**\n"
    result += f"� **Total gasto:** R$ {total_amount:.2f}\n"
    result += f"{'✅ Tudo quitado! 🎉' if unpaid_count == 0 else f'✅ {paid_count} pagas | ⏳ {unpaid_count} pendentes'}\n\n"
    
    # Listar despesas (máximo 10 para não sobrecarregar)
    for i, transaction in enumerate(transactions[:10]):
        status = "✅ Pago" if transaction.get("paid_date") else "⏳ Pendente"
        category = transaction["categories"]["name"] if transaction.get("categories") else "Outros"
        
        # Emoji da categoria
        category_emojis = {
            "Alimentação": "🍽️", "Transporte": "🚗", "Supermercado": "🛒", 
            "Casa": "🏠", "Saúde": "🏥", "Entretenimento": "🎯", 
            "Educação": "📚", "Roupas": "👕", "Outros": "📋"
        }
        category_emoji = category_emojis.get(category, "📋")
        
        # Info do cartão
        card_info = f" via {transaction['credit_cards']['name']}" if transaction.get("credit_cards") else ""
        
        # Info de vencimento
        due_info = ""
        if transaction.get("due_date"):
            due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
            due_info = f" • Vence {due_date.strftime('%d/%m')}"
        
        result += f"💰 **R$ {transaction['amount']:.2f}** - {transaction['description']}\n"
        result += f"{category_emoji} {category} • {status}{card_info}{due_info}\n\n"
    
    if len(transactions) > 10:
        result += f"📝 ... e mais {len(transactions) - 10} despesa(s). Quer ver mais detalhes?"
    
    return result

# Tool para marcar despesa como paga
async def mark_expense_paid(
    ctx: RunContext,
    description_keyword: str,
    paid_date: Optional[str] = None
) -> str:
    """
    Marca uma despesa como paga baseada em palavra-chave na descrição.
    
    Args:
        description_keyword: Palavra-chave para encontrar a despesa (ex: "telefone", "internet")
        paid_date: Data do pagamento (formato YYYY-MM-DD), se não informado usa hoje
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Busca despesas não pagas com a palavra-chave
    unpaid_transactions = find_unpaid_transactions_by_description(user_id, description_keyword)
    
    if not unpaid_transactions:
        return f"🤔 Hmm, não encontrei despesas pendentes com '{description_keyword}'. Já foi pago ou tem outro nome? 💭"
    
    if len(unpaid_transactions) == 1:
        # Apenas uma despesa encontrada, marca como paga automaticamente
        transaction = unpaid_transactions[0]
        result = mark_transaction_as_paid(transaction["id"], user_id, paid_date)
        
        if result["success"]:
            return f"🎉 **Despesa quitada!** \n💸 {transaction['description']} - R$ {transaction['amount']:.2f}\n✅ Seu orçamento foi atualizado! 📊"
        else:
            return f"😅 Ops! Algo deu errado: {result['message']}"
    
    else:
        # Múltiplas despesas encontradas, lista para o usuário escolher
        result = f"🤷‍♀️ **Encontrei {len(unpaid_transactions)} despesas pendentes** com '{description_keyword}':\n\n"
        
        for i, transaction in enumerate(unpaid_transactions, 1):
            category = transaction["categories"]["name"] if transaction.get("categories") else "Outros"
            
            # Emoji da categoria
            category_emojis = {
                "Alimentação": "🍽️", "Transporte": "🚗", "Supermercado": "🛒", 
                "Casa": "🏠", "Saúde": "🏥", "Entretenimento": "🎯", 
                "Educação": "📚", "Roupas": "👕", "Outros": "📋"
            }
            category_emoji = category_emojis.get(category, "📋")
            
            card_info = f" via {transaction['credit_cards']['name']}" if transaction.get("credit_cards") else ""
            
            due_info = ""
            if transaction.get("due_date"):
                due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
                due_info = f" • Vence {due_date.strftime('%d/%m')}"
            
            result += f"💰 **R$ {transaction['amount']:.2f}** - {transaction['description']}\n"
            result += f"{category_emoji} {category}{card_info}{due_info}\n\n"
        
        result += "💡 **Dica:** Seja mais específico pra eu saber qual você pagou! 😉"
        return result

# Tool para consultar fatura atual
async def check_current_invoice(
    ctx: RunContext,
    credit_card_name: Optional[str] = None
) -> str:
    """
    Consulta a fatura atual (mês corrente) de um cartão específico ou todos os cartões.
    
    Args:
        credit_card_name: Nome do cartão para filtrar (opcional)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    credit_card_id = None
    
    # Buscar ID do cartão se especificado
    if credit_card_name:
        for card in ctx.deps.credit_cards:
            if credit_card_name.lower() in card["name"].lower():
                credit_card_id = card["id"]
                break
        
        if not credit_card_id:
            cards_text = ", ".join([card["name"] for card in ctx.deps.credit_cards])
            return f"❌ Cartão '{credit_card_name}' não encontrado. Cartões disponíveis: {cards_text}"
    
    invoices = get_current_invoice(user_id, credit_card_id)
    
    if not invoices:
        card_text = f" do {credit_card_name}" if credit_card_name else ""
        return f"� **Tranquilo!** Não há faturas em aberto este mês{card_text}. Você está no azul! 💙"
    
    result = "💳 **Suas faturas de hoje:**\n\n"
    total_amount = 0
    
    for invoice in invoices:
        card_name = invoice["credit_cards"]["name"] if invoice.get("credit_cards") else "Cartão desconhecido"
        status = "✅ Quitada" if invoice["is_paid"] else "⏳ Pendente"
        due_date = datetime.fromisoformat(invoice["due_date"].replace('Z', '+00:00')).strftime('%d/%m')
        
        result += f"💳 **{card_name}**\n"
        result += f"💰 **R$ {invoice['total_amount']:.2f}** • {status}\n"
        result += f"📅 Vence dia {due_date}\n\n"
        
        if not invoice["is_paid"]:
            total_amount += invoice["total_amount"]
    
    if total_amount > 0:
        result += f"🎯 **Total para pagar: R$ {total_amount:.2f}**"
    else:
        result += "🎉 **Tudo quitado! Parabéns!** 🙌"
    
    return result

# Tool para consultar próxima fatura
async def check_next_invoice(
    ctx: RunContext,
    credit_card_name: Optional[str] = None
) -> str:
    """
    Consulta a próxima fatura (próximo mês) de um cartão específico ou todos os cartões.
    
    Args:
        credit_card_name: Nome do cartão para filtrar (opcional)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    credit_card_id = None
    
    # Buscar ID do cartão se especificado
    if credit_card_name:
        for card in ctx.deps.credit_cards:
            if credit_card_name.lower() in card["name"].lower():
                credit_card_id = card["id"]
                break
        
        if not credit_card_id:
            cards_text = ", ".join([card["name"] for card in ctx.deps.credit_cards])
            return f"❌ Cartão '{credit_card_name}' não encontrado. Cartões disponíveis: {cards_text}"
    
    invoices = get_next_invoice(user_id, credit_card_id)
    
    if not invoices:
        card_text = f" do {credit_card_name}" if credit_card_name else ""
        return f"� **Que bom!** Ainda não há gastos previstos para o próximo mês{card_text}. Continue assim! 👏"
    
    result = "� **Próximas faturas que vêm aí:**\n\n"
    total_amount = 0
    
    for invoice in invoices:
        card_name = invoice["credit_cards"]["name"] if invoice.get("credit_cards") else "Cartão desconhecido"
        due_date = datetime.fromisoformat(invoice["due_date"].replace('Z', '+00:00')).strftime('%d/%m')
        
        result += f"💳 **{card_name}**\n"
        result += f"💰 **R$ {invoice['total_amount']:.2f}**\n"
        result += f"📅 Vence dia {due_date}\n\n"
        
        total_amount += invoice["total_amount"]
    
    result += f"� **Total a se preparar: R$ {total_amount:.2f}**\n💡 *Já pode ir se organizando!* 😉"
    
    return result

# Tool para consultar gastos por cartão e categoria
async def check_card_expenses_by_category(
    ctx: RunContext,
    credit_card_name: str,
    category_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    Consulta gastos de um cartão específico, opcionalmente filtrado por categoria e período.
    
    Args:
        credit_card_name: Nome do cartão
        category_name: Nome da categoria para filtrar (opcional)
        start_date: Data de início (formato YYYY-MM-DD, opcional)
        end_date: Data de fim (formato YYYY-MM-DD, opcional)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Buscar ID do cartão
    credit_card_id = None
    for card in ctx.deps.credit_cards:
        if credit_card_name.lower() in card["name"].lower():
            credit_card_id = card["id"]
            break
    
    if not credit_card_id:
        cards_text = ", ".join([card["name"] for card in ctx.deps.credit_cards])
        return f"❌ Cartão '{credit_card_name}' não encontrado. Cartões disponíveis: {cards_text}"
    
    # Definir período padrão se não especificado (mês atual)
    if not start_date or not end_date:
        current_date = date.today()
        start_date = current_date.replace(day=1).isoformat()
        last_day = calendar.monthrange(current_date.year, current_date.month)[1]
        end_date = current_date.replace(day=last_day).isoformat()
    
    # Buscar transações do cartão
    transactions = get_credit_card_transactions_by_period(user_id, credit_card_id, start_date, end_date)
    
    # Filtrar por categoria se especificado
    if category_name:
        filtered_transactions = []
        for transaction in transactions:
            if transaction.get("categories") and transaction["categories"]["name"].lower() == category_name.lower():
                filtered_transactions.append(transaction)
        transactions = filtered_transactions
    
    if not transactions:
        period_text = f"neste período" if start_date != end_date else "hoje"
        category_text = f" em {category_name}" if category_name else ""
        return f"� **Ótimo!** Não houve gastos no {credit_card_name}{category_text} {period_text}. Economia em ação! 💰"
    
    total_amount = sum(t["amount"] for t in transactions)
    
    # Emoji da categoria
    category_emojis = {
        "Alimentação": "🍽️", "Transporte": "🚗", "Supermercado": "�", 
        "Casa": "🏠", "Saúde": "🏥", "Entretenimento": "🎯", 
        "Educação": "📚", "Roupas": "👕", "Outros": "📋"
    }
    category_emoji = category_emojis.get(category_name, "💳") if category_name else "💳"
    
    result = f"{category_emoji} **Gastos no {credit_card_name}**\n"
    if category_name:
        result += f"� **{category_name}**\n"
    result += f"� **R$ {total_amount:.2f}** em {len(transactions)} compra(s)\n\n"
    
    # Listar transações (máximo 8)
    for i, transaction in enumerate(transactions[:8]):
        category = transaction["categories"]["name"] if transaction.get("categories") else "Outros"
        category_emoji = category_emojis.get(category, "📋")
        created_date = datetime.fromisoformat(transaction["created_at"].replace('Z', '+00:00')).strftime('%d/%m')
        
        result += f"💰 **R$ {transaction['amount']:.2f}** - {transaction['description']}\n"
        result += f"{category_emoji} {category} • {created_date}\n\n"
    
    if len(transactions) > 8:
        result += f"📋 ... e mais {len(transactions) - 8} compra(s). Quer ver mais detalhes?"
    
    return result


# ==================== FERRAMENTAS DE RECEITAS ====================

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
    for category in ctx.deps.categories:
        if category["name"].lower() == category_name.lower():
            category_id = category["id"]
            break
    
    if not category_id:
        categories_text = ", ".join([cat["name"] for cat in ctx.deps.categories])
        return f"🤔 Categoria '{category_name}' não encontrada. Categorias disponíveis: {categories_text}"
    
    # Validação para receitas recorrentes
    if recurrence and due_day is None:
        return "📅 Para receitas recorrentes, você precisa informar o dia do mês (due_day). Exemplo: due_day=5 para dia 5 de cada mês."
    
    if due_day is not None and (due_day < 1 or due_day > 31):
        return "❌ O dia do vencimento deve estar entre 1 e 31."
    
    # Salvar receita
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
    
    if result["success"]:
        # Emoji da categoria
        category_emojis = {
            "Salário": "💼", "Freelance": "💻", "Vendas": "💰", 
            "Investimentos": "📈", "Aluguel": "🏠", "Outros": "💸"
        }
        category_emoji = category_emojis.get(category_name, "💸")
        
        # Mensagem personalizada por método de pagamento
        payment_messages = {
            "pix": "⚡ Via PIX - na conta! 💰",
            "transferencia": "🏦 Transferência bancária",
            "dinheiro": "💵 Dinheiro vivo",
            "cartao_debito": "💳 Cartão de débito"
        }
        payment_msg = payment_messages.get(payment_method, f"💳 {payment_method}")
        
        if recurrence:
            months = recurring_months or 6
            return (f"🎉 **Receita recorrente registrada!**\n"
                   f"💰 **R$ {amount:.2f}** - {description}\n"
                   f"{category_emoji} {category_name} • {payment_msg}\n"
                   f"🔄 **{months} meses** criados - todo dia {due_day}\n"
                   f"📊 Sua previsão de renda está atualizada! 📈")
        else:
            return (f"💰 **Receita registrada!**\n"
                   f"💸 **R$ {amount:.2f}** - {description}\n"
                   f"{category_emoji} {category_name} • {payment_msg}\n"
                   f"✅ Dinheiro já contabilizado! 🎯")
    else:
        return f"😅 Ops! {result['message']}"


# Tool para consultar receitas
async def search_income(
    ctx: RunContext,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_name: Optional[str] = None,
    payment_method: Optional[str] = None,
    is_received: Optional[bool] = None,
    description_contains: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> str:
    """
    Busca receitas com filtros.
    
    Args:
        start_date: Data inicial (formato YYYY-MM-DD)
        end_date: Data final (formato YYYY-MM-DD)
        category_name: Filtrar por categoria
        payment_method: Filtrar por método de recebimento
        is_received: True para recebidas, False para pendentes, None para todas
        description_contains: Palavra-chave na descrição
        min_amount: Valor mínimo
        max_amount: Valor máximo
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Monta filtros
    filters = {}
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date
    if category_name:
        filters["category_name"] = category_name
    if payment_method:
        filters["payment_method"] = payment_method
    if is_received is not None:
        filters["is_paid"] = is_received
    if description_contains:
        filters["description_contains"] = description_contains
    if min_amount:
        filters["min_amount"] = min_amount
    if max_amount:
        filters["max_amount"] = max_amount
    
    transactions = search_income_transactions(user_id, filters)
    
    if not transactions:
        return "😕 Ops! Não encontrei nenhuma receita com esses filtros. Que tal tentar uma busca mais ampla? 🔍"
    
    # Formatar resultado
    total_amount = sum(t["amount"] for t in transactions)
    received_count = sum(1 for t in transactions if t.get("paid_date"))
    pending_count = len(transactions) - received_count
    
    result = f"💰 **Aqui estão suas {len(transactions)} receita(s)!**\n"
    result += f"💸 **Total esperado:** R$ {total_amount:.2f}\n"
    result += f"{'💰 Tudo recebido! 🎉' if pending_count == 0 else f'✅ {received_count} recebidas | ⏳ {pending_count} pendentes'}\n\n"
    
    # Listar receitas (máximo 10 para não sobrecarregar)
    for i, transaction in enumerate(transactions[:10]):
        status = "✅ Recebido" if transaction.get("paid_date") else "⏳ Pendente"
        category = transaction["categories"]["name"] if transaction.get("categories") else "Outros"
        
        # Emoji da categoria
        category_emojis = {
            "Salário": "💼", "Freelance": "💻", "Vendas": "💰", 
            "Investimentos": "📈", "Aluguel": "🏠", "Outros": "💸"
        }
        category_emoji = category_emojis.get(category, "💸")
        
        # Info de data
        due_info = ""
        if transaction.get("due_date"):
            due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
            due_info = f" • Previsto {due_date.strftime('%d/%m')}"
        
        result += f"💰 **R$ {transaction['amount']:.2f}** - {transaction['description']}\n"
        result += f"{category_emoji} {category} • {status}{due_info}\n\n"
    
    if len(transactions) > 10:
        result += f"📝 ... e mais {len(transactions) - 10} receita(s). Quer ver mais detalhes?"
    
    return result


# Tool para confirmar recebimento de receita
async def confirm_income_received(
    ctx: RunContext,
    description_keyword: str,
    received_date: Optional[str] = None
) -> str:
    """
    Confirma o recebimento de uma receita baseada em palavra-chave na descrição.
    
    Args:
        description_keyword: Palavra-chave para encontrar a receita (ex: "salário", "freelance")
        received_date: Data do recebimento (formato YYYY-MM-DD), se não informado usa hoje
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Busca receitas pendentes com a palavra-chave
    pending_transactions = find_pending_income_by_description(user_id, description_keyword)
    
    if not pending_transactions:
        return f"🤔 Hmm, não encontrei receitas pendentes com '{description_keyword}'. Já foi recebido ou tem outro nome? 💭"
    
    if len(pending_transactions) == 1:
        # Apenas uma receita encontrada, confirma automaticamente
        transaction = pending_transactions[0]
        result = mark_income_as_received(transaction["id"], user_id, received_date)
        
        if result["success"]:
            return f"🎉 **Receita confirmada!** \n💰 {transaction['description']} - R$ {transaction['amount']:.2f}\n✅ Dinheiro já está na conta! 💸"
        else:
            return f"😅 Ops! Algo deu errado: {result['message']}"
    
    else:
        # Múltiplas receitas encontradas, lista para o usuário escolher
        result = f"🤷‍♀️ **Encontrei {len(pending_transactions)} receitas pendentes** com '{description_keyword}':\n\n"
        
        for i, transaction in enumerate(pending_transactions, 1):
            category = transaction["categories"]["name"] if transaction.get("categories") else "Outros"
            
            # Emoji da categoria
            category_emojis = {
                "Salário": "💼", "Freelance": "💻", "Vendas": "💰", 
                "Investimentos": "📈", "Aluguel": "🏠", "Outros": "💸"
            }
            category_emoji = category_emojis.get(category, "💸")
            
            due_info = ""
            if transaction.get("due_date"):
                due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
                due_info = f" • Previsto {due_date.strftime('%d/%m')}"
            
            result += f"💰 **R$ {transaction['amount']:.2f}** - {transaction['description']}\n"
            result += f"{category_emoji} {category}{due_info}\n\n"
        
        result += "💡 **Dica:** Seja mais específico pra eu saber qual você recebeu! 😉"
        return result


# ==================== FERRAMENTAS DE ANÁLISE DE SALDO ====================

# Tool para consultar saldo atual
async def check_balance(
    ctx: RunContext,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    Consulta o saldo atual baseado em receitas vs despesas.
    
    Args:
        start_date: Data inicial (formato YYYY-MM-DD), se não informado usa início do mês atual
        end_date: Data final (formato YYYY-MM-DD), se não informado usa data atual
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    balance_data = calculate_user_balance(user_id, start_date, end_date)
    
    # Determinar período para exibição
    if start_date and end_date:
        from datetime import datetime
        start = datetime.fromisoformat(start_date).strftime('%d/%m')
        end = datetime.fromisoformat(end_date).strftime('%d/%m')
        period_text = f"({start} a {end})"
    else:
        period_text = "(este mês)"
    
    # Status do saldo
    balance = balance_data["balance"]
    if balance > 0:
        balance_status = f"💰 **Saldo positivo: +R$ {balance:.2f}** 🎉"
        emoji = "📈"
    elif balance == 0:
        balance_status = f"⚖️ **Saldo neutro: R$ {balance:.2f}** 😐"
        emoji = "⚖️"
    else:
        balance_status = f"⚠️ **Saldo negativo: R$ {balance:.2f}** 😰"
        emoji = "📉"
    
    result = f"{emoji} **Análise Financeira** {period_text}\n\n"
    result += f"💸 **Receitas:** R$ {balance_data['total_income']:.2f} ({balance_data['income_count']} entradas)\n"
    result += f"💳 **Despesas:** R$ {balance_data['total_expenses']:.2f} ({balance_data['expense_count']} gastos)\n\n"
    result += f"{balance_status}\n\n"
    
    # Dicas baseadas no saldo
    if balance > 1000:
        result += "🌟 **Ótimo controle!** Você está conseguindo poupar. Que tal investir essa sobra? 💎"
    elif balance > 0:
        result += "👍 **No azul!** Continue assim para manter as contas em dia! 💙"
    elif balance >= -500:
        result += "⚠️ **Atenção!** Suas despesas estão próximas da sua renda. Cuidado com os gastos! 🎯"
    else:
        result += "🚨 **Alerta!** Você está gastando mais do que recebe. Hora de revisar o orçamento! 📊"
    
    return result


# Tool para análise por categoria
async def analyze_spending_by_category(
    ctx: RunContext,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    Análise detalhada de gastos por categoria.
    
    Args:
        start_date: Data inicial (formato YYYY-MM-DD), se não informado usa início do mês atual
        end_date: Data final (formato YYYY-MM-DD), se não informado usa data atual
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    category_data = get_category_analysis(user_id, start_date, end_date)
    
    if not category_data:
        return "😊 **Que bom!** Não há gastos registrados neste período. Continue economizando! 💰"
    
    # Determinar período para exibição
    if start_date and end_date:
        from datetime import datetime
        start = datetime.fromisoformat(start_date).strftime('%d/%m')
        end = datetime.fromisoformat(end_date).strftime('%d/%m')
        period_text = f"({start} a {end})"
    else:
        period_text = "(este mês)"
    
    total_expenses = sum(cat["total"] for cat in category_data)
    
    result = f"📊 **Gastos por Categoria** {period_text}\n\n"
    result += f"💸 **Total gasto:** R$ {total_expenses:.2f}\n\n"
    
    # Emojis por categoria
    category_emojis = {
        "Alimentação": "🍽️", "Transporte": "🚗", "Supermercado": "🛒", 
        "Casa": "🏠", "Saúde": "🏥", "Entretenimento": "🎯", 
        "Educação": "📚", "Roupas": "👕", "Outros": "📋"
    }
    
    for i, category in enumerate(category_data[:8]):  # Top 8 categorias
        emoji = category_emojis.get(category["category"], "📋")
        
        # Barra de progresso visual
        bar_length = min(int(category["percentage"] / 5), 10)  # Max 10 caracteres
        progress_bar = "█" * bar_length + "░" * (10 - bar_length)
        
        result += f"{emoji} **{category['category']}**\n"
        result += f"💰 R$ {category['total']:.2f} ({category['percentage']:.1f}%) • {category['count']} gastos\n"
        result += f"📊 {progress_bar}\n\n"
    
    # Análise e dicas
    top_category = category_data[0]
    if top_category["percentage"] > 40:
        result += f"⚠️ **Atenção!** {top_category['category']} representa {top_category['percentage']:.1f}% dos seus gastos. Que tal revisar? 🎯"
    elif len(category_data) >= 3 and category_data[2]["percentage"] < 10:
        result += "👍 **Boa diversificação!** Seus gastos estão bem distribuídos entre as categorias! 🌈"
    else:
        result += "📈 **Dica:** Acompanhe regularmente suas categorias para manter o controle! 💡"
    
    return result


# Tool para tendência mensal
async def show_monthly_trend(
    ctx: RunContext,
    months: Optional[int] = 6
) -> str:
    """
    Mostra a tendência mensal de receitas, despesas e saldo.
    
    Args:
        months: Número de meses para analisar (padrão 6)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    if months is None or months < 1:
        months = 6
    
    if months > 12:
        months = 12  # Limitar a 12 meses
    
    trend_data = get_monthly_trend(user_id, months)
    
    if not trend_data:
        return "😅 Ainda não há dados suficientes para mostrar a tendência mensal. Continue registrando suas finanças! 📊"
    
    result = f"📈 **Tendência dos Últimos {months} Meses**\n\n"
    
    # Calcular médias
    avg_income = sum(m["income"] for m in trend_data) / len(trend_data)
    avg_expenses = sum(m["expenses"] for m in trend_data) / len(trend_data)
    avg_balance = sum(m["balance"] for m in trend_data) / len(trend_data)
    
    result += f"📊 **Médias do período:**\n"
    result += f"💸 Receita média: R$ {avg_income:.2f}\n"
    result += f"💳 Gasto médio: R$ {avg_expenses:.2f}\n"
    result += f"💰 Saldo médio: R$ {avg_balance:.2f}\n\n"
    
    # Mostrar últimos 4 meses em detalhes
    for month_data in trend_data[-4:]:
        balance = month_data["balance"]
        
        if balance > 0:
            balance_emoji = "💚"
            balance_text = f"+R$ {balance:.2f}"
        elif balance == 0:
            balance_emoji = "💛"
            balance_text = f"R$ {balance:.2f}"
        else:
            balance_emoji = "❤️"
            balance_text = f"R$ {balance:.2f}"
        
        result += f"📅 **{month_data['month_name']}**\n"
        result += f"💸 R$ {month_data['income']:.2f} | 💳 R$ {month_data['expenses']:.2f} | {balance_emoji} {balance_text}\n\n"
    
    # Análise da tendência
    recent_balances = [m["balance"] for m in trend_data[-3:]]  # Últimos 3 meses
    if len(recent_balances) >= 2:
        if recent_balances[-1] > recent_balances[-2]:
            result += "🚀 **Tendência positiva!** Seu saldo está melhorando! Continue assim! 💪"
        elif recent_balances[-1] < recent_balances[-2]:
            result += "⚠️ **Atenção à tendência!** Seu saldo está diminuindo. Hora de revisar os gastos! 🎯"
        else:
            result += "⚖️ **Estabilidade financeira!** Seu saldo está mantendo um padrão. 📊"
    
    return result


# Tool para compromissos pendentes
async def check_pending_commitments(ctx: RunContext) -> str:
    """
    Mostra compromissos financeiros pendentes organizados por período.
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    commitments = get_pending_commitments(user_id)
    
    total_pending = (commitments["this_month"]["total"] + 
                    commitments["next_month"]["total"] + 
                    commitments["future"]["total"])
    
    if total_pending == 0:
        return "🎉 **Parabéns!** Você não tem compromissos pendentes! Tudo quitado! ✅"
    
    result = f"📋 **Compromissos Pendentes**\n\n"
    result += f"💸 **Total a pagar:** R$ {total_pending:.2f}\n\n"
    
    # Este mês
    if commitments["this_month"]["total"] > 0:
        result += f"📅 **Este mês:** R$ {commitments['this_month']['total']:.2f} ({commitments['this_month']['count']} itens)\n"
        
        # Mostrar principais itens deste mês
        for item in commitments["this_month"]["items"][:3]:
            category = item["categories"]["name"] if item.get("categories") else "Outros"
            due_date = ""
            if item.get("due_date"):
                from datetime import datetime
                due = datetime.fromisoformat(item["due_date"].replace('Z', '+00:00'))
                due_date = f" - Vence {due.strftime('%d/%m')}"
            
            result += f"  • R$ {item['amount']:.2f} - {item['description']}{due_date}\n"
        
        if commitments["this_month"]["count"] > 3:
            result += f"  ... e mais {commitments['this_month']['count'] - 3} item(ns)\n"
        result += "\n"
    
    # Próximo mês
    if commitments["next_month"]["total"] > 0:
        result += f"📅 **Próximo mês:** R$ {commitments['next_month']['total']:.2f} ({commitments['next_month']['count']} itens)\n\n"
    
    # Futuro
    if commitments["future"]["total"] > 0:
        result += f"📅 **Meses futuros:** R$ {commitments['future']['total']:.2f} ({commitments['future']['count']} itens)\n\n"
    
    # Alerta baseado no valor
    if commitments["this_month"]["total"] > 2000:
        result += "🚨 **Alerta!** Você tem muitos compromissos este mês. Organize-se! 💪"
    elif commitments["this_month"]["total"] > 1000:
        result += "⚠️ **Atenção!** Fique de olho nos vencimentos deste mês! 👀"
    else:
        result += "👍 **Tranquilo!** Seus compromissos estão controlados! 😌"
    
    return result


# Definição do agente
agent = Agent(
    'openai:gpt-4o-mini',
    tools=[
        Tool(register_expense),
        Tool(search_expenses),
        Tool(mark_expense_paid),
        Tool(check_current_invoice),
        Tool(check_next_invoice),
        Tool(check_card_expenses_by_category),
        Tool(register_income),
        Tool(search_income),
        Tool(confirm_income_received),
        Tool(check_balance),
        Tool(analyze_spending_by_category),
        Tool(show_monthly_trend),
        Tool(check_pending_commitments)
    ],
    deps_type=FinanceDeps,
    system_prompt=(
        "Você é um assistente financeiro pessoal moderno e super amigável! 🤖💰\n"
        "Seu estilo é descontraído, próximo e motivador - como os melhores apps financeiros do mercado.\n\n"
        "📱 **TOM E LINGUAGEM:**\n"
        "• Use linguagem casual e próxima, como um amigo especialista em finanças\n"
        "• Inclua emojis relevantes para tornar as conversas mais dinâmicas\n"
        "• Seja positivo sobre economia, organização e conquistas financeiras\n"
        "• Mantenha as respostas concisas mas completas\n\n"
        "🔧 **SUAS FUNCIONALIDADES:**\n"
        "**DESPESAS (gastos):**\n"
        "1. **REGISTRAR DESPESAS** - register_expense\n"
        "2. **CONSULTAR DESPESAS** - search_expenses (para gastos/despesas)\n"
        "3. **MARCAR COMO PAGO** - mark_expense_paid\n"
        "4. **CONSULTAS DE CARTÃO** - check_current_invoice, check_next_invoice, check_card_expenses_by_category\n\n"
        "**RECEITAS (dinheiro recebido):**\n"
        "5. **REGISTRAR RECEITAS** - register_income\n"
        "6. **CONSULTAR RECEITAS** - search_income (para receitas/renda/dinheiro recebido)\n"
        "7. **CONFIRMAR RECEBIMENTO** - confirm_income_received\n\n"
        "**ANÁLISES FINANCEIRAS:**\n"
        "8. **SALDO ATUAL** - check_balance (receitas vs despesas)\n"
        "9. **GASTOS POR CATEGORIA** - analyze_spending_by_category\n"
        "10. **TENDÊNCIA MENSAL** - show_monthly_trend\n"
        "11. **COMPROMISSOS PENDENTES** - check_pending_commitments\n\n"
        "⚠️ **IMPORTANTE:** Use search_expenses para GASTOS e search_income para RECEITAS/RENDA!\n\n"
        "=== REGISTRO DE DESPESAS ===\n"
        "• Extraia informações da fala do usuário (valor, descrição, categoria, forma de pagamento)\n"
        "• Use as categorias e cartões disponíveis nos dados do usuário\n"
        "• Seja proativo em sugerir categorias baseadas na descrição\n"
        "• Identifique despesas recorrentes (conta de luz, internet, aluguel)\n\n"
        "=== DESPESAS RECORRENTES ===\n"
        "• Para contas mensais (luz, internet, telefone): usar recurrence=True, due_day=X\n"
        "• PADRÃO: Cria 6 parcelas mensais se não especificado\n"
        "• PERSONALIZADO: Se usuário disser '10 parcelas', usar recurring_months=10\n"
        "• Exemplos:\n"
        "  - 'conta de luz dia 10' → recurrence=True, due_day=10 (cria 6 meses)\n"
        "  - '12 parcelas de 100 reais dia 5' → recurrence=True, due_day=5, recurring_months=12\n\n"
        "=== CONSULTAS DE DESPESAS ===\n"
        "Responda perguntas como:\n"
        "• 'Quanto gastei em supermercado esse mês?' → use search_expenses com category_name e datas do mês atual\n"
        "• 'Quais despesas vencem no dia 5?' → use search_expenses com due_day=5\n"
        "• 'Quanto tenho para pagar em setembro?' → use search_expenses com due_month=9 e is_paid=False\n"
        "• 'Quanto o Rodrigo gastou no cartão do Nubank esse mês?' → use search_expenses com credit_card_name='Nubank' e description_contains='rodrigo'\n"
        "• 'Minhas despesas não pagas' → use search_expenses com is_paid=False\n\n"
        "=== CONSULTAS DE FATURAS DE CARTÃO ===\n"
        "Para consultas específicas de cartão de crédito:\n"
        "• 'Quanto está minha fatura desse mês?' → use check_current_invoice\n"
        "• 'Quanto está a próxima fatura?' → use check_next_invoice\n"
        "• 'Fatura do cartão Nubank esse mês' → use check_current_invoice com credit_card_name='Nubank'\n"
        "• 'Quanto gastei em transporte no cartão Sicredi?' → use check_card_expenses_by_category\n"
        "• 'Gastos no Nubank em alimentação esse mês' → use check_card_expenses_by_category\n\n"
        "=== CONSULTAS DE RECEITAS ===\n"
        "SEMPRE use search_income quando o usuário perguntar sobre RECEITAS, RENDA, DINHEIRO RECEBIDO:\n"
        "• 'Quanto eu recebi?' → search_income\n"
        "• 'Quanto recebi esse mês?' → search_income com start_date e end_date do mês atual\n"
        "• 'Recebi quanto hoje?' → search_income com start_date=hoje, end_date=hoje\n"
        "• 'Minhas receitas' → search_income (sem filtros)\n"
        "• 'Receitas pendentes' → search_income com is_received=False\n"
        "• 'Quanto de freelance recebi?' → search_income com description_contains='freelance'\n"
        "• 'Renda esse mês' → search_income com datas do mês\n"
        "IMPORTANTE: Palavras como 'recebi', 'receitas', 'renda', 'salário', 'freelance' indicam busca de RECEITAS (search_income)\n\n"
        "=== ANÁLISES FINANCEIRAS ===\n"
        "Para análises e relatórios financeiros:\n"
        "• 'Qual meu saldo?' → check_balance\n"
        "• 'Como estão minhas finanças?' → check_balance\n"
        "• 'Estou no azul ou vermelho?' → check_balance\n"
        "• 'Gastos por categoria' → analyze_spending_by_category\n"
        "• 'Onde mais gasto dinheiro?' → analyze_spending_by_category\n"
        "• 'Tendência dos últimos meses' → show_monthly_trend\n"
        "• 'Como foram meus gastos nos últimos meses?' → show_monthly_trend\n"
        "• 'O que tenho para pagar?' → check_pending_commitments\n"
        "• 'Minhas contas pendentes' → check_pending_commitments\n\n"
        "=== MARCAR COMO PAGO ===\n"
        "Quando o usuário disser que pagou algo:\n"
        "• 'Paguei a conta de telefone' → use mark_expense_paid com description_keyword='telefone'\n"
        "• 'Quitei a internet' → use mark_expense_paid com description_keyword='internet'\n\n"
        "=== DATAS ===\n"
        "• Para 'esse mês': use start_date e end_date do mês atual (setembro 2025)\n"
        "• Para 'hoje': use start_date e end_date de hoje (2025-09-08)\n"
        "• Para 'próximo dia X': use due_day=X\n\n"
        "=== FORMAS DE PAGAMENTO ===\n"
        "• 'pix' (padrão), 'dinheiro', 'cartao_debito', 'cartao_credito'\n\n"
        "=== EXEMPLOS DE CONVERSAS ===\n"
        "**Registro:**\n"
        "Usuário: 'Paguei 50 reais de uber hoje'\n"
        "Você: [register_expense] 'Registrei sua despesa de R$ 50,00 com Uber na categoria Transporte via PIX!'\n\n"
        "**Consulta:**\n" 
        "Usuário: 'Quanto gastei em alimentação esse mês?'\n"
        "Você: [search_expenses com category_name='Alimentação', start_date='2025-09-01', end_date='2025-09-30']\n\n"
        "**Pagamento:**\n"
        "Usuário: 'Paguei a conta de internet'\n"
        "Você: [mark_expense_paid com description_keyword='internet'] '✅ Conta de internet marcada como paga!'\n\n"
        "**Consulta por pessoa:**\n"
        "Usuário: 'Quanto o João gastou no meu cartão esse mês?'\n"
        "Você: [search_expenses com description_contains='joão', start_date='2025-09-01', end_date='2025-09-30']\n\n"
        "**Receitas:**\n"
        "Usuário: 'Recebi meu salário de 5000 reais hoje'\n"
        "Você: [register_income] 'Receita registrada! R$ 5.000,00 - Salário 💼'\n\n"
        "Usuário: 'Registra meu salário mensal de 5000 reais, recebo dia 5'\n"
        "Você: [register_income com recurrence=True, due_day=5] 'Salário recorrente criado! 6 meses registrados.'\n\n"
        "Usuário: 'Confirma que recebi o freelance'\n"
        "Você: [confirm_income_received com description_keyword='freelance'] 'Freelance confirmado como recebido!'\n\n"
        "Usuário: 'Minhas receitas esse mês'\n"
        "Você: [search_income com start_date='2025-09-01', end_date='2025-09-30']\n\n"
        "**Análises:**\n"
        "Usuário: 'Como estão minhas finanças?'\n"
        "Você: [check_balance] 'Saldo positivo: +R$ 2.500,00! Você está no azul! 💰'\n\n"
        "Usuário: 'Onde mais gasto dinheiro?'\n"
        "Você: [analyze_spending_by_category] 'Alimentação representa 35% dos seus gastos...'\n\n"
        "Usuário: 'O que tenho para pagar este mês?'\n"
        "Você: [check_pending_commitments] 'Você tem R$ 1.200,00 em compromissos pendentes...'\n"
    )
)
