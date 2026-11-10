# AIChat

Aplicación personal de chat multimodelo con una API FastAPI, una interfaz React y persistencia local en SQLite. Permite seleccionar un proveedor y modelo, mantener conversaciones y solicitar búsqueda web con fuentes.

## Requisitos

- Python 3.10 o posterior
- Node.js 20 o posterior
- Claves de API de al menos un proveedor compatible

Las versiones directas del backend están fijadas en `requirements.txt`; el frontend usa `package-lock.json`.

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
pip install -r requirements.txt
uvicorn main:app --reload
```

En otra terminal, inicia la interfaz:

```bash
cd frontend
npm ci
npm run dev
```

Abre la dirección que Vite muestra en la terminal. La API escucha en `http://127.0.0.1:8000`.

## Proveedores

Las claves se leen desde variables de entorno o `.env`. Los modelos disponibles se definen en `models.py`. La búsqueda web requiere Tavily y se activa desde la casilla **Buscar en la web** del chat. En modelos compatibles, la calculadora se invoca automáticamente cuando el modelo la necesita.

La base SQLite se crea localmente al iniciar el backend. No se debe subir `.env`, archivos de base de datos ni artefactos de dependencias.

Para limitar el tamaño del contexto, cada solicitud admite hasta 24.000 caracteres. Al continuar una conversación, se envían como máximo los 12 turnos completos más recientes dentro de ese límite; el historial completo permanece guardado en SQLite.

Las cuotas locales se configuran por modelo en `quota_config.py`. Cada límite puede medirse por día, mes o acumulado total; los periodos diarios y mensuales usan UTC. Los valores `None` no imponen un tope, así que define valores de `requests` o `total_tokens` para activar una cuota.

## Exposición del backend

La API todavía no incluye autenticación. Mantén el backend en una máquina local o en una red privada de confianza; no lo publiques directamente en Internet.
