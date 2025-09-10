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
    get_pending_commitments,
    edit_transaction
)
from calculator_tool import FinancialCalculator
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

# Tool para editar transação existente
async def edit_expense(
    ctx: RunContext,
    description_keyword: str,
    new_payment_method: Optional[str] = None,
    new_category_name: Optional[str] = None,
    new_amount: Optional[float] = None,
    new_description: Optional[str] = None
) -> str:
    """
    Edita uma despesa existente baseada na descrição.
    
    Args:
        description_keyword: Palavra-chave para encontrar a despesa (ex: "cartão da mãe", "uber")
        new_payment_method: Novo método de pagamento ("pix", "dinheiro", "cartao_debito", "cartao_credito")
        new_category_name: Nova categoria (opcional)
        new_amount: Novo valor (opcional)
        new_description: Nova descrição (opcional)
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    # Verificar se nova categoria existe (se especificada)
    if new_category_name:
        category_found = False
        for cat in ctx.deps.categories:
            if cat["name"].lower() == new_category_name.lower():
                category_found = True
                break
        
        if not category_found:
            categories_text = ", ".join([cat["name"] for cat in ctx.deps.categories])
            return f"❌ Categoria '{new_category_name}' não encontrada. Categorias disponíveis: {categories_text}"
    
    # Editar transação
    result = edit_transaction(
        user_id=user_id,
        description_keyword=description_keyword,
        new_payment_method=new_payment_method,
        new_category_name=new_category_name,
        new_amount=new_amount,
        new_description=new_description
    )
    
    if result["success"]:
        return f"✏️ **Despesa editada com sucesso!**\n{result['message']}\n\n📊 Seu orçamento foi atualizado!"
    else:
        return f"😅 {result['message']}\n\n💡 Tente usar uma palavra-chave mais específica da descrição."

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
    
    Use esta função para responder perguntas sobre:
    - "O que tenho pendente este mês?"
    - "Quanto tenho pendente para o próximo mês?"
    - "Quais são meus compromissos futuros?"
    
    Retorna dados organizados por: este mês, próximo mês e meses futuros.
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
        from datetime import timedelta
        next_month_name = (datetime.now().replace(day=28) + timedelta(days=4)).strftime('%B de %Y')
        result += f"📅 **{next_month_name}:** R$ {commitments['next_month']['total']:.2f} ({commitments['next_month']['count']} itens)\n"
        
        # Mostrar principais itens do próximo mês
        for item in commitments["next_month"]["items"][:3]:
            category = item["categories"]["name"] if item.get("categories") else "Outros"
            due_date = ""
            if item.get("due_date"):
                due = datetime.fromisoformat(item["due_date"].replace('Z', '+00:00'))
                due_date = f" - Vence {due.strftime('%d/%m')}"
            
            result += f"  • R$ {item['amount']:.2f} - {item['description']}{due_date}\n"
        
        if commitments["next_month"]["count"] > 3:
            result += f"  ... e mais {commitments['next_month']['count'] - 3} item(ns)\n"
        result += "\n"
    
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


async def check_next_month_commitments(ctx: RunContext) -> str:
    """
    Mostra especificamente os compromissos do próximo mês.
    
    Use esta função quando o usuário perguntar especificamente sobre:
    - "Quanto tenho pendente para o próximo mês?"
    - "O que vence no próximo mês?"
    - "Quais são meus compromissos do mês que vem?"
    """
    if not ctx.deps:
        return "❌ Erro: Dados do usuário não encontrados"
    
    user_id = ctx.deps.user_id
    
    commitments = get_pending_commitments(user_id)
    next_month_data = commitments["next_month"]
    
    if next_month_data["total"] == 0:
        from datetime import timedelta
        next_month_name = (datetime.now().replace(day=28) + timedelta(days=4)).strftime('%B de %Y')
        return f"🎉 **Ótimas notícias!** Você não tem compromissos pendentes para {next_month_name}! 🌟"
    
    from datetime import timedelta
    next_month_name = (datetime.now().replace(day=28) + timedelta(days=4)).strftime('%B de %Y')
    
    result = f"📅 **Compromissos para {next_month_name}:**\n\n"
    result += f"💰 **Total:** R$ {next_month_data['total']:.2f} ({next_month_data['count']} compromissos)\n\n"
    
    # Listar todos os itens do próximo mês
    for item in next_month_data["items"]:
        category = item["categories"]["name"] if item.get("categories") else "Outros"
        
        # Determinar emoji da categoria
        category_emoji = "💳" if "cartão" in category.lower() else "🏠" if any(x in category.lower() for x in ["casa", "moradia", "aluguel"]) else "🍔" if "alimentação" in category.lower() else "🚗" if "transporte" in category.lower() else "💰"
        
        due_date = ""
        if item.get("due_date"):
            due = datetime.fromisoformat(item["due_date"].replace('Z', '+00:00'))
            due_date = f" - Vence {due.strftime('%d/%m')}"
        
        result += f"{category_emoji} R$ {item['amount']:.2f} - {item['description']}{due_date}\n"
        result += f"   📂 {category}\n\n"
    
    # Dica baseada no valor total
    if next_month_data["total"] > 2000:
        result += "💡 **Dica:** É um valor alto! Comece a se organizar já para não apertar no próximo mês! 💪"
    elif next_month_data["total"] > 1000:
        result += "👀 **Lembre-se:** Organize-se com antecedência para esses compromissos! 📝"
    else:
        result += "😌 **Tranquilo!** Um mês bem controlado te aguarda! ✨"
    
    return result


# Ferramenta de cálculo financeiro
async def financial_calculator(
    ctx: RunContext,
    operation: str,
    values: list[float]
) -> str:
    """
    Ferramenta de cálculos financeiros precisos para somas, subtrações, multiplicações e porcentagens.
    
    Args:
        operation: Tipo de operação ('sum', 'subtract', 'multiply', 'divide', 'percentage')
        values: Lista de valores para calcular (ex: [100.50, 200.30] para somar dois valores)
    
    Returns:
        Resultado formatado como moeda brasileira ou percentual
    """
    calc = FinancialCalculator()
    
    try:
        if operation == 'sum':
            result = calc.add(*values)
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


# Definição do agente
agent = Agent(
    'openai:gpt-4o-mini',
    tools=[
        Tool(register_expense),
        Tool(search_expenses),
        Tool(mark_expense_paid),
        Tool(edit_expense),
        Tool(check_current_invoice),
        Tool(check_next_invoice),
        Tool(check_card_expenses_by_category),
        Tool(register_income),
        Tool(search_income),
        Tool(confirm_income_received),
        Tool(check_balance),
        Tool(analyze_spending_by_category),
        Tool(show_monthly_trend),
        Tool(check_pending_commitments),
        Tool(check_next_month_commitments),
        Tool(financial_calculator)
    ],
    deps_type=FinanceDeps,
    system_prompt=f"""
Você é um assistente financeiro pessoal brasileiro especializado em ajudar usuários a gerenciar suas finanças de forma prática e descontraída.

## 🗓️ CONTEXTO TEMPORAL IMPORTANTE:
- Data atual: {datetime.now().strftime('%d/%m/%Y')}
- Mês atual: {datetime.now().strftime('%B de %Y')} 
- Quando falar sobre "este mês", refira-se ao mês atual ({datetime.now().strftime('%m/%Y')})
- Para consultas sobre próximo mês ou períodos futuros, use check_pending_commitments que mostra todos os períodos

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

### FORMATO DA CONFIRMAÇÃO (apenas quando necessário):
"✅ **Dados extraídos:**
- 💰 R$ [valor] - [descrição]
- 💳 [forma_pagamento]
- 📂 [categoria]

Está tudo correto? Responda 'sim' para confirmar ou me diga o que ajustar."

## 📝 TEMPLATES DE RESPOSTA OBRIGATÓRIOS:

### ✅ Para Registros de Despesa:
"💸 **Despesa registrada!**
- 💰 R$ [valor] - [descrição]
- 💳 [forma_pagamento]
- 📂 Categoria: [categoria]

Seu orçamento está atualizado! 📊"

### ✅ Para Registros de Receita:  
"💰 **Receita registrada!**
- 💵 R$ [valor] - [descrição]
- 📅 [data/recorrencia]
- 📂 Categoria: [categoria]

Suas finanças estão em dia! ✨"

### ✅ Para Consultas de Saldo:
"📊 **Seu saldo atual:**
- 💚 Receitas: R$ [valor]
- 💸 Despesas: R$ [valor]  
- ⚖️ Saldo: R$ [valor] [emoji_status]

[dica_personalizada]"

### ✅ Para Despesas Pendentes:
"📅 **Compromissos do mês:**
• R$ [valor] - [descrição] (Vence: [data])

Total: R$ [valor_total] 💳"

## 🔧 DESPESAS RECORRENTES - REGRAS IMPORTANTES:
- **PADRÃO**: 6 meses se não especificado
- **COMUNICAÇÃO**: Sempre informe quantos meses foram criados
- **EXEMPLO**: "Registrei pelos próximos 6 meses" (não "6 meses")

## 📊 ANÁLISES TEMPORAIS:
- **Este mês**: Dados do mês atual
- **Próximo mês**: Use check_pending_commitments para mostrar compromissos futuros
- **Pendentes**: Compromissos não pagos (use check_pending_commitments para ver todos os períodos)
- **Análise mensal**: Foque no período atual, mas responda sobre próximo mês quando perguntado

## ⚡ FUNCIONALIDADES DISPONÍVEIS:
**DESPESAS:** register_expense, search_expenses, mark_expense_paid, edit_expense, check_current_invoice, check_next_invoice, check_card_expenses_by_category
**RECEITAS:** register_income, search_income, confirm_income_received  
**ANÁLISES:** check_balance, analyze_spending_by_category, show_monthly_trend, check_pending_commitments, check_next_month_commitments
**CÁLCULOS:** financial_calculator (para somas, subtrações, multiplicações e porcentagens precisas)

**IMPORTANTE:** Para perguntas sobre próximo mês, use check_next_month_commitments para resposta focada e detalhada!

## 🎯 PRINCIPAIS REGRAS:
1. Use search_expenses para GASTOS e search_income para RECEITAS/RENDA
2. Para despesas recorrentes, sempre especifique o número de meses criados
3. **Para consultas sobre próximo mês:** Use check_pending_commitments que mostra todos os períodos
4. Use templates padronizados para confirmações
5. Seja claro sobre o que são pendências vs despesas futuras
6. **SEMPRE use financial_calculator para somas, subtrações e cálculos - NUNCA calcule manualmente**
7. Formate valores sempre em Real brasileiro
8. Confirme TODAS as ações com detalhes específicos
9. **Para edições:** Use edit_expense quando usuário quiser alterar método de pagamento, categoria, valor ou descrição

## 🔧 EXEMPLOS DE EDIÇÃO:
- "Muda essa última despesa para pix" → edit_expense(description_keyword="palavra_da_despesa", new_payment_method="pix")
- "Altera o cartão da minha mãe para pix" → edit_expense(description_keyword="cartão da mãe", new_payment_method="pix")
- "Muda a categoria do uber para transporte" → edit_expense(description_keyword="uber", new_category_name="Transporte")

IMPORTANTE: 
- Use financial_calculator para TODOS os cálculos matemáticos
- Para edições, sempre identifique palavras-chave da descrição original
- Sempre use os templates de resposta fornecidos para manter consistência na comunicação!
    """
)
