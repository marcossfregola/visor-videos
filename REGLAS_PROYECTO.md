# REGLAS DEL PROYECTO

> **DOCUMENTO HISTÓRICO (sustituido durante la adopción documental).** La fuente oficial vigente de reglas y políticas del proyecto es `RULES.md`. Este documento se conserva únicamente como referencia histórica; su contenido puede estar desactualizado y no debe usarse para determinar el estado vigente.

## Objetivo

Este documento contiene las reglas permanentes de desarrollo del
proyecto.

Todas las etapas futuras deberán respetarlas salvo autorización expresa
de ChatGPT.

## 1. Metodología

-   El proyecto avanza mediante etapas pequeñas, verificables y
    acumulativas.
-   Cada etapa debe tener un único objetivo claramente definido.
-   No mezclar funcionalidades grandes en una misma implementación.
-   No avanzar a una nueva etapa antes de aprobar la anterior.

## 2. Inspección previa

Antes de modificar cualquier archivo se debe: - inspeccionar el estado
actual del proyecto; - identificar los archivos a modificar; -
justificar por qué son necesarios; - indicar qué archivos no serán
modificados.

## 3. Cambios

-   Modificar únicamente los archivos estrictamente necesarios.
-   No realizar refactorizaciones innecesarias.
-   No introducir cambios ajenos al alcance de la etapa.

## 4. Auditoría

Al finalizar cada etapa se debe entregar: - archivos creados; - archivos
modificados; - archivos eliminados; - explicación técnica; - pruebas
realmente ejecutadas; - limitaciones restantes; - salida de
`git status`.

Nunca afirmar pruebas no ejecutadas ni verificaciones visuales no
realizadas.

## 5. Commits

Flujo obligatorio:

Implementación → Pruebas → Auditoría → Aprobación → Commit

-   Nunca crear commits por iniciativa propia.
-   Un commit por etapa aprobada.
-   No mezclar cambios.
-   Árbol limpio tras cada commit.

## 6. Preservación de archivos

Nunca eliminar, sobrescribir, reemplazar, mover ni renombrar archivos
existentes sin autorización expresa.

Incluye bases de datos, miniaturas, cachés, archivos temporales,
ignorados por Git y datos de prueba.

Ante la duda: preservar.

## 7. Arquitectura

Mantener separación entre: - interfaz; - lógica de catálogo; - SQLite; -
escaneo; - FFprobe; - FFmpeg; - caché; - trabajos en segundo plano; -
configuración.

La interfaz nunca debe acceder directamente a SQLite, FFprobe, FFmpeg,
archivos ni lógica pesada.

## 8. Evidencia

Diferenciar siempre: - código modificado; - archivos generados durante
pruebas; - cambios reales en SQLite; - cambios reales en miniaturas; -
archivos ignorados por Git.

## 9. Documentación

Cuando cambie la arquitectura o el comportamiento técnico: - verificar
si `DOCUMENTO_TECNICO.md` requiere actualización; - informarlo aunque no
forme parte de la etapa.

La arquitectura documental deberá auditarse periódicamente (cada 5-10
etapas o cuando se detecten síntomas de mezcla de responsabilidades o
duplicación entre documentos). Cada tipo de información debe tener un
único documento propietario (ver `ESTADO_PROYECTO.md`, sección
"Documentos del proyecto").

## 10. Calidad

Prioridades: 1. Seguridad de los datos. 2. Arquitectura. 3.
Mantenibilidad. 4. Estabilidad. 5. Rendimiento. 6. Nuevas
funcionalidades.

## 11. Evaluación de etapas

-   Cada etapa se evalúa exclusivamente contra el objetivo definido para
    ella en su momento de aprobación.
-   Las funcionalidades previstas para etapas futuras no constituyen
    evidencia de incompletitud de la etapa en evaluación: solo se
    evalúan contra lo prometido por esa etapa.

## 12. Gestión de hilos

-   Cuando el contexto de trabajo sea alto, se abren hilos nuevos de
    forma simultánea en ChatGPT y en OpenCode para continuar el
    desarrollo.
-   Los hilos nuevos parten siempre de los documentos oficiales
    actualizados (`REGLAS_PROYECTO.md`, `DOCUMENTO_TECNICO.md`,
    `ESTADO_PROYECTO.md` y `ROADMAP.md`), que constituyen la fuente
    principal de contexto del proyecto.
-   `VISION_PRODUCTO.md` se consulta como contexto estratégico para
    comprender la filosofía y las decisiones de producto que guían el
    desarrollo.
-   `HISTORIAL_PROYECTO.md` se consulta únicamente cuando sea necesario
    consultar antecedentes de etapas anteriores; no forma parte del
    contexto operativo de desarrollo.

## 13. Cierre y continuidad entre hilos

Al finalizar cada hilo de trabajo deberán realizarse dos cierres
independientes:

### Cierre técnico

Incluye únicamente:

- documentación técnica;
- pruebas correspondientes;
- commit de la etapa implementada.

### Cierre estratégico

Se realizará únicamente cuando durante el hilo hayan surgido nuevas
ideas de producto, cambios de prioridades, decisiones de arquitectura
de alto nivel o criterios de diseño que deban conservarse para el
futuro.

En ese caso:

- ChatGPT mantendrá una "memoria viva" durante toda la conversación.
- Al cerrar el hilo generará un prompt específico para sincronizar
  dicha memoria con la documentación.
- OpenCode actualizará exclusivamente la documentación correspondiente.
- La sincronización estratégica se realizará mediante un commit
  documental independiente.
- Solo después de actualizar las fuentes oficiales se abrirá el
  siguiente hilo de trabajo.

El objetivo de este proceso es evitar la pérdida de decisiones de
producto entre conversaciones y mantener la continuidad del proyecto a
largo plazo.

## 14. Protocolo de colaboración ChatGPT ↔ Bridge ↔ OpenCode

El protocolo de colaboración entre ChatGPT, el Bridge/MCP/Telegram y
OpenCode está **activo**. Su autoridad detallada (actores, flujo, estados,
auditoría, persistencia, seguridad) es `METODOLOGIA_DESARROLLO.md`. Estas
son las normas permanentes que siempre aplican:

- **GitHub vivo es la fuente de verdad** del producto; el ledger contextual
  del Bridge está **subordinado** a GitHub y no deriva datos del producto.
- El **fallback manual** (`Usuario → ChatGPT → copiar prompt → OpenCode →
  copiar informe → ChatGPT`) cambia solo el transporte y **conserva** el
  mismo alcance, evidencia, auditoría y autorizaciones.
- **OpenCode no ejecuta** acciones Git de publicación (commit, push, tag,
  release, merge, rebase, resets destructivos) ni otras acciones de alcance
  prohibido **sin autorización humana explícita**.
- Se debe **procesar el mensaje completo del usuario** antes de avanzar en
  la cadena (`post_audit`, `queue_task`).
- Los secretos nunca se versionan ni se exponen; las instancias de runtime
  no se trasladan para reconstruir otra máquina.
