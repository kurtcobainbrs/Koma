"""Expressões aritméticas limitadas, sem execução de código ou acesso a nomes."""

import ast
import math
import operator


MAX_EXPRESSION_LENGTH = 128
MAX_EXPRESSION_NODES = 64
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def arithmetic_value(text):
    """Aceita números, +, -, *, / e parênteses; vírgula decimal é permitida."""
    message = 'Use números e operações +, -, *, / com parênteses.'
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_EXPRESSION_LENGTH:
        raise ValueError(message)
    try:
        tree = ast.parse(text.strip().replace(',', '.'), mode='eval')
        if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
            raise ValueError(message)

        def calculate(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = float(node.value)
            elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
                value = _BINARY[type(node.op)](calculate(node.left), calculate(node.right))
            elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
                value = _UNARY[type(node.op)](calculate(node.operand))
            else:
                raise ValueError(message)
            if not math.isfinite(value):
                raise ValueError(message)
            return value

        return calculate(tree.body)
    except (SyntaxError, ValueError, ArithmeticError, RecursionError) as exc:
        raise ValueError(message) from exc
