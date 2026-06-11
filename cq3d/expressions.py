from __future__ import annotations

import ast
import math
import re
from collections.abc import Mapping

from cq3d.errors import ValidationError

UNIT_SUFFIX_RE = re.compile(r"\b\d+(?:\.\d+)?[A-Za-z_]+\b")
VALID_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SAFE_FUNCTIONS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def validate_identifier(name: str, *, line: int | None = None) -> None:
    if not VALID_NAME_RE.match(name):
        raise ValidationError(f"invalid identifier {name!r}", line=line)


def evaluate_expression(text: str, variables: Mapping[str, float], *, line: int) -> float:
    if UNIT_SUFFIX_RE.search(text):
        raise ValidationError("units are not allowed in values; use plain millimeters", line=line)

    try:
        parsed = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"invalid expression {text!r}", line=line) from exc

    value = _eval_node(parsed.body, variables, line=line)
    return float(value)


def _eval_node(node: ast.AST, variables: Mapping[str, float], *, line: int) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            raise ValidationError(f"function {node.id!r} must be called", line=line)
        if node.id not in variables:
            raise ValidationError(f"unknown variable {node.id!r}", line=line)
        return float(variables[node.id])

    if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS):
        left = _eval_node(node.left, variables, line=line)
        right = _eval_node(node.right, variables, line=line)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ValidationError("division by zero", line=line)
        return left / right

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ALLOWED_UNARYOPS):
        operand = _eval_node(node.operand, variables, line=line)
        return +operand if isinstance(node.op, ast.UAdd) else -operand

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValidationError(f"unknown function {func_name!r}", line=line)
        if node.keywords:
            raise ValidationError("keyword arguments are not supported", line=line)
        args = [_eval_node(arg, variables, line=line) for arg in node.args]
        try:
            return float(SAFE_FUNCTIONS[func_name](*args))
        except TypeError as exc:
            raise ValidationError(f"invalid arguments for function {func_name!r}", line=line) from exc

    raise ValidationError("unsupported expression syntax", line=line)
