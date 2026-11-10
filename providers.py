
import json
import logging

from litellm import completion

from config import PROVIDERS
from models import MODELS
from model_router import get_model_candidates
from usage_manager import record_usage
from tool_manager import get_available_tools, execute_tool


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """

Eres un asistente de inteligencia artificial útil, preciso y claro.

REGLAS DE PRESENTACIÓN:

1. Utiliza Markdown para estructurar las respuestas.
2. Utiliza títulos y subtítulos cuando ayuden a organizar el contenido.
3. Emplea listas numeradas o con viñetas cuando faciliten la lectura.
4. Utiliza tablas cuando permitan comparar información.
5. Presenta los fragmentos de código en bloques Markdown e identifica el lenguaje de programación.
6. Utiliza negritas para destacar conceptos importantes.
7. Utiliza citas cuando sea necesario destacar información.
8. Evita respuestas excesivamente fragmentadas o con títulos innecesarios.
9. Adapta la extensión y el nivel de detalle a la pregunta.
10. No utilices etiquetas HTML directamente.
11. Prioriza la claridad, la coherencia y la precisión.
12. Si una respuesta breve es suficiente, no la alargues artificialmente.
13. Las respuestas que contengan instrucciones de varios pasos, hacerlo paso por paso acompañando al usuario mientras ejecuta cada uno de estos pasos.
14. Evita suponer, si no tienes fuentes claras no los menciones.

IMPORTANTE:

Responde siempre en el idioma utilizado por el usuario,
salvo que este solicite expresamente otro idioma.

"""


def ask_model(provider, model, messages):

    # 1. Validar que el proveedor exista en el catálogo

    if provider not in MODELS:
        raise ValueError(
            f"Proveedor no soportado: {provider}"
        )

    # 2. Validar que el modelo esté registrado para ese proveedor

    available_models = [
        item["id"] for item in MODELS[provider]
    ]

    if model not in available_models:
        raise ValueError(
            f"Modelo no registrado para el proveedor {provider}: {model}"
        )

    # 3. Verificar que el proveedor esté configurado

    if provider not in PROVIDERS:
        raise ValueError(
            f"Proveedor no soportado en la configuración: {provider}"
        )

    # 4. Verificar que exista una API Key

    api_key = PROVIDERS[provider]

    if not api_key:
        raise ValueError(
            f"No hay API Key configurada para {provider}"
        )

    # 5. Agregar la instrucción global al historial

    formatted_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        *messages
    ]

    # 6. Enviar solicitud al modelo mediante LiteLLM

    try:

        response = completion(
            model=f"{provider}/{model}",
            messages=formatted_messages,
            api_key=api_key
        )

    except Exception:

        record_usage(
            provider=provider,
            model=model,
            success=False
        )

        raise

    # 7. Obtener consumo de tokens reportado por LiteLLM

    usage = getattr(response, "usage", None)

    prompt_tokens = getattr(
        usage, "prompt_tokens", 0
    ) or 0

    completion_tokens = getattr(
        usage, "completion_tokens", 0
    ) or 0

    # 8. Registrar consumo exitoso

    record_usage(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        success=True
    )

    # 9. Devolver la respuesta

    return response.choices[0].message.content


def ask_model_with_tools(
    provider,
    model,
    messages,
    max_iterations=5,
    tool_names=None
):
    # 1. Validar proveedor y modelo
    if provider not in MODELS:
        raise ValueError(
            f"Proveedor no soportado: {provider}"
        )

    model_config = next(
        (
            item for item in MODELS[provider]
            if item["id"] == model
        ),
        None
    )

    if model_config is None:
        raise ValueError(
            f"Modelo no registrado para {provider}: {model}"
        )

    if not model_config.get("supports_tools", False):
        raise ValueError(
            f"El modelo {model} no admite herramientas."
        )

    # 2. Validar API Key
    api_key = PROVIDERS.get(provider)

    if not api_key:
        raise ValueError(
            f"No hay API Key configurada para {provider}"
        )

    # 3. Cargar herramientas disponibles
    import tools_calculator
    import tools_web_search

    available_tools = get_available_tools()

    if tool_names is not None:
        allowed_tool_names = set(tool_names)
        available_tools = [
            tool for tool in available_tools
            if tool["name"] in allowed_tool_names
        ]

    if not available_tools:
        raise ValueError(
            "No hay herramientas registradas."
        )

    tool_definitions = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        for tool in available_tools
    ]

    # 4. Preparar historial
    conversation = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        *messages
    ]

    # 5. Ejecutar ciclo de herramientas
    for iteration in range(max_iterations + 1):
        try:
            response = completion(
                model=f"{provider}/{model}",
                messages=conversation,
                tools=tool_definitions,
                tool_choice="auto",
                api_key=api_key
            )

        except Exception:
            record_usage(
                provider=provider,
                model=model,
                success=False
            )

            logger.exception(
                "Error al consultar modelo con herramientas: %s / %s",
                provider,
                model
            )
            raise

        # 6. Registrar tokens y consumo de herramientas del servidor
        usage = getattr(response, "usage", None)

        prompt_tokens = getattr(
            usage,
            "prompt_tokens",
            0
        ) or 0

        completion_tokens = getattr(
            usage,
            "completion_tokens",
            0
        ) or 0

        server_tool_use = getattr(
            usage,
            "server_tool_use",
            None
        )

        web_search_requests = getattr(
            server_tool_use,
            "web_search_requests",
            0
        ) or 0

        browser_open_requests = getattr(
            server_tool_use,
            "browser_open_requests",
            0
        ) or 0

        record_usage(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            success=True,
            web_search_requests=web_search_requests,
            browser_open_requests=browser_open_requests
        )

        # 7. Obtener respuesta
        message = response.choices[0].message

        tool_calls = getattr(
            message,
            "tool_calls",
            None
        )

        if not tool_calls:
            return message.content

        # 8. Evitar ciclos infinitos
        if iteration == max_iterations:
            logger.warning(
                "Se alcanzó el límite de iteraciones de herramientas."
            )

            return (
                "No fue posible completar la solicitud "
                "dentro del límite de ejecuciones de herramientas."
            )

        # 9. Agregar llamada del asistente al historial
        conversation.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                }
                for call in tool_calls
            ]
        })

        # 10. Ejecutar herramientas solicitadas
        for call in tool_calls:
            tool_name = call.function.name

            try:
                arguments = json.loads(
                    call.function.arguments
                )

                result = execute_tool(
                    tool_name,
                    arguments
                )

            except Exception as error:
                logger.exception(
                    "Error procesando llamada a herramienta: %s",
                    tool_name
                )

                result = {
                    "success": False,
                    "tool": tool_name,
                    "error": str(error)
                }

            # 11. Devolver resultado al modelo
            conversation.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str
                )
            })

    raise RuntimeError(
        "Se alcanzó el límite de ejecución de herramientas."
    )


def ask_model_with_native_search(provider, model, messages):
    # 1. Validar proveedor y modelo
    if provider not in MODELS:
        raise ValueError(
            f"Proveedor no soportado: {provider}"
        )

    model_config = next(
        (
            item for item in MODELS[provider]
            if item["id"] == model
        ),
        None
    )

    if model_config is None:
        raise ValueError(
            f"Modelo no registrado para {provider}: {model}"
        )

    if not model_config.get("native_web_search", False):
        raise ValueError(
            f"El modelo {model} no admite búsqueda web nativa."
        )

    # 2. Validar API Key
    api_key = PROVIDERS.get(provider)

    if not api_key:
        raise ValueError(
            f"No hay API Key configurada para {provider}"
        )

    # 3. Preparar conversación
    conversation = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        *messages
    ]

    # 4. Ejecutar búsqueda nativa
    try:
        response = completion(
            model=f"{provider}/{model}",
            messages=conversation,
            tools=[
                {
                    "type": "browser_search"
                }
            ],
            tool_choice="required",
            api_key=api_key
        )

        # REGISTRO TEMPORAL PARA DIAGNOSTICAR
        # LA RESPUESTA COMPLETA DE GROQ

        try:
            complete_response = response.model_dump(
                exclude_none=True
            )
        except AttributeError:
            complete_response = str(response)

        logger.info(
            "RESPUESTA NATIVA COMPLETA: %s",
            complete_response
        )

    except Exception:
        record_usage(
            provider=provider,
            model=model,
            success=False
        )

        logger.exception(
            "Error en búsqueda nativa: %s / %s",
            provider,
            model
        )
        raise

    # 5. Extraer consumo de tokens
    usage = getattr(response, "usage", None)

    prompt_tokens = getattr(
        usage,
        "prompt_tokens",
        0
    ) or 0

    completion_tokens = getattr(
        usage,
        "completion_tokens",
        0
    ) or 0

    # 6. Extraer métricas de búsqueda del servidor
    server_tool_use = getattr(
        usage,
        "server_tool_use",
        None
    )

    web_search_requests = getattr(
        server_tool_use,
        "web_search_requests",
        0
    ) or 0

    browser_open_requests = getattr(
        server_tool_use,
        "browser_open_requests",
        0
    ) or 0

    # 7. Registrar consumo
    record_usage(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        success=True,
        web_search_requests=web_search_requests,
        browser_open_requests=browser_open_requests
    )

    # 8. Devolver respuesta
    return response.choices[0].message.content


def ask_model_with_manual_search(provider, model, messages):

    # 1. Validar la consulta
    if not messages:
        raise ValueError(
            "No hay mensajes para realizar la búsqueda."
        )

    user_query = messages[-1].get("content", "")

    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError(
            "No se encontró una consulta válida."
        )

    user_query = user_query.strip()

    # 2. Validar el modelo seleccionado
    model_config = next(
        (
            item for item in MODELS.get(provider, [])
            if item["id"] == model
        ),
        None
    )

    if model_config is None:
        raise ValueError(
            f"Modelo no registrado para {provider}: {model}"
        )

    # 3. Intentar búsqueda nativa
    if model_config.get("native_web_search", False):
        try:
            response = ask_model_with_native_search(
                provider=provider,
                model=model,
                messages=messages
            )

            return {
                "response": {
                    "answer": response,
                    "results": []
                },
                "provider": provider,
                "model": model,
                "search_method": "native"
            }

        except Exception:
            logger.exception(
                "Falló búsqueda nativa en %s / %s. "
                "Se utilizará Tavily.",
                provider,
                model
            )

    # 4. Detectar solicitudes de noticias recientes
    query_lower = user_query.lower()

    news_keywords = (
        "noticias",
        "noticia",
        "últimas noticias",
        "actualidad",
        "reciente",
        "recientes",
        "hoy",
        "esta semana"
    )

    is_news = any(
        keyword in query_lower
        for keyword in news_keywords
    )

    # 5. Ejecutar búsqueda con Tavily
    import tools_web_search

    search_arguments = {
        "query": user_query,
        "max_results": 5,
        "topic": "news" if is_news else "general"
    }

    if is_news:
        search_arguments["time_range"] = "week"

    result = execute_tool(
        "web_search",
        search_arguments
    )

    if not result.get("success"):
        raise RuntimeError(
            result.get(
                "error",
                "Falló la búsqueda con Tavily."
            )
        )

    tavily_response = result["result"]

    search_results = tavily_response.get("results", [])

    if not search_results:
        raise RuntimeError(
            "Tavily no devolvió fuentes para la consulta."
        )

    # 6. Preparar el contexto de búsqueda
    search_context = {
        "consulta": user_query,
        "respuesta_referencial": tavily_response.get("answer"),
        "fuentes": search_results
    }

    search_instruction = (
        "Responde la consulta del usuario utilizando "
        "las siguientes fuentes obtenidas mediante "
        "una búsqueda web.\n\n"
        "Contrasta la información, prioriza los datos "
        "respaldados por las fuentes y no inventes "
        "información.\n"
        "Ten en cuenta las fechas de publicación y "
        "prioriza la información más reciente.\n"
        "Si las fuentes no permiten responder con certeza, "
        "indica esa limitación.\n"
        "Incluye enlaces a las fuentes cuando sean relevantes.\n\n"
        "RESULTADOS DE BÚSQUEDA:\n"
        + json.dumps(
            search_context,
            ensure_ascii=False,
            default=str
        )
    )

    # 7. Colocar las instrucciones antes de la consulta
    messages_with_context = [
        {
            "role": "system",
            "content": search_instruction
        },
        *messages
    ]

    # 8. Generar respuesta con el modelo manual seleccionado
    response = ask_model(
        provider=provider,
        model=model,
        messages=messages_with_context
    )

    # 9. Devolver respuesta, fuentes y modelo utilizado
    return {
        "response": {
            "answer": response,
            "results": search_results
        },
        "provider": provider,
        "model": model,
        "search_method": "tavily"
    }


def ask_model_with_fallback(messages, strategy="free_first"):

    candidates = get_model_candidates(
        capability="general",
        strategy=strategy
    )

    errors = []

    for candidate in candidates:

        provider = candidate["provider"]
        model = candidate["model"]

        try:

            if candidate.get("supports_tools"):
                response = ask_model_with_tools(
                    provider=provider,
                    model=model,
                    messages=messages,
                    tool_names=["calculator"]
                )
            else:
                response = ask_model(
                    provider=provider,
                    model=model,
                    messages=messages
                )

            return {
                "response": response,
                "provider": provider,
                "model": model
            }

        except Exception as error:

            logger.exception(
                "Falló %s / %s. Intentando siguiente modelo.",
                provider,
                model
            )

            errors.append(str(error))

    raise RuntimeError(
        "Todos los modelos disponibles fallaron: "
        + " | ".join(errors)
    )


def ask_model_with_search_fallback(
    messages,
    strategy="free_first"
):
    errors = []

    # 1. Validar la consulta
    if not messages:
        raise ValueError(
            "No hay mensajes para realizar la búsqueda."
        )

    user_query = messages[-1].get("content", "")

    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError(
            "No se encontró una consulta válida."
        )

    user_query = user_query.strip()

    # 2. Detectar solicitudes de noticias recientes
    query_lower = user_query.lower()

    news_keywords = (
        "noticias",
        "noticia",
        "últimas noticias",
        "actualidad",
        "reciente",
        "recientes",
        "hoy",
        "esta semana"
    )

    is_news = any(
        keyword in query_lower
        for keyword in news_keywords
    )

    # 3. Intentar búsqueda nativa
    try:
        candidates = get_model_candidates(
            capability="general",
            strategy=strategy,
            native_web_search=True
        )
    except Exception as error:
        logger.warning(
            "No hay modelos nativos disponibles: %s",
            error
        )
        candidates = []

    for candidate in candidates:
        provider = candidate["provider"]
        model = candidate["model"]

        try:
            response = ask_model_with_native_search(
                provider=provider,
                model=model,
                messages=messages
            )

            return {
                "response": {
                    "answer": response,
                    "results": []
                },
                "provider": provider,
                "model": model,
                "search_method": "native"
            }

        except Exception as error:
            logger.exception(
                "Falló búsqueda nativa en %s / %s.",
                provider,
                model
            )
            errors.append(
                f"{provider}/{model}: {error}"
            )

    # 4. Fallback mediante Tavily
    try:
        import tools_web_search

        search_arguments = {
            "query": user_query,
            "max_results": 5,
            "topic": "news" if is_news else "general"
        }

        if is_news:
            search_arguments["time_range"] = "week"

        result = execute_tool(
            "web_search",
            search_arguments
        )

        if not result.get("success"):
            raise RuntimeError(
                result.get(
                    "error",
                    "Falló la búsqueda con Tavily."
                )
            )

        tavily_response = result["result"]

        search_results = tavily_response.get(
            "results",
            []
        )

        if not search_results:
            raise RuntimeError(
                "Tavily no devolvió fuentes para la consulta."
            )

        # 5. Preparar contexto con las fuentes
        search_context = {
            "consulta": user_query,
            "respuesta_referencial": tavily_response.get("answer"),
            "fuentes": search_results
        }

        search_instruction = (
            "Responde la consulta del usuario utilizando "
            "las siguientes fuentes obtenidas mediante "
            "una búsqueda web.\n\n"
            "Contrasta la información y prioriza los datos "
            "respaldados por las fuentes.\n"
            "Ten en cuenta las fechas de publicación y "
            "prioriza la información más reciente.\n"
            "No inventes información ni afirmes datos "
            "que no estén respaldados por las fuentes.\n"
            "Si las fuentes no permiten responder con certeza, "
            "indica esa limitación.\n"
            "Incluye enlaces a las fuentes cuando sean relevantes.\n\n"
            "RESULTADOS DE BÚSQUEDA:\n"
            + json.dumps(
                search_context,
                ensure_ascii=False,
                default=str
            )
        )

        messages_with_context = [
            {
                "role": "system",
                "content": search_instruction
            },
            *messages
        ]

        # 6. Generar respuesta con fallback automático
        model_result = ask_model_with_fallback(
            messages=messages_with_context,
            strategy=strategy
        )

        response = model_result["response"]

        if not response:
            raise RuntimeError(
                "Los modelos no generaron una respuesta."
            )

        # 7. Devolver respuesta, fuentes y modelo real
        return {
            "response": {
                "answer": response,
                "results": search_results
            },
            "provider": model_result["provider"],
            "model": model_result["model"],
            "search_method": "tavily"
        }

    except Exception as error:
        logger.exception(
            "Falló el fallback de búsqueda mediante Tavily "
            "o el procesamiento de sus resultados."
        )

        errors.append(
            f"Tavily/modelo: {error}"
        )

    # 8. Informar si fallaron todos los mecanismos
    raise RuntimeError(
        "Fallaron todos los servicios de búsqueda: "
        + " | ".join(errors)
    )

