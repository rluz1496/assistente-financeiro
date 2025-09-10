from database import supabase
from datetime import datetime, date
import calendar

def calculate_credit_card_due_date(purchase_date: date, close_day: int, due_day: int):
    """
    Calcula a data de vencimento de uma compra no cartão baseada no ciclo
    
    Args:
        purchase_date: Data da compra
        close_day: Dia que fecha a fatura (ex: 1)
        due_day: Dia que vence a fatura (ex: 10)
    
    Returns:
        tuple: (due_date, close_date) - datas de vencimento e fechamento da fatura
    """
    purchase_year = purchase_date.year
    purchase_month = purchase_date.month
    purchase_day = purchase_date.day
    
    # Determinar em qual fatura a compra entra
    if purchase_day <= close_day:
        # Compra feita antes ou no dia de fechamento - entra na fatura do mês atual
        # Fatura fecha no mês atual e vence no mês atual
        close_month = purchase_month
        close_year = purchase_year
        due_month = purchase_month  
        due_year = purchase_year
    else:
        # Compra feita após o fechamento - entra na fatura do próximo mês
        # Fatura fecha no próximo mês
        close_month = purchase_month + 1
        close_year = purchase_year
        
        # Ajustar se passou de dezembro
        if close_month > 12:
            close_month = 1
            close_year += 1
            
        # Data de vencimento é no mesmo mês do fechamento
        due_month = close_month
        due_year = close_year
    
    # Calcular data de fechamento da fatura
    try:
        close_date = date(close_year, close_month, close_day)
    except ValueError:
        # Se o dia não existe no mês, usar último dia
        last_day = calendar.monthrange(close_year, close_month)[1]
        close_date = date(close_year, close_month, min(close_day, last_day))
    
    # Calcular data de vencimento da fatura
    try:
        due_date = date(due_year, due_month, due_day)
    except ValueError:
        # Se o dia não existe no mês, usar último dia
        last_day = calendar.monthrange(due_year, due_month)[1]
        due_date = date(due_year, due_month, min(due_day, last_day))
    
    return due_date, close_date

def get_credit_card_details(user_id: str, credit_card_id: str):
    """Busca detalhes completos de um cartão específico"""
    if not supabase:
        return {
            "id": credit_card_id,
            "name": "Cartão Teste",
            "limit": 5000.00,
            "close_day": 1,
            "due_day": 10
        }
    
    try:
        resp = supabase.table("credit_cards").select("*").eq("user_id", user_id).eq("id", credit_card_id).execute()
        if resp.data:
            card = resp.data[0]
            return card
        return None
    except Exception as e:
        print(f"Erro ao buscar detalhes do cartão: {e}")
        return None

def create_or_update_invoice(user_id: str, credit_card_id: str, bill_month: int, bill_year: int, amount: float):
    """
    Cria ou atualiza uma fatura do cartão
    
    Args:
        user_id: ID do usuário
        credit_card_id: ID do cartão
        bill_month: Mês da fatura
        bill_year: Ano da fatura
        amount: Valor a ser adicionado na fatura
    """
    if not supabase:
        print(f"Mock: Criando/atualizando fatura - Cartão: {credit_card_id}, Mês: {bill_month}/{bill_year}, Valor: R$ {amount:.2f}")
        return {"success": True}
    
    try:
        # Buscar fatura existente (usando nomes corretos dos campos)
        existing_invoice = supabase.table("invoices").select("*").eq("user_id", user_id).eq("credit_card_id", credit_card_id).eq("month", bill_month).eq("year", bill_year).execute()
        
        if existing_invoice.data:
            # Atualizar fatura existente
            current_amount = existing_invoice.data[0]["total_amount"] or 0
            new_amount = current_amount + amount
            
            resp = supabase.table("invoices").update({
                "total_amount": new_amount
            }).eq("id", existing_invoice.data[0]["id"]).execute()
            
            return {"success": True, "invoice_id": existing_invoice.data[0]["id"], "new_amount": new_amount}
        else:
            # Buscar detalhes do cartão para obter as datas
            card_details = get_credit_card_details(user_id, credit_card_id)
            if not card_details:
                return {"success": False, "message": "Cartão não encontrado"}
            
            # Calcular datas da fatura
            due_date = date(bill_year, bill_month, card_details["due_day"])
            
            # Criar nova fatura
            invoice_data = {
                "user_id": user_id,
                "credit_card_id": credit_card_id,
                "total_amount": amount,
                "month": bill_month,
                "year": bill_year,
                "due_date": due_date.isoformat(),
                "close_day": card_details["close_day"],
                "is_paid": False,
                "paid_date": None
            }
            
            resp = supabase.table("invoices").insert(invoice_data).execute()
            
            if resp.data:
                return {"success": True, "invoice_id": resp.data[0]["id"], "new_amount": amount}
            else:
                return {"success": False, "message": "Erro ao criar fatura"}
                
    except Exception as e:
        print(f"Erro ao criar/atualizar fatura: {e}")
        return {"success": False, "message": str(e)}

def get_user_by_phone(phone_number: str):
    """Busca usuário pelo número de telefone"""
    if not supabase:
        # Dados mock para desenvolvimento
        return {"id": "550e8400-e29b-41d4-a716-446655440000", "name": "Usuário Teste", "phone_number": phone_number}
    
    try:
        print(f"Debug: Buscando por phone_number = '{phone_number}'")
        resp = supabase.table("users").select("*").eq("phone_number", phone_number).execute()
        print(f"Debug: Resposta do banco: {resp.data}")
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None

# def create_user(phone_number: str, name: str = None):
#     """Cria um novo usuário - FUNÇÃO DESABILITADA"""
#     # Função antiga usando SQLAlchemy - não está sendo usada
#     pass

# def get_or_create_user(phone_number: str, name: str = None):
#     """Busca usuário pelo telefone ou cria se não existir - FUNÇÃO DESABILITADA"""
#     # Função antiga - não está sendo usada
#     pass

def get_user_categories(user_id: str):
    """Busca categorias do usuário"""
    if not supabase:
        return [
            {"id": "cat1", "name": "Alimentação"},
            {"id": "cat2", "name": "Transporte"},
            {"id": "cat3", "name": "Lazer"},
            {"id": "cat4", "name": "Saúde"},
            {"id": "cat5", "name": "Moradia"},
            {"id": "cat6", "name": "Compras"},
            {"id": "cat7", "name": "Educação"},
            {"id": "cat8", "name": "Entretenimento"}
        ]
    
    try:
        # Primeiro tenta buscar categorias específicas do usuário
        resp = supabase.table("categories").select("*").eq("user_id", user_id).execute()
        categories = resp.data or []
        
        # Se não encontrou categorias do usuário, busca categorias globais
        if not categories:
            resp = supabase.table("categories").select("*").is_("user_id", "null").execute()
            categories = resp.data or []
        
        # Se ainda não encontrou, retorna categorias padrão
        if not categories:
            return [
                {"id": "default1", "name": "Alimentação"},
                {"id": "default2", "name": "Transporte"},
                {"id": "default3", "name": "Lazer"},
                {"id": "default4", "name": "Saúde"},
                {"id": "default5", "name": "Moradia"},
                {"id": "default6", "name": "Compras"},
                {"id": "default7", "name": "Educação"},
                {"id": "default8", "name": "Entretenimento"}
            ]
        return categories
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return [
            {"id": "default1", "name": "Alimentação"},
            {"id": "default2", "name": "Transporte"},
            {"id": "default3", "name": "Lazer"},
            {"id": "default4", "name": "Saúde"},
            {"id": "default5", "name": "Moradia"}
        ]

def save_expense_transaction(user_id: str, amount: float, description: str, category_id: str, 
                           payment_method: str = "pix", credit_card_id: str = None, 
                           installments: int = 1, recurrence: bool = False, due_day: int = None, 
                           recurring_months: int = None):
    """Salva uma despesa na tabela transactions"""
    if not supabase:
        print(f"Mock: Salvando despesa - Usuário: {user_id}, Valor: R$ {amount:.2f}, Descrição: {description}, Categoria: {category_id}")
        return {"success": True, "message": "Despesa salva com sucesso! (modo desenvolvimento)"}
    
    try:
        # Definir datas baseado no método de pagamento e recorrência
        from datetime import date
        today = date.today()
        
        # Lógica para despesas recorrentes
        if recurrence and due_day is not None:
            # Para despesas recorrentes: due_date é o dia especificado, paid_date fica null
            try:
                # Criar data para o dia especificado no mês atual
                due_date = today.replace(day=due_day).isoformat()
            except ValueError:
                # Se o dia não existe no mês atual (ex: dia 31 em fevereiro), usar último dia do mês
                import calendar
                last_day = calendar.monthrange(today.year, today.month)[1]
                due_date = today.replace(day=min(due_day, last_day)).isoformat()
            
            paid_date = None  # Null para despesas recorrentes não pagas
        else:
            # Lógica para despesas não recorrentes
            today_str = today.isoformat()
            
            # Para dinheiro, pix e débito: pago na hora (due_date e paid_date = hoje)
            if payment_method in ["dinheiro", "pix", "cartao_debito"]:
                due_date = today_str
                paid_date = today_str
            # Para cartão de crédito: calcular data de vencimento baseada no ciclo
            elif payment_method == "cartao_credito" and credit_card_id:
                # Buscar detalhes do cartão
                card_details = get_credit_card_details(user_id, credit_card_id)
                if card_details:
                    # Calcular data de vencimento baseada no ciclo do cartão
                    due_date_obj, close_date_obj = calculate_credit_card_due_date(
                        today, 
                        card_details["close_day"], 
                        card_details["due_day"]
                    )
                    due_date = due_date_obj.isoformat()
                    paid_date = None  # Cartão não é pago imediatamente
                    
                    # Atualizar/criar fatura do cartão
                    bill_result = create_or_update_invoice(
                        user_id, 
                        credit_card_id, 
                        due_date_obj.month, 
                        due_date_obj.year, 
                        amount
                    )
                    
                    if not bill_result["success"]:
                        print(f"Aviso: Erro ao atualizar fatura: {bill_result.get('message', 'Erro desconhecido')}")
                else:
                    # Cartão não encontrado, usar lógica padrão
                    due_date = None
                    paid_date = None
            else:
                # Outros casos
                due_date = None
                paid_date = None
        
        transaction_data = {
            "user_id": user_id,
            "amount": abs(amount),  # Valor sempre positivo, o tipo define se é receita/despesa
            "description": description,
            "category_id": category_id,
            "payment_method": payment_method,
            "transaction_type": "expense",  # Sempre despesa nesta função
            "type": "expense",  # Campo legado
            "recurrence": recurrence,
            "credit_card_id": credit_card_id,
            "installments": installments if payment_method == "cartao_credito" else 1,
            "due_date": due_date,
            "paid_date": paid_date
        }
        
        # Remove campos None para evitar erros
        transaction_data = {k: v for k, v in transaction_data.items() if v is not None}
        
        # Para despesas recorrentes, criar o número especificado de parcelas (padrão 6 meses)
        if recurrence and due_day is not None:
            transactions_to_insert = []
            
            # Definir número de meses (padrão 6 se não informado)
            months_to_create = recurring_months if recurring_months is not None else 6
            
            # Criar as parcelas mensais
            for month_offset in range(months_to_create):
                transaction_copy = transaction_data.copy()
                
                # Calcular a data de vencimento para cada mês
                target_year = today.year
                target_month = today.month + month_offset
                
                # Ajustar ano se necessário
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                
                # Criar a data de vencimento
                try:
                    due_date_obj = date(target_year, target_month, due_day)
                except ValueError:
                    # Se o dia não existe no mês (ex: dia 31 em fevereiro), usar último dia do mês
                    import calendar
                    last_day = calendar.monthrange(target_year, target_month)[1]
                    due_date_obj = date(target_year, target_month, min(due_day, last_day))
                
                transaction_copy["due_date"] = due_date_obj.isoformat()
                
                # Adicionar sufixo na descrição para identificar o mês/ano
                month_year = due_date_obj.strftime("%m/%Y")
                transaction_copy["description"] = f"{description} - {month_year}"
                
                transactions_to_insert.append(transaction_copy)
            
            # Inserir todas as parcelas de uma vez
            resp = supabase.table("transactions").insert(transactions_to_insert).execute()
            
            if resp.data:
                return {
                    "success": True, 
                    "message": f"Despesa recorrente criada com sucesso! Geradas {len(transactions_to_insert)} parcelas para os próximos 6 meses.",
                    "data": resp.data,
                    "recurring_count": len(transactions_to_insert)
                }
            else:
                return {"success": False, "message": "Erro ao criar despesas recorrentes"}
        else:
            # Despesa normal (não recorrente)
            resp = supabase.table("transactions").insert(transaction_data).execute()
            return {"success": True, "message": "Despesa salva com sucesso!", "data": resp.data}
    except Exception as e:
        print(f"Erro ao salvar despesa: {e}")
        return {"success": False, "message": f"Erro ao salvar: {str(e)}"}

def get_user_credit_cards(user_id: str):
    """Busca cartões de crédito do usuário"""
    if not supabase:
        return [
            {"id": "card1", "name": "Cartão Visa", "limit": 3000.00},
            {"id": "card2", "name": "Cartão Master", "limit": 2000.00}
        ]
    
    try:
        resp = supabase.table("credit_cards").select("*").eq("user_id", user_id).execute()
        return resp.data or []
    except Exception as e:
        print(f"Erro ao buscar cartões: {e}")
        return []

def get_recent_transactions(user_id: str, limit: int = 10):
    """Busca transações recentes do usuário"""
    if not supabase:
        return [
            {"id": "t1", "amount": -25.50, "description": "Almoço", "category": "Alimentação", "created_at": "2025-09-08"},
            {"id": "t2", "amount": -12.00, "description": "Uber", "category": "Transporte", "created_at": "2025-09-07"}
        ]
    
    try:
        resp = supabase.table("transactions").select("*, categories(name)").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception as e:
        print(f"Erro ao buscar transações: {e}")
        return []

def search_transactions(user_id: str, filters: dict = None):
    """
    Busca transações com filtros avançados
    
    Filtros disponíveis:
    - start_date: Data início (YYYY-MM-DD)
    - end_date: Data fim (YYYY-MM-DD) 
    - category_name: Nome da categoria
    - payment_method: Método de pagamento
    - is_paid: True/False para transações pagas
    - due_day: Dia do vencimento (1-31)
    - due_month: Mês do vencimento (1-12)
    - credit_card_name: Nome do cartão de crédito
    - description_contains: Texto que deve estar na descrição
    - min_amount: Valor mínimo
    - max_amount: Valor máximo
    """
    if not supabase:
        return []
    
    try:
        # Query base com joins
        query = supabase.table("transactions").select("""
            id, amount, description, transaction_type, payment_method, 
            due_date, paid_date, recurrence, installments, created_at,
            categories(id, name),
            credit_cards(id, name)
        """).eq("user_id", user_id)
        
        if not filters:
            # Sem filtros, retorna todas as transações
            resp = query.order("created_at", desc=True).execute()
            return resp.data or []
        
        # Aplicar filtros de data
        if filters.get("start_date"):
            query = query.gte("created_at", f"{filters['start_date']}T00:00:00")
        if filters.get("end_date"):
            query = query.lte("created_at", f"{filters['end_date']}T23:59:59")
            
        # Filtro por método de pagamento
        if filters.get("payment_method"):
            query = query.eq("payment_method", filters["payment_method"])
            
        # Filtro por recorrência
        if filters.get("recurrence"):
            query = query.eq("recurrence", filters["recurrence"])
        
        # Executar query base
        resp = query.order("created_at", desc=True).execute()
        transactions = resp.data or []
        
        # Aplicar filtros que precisam ser feitos no Python
        filtered_transactions = []
        
        for transaction in transactions:
            # Filtro por categoria
            if filters.get("category_name"):
                if not transaction.get("categories") or \
                   transaction["categories"]["name"].lower() != filters["category_name"].lower():
                    continue
            
            # Filtro por cartão de crédito
            if filters.get("credit_card_name"):
                if not transaction.get("credit_cards") or \
                   transaction["credit_cards"]["name"].lower() != filters["credit_card_name"].lower():
                    continue
            
            # Filtro por status de pagamento
            if filters.get("is_paid") is not None:
                is_paid = bool(transaction.get("paid_date"))
                if is_paid != filters["is_paid"]:
                    continue
            
            # Filtro por dia do vencimento
            if filters.get("due_day"):
                if not transaction.get("due_date"):
                    continue
                due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
                if due_date.day != filters["due_day"]:
                    continue
            
            # Filtro por mês do vencimento
            if filters.get("due_month"):
                if not transaction.get("due_date"):
                    continue
                due_date = datetime.fromisoformat(transaction["due_date"].replace('Z', '+00:00'))
                if due_date.month != filters["due_month"]:
                    continue
            
            # Filtro por conteúdo na descrição
            if filters.get("description_contains"):
                if filters["description_contains"].lower() not in transaction["description"].lower():
                    continue
            
            # Filtros por valor
            if filters.get("min_amount") and transaction["amount"] < filters["min_amount"]:
                continue
            if filters.get("max_amount") and transaction["amount"] > filters["max_amount"]:
                continue
                
            filtered_transactions.append(transaction)
        
        return filtered_transactions
        
    except Exception as e:
        print(f"Erro ao buscar transações: {e}")
        return []

def mark_transaction_as_paid(transaction_id: str, user_id: str, paid_date: str = None):
    """
    Marca uma transação como paga
    
    Args:
        transaction_id: ID da transação
        user_id: ID do usuário (para validação)
        paid_date: Data do pagamento (formato YYYY-MM-DD), se None usa data atual
    """
    if not supabase:
        return {"success": False, "message": "Banco de dados não disponível"}
    
    try:
        from datetime import datetime
        
        # Se não informou data, usa hoje
        if not paid_date:
            paid_date = datetime.now().strftime('%Y-%m-%d')
        
        # Primeiro verifica se a transação existe e pertence ao usuário
        resp = supabase.table("transactions").select("id, description, amount").eq("id", transaction_id).eq("user_id", user_id).execute()
        
        if not resp.data:
            return {"success": False, "message": "Transação não encontrada"}
        
        transaction = resp.data[0]
        
        # Atualiza a transação
        update_resp = supabase.table("transactions").update({
            "paid_date": paid_date
        }).eq("id", transaction_id).eq("user_id", user_id).execute()
        
        if update_resp.data:
            return {
                "success": True, 
                "message": f"Transação '{transaction['description']}' (R$ {transaction['amount']}) marcada como paga em {paid_date}",
                "transaction": transaction
            }
        else:
            return {"success": False, "message": "Erro ao atualizar transação"}
            
    except Exception as e:
        print(f"Erro ao marcar transação como paga: {e}")
        return {"success": False, "message": f"Erro: {str(e)}"}

def find_unpaid_transactions_by_description(user_id: str, description_keyword: str):
    """
    Busca transações não pagas que contenham uma palavra-chave na descrição
    Útil para identificar uma despesa específica para marcar como paga
    """
    if not supabase:
        return []
    
    try:
        # Busca transações não pagas com a palavra-chave na descrição
        resp = supabase.table("transactions").select("""
            id, amount, description, payment_method, due_date, created_at,
            categories(name),
            credit_cards(name)
        """).eq("user_id", user_id).is_("paid_date", "null").ilike("description", f"%{description_keyword}%").execute()
        
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar transações não pagas: {e}")
        return []

def get_current_invoice(user_id: str, credit_card_id: str = None):
    """
    Busca a fatura atual (do mês corrente) de um cartão específico ou todos os cartões
    """
    if not supabase:
        return []
    
    try:
        current_date = date.today()
        query = supabase.table("invoices").select("""
            id, total_amount, month, year, due_date, is_paid, paid_date, close_day,
            credit_cards(name)
        """).eq("user_id", user_id).eq("month", current_date.month).eq("year", current_date.year)
        
        if credit_card_id:
            query = query.eq("credit_card_id", credit_card_id)
        
        resp = query.execute()
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar fatura atual: {e}")
        return []

def get_next_invoice(user_id: str, credit_card_id: str = None):
    """
    Busca a próxima fatura (do próximo mês) de um cartão específico ou todos os cartões
    """
    if not supabase:
        return []
    
    try:
        current_date = date.today()
        next_month = current_date.month + 1
        next_year = current_date.year
        
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        query = supabase.table("invoices").select("""
            id, total_amount, month, year, due_date, is_paid, paid_date, close_day,
            credit_cards(name)
        """).eq("user_id", user_id).eq("month", next_month).eq("year", next_year)
        
        if credit_card_id:
            query = query.eq("credit_card_id", credit_card_id)
        
        resp = query.execute()
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar próxima fatura: {e}")
        return []

def get_credit_card_transactions_by_period(user_id: str, credit_card_id: str, start_date: str, end_date: str):
    """
    Busca transações de um cartão específico em um período
    """
    if not supabase:
        return []
    
    try:
        resp = supabase.table("transactions").select("""
            id, amount, description, payment_method, due_date, created_at,
            categories(name),
            credit_cards(name)
        """).eq("user_id", user_id).eq("credit_card_id", credit_card_id).eq("payment_method", "cartao_credito").gte("created_at", f"{start_date}T00:00:00").lte("created_at", f"{end_date}T23:59:59").order("created_at", desc=True).execute()
        
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar transações do cartão: {e}")
        return []


# ==================== FUNÇÕES DE RECEITAS ====================

def save_income_transaction(user_id: str, amount: float, description: str, category_id: str, 
                           payment_method: str = "pix", recurrence: bool = False, due_day: int = None, 
                           recurring_months: int = None):
    """Salva uma receita na tabela transactions"""
    if not supabase:
        print(f"Mock: Salvando receita - Usuário: {user_id}, Valor: R$ {amount:.2f}, Descrição: {description}, Categoria: {category_id}")
        return {"success": True, "message": "Receita salva com sucesso! (modo desenvolvimento)"}
    
    try:
        # Definir datas baseado na recorrência
        from datetime import date
        today = date.today()
        
        # Lógica para receitas recorrentes
        if recurrence and due_day is not None:
            # Para receitas recorrentes: due_date é o dia especificado, paid_date fica null (aguardando confirmação)
            try:
                # Criar data para o dia especificado no mês atual
                due_date = today.replace(day=due_day).isoformat()
            except ValueError:
                # Se o dia não existe no mês atual (ex: dia 31 em fevereiro), usar último dia do mês
                import calendar
                last_day = calendar.monthrange(today.year, today.month)[1]
                due_date = today.replace(day=min(due_day, last_day)).isoformat()
            
            paid_date = None  # Null para receitas recorrentes não confirmadas
        else:
            # Receitas avulsas: recebidas na data atual
            today_str = today.isoformat()
            due_date = today_str
            paid_date = today_str
        
        transaction_data = {
            "user_id": user_id,
            "amount": abs(amount),  # Valor sempre positivo
            "description": description,
            "category_id": category_id,
            "payment_method": payment_method,
            "transaction_type": "income",  # Tipo receita
            "type": "income",  # Campo legado
            "recurrence": recurrence,
            "due_date": due_date,
            "paid_date": paid_date
        }
        
        # Remove campos None para evitar erros
        transaction_data = {k: v for k, v in transaction_data.items() if v is not None}
        
        # Para receitas recorrentes, criar o número especificado de parcelas (padrão 6 meses)
        if recurrence and due_day is not None:
            transactions_to_insert = []
            
            # Definir número de meses (padrão 6 se não informado)
            months_to_create = recurring_months if recurring_months is not None else 6
            
            # Criar as parcelas mensais
            for month_offset in range(months_to_create):
                transaction_copy = transaction_data.copy()
                
                # Calcular a data de vencimento para cada mês
                target_year = today.year
                target_month = today.month + month_offset
                
                # Ajustar ano se necessário
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                
                # Calcular data de vencimento
                try:
                    due_date_obj = date(target_year, target_month, due_day)
                except ValueError:
                    # Se o dia não existe no mês, usar último dia
                    import calendar
                    last_day = calendar.monthrange(target_year, target_month)[1]
                    due_date_obj = date(target_year, target_month, min(due_day, last_day))
                
                transaction_copy["due_date"] = due_date_obj.isoformat()
                transaction_copy["paid_date"] = None  # Receitas recorrentes aguardam confirmação
                
                transactions_to_insert.append(transaction_copy)
            
            # Inserir todas as parcelas
            resp = supabase.table("transactions").insert(transactions_to_insert).execute()
            
            return {
                "success": True, 
                "message": f"Receita recorrente criada com sucesso! {months_to_create} parcelas mensais registradas.",
                "transactions": resp.data
            }
        else:
            # Inserir receita única
            resp = supabase.table("transactions").insert(transaction_data).execute()
            
            return {
                "success": True, 
                "message": "Receita registrada com sucesso!",
                "transaction": resp.data[0] if resp.data else None
            }
            
    except Exception as e:
        error_msg = f"Erro ao salvar receita: {str(e)}"
        print(error_msg)
        return {"success": False, "message": error_msg}


def search_income_transactions(user_id: str, filters: dict = None):
    """Busca receitas com filtros específicos"""
    if not supabase:
        print(f"Mock: Buscando receitas para usuário {user_id} com filtros: {filters}")
        return []
    
    try:
        # Query base para receitas
        query = supabase.table("transactions").select("""
            id, amount, description, payment_method, due_date, paid_date, created_at, recurrence,
            categories(name)
        """).eq("user_id", user_id).eq("transaction_type", "income").order("created_at", desc=True)
        
        # Aplicar filtros se fornecidos
        if filters:
            if filters.get("start_date"):
                query = query.gte("due_date", filters["start_date"])
            if filters.get("end_date"):
                query = query.lte("due_date", filters["end_date"])
            if filters.get("category_name"):
                # Implementar filtro por categoria (requer join)
                pass
            if filters.get("payment_method"):
                query = query.eq("payment_method", filters["payment_method"])
            if filters.get("is_paid") is not None:
                if filters["is_paid"]:
                    query = query.is_("paid_date", "not.null")
                else:
                    query = query.is_("paid_date", "null")
            if filters.get("description_contains"):
                query = query.ilike("description", f"%{filters['description_contains']}%")
            if filters.get("min_amount"):
                query = query.gte("amount", filters["min_amount"])
            if filters.get("max_amount"):
                query = query.lte("amount", filters["max_amount"])
        
        resp = query.execute()
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar receitas: {e}")
        return []


def mark_income_as_received(transaction_id: str, user_id: str, received_date: str = None):
    """Marca uma receita como recebida"""
    if not supabase:
        print(f"Mock: Marcando receita {transaction_id} como recebida para usuário {user_id}")
        return {"success": True, "message": "Receita marcada como recebida! (modo desenvolvimento)"}
    
    try:
        # Usar data atual se não fornecida
        if not received_date:
            from datetime import date
            received_date = date.today().isoformat()
        
        # Atualizar a receita
        resp = supabase.table("transactions").update({
            "paid_date": received_date
        }).eq("id", transaction_id).eq("user_id", user_id).eq("transaction_type", "income").execute()
        
        if resp.data:
            return {
                "success": True, 
                "message": f"Receita confirmada como recebida em {received_date}!"
            }
        else:
            return {"success": False, "message": "Receita não encontrada"}
            
    except Exception as e:
        error_msg = f"Erro ao confirmar recebimento: {str(e)}"
        print(error_msg)
        return {"success": False, "message": error_msg}


def find_pending_income_by_description(user_id: str, description_keyword: str):
    """Encontra receitas pendentes por palavra-chave na descrição"""
    if not supabase:
        print(f"Mock: Buscando receitas pendentes com palavra-chave '{description_keyword}' para usuário {user_id}")
        return []
    
    try:
        resp = supabase.table("transactions").select("""
            id, amount, description, payment_method, due_date, created_at,
            categories(name)
        """).eq("user_id", user_id).eq("transaction_type", "income").is_("paid_date", "null").ilike("description", f"%{description_keyword}%").order("created_at", desc=True).execute()
        
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar receitas pendentes: {e}")
        return []


def find_pending_expenses_by_description(user_id: str, description_keyword: str):
    """Encontra despesas pendentes por palavra-chave na descrição"""
    if not supabase:
        print(f"Mock: Buscando despesas pendentes com palavra-chave '{description_keyword}' para usuário {user_id}")
        return []
    
    try:
        resp = supabase.table("transactions").select("""
            id, amount, description, payment_method, due_date, created_at,
            categories(name)
        """).eq("user_id", user_id).eq("transaction_type", "expense").is_("paid_date", "null").ilike("description", f"%{description_keyword}%").order("due_date", desc=False).execute()
        
        return resp.data or []
        
    except Exception as e:
        print(f"Erro ao buscar despesas pendentes: {e}")
        return []


def mark_expense_as_paid(transaction_id: str, user_id: str, paid_date: str = None):
    """Marca uma despesa como paga"""
    if not supabase:
        print(f"Mock: Marcando despesa {transaction_id} como paga para usuário {user_id}")
        return {"success": True, "message": "Despesa marcada como paga! (modo desenvolvimento)"}
    
    try:
        # Usar data atual se não fornecida
        if not paid_date:
            from datetime import date
            paid_date = date.today().isoformat()
        
        # Atualizar a despesa
        resp = supabase.table("transactions").update({
            "paid_date": paid_date
        }).eq("id", transaction_id).eq("user_id", user_id).eq("transaction_type", "expense").execute()
        
        if resp.data:
            return {
                "success": True, 
                "message": f"Despesa marcada como paga em {paid_date}!"
            }
        else:
            return {"success": False, "message": "Despesa não encontrada"}
            
    except Exception as e:
        error_msg = f"Erro ao marcar despesa como paga: {str(e)}"
        print(error_msg)
        return {"success": False, "message": error_msg}


# ==================== FUNÇÕES DE SALDO E ANÁLISES ====================

def calculate_user_balance(user_id: str, start_date: str = None, end_date: str = None):
    """
    Calcula o saldo do usuário baseado em receitas e despesas em um período
    
    Args:
        user_id: ID do usuário
        start_date: Data inicial (formato YYYY-MM-DD), se None usa início do mês atual
        end_date: Data final (formato YYYY-MM-DD), se None usa data atual
    
    Returns:
        dict: Dados do saldo e análises
    """
    if not supabase:
        print(f"Mock: Calculando saldo para usuário {user_id}")
        return {
            "total_income": 5000.0,
            "total_expenses": 2500.0,
            "balance": 2500.0,
            "income_count": 2,
            "expense_count": 15,
            "period": {"start": start_date, "end": end_date}
        }
    
    try:
        from datetime import date
        
        # Definir período padrão se não especificado
        if not start_date or not end_date:
            today = date.today()
            start_date = today.replace(day=1).isoformat()
            end_date = today.isoformat()
        
        # Buscar todas as transações do período (receitas e despesas pagas)
        query = supabase.table("transactions").select("""
            transaction_type, amount, paid_date
        """).eq("user_id", user_id).not_.is_("paid_date", "null")
        
        # Aplicar filtros de data
        if start_date:
            query = query.gte("paid_date", start_date)
        if end_date:
            query = query.lte("paid_date", end_date)
        
        resp = query.execute()
        transactions = resp.data or []
        
        # Calcular totais
        total_income = 0
        total_expenses = 0
        income_count = 0
        expense_count = 0
        
        for transaction in transactions:
            amount = transaction["amount"]
            
            if transaction["transaction_type"] == "income":
                total_income += amount
                income_count += 1
            elif transaction["transaction_type"] == "expense":
                total_expenses += amount
                expense_count += 1
        
        balance = total_income - total_expenses
        
        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": balance,
            "income_count": income_count,
            "expense_count": expense_count,
            "period": {"start": start_date, "end": end_date}
        }
        
    except Exception as e:
        print(f"Erro ao calcular saldo: {e}")
        return {
            "total_income": 0,
            "total_expenses": 0,
            "balance": 0,
            "income_count": 0,
            "expense_count": 0,
            "period": {"start": start_date, "end": end_date}
        }


def get_category_analysis(user_id: str, start_date: str = None, end_date: str = None):
    """
    Análise de gastos por categoria em um período
    
    Returns:
        list: Lista de categorias com totais gastos
    """
    if not supabase:
        print(f"Mock: Análise por categoria para usuário {user_id}")
        return [
            {"category": "Alimentação", "total": 800.0, "count": 12, "percentage": 32.0},
            {"category": "Transporte", "total": 600.0, "count": 8, "percentage": 24.0},
            {"category": "Casa", "total": 400.0, "count": 3, "percentage": 16.0}
        ]
    
    try:
        from datetime import date
        
        # Definir período padrão se não especificado
        if not start_date or not end_date:
            today = date.today()
            start_date = today.replace(day=1).isoformat()
            end_date = today.isoformat()
        
        # Buscar despesas pagas com categorias
        query = supabase.table("transactions").select("""
            amount,
            categories(name)
        """).eq("user_id", user_id).eq("transaction_type", "expense").not_.is_("paid_date", "null")
        
        # Aplicar filtros de data
        if start_date:
            query = query.gte("paid_date", start_date)
        if end_date:
            query = query.lte("paid_date", end_date)
        
        resp = query.execute()
        transactions = resp.data or []
        
        # Agrupar por categoria
        category_totals = {}
        total_expenses = 0
        
        for transaction in transactions:
            amount = transaction["amount"]
            category_name = "Outros"
            
            if transaction.get("categories"):
                category_name = transaction["categories"]["name"]
            
            if category_name not in category_totals:
                category_totals[category_name] = {"total": 0, "count": 0}
            
            category_totals[category_name]["total"] += amount
            category_totals[category_name]["count"] += 1
            total_expenses += amount
        
        # Calcular percentuais e formatar resultado
        result = []
        for category, data in category_totals.items():
            percentage = (data["total"] / total_expenses * 100) if total_expenses > 0 else 0
            result.append({
                "category": category,
                "total": data["total"],
                "count": data["count"],
                "percentage": round(percentage, 1)
            })
        
        # Ordenar por total (maior primeiro)
        result.sort(key=lambda x: x["total"], reverse=True)
        
        return result
        
    except Exception as e:
        print(f"Erro ao analisar categorias: {e}")
        return []


def get_monthly_trend(user_id: str, months: int = 6):
    """
    Análise de tendência mensal de receitas e despesas
    
    Args:
        user_id: ID do usuário
        months: Número de meses para analisar (padrão 6)
    
    Returns:
        list: Lista com dados mensais
    """
    if not supabase:
        print(f"Mock: Tendência mensal para usuário {user_id}")
        return [
            {"month": "2025-04", "income": 5000, "expenses": 3200, "balance": 1800},
            {"month": "2025-05", "income": 5000, "expenses": 2800, "balance": 2200},
            {"month": "2025-06", "income": 5500, "expenses": 3100, "balance": 2400},
            {"month": "2025-07", "income": 5000, "expenses": 2900, "balance": 2100},
            {"month": "2025-08", "income": 5200, "expenses": 3300, "balance": 1900},
            {"month": "2025-09", "income": 3000, "expenses": 2500, "balance": 500}
        ]
    
    try:
        from datetime import date, timedelta
        import calendar
        
        today = date.today()
        result = []
        
        # Iterar pelos últimos N meses
        for month_offset in range(months - 1, -1, -1):
            # Calcular mês e ano
            target_date = today.replace(day=1) - timedelta(days=month_offset * 30)
            year = target_date.year
            month = target_date.month
            
            # Primeiro e último dia do mês
            first_day = date(year, month, 1)
            last_day_num = calendar.monthrange(year, month)[1]
            last_day = date(year, month, last_day_num)
            
            # Buscar transações do mês
            balance_data = calculate_user_balance(
                user_id, 
                first_day.isoformat(), 
                last_day.isoformat()
            )
            
            result.append({
                "month": f"{year}-{month:02d}",
                "month_name": calendar.month_name[month],
                "income": balance_data["total_income"],
                "expenses": balance_data["total_expenses"],
                "balance": balance_data["balance"]
            })
        
        return result
        
    except Exception as e:
        print(f"Erro ao calcular tendência mensal: {e}")
        return []


def get_pending_commitments(user_id: str):
    """
    Busca compromissos pendentes (despesas não pagas) agrupados por período
    
    Returns:
        dict: Compromissos organizados por período
    """
    if not supabase:
        print(f"Mock: Compromissos pendentes para usuário {user_id}")
        return {
            "this_month": {"total": 1200.0, "count": 5, "items": []},
            "next_month": {"total": 800.0, "count": 3, "items": []},
            "future": {"total": 400.0, "count": 2, "items": []}
        }
    
    try:
        from datetime import date, timedelta
        
        today = date.today()
        current_month_start = today.replace(day=1)
        next_month = today.replace(day=28) + timedelta(days=4)  # Próximo mês
        next_month_start = next_month.replace(day=1)
        
        # Buscar despesas não pagas
        resp = supabase.table("transactions").select("""
            amount, description, due_date,
            categories(name),
            credit_cards(name)
        """).eq("user_id", user_id).eq("transaction_type", "expense").is_("paid_date", "null").order("due_date", desc=False).execute()
        
        pending_transactions = resp.data or []
        
        # Agrupar por período
        this_month = {"total": 0, "count": 0, "items": []}
        next_month_data = {"total": 0, "count": 0, "items": []}
        future = {"total": 0, "count": 0, "items": []}
        
        for transaction in pending_transactions:
            amount = transaction["amount"]
            due_date_str = transaction.get("due_date")
            
            # Determinar período
            if due_date_str:
                from datetime import datetime
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).date()
                
                if due_date >= current_month_start and due_date < next_month_start:
                    this_month["total"] += amount
                    this_month["count"] += 1
                    this_month["items"].append(transaction)
                elif due_date >= next_month_start and due_date.month == next_month_start.month:
                    next_month_data["total"] += amount
                    next_month_data["count"] += 1
                    next_month_data["items"].append(transaction)
                else:
                    future["total"] += amount
                    future["count"] += 1
                    future["items"].append(transaction)
        
        return {
            "this_month": this_month,
            "next_month": next_month_data,
            "future": future
        }
        
    except Exception as e:
        print(f"Erro ao buscar compromissos pendentes: {e}")
        return {
            "this_month": {"total": 0, "count": 0, "items": []},
            "next_month": {"total": 0, "count": 0, "items": []},
            "future": {"total": 0, "count": 0, "items": []}
        }

def edit_transaction(user_id: str, description_keyword: str, new_payment_method: str = None, 
                    new_category_name: str = None, new_amount: float = None, 
                    new_description: str = None):
    """
    Edita uma transação existente baseada na descrição
    
    Args:
        user_id: ID do usuário
        description_keyword: Palavra-chave para encontrar a transação
        new_payment_method: Novo método de pagamento (opcional)
        new_category_name: Nova categoria (opcional)
        new_amount: Novo valor (opcional)
        new_description: Nova descrição (opcional)
    """
    if not supabase:
        return {"success": True, "message": f"Mock: Transação com '{description_keyword}' editada com sucesso!"}
    
    try:
        # Buscar transação pela descrição (mais recente primeiro)
        resp = supabase.table("transactions").select("*").eq("user_id", user_id).ilike("description", f"%{description_keyword}%").order("created_at", desc=True).limit(1).execute()
        
        if not resp.data:
            return {"success": False, "message": f"Nenhuma transação encontrada com '{description_keyword}'"}
        
        transaction = resp.data[0]
        transaction_id = transaction["id"]
        
        # Preparar dados para atualização
        update_data = {}
        
        if new_payment_method:
            update_data["payment_method"] = new_payment_method
        
        if new_amount:
            update_data["amount"] = abs(new_amount)
            
        if new_description:
            update_data["description"] = new_description
            
        # Se mudou categoria, buscar ID da nova categoria
        if new_category_name:
            # Buscar categoria por nome
            cat_resp = supabase.table("categories").select("id").eq("user_id", user_id).ilike("name", f"%{new_category_name}%").execute()
            if cat_resp.data:
                update_data["category_id"] = cat_resp.data[0]["id"]
            else:
                return {"success": False, "message": f"Categoria '{new_category_name}' não encontrada"}
        
        if not update_data:
            return {"success": False, "message": "Nenhuma alteração especificada"}
        
        # Atualizar transação
        update_resp = supabase.table("transactions").update(update_data).eq("id", transaction_id).execute()
        
        if update_resp.data:
            changes = []
            if new_payment_method:
                changes.append(f"método de pagamento para {new_payment_method}")
            if new_category_name:
                changes.append(f"categoria para {new_category_name}")
            if new_amount:
                changes.append(f"valor para R$ {new_amount:.2f}")
            if new_description:
                changes.append(f"descrição para {new_description}")
            
            changes_text = ", ".join(changes)
            return {"success": True, "message": f"✅ Transação '{transaction['description']}' atualizada! Alterações: {changes_text}"}
        else:
            return {"success": False, "message": "Erro ao atualizar transação"}
            
    except Exception as e:
        print(f"Erro ao editar transação: {e}")
        return {"success": False, "message": f"Erro ao editar: {str(e)}"}
