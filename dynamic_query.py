"""
Sistema de queries dinâmicas para o assistente financeiro
O agente pode construir queries SQL flexíveis baseado nas necessidades do usuário
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, date
import json
from functions_database import supabase

class DynamicQueryBuilder:
    """Construtor de queries dinâmicas para dados financeiros"""
    
    @staticmethod
    def build_financial_query(
        query_type: str,
        user_id: str,
        filters: Dict[str, Any] = None,
        date_range: Dict[str, str] = None,
        order_by: str = None,
        limit: int = None
    ) -> Tuple[str, List[Any]]:
        """
        Constrói query SQL dinâmica baseada nos parâmetros fornecidos
        
        Args:
            query_type: Tipo de query (transactions, commitments, balance, summary)
            user_id: ID do usuário
            filters: Filtros adicionais (categoria, método_pagamento, etc)
            date_range: Range de datas (start_date, end_date)
            order_by: Campo para ordenar
            limit: Limite de resultados
            
        Returns:
            Tupla com (query_string, parameters)
        """
        filters = filters or {}
        
        if query_type == "transactions":
            return DynamicQueryBuilder._build_transactions_query(
                user_id, filters, date_range, order_by, limit
            )
        elif query_type == "commitments":
            return DynamicQueryBuilder._build_commitments_query(
                user_id, filters, date_range, order_by, limit
            )
        elif query_type == "balance":
            return DynamicQueryBuilder._build_balance_query(
                user_id, filters, date_range
            )
        elif query_type == "summary":
            return DynamicQueryBuilder._build_summary_query(
                user_id, filters, date_range, order_by, limit
            )
        else:
            raise ValueError(f"Tipo de query não suportado: {query_type}")
    
    @staticmethod
    def _build_transactions_query(
        user_id: str,
        filters: Dict[str, Any],
        date_range: Dict[str, str],
        order_by: str,
        limit: int
    ) -> Tuple[str, List[Any]]:
        """Constrói query para transações"""
        
        # Seleções básicas
        select_fields = """
            t.id,
            t.amount,
            t.description,
            t.transaction_date,
            t.payment_method,
            t.transaction_type,
            t.is_paid,
            t.due_date,
            t.paid_date,
            t.installments,
            c.name as category_name,
            cc.name as credit_card_name
        """
        
        # Query base usando Supabase format
        base_query = f"""
        SELECT {select_fields}
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN credit_cards cc ON t.credit_card_id = cc.id
        WHERE t.user_id = %s
        """
        
        params = [user_id]
        conditions = []
        
        # Adicionar filtros dinâmicos
        if filters.get('category'):
            conditions.append("c.name ILIKE %s")
            params.append(f"%{filters['category']}%")
        
        if filters.get('payment_method'):
            conditions.append("t.payment_method = %s")
            params.append(filters['payment_method'])
        
        if filters.get('transaction_type'):
            conditions.append("t.transaction_type = %s")
            params.append(filters['transaction_type'])
        
        if filters.get('is_paid') is not None:
            if filters['is_paid']:
                conditions.append("t.is_paid = true")
            else:
                conditions.append("t.is_paid = false")
        
        if filters.get('credit_card_name'):
            conditions.append("cc.name ILIKE %s")
            params.append(f"%{filters['credit_card_name']}%")
        
        if filters.get('min_amount'):
            conditions.append("t.amount >= %s")
            params.append(float(filters['min_amount']))
        
        if filters.get('max_amount'):
            conditions.append("t.amount <= %s")
            params.append(float(filters['max_amount']))
        
        if filters.get('description'):
            conditions.append("t.description ILIKE %s")
            params.append(f"%{filters['description']}%")
        
        # Adicionar range de datas
        if date_range:
            if date_range.get('start_date'):
                conditions.append("t.transaction_date >= %s")
                params.append(date_range['start_date'])
            
            if date_range.get('end_date'):
                conditions.append("t.transaction_date <= %s")
                params.append(date_range['end_date'])
        
        # Montar query final
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # Order by
        if order_by:
            # Validar campo para segurança
            allowed_orders = [
                "t.transaction_date", "t.amount", "t.description", 
                "c.name", "t.due_date", "amount DESC", "amount ASC",
                "transaction_date DESC", "transaction_date ASC"
            ]
            if any(order_by.lower().startswith(allowed.lower()) for allowed in allowed_orders):
                base_query += f" ORDER BY {order_by}"
            else:
                base_query += " ORDER BY t.transaction_date DESC"
        else:
            base_query += " ORDER BY t.transaction_date DESC"
        
        # Limit
        if limit and isinstance(limit, int) and limit > 0:
            base_query += f" LIMIT {min(limit, 100)}"  # Máximo de 100 para segurança
        
        return base_query, params
    
    @staticmethod
    def _build_commitments_query(
        user_id: str,
        filters: Dict[str, Any],
        date_range: Dict[str, str],
        order_by: str,
        limit: int
    ) -> Tuple[str, List[Any]]:
        """Constrói query para compromissos pendentes"""
        
        # Query para buscar despesas não pagas (compromissos)
        base_query = """
        SELECT 
            t.id,
            t.amount,
            t.description,
            t.due_date,
            t.payment_method,
            t.transaction_date,
            t.is_paid,
            c.name as category_name,
            cc.name as credit_card_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN credit_cards cc ON t.credit_card_id = cc.id
        WHERE t.user_id = %s AND t.transaction_type = 'expense'
        """
        
        params = [user_id]
        conditions = []
        
        # Por padrão, buscar apenas não pagos para compromissos
        if filters.get('is_paid') is None:
            conditions.append("t.is_paid = false")
        elif filters.get('is_paid') is not None:
            if filters['is_paid']:
                conditions.append("t.is_paid = true")
            else:
                conditions.append("t.is_paid = false")
        
        # Outros filtros similares às transações
        if filters.get('category'):
            conditions.append("c.name ILIKE %s")
            params.append(f"%{filters['category']}%")
        
        if filters.get('payment_method'):
            conditions.append("t.payment_method = %s")
            params.append(filters['payment_method'])
        
        if filters.get('credit_card_name'):
            conditions.append("cc.name ILIKE %s")
            params.append(f"%{filters['credit_card_name']}%")
        
        if filters.get('min_amount'):
            conditions.append("t.amount >= %s")
            params.append(float(filters['min_amount']))
        
        if filters.get('max_amount'):
            conditions.append("t.amount <= %s")
            params.append(float(filters['max_amount']))
        
        # Range de datas (usar due_date para compromissos)
        if date_range:
            if date_range.get('start_date'):
                conditions.append("t.due_date >= %s")
                params.append(date_range['start_date'])
            
            if date_range.get('end_date'):
                conditions.append("t.due_date <= %s")
                params.append(date_range['end_date'])
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # Order by
        if order_by:
            allowed_orders = ["t.due_date", "t.amount", "due_date ASC", "due_date DESC", "amount DESC", "amount ASC"]
            if any(order_by.lower().startswith(allowed.lower()) for allowed in allowed_orders):
                base_query += f" ORDER BY {order_by}"
            else:
                base_query += " ORDER BY t.due_date ASC"
        else:
            base_query += " ORDER BY t.due_date ASC"
        
        if limit and isinstance(limit, int) and limit > 0:
            base_query += f" LIMIT {min(limit, 100)}"
        
        return base_query, params
    
    @staticmethod
    def _build_balance_query(
        user_id: str,
        filters: Dict[str, Any],
        date_range: Dict[str, str]
    ) -> Tuple[str, List[Any]]:
        """Constrói query para saldo/balanço"""
        
        base_query = """
        SELECT 
            COALESCE(SUM(CASE 
                WHEN t.transaction_type = 'income' AND t.is_paid = true THEN t.amount 
                ELSE 0 
            END), 0) as total_receitas,
            COALESCE(SUM(CASE 
                WHEN t.transaction_type = 'expense' AND t.is_paid = true THEN t.amount 
                ELSE 0 
            END), 0) as total_despesas,
            COALESCE(SUM(CASE 
                WHEN t.transaction_type = 'income' AND t.is_paid = true THEN t.amount 
                WHEN t.transaction_type = 'expense' AND t.is_paid = true THEN -t.amount 
                ELSE 0 
            END), 0) as saldo_atual,
            COALESCE(SUM(CASE 
                WHEN t.transaction_type = 'expense' AND t.is_paid = false THEN t.amount 
                ELSE 0 
            END), 0) as pendencias_despesas,
            COALESCE(SUM(CASE 
                WHEN t.transaction_type = 'income' AND t.is_paid = false THEN t.amount 
                ELSE 0 
            END), 0) as pendencias_receitas
        FROM transactions t
        WHERE t.user_id = %s
        """
        
        params = [user_id]
        conditions = []
        
        # Range de datas
        if date_range:
            if date_range.get('start_date'):
                conditions.append("t.transaction_date >= %s")
                params.append(date_range['start_date'])
            
            if date_range.get('end_date'):
                conditions.append("t.transaction_date <= %s")
                params.append(date_range['end_date'])
        
        # Filtros adicionais
        if filters.get('category'):
            base_query = base_query.replace("FROM transactions t", 
                "FROM transactions t LEFT JOIN categories c ON t.category_id = c.id")
            conditions.append("c.name ILIKE %s")
            params.append(f"%{filters['category']}%")
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        return base_query, params
    
    @staticmethod
    def _build_summary_query(
        user_id: str,
        filters: Dict[str, Any],
        date_range: Dict[str, str]
    ) -> Tuple[str, List[Any]]:
        """Constrói query para resumo por categoria"""
        
        base_query = """
        SELECT 
            c.name as category_name,
            t.transaction_type,
            COUNT(*) as count_transactions,
            SUM(t.amount) as total_amount,
            AVG(t.amount) as avg_amount,
            MIN(t.amount) as min_amount,
            MAX(t.amount) as max_amount
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = %s
        """
        
        params = [user_id]
        conditions = []
        
        # Filtros
        if filters.get('transaction_type'):
            conditions.append("t.transaction_type = %s")
            params.append(filters['transaction_type'])
        
        if filters.get('is_paid') is not None:
            conditions.append("t.is_paid = %s")
            params.append(filters['is_paid'])
        
        # Range de datas
        if date_range:
            if date_range.get('start_date'):
                conditions.append("t.transaction_date >= %s")
                params.append(date_range['start_date'])
            
            if date_range.get('end_date'):
                conditions.append("t.transaction_date <= %s")
                params.append(date_range['end_date'])
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        base_query += " GROUP BY c.name, t.transaction_type ORDER BY total_amount DESC"
        
        return base_query, params

    def __init__(self, deps):
        """Inicializa o query builder com as dependências do usuário"""
        self.deps = deps

    async def execute_query(
        self,
        query_type: str,
        filters: Dict[str, Any] = None,
        grouping: str = None,
        period_start: str = None,
        period_end: str = None,
        limit: int = None
    ) -> str:
        """
        Executa uma query dinâmica e retorna os resultados formatados
        """
        try:
            # Preparar filtros e range de datas
            filters = filters or {}
            date_range = {}
            
            if period_start:
                date_range['start_date'] = period_start
            if period_end:
                date_range['end_date'] = period_end
                
            # Executar a query dinâmica
            results = await execute_dynamic_query(
                query_type=query_type,
                user_id=self.deps.user_id,
                filters=filters,
                date_range=date_range if date_range else None,
                limit=limit
            )
            
            # Formatar os resultados
            if not results:
                return f"📊 Nenhum resultado encontrado para a consulta de {query_type}"
            
            return self._format_query_results(query_type, results, grouping)
            
        except Exception as e:
            print(f"❌ Erro ao executar query: {e}")
            return f"❌ Erro ao executar consulta: {str(e)}"

    def _format_query_results(self, query_type: str, results: List[Dict], grouping: str = None) -> str:
        """Formata os resultados da query para apresentação"""
        
        if query_type == "transactions":
            return self._format_transactions(results)
        elif query_type == "summary":
            return self._format_summary(results, grouping)
        elif query_type == "balance":
            return self._format_balance(results)
        elif query_type == "trends":
            return self._format_trends(results)
        else:
            return json.dumps(results, indent=2, ensure_ascii=False)

    def _format_transactions(self, transactions: List[Dict]) -> str:
        """Formata lista de transações"""
        if not transactions:
            return "📊 Nenhuma transação encontrada"
        
        response = f"💰 **Transações encontradas:** {len(transactions)}\n\n"
        
        total = 0
        for t in transactions:
            emoji = "💸" if t.get('transaction_type') == 'expense' else "💚"
            status = "✅" if t.get('is_paid') else "⏳"
            
            response += f"{emoji} {status} R$ {t['amount']:.2f} - {t['description']}\n"
            response += f"   📅 {t['transaction_date']} | 📂 {t.get('category_name', 'N/A')}\n\n"
            
            if t.get('transaction_type') == 'expense':
                total -= t['amount']
            else:
                total += t['amount']
        
        response += f"💰 **Impacto total:** R$ {total:,.2f}"
        return response

    def _format_summary(self, summary: List[Dict], grouping: str = None) -> str:
        """Formata resumo por categoria/agrupamento"""
        if not summary:
            return "📊 Nenhum dado para resumo"
        
        response = f"📊 **Resumo por {grouping or 'categoria'}:**\n\n"
        
        for item in summary:
            emoji = "💸" if item.get('transaction_type') == 'expense' else "💚"
            response += f"{emoji} **{item.get('category_name', 'N/A')}**\n"
            response += f"   💰 Total: R$ {item['total_amount']:,.2f}\n"
            response += f"   📈 Média: R$ {item['avg_amount']:,.2f}\n"
            response += f"   🔢 Transações: {item['count_transactions']}\n\n"
        
        return response

    def _format_balance(self, balance: List[Dict]) -> str:
        """Formata análise de saldo"""
        if not balance:
            return "📊 Dados de saldo indisponíveis"
        
        # Por enquanto, formato simples
        return json.dumps(balance, indent=2, ensure_ascii=False)

    def _format_trends(self, trends: List[Dict]) -> str:
        """Formata análise de tendências"""
        if not trends:
            return "📊 Dados de tendência indisponíveis"
        
        # Por enquanto, formato simples
        return json.dumps(trends, indent=2, ensure_ascii=False)


async def execute_dynamic_query(
    query_type: str,
    user_id: str,
    filters: Dict[str, Any] = None,
    date_range: Dict[str, str] = None,
    order_by: str = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Executa uma query dinâmica usando diretamente o cliente Supabase
    """
    try:
        print(f"🔍 Executando query dinâmica: {query_type}")
        print(f"📋 Filtros: {filters}")
        print(f"📅 Range: {date_range}")
        
        # Processar shortcuts de período
        if date_range and date_range.get('period'):
            date_range = process_period_shortcuts(date_range['period'])
            print(f"📅 Range processado: {date_range}")
        
        if not supabase:
            print("⚠️ Supabase não configurado, retornando dados mock")
            return _get_mock_data(query_type, filters)
        
        # Executar query usando o cliente Supabase
        results = await _execute_supabase_native_query(query_type, user_id, filters or {}, date_range, limit)
        return results if results else []
        
    except Exception as e:
        print(f"❌ Erro ao executar query dinâmica: {e}")
        return []


async def _execute_supabase_native_query(
    query_type: str, 
    user_id: str, 
    filters: Dict[str, Any], 
    date_range: Dict[str, str] = None, 
    limit: int = None
) -> List[Dict[str, Any]]:
    """Executa query usando o cliente nativo do Supabase"""
    try:
        if query_type == "transactions":
            # Query base para transações
            query = supabase.table("transactions").select("""
                id, amount, description, transaction_date, payment_method, 
                transaction_type, due_date, paid_date, installments,
                categories(name),
                credit_cards(name)
            """).eq("user_id", user_id)
            
            # Aplicar filtros
            if filters.get("transaction_type"):
                query = query.eq("transaction_type", filters["transaction_type"])
            
            if filters.get("is_paid") is not None:
                if filters["is_paid"]:
                    query = query.not_.is_("paid_date", "null")
                else:
                    query = query.is_("paid_date", "null")
            
            if filters.get("payment_method"):
                query = query.eq("payment_method", filters["payment_method"])
            
            if filters.get("description"):
                query = query.ilike("description", f"%{filters['description']}%")
            
            if filters.get("valor_min"):
                query = query.gte("amount", filters["valor_min"])
            
            if filters.get("valor_max"):
                query = query.lte("amount", filters["valor_max"])
            
            # Filtros de período
            if date_range:
                if date_range.get("start_date"):
                    query = query.gte("due_date", date_range["start_date"])
                if date_range.get("end_date"):
                    query = query.lte("due_date", date_range["end_date"])
            
            # Ordenação e limite
            query = query.order("due_date", desc=False)
            if limit:
                query = query.limit(limit)
            
            resp = query.execute()
            return resp.data or []
            
        elif query_type == "summary":
            # Para resumo, precisamos fazer query manual e agrupar
            query = supabase.table("transactions").select("""
                amount, transaction_type,
                categories(name),
                credit_cards(name)
            """).eq("user_id", user_id)
            
            # Aplicar filtros básicos
            if filters.get("transaction_type"):
                query = query.eq("transaction_type", filters["transaction_type"])
            
            if date_range:
                if date_range.get("start_date"):
                    query = query.gte("due_date", date_range["start_date"])
                if date_range.get("end_date"):
                    query = query.lte("due_date", date_range["end_date"])
            
            resp = query.execute()
            transactions = resp.data or []
            
            # Agrupar por categoria
            summary_by_category = {}
            for t in transactions:
                category = t.get("categories", {}).get("name", "Sem categoria") if t.get("categories") else "Sem categoria"
                
                if category not in summary_by_category:
                    summary_by_category[category] = {
                        "category_name": category,
                        "total_amount": 0,
                        "count_transactions": 0,
                        "transaction_type": t["transaction_type"]
                    }
                
                summary_by_category[category]["total_amount"] += float(t["amount"])
                summary_by_category[category]["count_transactions"] += 1
            
            # Calcular médias
            for category_data in summary_by_category.values():
                category_data["avg_amount"] = category_data["total_amount"] / category_data["count_transactions"]
            
            return list(summary_by_category.values())
            
        elif query_type == "balance":
            # Para balance, buscar receitas e despesas separadamente
            
            # Receitas
            income_query = supabase.table("transactions").select("amount").eq("user_id", user_id).eq("transaction_type", "income")
            if date_range:
                if date_range.get("start_date"):
                    income_query = income_query.gte("due_date", date_range["start_date"])
                if date_range.get("end_date"):
                    income_query = income_query.lte("due_date", date_range["end_date"])
            
            # Filtrar por status se especificado
            if filters.get("is_paid") is not None:
                if filters["is_paid"]:
                    income_query = income_query.not_.is_("paid_date", "null")
                else:
                    income_query = income_query.is_("paid_date", "null")
            
            income_resp = income_query.execute()
            
            # Despesas 
            expense_query = supabase.table("transactions").select("amount").eq("user_id", user_id).eq("transaction_type", "expense")
            if date_range:
                if date_range.get("start_date"):
                    expense_query = expense_query.gte("due_date", date_range["start_date"])
                if date_range.get("end_date"):
                    expense_query = expense_query.lte("due_date", date_range["end_date"])
            
            # Filtrar por status se especificado
            if filters.get("is_paid") is not None:
                if filters["is_paid"]:
                    expense_query = expense_query.not_.is_("paid_date", "null")
                else:
                    expense_query = expense_query.is_("paid_date", "null")
                    
            expense_resp = expense_query.execute()
            
            # Calcular totais
            total_income = sum(float(t["amount"]) for t in (income_resp.data or []))
            total_expenses = sum(float(t["amount"]) for t in (expense_resp.data or []))
            balance = total_income - total_expenses
            
            return [{
                "total_income": total_income,
                "total_expenses": total_expenses,
                "balance": balance,
                "income_count": len(income_resp.data or []),
                "expense_count": len(expense_resp.data or [])
            }]
            
        else:
            return []
            
    except Exception as e:
        print(f"❌ Erro na query nativa: {e}")
        return []


async def _execute_supabase_query(query: str, params: List[Any]) -> List[Dict[str, Any]]:
    """Executa query SQL no Supabase"""
    try:
        # Para Supabase, vamos usar o client diretamente com select
        # Como não podemos executar SQL raw diretamente, vamos adaptar
        print("📡 Executando via Supabase client...")
        
        # Por enquanto, vamos retornar dados básicos
        # Em produção, você pode usar supabase.rpc() para stored procedures
        return []
        
    except Exception as e:
        print(f"❌ Erro no Supabase: {e}")
        return []


def process_period_shortcuts(period: str) -> Dict[str, str]:
    """Converte shortcuts de período em datas"""
    today = date.today()
    
    if period == "this_month":
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            
    elif period == "next_month":
        if today.month == 12:
            start_date = today.replace(year=today.year + 1, month=1, day=1)
            end_date = today.replace(year=today.year + 1, month=1, day=31)
        else:
            start_date = today.replace(month=today.month + 1, day=1)
            if today.month == 11:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 2, day=1) - timedelta(days=1)
                
    elif period == "last_month":
        if today.month == 1:
            start_date = today.replace(year=today.year - 1, month=12, day=1)
            end_date = today.replace(year=today.year - 1, month=12, day=31)
        else:
            start_date = today.replace(month=today.month - 1, day=1)
            end_date = today.replace(day=1) - timedelta(days=1)
            
    elif period == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
        
    elif period == "last_7_days":
        end_date = today
        start_date = today - timedelta(days=7)
        
    elif period == "last_30_days":
        end_date = today
        start_date = today - timedelta(days=30)
        
    else:
        return {}
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }


def _get_mock_data(query_type: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Retorna dados mock para testes quando Supabase não está disponível"""
    
    if query_type == "balance":
        return [{
            "total_receitas": 3500.0,
            "total_despesas": 2800.0,
            "saldo_atual": 700.0,
            "pendencias_despesas": 450.0,
            "pendencias_receitas": 800.0
        }]
    
    elif query_type == "transactions":
        return [
            {
                "id": 1,
                "amount": 1200.0,
                "description": "Salário",
                "transaction_date": "2025-09-01",
                "payment_method": "pix",
                "transaction_type": "income",
                "is_paid": True,
                "category_name": "Salário"
            },
            {
                "id": 2,
                "amount": 250.0,
                "description": "Mercado",
                "transaction_date": "2025-09-05",
                "payment_method": "cartao_credito",
                "transaction_type": "expense",
                "is_paid": True,
                "category_name": "Alimentação",
                "credit_card_name": "Nubank"
            }
        ]
    
    elif query_type == "commitments":
        return [
            {
                "id": 3,
                "amount": 800.0,
                "description": "Aluguel",
                "due_date": "2025-10-05",
                "payment_method": "pix",
                "is_paid": False,
                "category_name": "Moradia"
            }
        ]
    
    return []
