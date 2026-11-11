# Informe de arquitectura y auditoría funcional de AIChat

**Revisión:** 2026-11-10. **Base de código:** `main`, commit `1b2f444` (PR #1–#8 mergeados). Se revisaron backend, frontend, persistencia, selección, herramientas, búsqueda, cuotas y configuración. No se leyeron `.env`, credenciales ni bases de datos reales.

**Estado de dependencias:** `requirements.txt` y `requirements.lock` fijan `litellm==1.105.1`; el lock resuelve dependencias transitivas de forma universal desde Python 3.10.

## Arquitectura descrita en el diagnóstico inicial

AIChat es una aplicación con frontend React/Vite y backend FastAPI. El backend concentra las rutas HTTP, la selección de modelos, las llamadas a proveedores mediante LiteLLM, la búsqueda web y la persistencia en SQLite. La configuración de proveedores y los catálogos de modelos están definidos en módulos Python.

La estructura fuente visible incluye:

- Backend: main.py, providers.py, model_router.py, models.py, config.py, quota_manager.py, usage_manager.py, database.py y módulos de herramientas.
- Frontend: frontend/src/App.tsx, frontend/src/services/api.ts y estilos; Vite y TypeScript se configuran en frontend/.
- Pruebas o scripts de prueba: test_providers.py y test_groq.py.
- Copias antiguas: main_backup.py y models_backup.py.

## Flujo de ejecución vigente

1. Al iniciar, FastAPI inicializa SQLite y migra las columnas de métricas de búsqueda. La importación del backend registra la calculadora y la búsqueda de Tavily.
2. La interfaz carga conversaciones y el catálogo. `/providers` devuelve proveedores configurados, proveedores con modelos habilitados y `available`, la intersección que utiliza el selector manual. `/models` entrega los modelos habilitados del proveedor solicitado.
3. El usuario envía mensaje, conversación, estrategia (`manual`, `free_first` o `best_available`), proveedor/modelo y `web_search`. La API limita el mensaje a 24.000 caracteres.
4. En una conversación existente, la API limita la entrada a 12 turnos completos, 24.000 caracteres y 8.192 tokens estimados, contando el mensaje nuevo, el prompt del sistema y los esquemas de herramientas. Reserva 2.048 tokens para resultados que se agregan después: hasta 1.024 de búsqueda y 1.024 de herramientas. Las respuestas del modelo tienen un máximo de 2.048 tokens. El historial completo permanece en SQLite.
5. En modo manual se respeta el modelo elegido. Si se activa búsqueda web, se intenta búsqueda nativa cuando el modelo la declara y luego Tavily; de lo contrario, un modelo compatible puede usar la calculadora. En modo automático, el router filtra modelos configurados, habilitados y dentro de cuota; `free_first` prioriza los gratuitos y `best_available` conserva el orden del catálogo. El fallback intenta candidatos posteriores si uno falla.
6. Tras una respuesta correcta se crea una conversación nueva, si corresponde, y se guardan mensaje del usuario, respuesta, título y modelo utilizado. El backend responde con texto, modelo, proveedor y fuentes de búsqueda.
7. La interfaz muestra Markdown, fuentes y errores. Al abrir una conversación anterior recupera mensajes, pero no las fuentes asociadas a las respuestas porque estas no se persisten.
8. Cada llamada a proveedor registra tokens, resultado y métricas de búsqueda. `/usage` muestra agregados históricos; `/quotas` muestra el consumo del periodo configurado.

## Componentes y responsabilidades vigentes

- **API y coordinación:** `main.py` define chat, catálogo, uso, cuotas y CRUD de conversaciones; además decide qué flujo de proveedor invocar.
- **Proveedores y fallback:** `providers.py` valida modelos y claves, llama a LiteLLM, registra uso, ejecuta herramientas y gestiona búsqueda nativa/Tavily.
- **Catálogo y selección:** `models.py` mantiene manualmente capacidades, costos, soporte de herramientas y orden de prioridad. `model_router.py` filtra por proveedor, capacidad y cuota.
- **Configuración:** config.py lee claves desde variables de entorno mediante python-dotenv. No se inspeccionaron sus valores.
- **Cuotas y utilización:** `quota_manager.py` calcula consumo por día, mes o total; `usage_manager.py` registra cada llamada a proveedor en SQLite.
- **Persistencia:** database.py gestiona conversaciones, mensajes, índices y una migración para columnas de métricas de búsqueda.
- **Herramientas:** tool_manager.py registra herramientas y valida argumentos con JSON Schema. tools_web_search.py implementa Tavily; tools_calculator.py evalúa expresiones mediante un subconjunto de AST.
- **Contexto:** `conversation_context.py` limita turnos completos, caracteres y tokens estimados enviados al modelo.
- **Frontend:** `frontend/src/App.tsx` administra catálogo, estrategia, chat, búsqueda e historial; `frontend/src/services/api.ts` centraliza las llamadas HTTP.

## Hallazgos del diagnóstico original (referencia histórica)

1. **La interfaz no expone la búsqueda web.** El backend admite web_search, pero el frontend no lo incluye en la petición ni ofrece control para activarlo. La búsqueda web no está disponible desde la interfaz actual.
2. **El ciclo general de herramientas parece desconectado.** ask_model_with_tools implementa llamadas iterativas a herramientas, pero las rutas de chat invocan ask_model o funciones de fallback. No se encontró una ruta que llame a ask_model_with_tools; por tanto, la calculadora y el uso general de herramientas por el modelo no parecen alcanzables en el flujo normal. La búsqueda de Tavily sí se invoca directamente en las rutas especializadas.
3. **Cuotas sin límites efectivos.** Los límites visibles en quota_config.py son None; los demás modelos reciben límites por defecto también sin topes. Además, el consumo se agrega sin ventana temporal, así que no representa cuotas por día o mes.
4. **Selección automática y catálogo pueden divergir.** /providers separa proveedores configurados de proveedores con modelos habilitados, mientras la interfaz selecciona el primero de los configurados. Un proveedor puede estar configurado y no tener modelos activos; también hay modelos activos que no estarán disponibles si falta su clave.
5. **Las solicitudes fallidas pueden dejar conversaciones vacías.** En /chat se crea una conversación antes de consultar al proveedor, pero los mensajes se persisten solo después de recibir respuesta. Si falla la llamada, queda una conversación sin mensajes.
6. **El historial se reenvía completo.** Cada solicitud vuelve a enviar todos los mensajes almacenados, sin truncamiento ni resumen. El costo, el tiempo y el uso de contexto pueden crecer con la duración de la conversación.
7. **Hay diagnóstico excesivo en logs de búsqueda nativa.** providers.py registra la respuesta completa del proveedor; según el contenido devuelto, esto puede incluir texto de la conversación y datos de búsqueda.
8. **La prueba de proveedor no coincide con la función actual.** test_providers.py llama a ask_model con message=, mientras la función espera messages. También es un script que hace una llamada real, no un test aislado.
9. **Resuelto en esta revisión — Dependencias reproducibles del backend.** `requirements.txt` declara dependencias directas y `requirements.lock` fija las transitivas con hashes para Python 3.10 y posteriores en plataformas compatibles.
10. **Los contratos del frontend y backend no están completamente alineados.** El tipo TypeScript de estrategia admite manual, free_first y best_available, pero la interfaz solo ofrece las dos primeras. Asimismo, el tipo de respuesta del chat no contempla results, aunque el backend los devuelve.

## Riesgos de mantenimiento identificados inicialmente

- **Acoplamiento:** main.py coordina demasiadas responsabilidades; providers.py combina validación, transporte, fallback, búsqueda y contabilidad.
- **Catálogo mantenido a mano:** modelos, capacidades y límites están en estructuras separadas, con posibilidad de inconsistencias.
- **Estado y concurrencia:** SQLite es sencillo para uso local, pero el sistema no muestra límites de concurrencia, retención o paginación para historial y utilización.
- **Seguridad de API:** no hay autenticación en las rutas visibles. CORS limita algunos orígenes del navegador, pero no protege los endpoints frente a clientes que los llamen directamente. Esto importa especialmente si el servicio se expone fuera de una máquina local.
- **Validación difícil:** los scripts de prueba requieren acceso a proveedores externos y credenciales; no se aprecia una suite de pruebas automatizada aislada.
- **Código de respaldo:** main_backup.py y models_backup.py duplican código y pueden confundir sobre cuál es la implementación activa.

## Recomendaciones originales

1. **P0 — Alinear capacidades visibles con las funcionales.** Decidir si la búsqueda y las herramientas deben estar en la interfaz y conectar el flujo correspondiente; si no, evitar presentarlas como capacidades activas.
2. **P0 — Definir límites de exposición.** Si el backend puede ser accesible desde una red, establecer autenticación y controles de acceso antes de publicar el servicio.
3. **P1 — Hacer efectivas las cuotas.** Definir ventanas de medición y límites reales, además de considerar concurrencia para evitar que solicitudes simultáneas excedan el límite.
4. **P1 — Evitar conversaciones huérfanas y gestionar fallos.** Revisar el orden de creación y persistencia para que un fallo del proveedor no deje registros incompletos.
5. **P1 — Controlar el historial enviado al modelo.** Establecer una política de truncamiento o resumen para conversaciones largas.
6. **P1 — Reducir datos sensibles en logs.** Evitar registrar respuestas completas de proveedores en operación normal.
7. **P2 — Unificar catálogo, proveedor y cuota.** Centralizar o validar estas configuraciones para que el selector y el router utilicen criterios coherentes.
8. **P2 — Añadir pruebas aisladas y dependencias reproducibles.** Separar pruebas unitarias de llamadas reales y declarar dependencias del backend.
9. **P3 — Simplificar estructura.** Retirar o archivar copias de respaldo una vez confirmada la versión vigente, y separar coordinación HTTP de lógica de proveedores.

## Verificación del diagnóstico original

No se modificó ni ejecutó código. El informe se basa en inspección estática de los archivos fuente permitidos; no incluye validación dinámica de dependencias, endpoints o servicios externos.

## Cambios incorporados en `main` hasta PR #8

La versión inicial y su evolución incorporan estos cambios respecto al estado descrito arriba:

- La interfaz envía la opción `web_search` y muestra los enlaces de las fuentes recibidas.
- `/chat` conecta `ask_model_with_tools` para modelos compatibles en modo manual y automático. En el chat normal solo expone la calculadora; la búsqueda web continúa bajo el control de la casilla de búsqueda.
- Las conversaciones nuevas se crean después de recibir una respuesta del modelo, evitando registros vacíos cuando falla la consulta al proveedor.
- La búsqueda nativa registra proveedor y modelo, no el objeto completo de respuesta del proveedor.
- El contexto enviado al modelo se limita a un máximo de 12 turnos completos, 24.000 caracteres y un presupuesto de tokens; la base conserva el historial íntegro.
- Las cuotas pueden medir consumo por día, mes o acumulado total en UTC; los topes numéricos se configuran por modelo en `quota_config.py` y permanecen sin límite mientras sean `None`.
- `/providers` expone `available`, la intersección entre proveedores configurados y proveedores con modelos habilitados; la interfaz usa esa lista para el selector manual.
- La interfaz ofrece `manual`, `free_first` y `best_available`; esta última utiliza el orden declarado en `models.py`.
- `requirements.txt` declara las dependencias directas del backend, incluida `jsonschema` para validar argumentos de herramientas; `requirements.lock` fija todas las dependencias resueltas con hashes para Python 3.10 y posteriores en plataformas compatibles.
- Los tipos del frontend incluyen `web_search` y los resultados devueltos por el backend.

## Auditoría funcional de la versión actual

### Cobertura revisada

- **Chat y persistencia:** se verificaron respuestas simuladas en modo manual, búsqueda manual con fuentes, selección automática `best_available`, guardado de mensajes y ausencia de conversaciones/mensajes nuevos cuando falla el proveedor.
- **Herramientas:** se verificó la llamada de `/chat` al flujo de herramientas para un modelo compatible y se probó la calculadora. No se simuló el protocolo de tool-calling de cada proveedor.
- **Contexto y cuotas:** se revisó el recorte a turnos completos y se ejercitaron los periodos UTC diarios, mensuales y acumulados. Los límites numéricos siguen en `None`.
- **Frontend:** `npm ci`, `npm run build` y `npm run lint` terminaron correctamente en un checkout temporal de `main`.
- **Backend:** se instalaron las dependencias fijadas de `main` en un entorno temporal y pasaron pruebas de humo con `TestClient` y proveedores simulados.

No se probaron llamadas reales a Groq, Gemini, OpenRouter ni Tavily porque dependen de claves externas, que no se leyeron. La verificación se hizo en Linux con Python 3.12 y Node 24, no en el entorno macOS del usuario. La API local sí respondió correctamente en las pruebas simuladas; eso no demuestra la disponibilidad de cada proveedor ni de sus modelos actuales.

### Problemas técnicos vigentes

1. **P0 condicional — API sin autenticación.** Todas las rutas son accesibles a cualquier cliente que alcance el backend. CORS limita navegadores, no clientes directos. Uvicorn usa loopback por defecto; no se debe enlazar a una interfaz de red ni publicar el servicio sin añadir autenticación.
2. **P1 — Cuotas desactivadas por configuración.** Los periodos se calculan en UTC, pero los topes `requests` y `total_tokens` permanecen en `None`; por tanto, no se impone un límite. Definir valores requiere conocer los topes que quiere aplicar el propietario a cada modelo.
3. **P2 — El presupuesto de entrada no se adapta a la ventana real de cada modelo.** Se limita la entrada a 8.192 tokens, se cuentan los esquemas de herramientas, se reservan 1.024 tokens cada uno para resultados de búsqueda y de herramientas y se limita la salida a 2.048 tokens. Cuando LiteLLM no identifica un tokenizador, se estima por bytes UTF-8. Varios modelos no declaran `context_window`, por lo que el presupuesto global todavía no garantiza compatibilidad con la ventana de cada proveedor.
4. **P2 — Paginación y retención parciales.** El listado usa páginas de 25 conversaciones, y el detalle muestra 50 mensajes por página, ambos con máximo de 100. Las estadísticas de uso todavía se devuelven completas y no hay política de retención.
5. **P2 — Suite automatizada ausente.** El repositorio no contiene pruebas backend aisladas. Las pruebas de humo de esta revisión fueron temporales y no quedaron como suite reproducible. Las llamadas de proveedores requieren pruebas simuladas para evitar credenciales y cargos.
6. **P3 — Responsabilidades concentradas.** `main.py` aún coordina demasiadas rutas y `providers.py` combina transporte, fallback, herramientas, búsqueda y contabilidad.

### Estado de las recomendaciones

- **Resueltas en código:** búsqueda web visible; calculadora conectada para modelos compatibles; conversaciones nuevas creadas después de una respuesta exitosa; turnos, fuentes y metadatos guardados atómicamente; errores del envío reflejados correctamente en el frontend; contexto acotado; logs sin serializar la respuesta nativa completa; selector de proveedores disponibles; estrategias frontend alineadas; URL de API y orígenes CORS configurables; paginación del listado de conversaciones; reservas SQLite para cuotas concurrentes.
- **Parciales:** cuotas con periodos y reservas, pero sin valores numéricos; presupuesto de entrada acotado, salida limitada y reserva para herramientas; la compatibilidad con ventanas por modelo sigue pendiente; paginación/retención de estadísticas de uso pendientes.
- **Pendientes:** autenticación si el backend se expone fuera de loopback o una red privada; pruebas backend aisladas; refactor de coordinación.

## Verificación de esta revisión

- Frontend temporal: `npm ci`, `npm run build` y `npm run lint` — correctos.
- Backend temporal: instalación desde dependencias fijadas de `main` y pruebas de humo con proveedores simulados — correctas. Lock: compilación universal desde las dependencias locales para Python 3.10 y posteriores, con hashes — correcta.
- `git diff --check` del informe — correcto.
- No se hicieron llamadas externas a modelos ni a Tavily, ni se inspeccionaron claves o bases de datos del usuario.
