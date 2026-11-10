import logging

from jsonschema import validate, ValidationError


logger = logging.getLogger(__name__)


TOOLS = {}


def register_tool(name, description, parameters, function):
    """
    Registra una herramienta disponible para AIChat.
    """

    if not name or not isinstance(name, str):
        raise ValueError("El nombre de la herramienta no es válido.")

    if name in TOOLS:
        raise ValueError(
            f"La herramienta '{name}' ya está registrada."
        )

    if not callable(function):
        raise ValueError(
            "La herramienta debe tener una función ejecutable."
        )

    if not isinstance(parameters, dict):
        raise ValueError(
            "Los parámetros deben definirse mediante un esquema JSON."
        )

    TOOLS[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "function": function
    }

    logger.info("Herramienta registrada: %s", name)


def get_tool(name):
    """
    Obtiene una herramienta por su nombre.
    """

    return TOOLS.get(name)


def get_available_tools():
    """
    Devuelve la descripción pública de las herramientas registradas.
    """

    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"]
        }
        for tool in TOOLS.values()
    ]


def validate_tool_arguments(name, arguments):
    """
    Valida los argumentos antes de ejecutar una herramienta.
    """

    tool = get_tool(name)

    if tool is None:
        raise ValueError(
            f"La herramienta '{name}' no está registrada."
        )

    try:
        validate(
            instance=arguments,
            schema=tool["parameters"]
        )

        return True

    except ValidationError as error:
        raise ValueError(
            f"Parámetros inválidos para '{name}': {error.message}"
        )

def execute_tool(name, arguments):
    """
    Valida y ejecuta una herramienta registrada.
    """

    tool = get_tool(name)

    if tool is None:
        raise ValueError(
            f"La herramienta '{name}' no está registrada."
        )

    # 1. Validar argumentos
    validate_tool_arguments(name, arguments)

    # 2. Ejecutar herramienta
    try:
        result = tool["function"](**arguments)

        logger.info(
            "Herramienta ejecutada correctamente: %s",
            name
        )

        return {
            "success": True,
            "tool": name,
            "result": result
        }

    except Exception:
        logger.exception(
            "Error al ejecutar la herramienta: %s",
            name
        )

        return {
            "success": False,
            "tool": name,
            "error": "Error interno al ejecutar la herramienta."
        }
