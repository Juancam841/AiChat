# Informe de diagnóstico de arquitectura de AIChat

**Alcance:** análisis estático del código fuente y las configuraciones visibles. No se modificaron otros archivos, no se leyeron .env, credenciales, bases de datos, entornos virtuales ni artefactos compilados, y no se ejecutaron pruebas. No se encontró un manifiesto de dependencias del backend entre los archivos fuente visibles.

## Arquitectura actual

AIChat es una aplicación con frontend React/Vite y backend FastAPI. El backend concentra las rutas HTTP, la selección de modelos, las llamadas a proveedores mediante LiteLLM, la búsqueda web y la persistencia en SQLite. La configuración de proveedores y los catálogos de modelos están definidos en módulos Python.

La estructura fuente visible incluye:

- Backend: main.py, providers.py, model_router.py, models.py, config.py, quota_manager.py, usage_manager.py, database.py y módulos de herramientas.
- Frontend: frontend/src/App.tsx, frontend/src/services/api.ts y estilos; Vite y TypeScript se configuran en frontend/.
- Pruebas o scripts de prueba: test_providers.py y test_groq.py.
- Copias antiguas: main_backup.py y models_backup.py.

## Flujo de ejecución de una solicitud

1. El frontend carga los proveedores configurados y modelos mediante /providers y /models.
2. Al enviar un mensaje, manda conversation_id, message, provider, model y strategy a /chat.
3. FastAPI elige el modelo manualmente o llama a select_model. En estrategia automática, el router filtra el catálogo por proveedor configurado, capacidad, estado y cuota local.
4. El backend recupera el historial de SQLite y añade el nuevo mensaje.
5. Según la estrategia y si se solicitó búsqueda web, llama a LiteLLM directamente o recorre candidatos de fallback. La búsqueda puede usar la búsqueda nativa de un modelo compatible o Tavily.
6. Tras obtener respuesta, guarda usuario y asistente en SQLite, actualiza título y modelo de la conversación y devuelve la respuesta al frontend.

Las rutas están en main.py; el frontend arma la petición en frontend/src/App.tsx y la envía desde frontend/src/services/api.ts.

## Componentes y responsabilidades

- **API y coordinación:** main.py define las rutas de chat, modelos, proveedores, consumo, cuotas y conversaciones. También inicializa la base al arrancar.
- **Proveedores y fallback:** providers.py valida modelo y API key, llama a LiteLLM y registra tokens. Incluye fallback entre modelos y búsqueda web.
- **Catálogo y selección:** models.py define capacidades, costos declarados y compatibilidad con herramientas. model_router.py filtra candidatos y ordena los gratuitos primero.
- **Configuración:** config.py lee claves desde variables de entorno mediante python-dotenv. No se inspeccionaron sus valores.
- **Cuotas y utilización:** quota_manager.py compara límites estáticos con los agregados de usage_manager.py, que registra solicitudes y tokens en SQLite.
- **Persistencia:** database.py gestiona conversaciones, mensajes, índices y una migración para columnas de métricas de búsqueda.
- **Herramientas:** tool_manager.py registra herramientas y valida argumentos con JSON Schema. tools_web_search.py implementa Tavily; tools_calculator.py evalúa expresiones mediante un subconjunto de AST.
- **Frontend:** frontend/src/App.tsx administra catálogo, selector de estrategia, chat e historial. frontend/src/services/api.ts centraliza las llamadas HTTP.

## Problemas técnicos detectados

1. **La interfaz no expone la búsqueda web.** El backend admite web_search, pero el frontend no lo incluye en la petición ni ofrece control para activarlo. La búsqueda web no está disponible desde la interfaz actual.
2. **El ciclo general de herramientas parece desconectado.** ask_model_with_tools implementa llamadas iterativas a herramientas, pero las rutas de chat invocan ask_model o funciones de fallback. No se encontró una ruta que llame a ask_model_with_tools; por tanto, la calculadora y el uso general de herramientas por el modelo no parecen alcanzables en el flujo normal. La búsqueda de Tavily sí se invoca directamente en las rutas especializadas.
3. **Cuotas sin límites efectivos.** Los límites visibles en quota_config.py son None; los demás modelos reciben límites por defecto también sin topes. Además, el consumo se agrega sin ventana temporal, así que no representa cuotas por día o mes.
4. **Selección automática y catálogo pueden divergir.** /providers separa proveedores configurados de proveedores con modelos habilitados, mientras la interfaz selecciona el primero de los configurados. Un proveedor puede estar configurado y no tener modelos activos; también hay modelos activos que no estarán disponibles si falta su clave.
5. **Las solicitudes fallidas pueden dejar conversaciones vacías.** En /chat se crea una conversación antes de consultar al proveedor, pero los mensajes se persisten solo después de recibir respuesta. Si falla la llamada, queda una conversación sin mensajes.
6. **El historial se reenvía completo.** Cada solicitud vuelve a enviar todos los mensajes almacenados, sin truncamiento ni resumen. El costo, el tiempo y el uso de contexto pueden crecer con la duración de la conversación.
7. **Hay diagnóstico excesivo en logs de búsqueda nativa.** providers.py registra la respuesta completa del proveedor; según el contenido devuelto, esto puede incluir texto de la conversación y datos de búsqueda.
8. **La prueba de proveedor no coincide con la función actual.** test_providers.py llama a ask_model con message=, mientras la función espera messages. También es un script que hace una llamada real, no un test aislado.
9. **No se ve configuración reproducible de dependencias del backend.** Las dependencias frontend figuran en frontend/package.json; no se encontró un requirements.txt o equivalente entre los archivos fuente visibles.
10. **Los contratos del frontend y backend no están completamente alineados.** El tipo TypeScript de estrategia admite manual, free_first y best_available, pero la interfaz solo ofrece las dos primeras. Asimismo, el tipo de respuesta del chat no contempla results, aunque el backend los devuelve.

## Riesgos de mantenimiento

- **Acoplamiento:** main.py coordina demasiadas responsabilidades; providers.py combina validación, transporte, fallback, búsqueda y contabilidad.
- **Catálogo mantenido a mano:** modelos, capacidades y límites están en estructuras separadas, con posibilidad de inconsistencias.
- **Estado y concurrencia:** SQLite es sencillo para uso local, pero el sistema no muestra límites de concurrencia, retención o paginación para historial y utilización.
- **Seguridad de API:** no hay autenticación en las rutas visibles. CORS limita algunos orígenes del navegador, pero no protege los endpoints frente a clientes que los llamen directamente. Esto importa especialmente si el servicio se expone fuera de una máquina local.
- **Validación difícil:** los scripts de prueba requieren acceso a proveedores externos y credenciales; no se aprecia una suite de pruebas automatizada aislada.
- **Código de respaldo:** main_backup.py y models_backup.py duplican código y pueden confundir sobre cuál es la implementación activa.

## Recomendaciones priorizadas

1. **P0 — Alinear capacidades visibles con las funcionales.** Decidir si la búsqueda y las herramientas deben estar en la interfaz y conectar el flujo correspondiente; si no, evitar presentarlas como capacidades activas.
2. **P0 — Definir límites de exposición.** Si el backend puede ser accesible desde una red, establecer autenticación y controles de acceso antes de publicar el servicio.
3. **P1 — Hacer efectivas las cuotas.** Definir ventanas de medición y límites reales, además de considerar concurrencia para evitar que solicitudes simultáneas excedan el límite.
4. **P1 — Evitar conversaciones huérfanas y gestionar fallos.** Revisar el orden de creación y persistencia para que un fallo del proveedor no deje registros incompletos.
5. **P1 — Controlar el historial enviado al modelo.** Establecer una política de truncamiento o resumen para conversaciones largas.
6. **P1 — Reducir datos sensibles en logs.** Evitar registrar respuestas completas de proveedores en operación normal.
7. **P2 — Unificar catálogo, proveedor y cuota.** Centralizar o validar estas configuraciones para que el selector y el router utilicen criterios coherentes.
8. **P2 — Añadir pruebas aisladas y dependencias reproducibles.** Separar pruebas unitarias de llamadas reales y declarar dependencias del backend.
9. **P3 — Simplificar estructura.** Retirar o archivar copias de respaldo una vez confirmada la versión vigente, y separar coordinación HTTP de lógica de proveedores.

## Verificación

No se modificó ni ejecutó código. El informe se basa en inspección estática de los archivos fuente permitidos; no incluye validación dinámica de dependencias, endpoints o servicios externos.

## Seguimiento posterior al diagnóstico

La versión inicial y su evolución incorporan estos cambios respecto al estado descrito arriba:

- La interfaz envía la opción `web_search` y muestra los enlaces de las fuentes recibidas.
- `/chat` conecta `ask_model_with_tools` para modelos compatibles en modo manual y automático. En el chat normal solo expone la calculadora; la búsqueda web continúa bajo el control de la casilla de búsqueda.
- Las conversaciones nuevas se crean después de recibir una respuesta del modelo, evitando registros vacíos cuando falla la consulta al proveedor.
- La búsqueda nativa registra proveedor y modelo, no el objeto completo de respuesta del proveedor.
- El contexto enviado al modelo se limita a un máximo de 12 turnos completos y 24.000 caracteres por solicitud; la base conserva el historial íntegro.
- Las cuotas pueden medir consumo por día, mes o acumulado total en UTC; los topes numéricos se configuran por modelo en `quota_config.py` y permanecen sin límite mientras sean `None`.
- `/providers` expone `available`, la intersección entre proveedores configurados y proveedores con modelos habilitados; la interfaz usa esa lista para el selector manual.
- `requirements.txt` declara dependencias directas del backend, incluida `jsonschema` para validar argumentos de herramientas.
- Los tipos del frontend incluyen `web_search` y los resultados devueltos por el backend.

Estos cambios no resuelven las otras recomendaciones del diagnóstico. No se ejecutaron pruebas ni una compilación para esta actualización.
