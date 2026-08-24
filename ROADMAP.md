# ROADMAP — Visor de Videos

Trabajo futuro **decidido** y priorizado. Separacion obligatoria: `ROADMAP = decidido`, `BACKLOG = quiza`. Las ideas tentativas viven en `BACKLOG.md`; lo ya implementado queda registrado en `HISTORIAL_PROYECTO.md` y en `STATUS.md`.

## Estado post-Beta 7

**Beta 7 — "Organización y operaciones de archivos" (B7.13) cerrada y publicada.** Commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` (`B7 Cerrar Beta 7 B7.13`); tag `v7.0-beta` → `f9976d3`; rama `beta7` publicada (reconciliación posterior `97e6fcf`); Release `v7.0-beta` prerelease PUBLIC; `main` reconciliada mediante este cierre (V1.3 + Beta 7). Capacidades entregadas: exploración temporal, marcadores/segmentos, clasificación por color, exportación y trazabilidad de derivados, organización de archivos (renombrado individual/masivo, mover/copiar/eliminar por lote, crear carpetas, modo Organización/Explorer con doble panel y drag & drop). Contrato estático y build/artefacto Beta 7 aprobados; el ciclo real instalación/desinstalación/reinstalación no se ejecutó por seguridad y no bloquea el desarrollo. Historial completo en `HISTORIAL_PROYECTO.md` (121).

> **Nota de alcance:** la distribución pública queda **fuera de alcance**. El instalador (`PyInstaller`/`Inno Setup`) es secundario y opcional para comodidad personal del propietario; su validación real completa no es requisito para futuras betas y solo se retomará por pedido explícito. La validación del instalador Beta 7 no bloquea el desarrollo. Visor de Videos es de **uso exclusivamente personal**.

## Beta 8 — IDENTIDAD E INTEGRIDAD DEL CATÁLOGO

**Objetivo:** corregir el modelo de identidad antes de seguir construyendo funciones multicarpeta y visuales. Mantener conceptualmente limpia: no agregar mejoras UX generales salvo las estrictamente necesarias para el cambio técnico.

**B8.1 — Preparación de identidad**
Agregar `ruta_normalizada` (helper central `rutas.normalizar_ruta_clave` con `abspath+normpath+normcase+strip`), poblarla, `UNIQUE(ruta_normalizada)`, dual-write `ruta`+`ruta_normalizada`, mantener `UNIQUE(nombre)` y `ON CONFLICT(nombre)`, `guardar_videos` empieza a devolver `video_id` manteniendo compatibilidad, reordenar pipeline para guardar antes de generar miniaturas y preservar `cantidad_miniaturas` con actualización puntual por `video_id`.

**B8.2 — Cache por video_id**
Miniaturas y previews normales por `video_id` (`v<video_id>_<NN>.jpg`), migración no destructiva de cache legacy (`video_*.jpg` → `v<id>_*.jpg` por copia, sin borrar legacy, sin fallback ambiguo por nombre), renombrar/mover dejan de depender del nombre para cache, corregir preview obsoleto T16 y eliminar fragilidad de prefijos por nombre asociada a T03.

**B8.3 — Cutover de identidad**
Eliminar `UNIQUE(nombre)` (nombre pasa a atributo no único), `UNIQUE` por `ruta_normalizada`, dos videos homónimos en carpetas distintas pueden coexistir, guardar/upsert por identidad física de ruta, sincronización por `ruta_normalizada`, reutilización FFprobe/metadata por `ruta_normalizada`, copiar/mover/renombrar/lotes/panel Organización compatibles, marcadores/segmentos/derivados preservan asociaciones mediante `video_id`. Solo en este punto se habilitan homónimos.

**B8.4 — Regresión y cierre**
Migración de DB existente, homónimos, cache, miniaturas/previews, FFprobe, sincronización, copiar/mover/renombrar/lotes/drag&drop, marcadores, segmentos, derivados, `AUTOINCREMENT`, validación real, documentación de cierre. La reconciliación automática de movimientos/renombres realizados **externamente** en Explorer **no forma parte de B8** (fingerprint/hash futuro evaluable, no necesario para T09).

## Beta 9 — EXPLORACIÓN VISUAL AVANZADA

**Objetivo:** mejorar directamente la función principal: identificar y explorar visualmente videos mediante previews.

* **P01** — tarjetas expandidas con muchas más previews.
* **P02** — gestión de expansión: qué tarjetas quedan abiertas/fijadas y cuáles pueden autocolapsar.
* **P03** — distintos modos de expansión/inspección.
* **P04** — mejor navegación entre muchas previews.
* **P05** — tres modalidades de muchas previews: todas + scroll; cantidad reducida sin scroll; todas ajustadas automáticamente al ancho.
* **P06** — actualización automática de previews después de generación.
* **P07** — corregir flicker de vista ampliada/hover.
* **P08** — activar/desactivar ampliación por hover, verificando primero lo ya implementado.
* **P09** — alineación horizontal uniforme de previews/información; ancho estable para información y elipsis.
* **P18** — mejorar ubicación del resumen de marcadores/segmentos cuando la tarjeta está colapsada.
* **P23** — verificar/corregir doble clic en preview temporal para abrir exactamente en el timestamp correspondiente.

**Requisito técnico Beta 9:** `T04 — RAM/QPixmap`. Antes de aprobar muchas previews y múltiples tarjetas expandidas: medir RAM, pixmaps, widgets, fluidez y notebook objetivo. No asumir que la retención actual es problemática sin medición, pero no permitir expansión masiva sin validación.

## Beta 10 — VISTAS, NAVEGACIÓN Y ORGANIZACIÓN PERSONAL

**Objetivo:** reorganizar cómo se navega y trabaja con grandes colecciones.

* **P10** — modos de vista: completa, compacta, detalle, fila/lista pequeña.
* **P11** — conservar selección, posición, scroll y contexto al cambiar de vista.
* **P22** — rediseño estructural de botones, comandos, configuraciones, solapas/barra superior. *Justificación: no rediseñar comandos antes de conocer las nuevas vistas; Beta 10 permite reorganizar una sola vez con los nuevos modos ya definidos.*
* **P12** — carpetas favoritas.
* **P13** — videos recientes.
* **P14** — videos pendientes / para revisar.
* **P24** — eliminar/reducir flashes o ventanas de consola/Python durante cargas y reescaneos; reproducir y diagnosticar antes de corregir.
* **T08** — filtrado del catálogo desde el árbol.
* **T07** — cancelación de escaneo.
* **T05** — revisar persistencia/semántica del estado de carpetas escaneadas si aporta valor al nuevo modelo de navegación.

## Beta 11 — RELACIONES Y SEGMENTOS MULTIVIDEO

**Objetivo:** trabajo cruzado entre múltiples videos una vez resuelta la identidad multicarpeta en Beta 8.

* **P15** — videos relacionados / agrupaciones.
* **P16** — recordar modo de creación de segmento.
* **P17** — recordar color de segmento seleccionado.
* **P19** — visualización conjunta de segmentos de varios videos.
* **P20** — reproducción de segmentos multivideo por color/categoría.
* **P21** — unir/exportar segmentos provenientes de distintos videos. **P21 debe considerar explícitamente compatibilidad técnica:** codec, resolución, FPS, timebase, audio, posibilidad de stream-copy, necesidad eventual de re-encode. No convertir esto en editor timeline tradicional.

## Deuda técnica transversal

Mantener registrada como deuda conocida, **NO convertirla automáticamente en una beta comprometida:**

* **T01** — crecimiento acumulativo de cache/miniaturas.
* **T02** — reutilización de metadata sin hash de contenido. Hash/fingerprint puede ser relevante más adelante para reconciliar movimientos externos, no para resolver T09.
* **T06** — duplicación de helpers/infraestructura de tests.
* **T11** — tests históricos potencialmente no aislados.
* **T12** — fallo transitorio no reproducido.
* **T15** — coexistencia FFmpeg 8.1.1 / 9.0 mientras no produzca fallo real.

`T04` pasa a requisito explícito de Beta 9. `T03`/`T16` pasan al alcance Beta 8. `T05`/`T07`/`T08` pasan a Beta 10 según lo anterior. `T09` es el núcleo técnico de Beta 8.

## Futuro / BACKLOG — no comprometido

Lo no listado arriba permanece en `BACKLOG.md` como **quizá**: selección inteligente de fotogramas, evitar negros/fundidos/créditos automáticamente, elección manual/fijación de previews si no está explícitamente comprometida, detección automática de archivos movidos externamente, detección de duplicados, organización automática, IA/OCR/rostros/objetos, plugins/extensiones, paneles avanzados, ideas no priorizadas. Ver `BACKLOG.md` reconciliado (sin duplicar lo ya promovido a ROADMAP).

## Beta 8 — progreso

- **B8.1 — Preparación de identidad — COMPLETADA** `d43c1b8e9c38d132c346933967e8e8bac7fdae9f` (2026-08-23): `ruta_normalizada` + `UNIQUE(ruta_normalizada)` + dual-write.
- **B8.2 — Cache por video_id — COMPLETADA** `33da65066867026d9a72bb333216bfd9fdc4b626` (2026-08-24): cache normal `v<id>`, migración legacy por copia.
- **B8.3 — Cutover de identidad — COMPLETADA** `e4104ae53cf205811e57e582350733552aaa8740` (2026-08-24): elimina `UNIQUE(nombre)`, `UNIQUE(ruta_normalizada)` vigente, homónimos `AAAA.mp4` en `A/B` con `video_id` distinto, `ruta_normalizada` única, `nombre` no único.
- **B8.4 — Regresión y cierre — COMPLETADA** `97cb2f7f30853ed3a80ac310b7112cac80440158` (2026-08-24): migración DB, navegación `MADRE/A/B` sin `shrink` ancestro, descarte lecturas obsoletas por generación, `preparar_registros_basicos` `basename`, validación humana `MADRE→A→MADRE→B→MADRE` aprobada.

**Beta 8 — CERRADA FUNCIONALMENTE** `beta8` HEAD técnico `97cb2f7` / cierre documental `38fbc88`. Rama de versión `beta8`, tag `v8.0-beta`, publicación GitHub mediante `beta8` + `v8.0-beta` (validación humana aprobada).

## Próximo paso exacto

**Beta 9 — Exploración visual avanzada** (P01–P09, P18, P23, T04). `beta8` cerrada, sin pendientes de identidad/cache.

## Criterio

Las funcionalidades pasan de este documento o de `BACKLOG.md` al desarrollo solo cuando existe una etapa aprobada para implementarlas. `ROADMAP` no es historial; el historial es `HISTORIAL_PROYECTO.md`.
