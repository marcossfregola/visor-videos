# METODOLOGÍA DE DESARROLLO

## 1. Propósito y autoridad del documento

Este documento es la **autoridad detallada** del protocolo de desarrollo y
auditoría del proyecto, incluyendo la operación del Bridge/MCP/Telegram, la
persistencia de la infraestructura y las condiciones de retorno al flujo
automático.

Complementa y desarrolla las normas permanentes de `RULES.md` (reglas permanentes vigentes; `REGLAS_PROYECTO.md` es histórico).
Mientras que `RULES.md` reúne las reglas normativas obligatorias en
todo momento, este documento describe **cómo** se ejecuta el protocolo en la
práctica: actores, flujo, estados, evidencia, auditoría y protección de datos.

No es una copia de `STATUS.md` (estado vigente; `ESTADO_PROYECTO.md` es histórico) ni de
`HISTORIAL_PROYECTO.md` (hitos cronológicos), ni de `ARCHITECTURE.md` (arquitectura; `PROJECT.md` es producto/alcance). Ver "Límites documentales"
(sección 16) para el reparto de responsabilidades. Este documento es autoridad detallada del protocolo; no se inventa protocolo externo.

## 2. Actores y responsabilidades

- **Usuario / Marcos** — decisor humano final. Otorga o deniega autorizaciones
  y es la única instancia que puede resolver decisiones que requieren criterio
  humano.
- **ChatGPT** — director técnico, arquitecto y auditor. Define el plan, la
  arquitectura, el alcance de cada etapa y la evidencia requerida; lidera la
  auditoría y la cadena de aprobación.
- **OpenCode** — ejecutor. Implementa los cambios autorizados dentro del
  alcance declarado de la tarea, verifica y reporta. **No decide** por cuenta
  propia acciones de alcance amplio ni autorizaciones humanas.
- **Bridge/MCP/Telegram** — transporte y orquestación de mensajes. Facilitan
  la comunicación y la persistencia operativa, pero **no sustituyen** la
  auditoría ni la autorización humana.

El Bridge y sus auxiliares son herramientas de transmisión: cambian el
transporte (cómo llegan y se registran las tareas e informes), pero no alteran
el alcance, la evidencia, la auditoría ni las autorizaciones del protocolo.

## 3. Flujo normal

`Usuario → ChatGPT → Bridge → OpenCode → Bridge → ChatGPT → auditoría`

1. El usuario plantea el objetivo en lenguaje natural (típicamente vía
   ChatGPT/Telegram).
2. ChatGPT traduce el objetivo en una tarea técnica con alcance, precondiciones,
   archivos permitidos, prohibiciones y verificación obligatoria.
3. El Bridge encola y entrega la tarea a OpenCode.
4. OpenCode ejecuta la tarea dentro del alcance declarado, verifica y genera un
   informe.
5. El Bridge devuelve el informe a ChatGPT.
6. ChatGPT audita el informe contra el objetivo y la evidencia, y decide
   aprobar, corregir o avanzar a la siguiente etapa.

## 4. Procesar primero todo el mensaje actual del usuario

Antes de `post_audit`, `queue_task` o cualquier acción de orquestación, se debe
**procesar por completo** el mensaje actual del usuario tal como fue
entregado. No se avanza en la cadena con un mensaje parcialmente leído o
malinterpretado.

Las reglas de `AUDIT`/`RELATED`, `previous_task_id` y la cadena de auditoría se
aplican **después** de comprender y procesar íntegramente el mensaje en curso.

## 5. Evidencia y criterio de aprobación

Cada tarea especifica su evidencia mínima. En general:

- salida verificable de comandos reales ejecutados;
- `git diff --check` limpio cuando corresponda;
- `git status --short` que confirme que no hay cambios fuera de alcance;
- revisión del diff completa de los archivos permitidos.

Nunca se afirma una verificación que no se ejecutó. La aprobación de una etapa
se realiza evaluándola **exclusivamente contra el objetivo definido** para esa
etapa, no contra funcionalidades de etapas futuras.

## 6. Estados relevantes del Bridge y semántica mínima

- **SIN TAREA** — no hay tarea activa; el sistema espera una nueva.
- **TRABAJANDO** — una tarea está en ejecución y todavía no reportó.
- **AUDIT** — hay una tarea realmente **pendiente de auditoría**.
- **RELATED** — una auditoría ya se aplicó y corresponde una única tarea
  relacionada con `previous_task_id` exacto.
- **USER_DECISION** — una persona debe elegir explícitamente entre opciones.
- **ERROR / AUTO_BLOCKED** — falló una validación o se requirió intervención;
  corresponde operar conforme a la causa y a las reglas de autorización.

## 7. `AUDIT` vs `RELATED`

- **`AUDIT`** = tarea realmente **pendiente de auditoría**; aún no se ha
  emitido el `post_audit` correspondiente.
- **`RELATED`** = auditoría **ya aplicada**; solo corresponde una tarea
  relacionada con el `previous_task_id` **exacto**.

No se mezclan ambos estados ni se inventan relaciones que no correspondan al
`previous_task_id` exacto.

## 8. Auditoría B4 / B4.2 y cadena relacionada

El mecanismo y el contrato de auditoría son **versionables**; las instancias
concretas del ledger o del runtime **no** son versionables.

La cadena de auditoría usa, cuando corresponde:

- `get_audit_context` — obtener el contexto previo;
- `get_report` — obtener el informe de una tarea;
- verificación de **GitHub vivo** como fuente de verdad del producto cuando
  corresponde;
- `post_audit` — registrar el resultado de la auditoría;
- `previous_task_id` **exacto** para `CORRECTION` o `NEXT_STAGE`.

El patrón `BRIDGE_RETURN_TO_AUTO_OK` es un **patrón de validación**, no una
regla ligada a un `task_id` concreto (ver sección 11).

## 9. Ledger contextual

El ledger contextual del Bridge mantiene el estado operativo de la
colaboración y está **subordinado a GitHub** como fuente de verdad del
producto. Sus campos típicos incluyen:

- `protocol_version`;
- `bootstrap_rules`;
- `context_scope`;
- `stage_id`;
- decisiones beta/permanentes;
- resúmenes recientes de auditoría;
- decisiones sustituidas (`superseded`);
- pendientes vs aplicados (`pending/applied`);
- la subordinación a GitHub.

Ningún dato del producto se deriva del ledger; el ledger describe el estado
del protocolo, no de la aplicación.

## 10. Fallback manual oficial

Flujo de respaldo si el flujo automático no puede continuar:

`Usuario → ChatGPT → copiar prompt → OpenCode → copiar informe → ChatGPT`

Este fallback **cambia solo el transporte** (copia manual en lugar de
Bridge/MCP/Telegram) y **mantiene** el alcance, la evidencia, la auditoría y
las autorizaciones del protocolo.

## 11. Retorno seguro al automático

Criterios para retornar del fallback manual al flujo automático:

- el Bridge está consistente;
- no hay decisiones/resoluciones pendientes;
- branch/HEAD verificados;
- working tree conforme;
- ausencia de duplicados;
- validación read-only cuando corresponda.

`BRIDGE_RETURN_TO_AUTO_OK` es un **patrón de validación**, no una regla
atada a un `task_id` concreto; se evalúa por las condiciones del momento y su
equivalente read-only, no por un identificador de tarea.

## 12. Convergencia asíncrona

Puede existir una ventana breve de convergencia asíncrona

`post_audit → Invoke-AuditPoll → get_status`

durante la cual los estados aún no se consolidan. Es un comportamiento normal
de actualización asíncrona y **no debe confundirse** con una inconsistencia
permanente, ni inventarse un número fijo de segundos para su duración.

## 13. Seguridad y secretos

- **Nunca versionar** tokens, credenciales, materiales DPAPI (`*.dpapi`,
  `token.bin`) ni ninguna clave sensible.
- Los secretos son **siempre locales** a la máquina y no se copian al
  repositorio.
- **No trasladar runtime** (venv, logs, ledger concreto, PIDs) para
  reconstruir otra PC: la reconstrucción se basa en **mecanismo/código/
  contrato/tests/templates sanitizados**, no en instancias de máquina.
- No exponer secretos ni credenciales en informes, comentarios ni salida de
  comandos.

## 14. Persistencia / reconstrucción conceptual

Clasificación de qué se versiona y qué no:

- **A — Se versiona:** código, contratos, tests vigentes, mecanismo/código, y
  templates/configs sanitizados (futuros `*.example`).
- **B — No se versiona (o queda pendiente):** configs reales, binarios reales,
  artefactos E2E históricos pendientes.
- **C — No se versiona:** runtime, logs, ledger concreto, venv, PIDs.
- **D — Nunca:** secretos.

La reconstrucción correcta de otra máquina parte de lo versionable (A) más
configuración local sanitizada; nunca del runtime (C) ni de secretos (D).

## 15. Git/GitHub y autorizaciones prohibidas a OpenCode

OpenCode **no ejecuta** las siguientes acciones por iniciativa propia, sin
autorización humana explícita:

- commit, push, tag, release;
- merge, rebase, force push;
- reset destructivo (hard/mixed en el repositorio);
- cambiar visibilidad de repositorios o issues;
- borrar datos reales de usuario;
- borrar caches/bases de datos reales;
- instalar/desinstalar software real del sistema;
- tocar secretos/tokens/credenciales;
- modificar infraestructura fuera del alcance declarado de la tarea.

## 16. Límites documentales

Cada tipo de información tiene un único documento propietario:

- `RULES.md` — **normas permanentes vigentes** (obligatorias siempre); `REGLAS_PROYECTO.md` es histórico.
- `STATUS.md` — **estado vigente** (no contrato detallado ni historia extensa); `ESTADO_PROYECTO.md` es histórico.
- `ARCHITECTURE.md` — **arquitectura vigente**; `PROJECT.md` — **producto/alcance**; `DOCUMENTO_TECNICO.md` es histórico/de referencia.
- `HISTORIAL_PROYECTO.md` — **hitos** cronológicos (no especificación operativa).
- `METODOLOGIA_DESARROLLO.md` — **protocolo detallado** (este documento, autoridad detallada del protocolo).

No se duplica aquí arquitectura/producto (`DOCUMENTO_TECNICO.md`, `ROADMAP.md`,
`VISION_PRODUCTO.md`) ni se convierten incidentes históricos en reglas atadas a
IDs concretos. `REGLAS_PROYECTO.md` referencia este documento para el detalle
operativo y permanece como autoridad de las normas permanentes.
