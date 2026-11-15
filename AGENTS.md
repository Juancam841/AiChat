# AGENTS.md — AIChat

## Propósito

Estas instrucciones orientan el trabajo de desarrollo en AIChat. Busca cambios correctos, pequeños, mantenibles y verificables, reduciendo lecturas, análisis y ejecuciones redundantes sin omitir controles necesarios.

El código actual es la fuente de verdad. Contrasta la documentación con el código cuando afecte a la tarea; no des por vigente una decisión solo porque figure en un documento.

## Contexto del proyecto

AIChat es una aplicación personal de chat multimodelo. Según el estado documentado del proyecto, usa:

- Backend Python con FastAPI.
- Frontend React, TypeScript y Vite.
- SQLite para persistencia local.
- LiteLLM y proveedores compatibles.
- Enrutamiento y cuotas locales, calculadora y búsqueda web.

El documento de arquitectura es [`INFORME_ARQUITECTURA.md`](INFORME_ARQUITECTURA.md). El README contiene instrucciones de instalación y configuración. Ambos pueden quedar desactualizados; confirma detalles en el código pertinente.

## Forma de trabajar

1. Aclara el resultado esperado e identifica los archivos y contratos relacionados.
2. Inspecciona primero esos archivos y sus dependencias inmediatas; amplía el alcance solo si encuentras una dependencia o riesgo concreto.
3. Conserva el comportamiento existente salvo que el requerimiento pida cambiarlo.
4. Implementa el cambio mínimo que resuelva la tarea y siga las convenciones del repositorio.
5. Verifica el cambio con las comprobaciones relevantes y comunica con precisión qué se ejecutó y qué no.

Para cambios pequeños no hace falta un plan extenso. Profundiza el análisis ante cambios de persistencia, seguridad, contratos API, enrutamiento de modelos o integración de proveedores.

## Eficiencia y verificaciones

- Evita leer archivos enteros si basta con una sección, repetir análisis sin cambios relevantes o recorrer el repositorio sin motivo.
- Limita comandos y salidas a lo necesario para la tarea.
- Ejecuta pruebas o comprobaciones relacionadas cuando la tarea lo requiera o el usuario lo solicite; no repitas verificaciones que sigan siendo válidas tras el cambio.
- Investiga la causa de un fallo antes de ajustar código. No elimines ni debilites pruebas para ocultarlo.
- Informa los resultados reales. Un build correcto no demuestra por sí solo que todos los flujos funcionen.
- No añadas dependencias sin necesidad justificada.

## Reglas funcionales

Antes de cambiar selección de modelos, enrutamiento o cuotas, revisa en el código cómo interactúan la estrategia seleccionada, disponibilidad, límites, fallback y registro de uso. En particular, preserva la selección manual del usuario y no cambies silenciosamente el modelo elegido.

Antes de cambiar búsqueda web, confirma las rutas, activación, proveedores y comportamiento de error implementados actualmente. Distingue las capacidades nativas de un modelo de las herramientas externas; no asumas que existe un proveedor de fallback o una ruta predeterminada sin comprobarlo.

Mantén la trazabilidad del proveedor y modelo realmente utilizados y el registro de consumo y errores cuando el flujo existente lo contemple.

## Arquitectura, seguridad y contratos

- Respeta la arquitectura, estilo y contratos API actuales, salvo que la tarea justifique explícitamente modificarlos.
- Evita duplicación y abstracciones que no aporten valor al cambio.
- Conserva compatibilidad entre backend y frontend.
- No introduzcas secretos ni credenciales en el repositorio. No cambies configuraciones sensibles sin que la tarea lo autorice.
- Considera las implicaciones de seguridad de los cambios, especialmente en la API, persistencia, configuración y exposición de servicios.
- Registra como recomendación las mejoras ajenas al alcance; no las implementes automáticamente.

## Git y cambios locales

- Revisa el estado de Git antes de operaciones que puedan afectar archivos o ramas.
- Preserva cambios locales y trabajo de otras tareas. No sobrescribas archivos modificados sin entender el impacto.
- No cambies de rama, hagas commits o push, ni ejecutes operaciones destructivas como `reset --hard`, `clean`, `rebase` o eliminación de worktrees sin autorización explícita.
- Distingue los cambios preexistentes de los realizados para la tarea actual.

## Documentación y continuidad

Actualiza `INFORME_ARQUITECTURA.md` solo cuando el trabajo cambie de forma relevante la arquitectura, comportamiento, contratos, integraciones o decisiones técnicas. Evita duplicar documentación o registrar cambios triviales.

Mantén este archivo centrado en instrucciones permanentes, no en el historial de cambios. En tareas importantes, deja documentados los nuevos hechos técnicos y pendientes en el lugar apropiado.

## Comunicación

Al terminar, resume qué cambió, qué archivos afectó y qué verificaciones se ejecutaron, incluidos los resultados y cualquier limitación o pendiente relevante. Sé concreto y no declares terminada una tarea si quedan errores conocidos o verificaciones necesarias sin resolver.
