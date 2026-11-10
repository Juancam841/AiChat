import ast
import operator


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod
}


def calculate(expression):
    """
    Evalúa operaciones matemáticas de forma controlada.
    """

    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("La expresión matemática está vacía.")

    if len(expression) > 200:
        raise ValueError("La expresión es demasiado larga.")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _evaluate(tree.body)

        if isinstance(result, float):
            if not result == result or abs(result) == float("inf"):
                raise ValueError("El resultado no es válido.")

        return result

    except (SyntaxError, ZeroDivisionError, OverflowError) as error:
        raise ValueError(
            f"No se pudo calcular la expresión: {error}"
        )


def _evaluate(node):

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            raise ValueError("Solo se permiten números.")

        return node.value

    if isinstance(node, ast.BinOp):
        operation = OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operación no permitida.")

        left = _evaluate(node.left)
        right = _evaluate(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Exponente demasiado grande.")

        return operation(left, right)

    if isinstance(node, ast.UnaryOp):
        operation = OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Operación no permitida.")

        return operation(_evaluate(node.operand))

    raise ValueError("La expresión contiene elementos no permitidos.")

from tool_manager import register_tool


register_tool(
    name="calculator",
    description="Realiza operaciones matemáticas básicas.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Expresión matemática, por ejemplo: (25 + 15) * 2"
            }
        },
        "required": ["expression"],
        "additionalProperties": False
    },
    function=calculate
)
