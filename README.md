# AIChat

Aplicación personal de chat multimodelo con una API FastAPI, una interfaz React y persistencia local en SQLite. Permite seleccionar un proveedor y modelo, mantener conversaciones y solicitar búsqueda web con fuentes.

## Requisitos

- Python 3.10 o posterior
- Node.js 20 o posterior
- Claves de API de al menos un proveedor compatible

Las dependencias directas del backend están declaradas en `requirements.txt` y sus versiones transitivas están fijadas con hashes en `requirements.lock`; el frontend usa `package-lock.json`.

## Configuración

Instala las dependencias del backend y crea un archivo `.env` en la raíz:

```env
GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
MISTRAL_API_KEY=
TAVILY_API_KEY=
```

Solo hace falta configurar los proveedores que quieras utilizar. `TAVILY_API_KEY` habilita la búsqueda web.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.lock
uvicorn main:app --reload
```

En otra terminal, inicia la interfaz:

```bash
cd frontend
npm ci
npm run dev
```

Abre la dirección que Vite muestra en la terminal. La API escucha en `http://127.0.0.1:8000`.

Si el frontend y la API están en hosts distintos, define `VITE_API_URL` en `frontend/.env.local` con la URL base de la API, por ejemplo `VITE_API_URL=https://api.ejemplo.com`. En el entorno del backend, configura `AI_CHAT_CORS_ORIGINS` con el origen completo del frontend, por ejemplo `https://chat.ejemplo.com`. Si no defines estas variables, se usan las direcciones locales de desarrollo.

## Proveedores

Las claves se leen desde variables de entorno o `.env`. Los modelos disponibles se definen en `models.py`. La búsqueda web requiere Tavily y se activa desde la casilla **Buscar en la web** del chat. En modelos compatibles, la calculadora se invoca automáticamente cuando el modelo la necesita.

La base SQLite se crea localmente al iniciar el backend. No se debe subir `.env`, archivos de base de datos ni artefactos de dependencias.

En el selector, **Gratis primero** prioriza modelos gratuitos; **Mejor disponible** utiliza el orden de prioridad definido en `models.py`. La estrategia manual respeta el proveedor y el modelo seleccionados.

Cada mensaje admite hasta 24.000 caracteres. Al continuar una conversación, el backend cuenta tokens con LiteLLM y envía como máximo los 12 turnos completos más recientes dentro de un presupuesto de 8.192 tokens; el cálculo incluye el mensaje nuevo y el prompt del sistema, y reserva 2.048 tokens para instrucciones y herramientas adicionales. También conserva el tope de caracteres. Si LiteLLM no puede identificar un tokenizador para el modelo, usa una estimación conservadora basada en el tamaño UTF-8. El historial completo permanece guardado en SQLite.

Las cuotas locales se configuran por modelo en `quota_config.py`. Cada límite puede medirse por día, mes o acumulado total; los periodos diarios y mensuales usan UTC. Los valores `None` no imponen un tope, así que define valores de `requests` o `total_tokens` para activar una cuota.

Cuando una cuota tiene un límite numérico, el backend reserva capacidad en SQLite antes de cada llamada al proveedor y la libera al registrar su consumo. Las reservas abandonadas caducan después de 120 minutos. Si se configura `total_tokens`, el backend reserva el saldo restante para una llamada activa hasta recibir el consumo real, por lo que esas llamadas se procesan de una en una para ese modelo.

## Exposición del backend

La API todavía no incluye autenticación. Mantén el backend en una máquina local o en una red privada de confianza; no lo publiques directamente en Internet.


Para regenerar `requirements.lock` después de cambiar dependencias directas, instala [uv](https://docs.astral.sh/uv/) y ejecuta desde la raíz:

```bash
uv pip compile --universal --python-version 3.10 --generate-hashes requirements.txt -o requirements.lock
```
