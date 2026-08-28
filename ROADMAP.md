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

* **P01** — tarjetas expandidas con muchas más previews (Densidad como única autoridad temporal).
* **P02** — gestión de expansión: tarjetas fijadas persistentes durante la vista; múltiples fijadas; colapsar manualmente desfija.
* **P03** — distintos modos de expansión/inspección — vistas Dinámica, Tira, Reducida y Ajustada.
* **P04** — mejor navegación entre muchas previews (Tira virtualizada horizontal con anotaciones temporales y marcadores/segmentos).
* **P05** — tres modalidades: Tira (todas + scroll virtualizado), Reducida (cantidad reducida sin scroll propio), Ajustada (todas ajustadas al ancho en grilla responsive virtualizada/acotada).
* **P06** — actualización automática de previews después de generación (autorepaint/retries acotados; B9.9 corrige pending agotado y stale por `video_id+version+request_id`).
* **P07** — corregir flicker de vista ampliada/hover.
* **P08** — hover ampliado desactivable con sentinel `0` persistente (`FACTOR_VISTA_AMPLIADA_DESACTIVADO`).
* **P09** — alineación horizontal uniforme; columna de datos estable con elipsis.
* **P18** — reubicación de barra resumen B6.4 sobre miniaturas cuando colapsada (solo reubicación, sin reestructuración).
* **P23** — doble clic temporal exacto en Tira/Reducida/Ajustada.

**Requisito técnico Beta 9:** `T04 — RAM/QPixmap` — **diagnóstico base completado en B9.1 (PC de desarrollo)**: riesgo caracterizado vía medición real (`WorkingSet64`/`PrivateMemorySize64`, 7 previews `512×288`, 1 expandida, 10 ciclos sin crecimiento acumulativo observado, cambio carpeta/recarga por flujo real, modelo `3P+2+2D`); validación en notebook sigue pendiente; virtualización implementada en Tira/Ajustada (B9.3/B9.5).

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
* **T02** — reutilización de metadata sin hash de contenido (`mtime` sin hash). Hash/fingerprint puede ser relevante más adelante para reconciliar movimientos externos, no para resolver T09.
* **T06** — duplicación de helpers/infraestructura de tests (helpers de tests duplicados).
* **T11** — tests históricos potencialmente no aislados / warnings `QMouseEvent`/`disconnect` no bloqueantes.
* **T12** — fallo transitorio no reproducido (incl. `prueba_doble_clic.py` T10/T12/T13/T14 histórica).
* **T15** — coexistencia FFmpeg 8.1.1 / 9.0 mientras no produzca fallo real.
* **Deudas Beta 9 aceptadas no bloqueantes:** `prueba_doble_clic.py` T10/T12/T13/T14 (histórica), `prueba_pulido_ancho_layout.py` T08, `prueba_carga_visual_b462.py` P02/P06 histórica ajena a P06; Vista Ajustada Densidad 120/200 pocas miniaturas blancas permanentes (validación humana); rendimiento densidad alta demora por FFmpeg secuencial por muestra faltante (costo dominante, sin reducir N); warnings `QMouseEvent`/`disconnect`.

`T04` pasa a requisito explícito de Beta 9. `T03`/`T16` pasan al alcance Beta 8. `T05`/`T07`/`T08` pasan a Beta 10 según lo anterior. `T09` es el núcleo técnico de Beta 8.

## Futuro / BACKLOG — no comprometido

Lo no listado arriba permanece en `BACKLOG.md` como **quizá**: selección inteligente de fotogramas, evitar negros/fundidos/créditos automáticamente, elección manual/fijación de previews si no está explícitamente comprometida, detección automática de archivos movidos externamente, detección de duplicados, organización automática, IA/OCR/rostros/objetos, plugins/extensiones, paneles avanzados, ideas no priorizadas. Ver `BACKLOG.md` reconciliado (sin duplicar lo ya promovido a ROADMAP).

## Beta 8 — progreso

- **B8.1 — Preparación de identidad — COMPLETADA** `d43c1b8e9c38d132c346933967e8e8bac7fdae9f` (2026-08-23): `ruta_normalizada` + `UNIQUE(ruta_normalizada)` + dual-write.
- **B8.2 — Cache por video_id — COMPLETADA** `33da65066867026d9a72bb333216bfd9fdc4b626` (2026-08-24): cache normal `v<id>`, migración legacy por copia.
- **B8.3 — Cutover de identidad — COMPLETADA** `e4104ae53cf205811e57e582350733552aaa8740` (2026-08-24): elimina `UNIQUE(nombre)`, `UNIQUE(ruta_normalizada)` vigente, homónimos `AAAA.mp4` en `A/B` con `video_id` distinto, `ruta_normalizada` única, `nombre` no único.
- **B8.4 — Regresión y cierre — COMPLETADA** `97cb2f7f30853ed3a80ac310b7112cac80440158` (2026-08-24): migración DB, navegación `MADRE/A/B` sin `shrink` ancestro, descarte lecturas obsoletas por generación, `preparar_registros_basicos` `basename`, validación humana `MADRE→A→MADRE→B→MADRE` aprobada.

**Beta 8 — CERRADA Y PUBLICADA** `beta8`/`origin/beta8` y `v8.0-beta` → `e851c7c2be1c3d12aac8ccb633e1aaecea2b7d3d` (HEAD `B8 Preparar identidad de publicación`; técnico `97cb2f7`, documental `38fbc88`; validación humana aprobada).

## Beta 9 — progreso (cerrada y publicada `v9.0-beta`)

- **B9.0 — Apertura — 2026-08-24:** `8fe1054` rama `beta9` creada exactamente desde `v8.0-beta`/`e851c7c2be1c3d12aac8ccb633e1aaecea2b7d3d` (NO desde `main` `d04a712`). Sin push/tag/Release.
- **B9.1 — Diagnóstico T04 — `76f3777048bb44e76b40ccf61ab07b605e914d64`:** medición real PC desarrollo (`WorkingSet64`/`PrivateMemorySize64`, 7 previews `512×288`, 1 expandida, 10 ciclos sin crecimiento acumulativo, modelo `3P+2+2D`); notebook pendiente.
- **B9.2 — Gestión expansión fijada — `d81fc93fe5f12d4ab3367a8fefb459851d77e67a`:** tarjetas fijadas persistentes, múltiples fijadas, colapsar desfija.
- **B9.3 — Tira virtual — `431f1fa8f142e6d776713a6cfe7c17ab3645945d`:** Tira virtualizada horizontal, anotaciones temporales, marcadores/segmentos; Densidad `Auto/15/30/60/120/200` autoridad temporal.
- **B9.4 — Reducida — `4d475cefd6ef974c3baa57e65ecb4c7d962d9971`:** modalidad Reducida sin scroll horizontal propio.
- **B9.5 — Ajustada — `4dcaae0e3400eaa065f115cf1ff70df649cfdb3b`:** Vista Ajustada en grilla.
- **B9.6 — Geometría responsive — `24bd7a9e86d92925e57d71d6f94b458f3d1017fa`:** grilla responsive.
- **B9.7.1 — Doble clic temporal — `8c1ea0c6e5cec3c6bdf3cf9808a6ba959c30a790`:** doble clic exacto Tira/Reducida/Ajustada.
- **B9.7.2 — Alineación/elipsis — `4de180d43d1dfd4db819582cfaf56fea4325eb43`:** columna datos estable con elipsis.
- **B9.7.3 — Autorepaint Ajustada — `2e2335b795ce4d10ee55d600fd468bddecf8b825`:** actualización automática P06.
- **B9.8 P18 — `4909020e11e52121d0a2a13307964bed7247cbde`:** reubicación barra resumen B6.4 sobre miniaturas (simplificado, sin reestructuración).
- **Hover desactivable — `41216a10edfed416d32df7a39e7eaccd77b9b5ae`:** sentinel `0` persistente (`FACTOR_VISTA_AMPLIADA_DESACTIVADO`).
- **B9.9 — Convergencia visual — `03fd856c9e43ee092ce09d87bad8791292e19eb3`:** corrige pending agotado (`retry>=3`) y stale por `video_id+version+request_id`; estabiliza regresiones.

**Beta 9 — CERRADA Y PUBLICADA** `beta9`/`origin/beta9` + tag anotado `v9.0-beta` (último commit técnico B9.9 `03fd856` previo al cierre; hover `41216a1`; identidad `Beta 9 - B9.9`); sin GitHub Release ni instalador público; próximo foco Beta 10.

## Próximo paso exacto

**Beta 9 — cerrada y publicada `v9.0-beta`.** Próximo: **Beta 10 — Vistas, navegación y organización personal** (P10/P11/P22/P12–P14/P24/T07/T08/T05).

## Criterio

Las funcionalidades pasan de este documento o de `BACKLOG.md` al desarrollo solo cuando existe una etapa aprobada para implementarlas. `ROADMAP` no es historial; el historial es `HISTORIAL_PROYECTO.md`.
