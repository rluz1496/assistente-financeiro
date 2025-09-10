"""
Ferramenta de cálculos para o assistente financeiro
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union
import re

class FinancialCalculator:
    """Calculadora financeira para operações precisas"""
    
    @staticmethod
    def safe_decimal(value: Union[str, int, float]) -> Decimal:
        """Converte valor para Decimal de forma segura"""
        if isinstance(value, str):
            # Remove caracteres não numéricos exceto ponto e vírgula
            clean_value = re.sub(r'[^\d.,\-]', '', value)
            clean_value = clean_value.replace(',', '.')
        else:
            clean_value = str(value)
        
        try:
            return Decimal(clean_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except:
            return Decimal('0.00')
    
    @staticmethod
    def add(*values) -> Decimal:
        """Soma valores com precisão"""
        result = Decimal('0.00')
        for value in values:
            result += FinancialCalculator.safe_decimal(value)
        return result
    
    @staticmethod
    def subtract(value1, value2) -> Decimal:
        """Subtrai valores com precisão"""
        return FinancialCalculator.safe_decimal(value1) - FinancialCalculator.safe_decimal(value2)
    
    @staticmethod
    def multiply(value1, value2) -> Decimal:
        """Multiplica valores com precisão"""
        return FinancialCalculator.safe_decimal(value1) * FinancialCalculator.safe_decimal(value2)
    
    @staticmethod
    def divide(value1, value2) -> Decimal:
        """Divide valores com precisão"""
        divisor = FinancialCalculator.safe_decimal(value2)
        if divisor == 0:
            return Decimal('0.00')
        return FinancialCalculator.safe_decimal(value1) / divisor
    
    @staticmethod
    def format_currency(value: Union[Decimal, str, int, float]) -> str:
        """Formata valor como moeda brasileira"""
        decimal_value = FinancialCalculator.safe_decimal(value)
        return f"R$ {decimal_value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

# Funções para uso no agente
def calculate_sum(values: list) -> str:
    """Calcula soma de uma lista de valores"""
    calc = FinancialCalculator()
    result = calc.add(*values)
    return calc.format_currency(result)

def calculate_difference(value1: float, value2: float) -> str:
    """Calcula diferença entre dois valores"""
    calc = FinancialCalculator()
    result = calc.subtract(value1, value2)
    return calc.format_currency(result)

def calculate_percentage(value: float, total: float) -> str:
    """Calcula porcentagem"""
    calc = FinancialCalculator()
    if total == 0:
        return "0%"
    result = calc.divide(calc.multiply(value, 100), total)
    return f"{result:.1f}%"
