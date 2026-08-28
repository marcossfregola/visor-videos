# STATUS — Visor de Videos

## Fase actual

**Beta 9 — CERRADA Y PUBLICADA `v9.0-beta` (rama `beta9`/`origin/beta9`; último commit técnico B9.9 `03fd856c9e43ee092ce09d87bad8791292e19eb3` previo al cierre). Identidad `Beta 9 - B9.9` publicada vía tag anotado `v9.0-beta`. Sin GitHub Release ni instalador público. Próximo foco Beta 10.**

- Beta 8 **cerrada funcional y documentalmente**: cierre técnico B8.4 `97cb2f7f30853ed3a80ac310b7112cac80440158` (parent B8.3 `e4104ae53cf205811e57e582350733552aaa8740`), cierre documental `38fbc88e30c892b75b3bf66d752c49ba4c057c33` (2026-08-24).
- Publicación GitHub Beta 8: rama `beta8` + tag anotado `v8.0-beta` → `e851c7c2be1c3d12aac8ccb633e1aaecea2b7d3d` (`B8 Preparar identidad de publicación`; sin GitHub Release ni instalador público). `origin/beta8` y `v8.0-beta^{commit}` alineados en `e851c7c`.
- **Beta 9 — cerrada y publicada** `beta9`/`origin/beta9` + tag anotado `v9.0-beta` (último commit técnico B9.9 `03fd856` previo al cierre):
  - B9.0 `8fe1054` apertura desde `v8.0-beta`/`e851c7c` (NO desde `main`).
  - B9.1 `76f3777048bb44e76b40ccf61ab07b605e914d64` diagnóstico T04 (PC desarrollo; notebook pendiente).
  - B9.2 `d81fc93fe5f12d4ab3367a8fefb459851d77e67a` tarjetas fijadas persistentes (múltiples; colapsar desfija).
  - B9.3 `431f1fa8f142e6d776713a6cfe7c17ab3645945d` Tira virtualizada horizontal + anotaciones temporales + marcadores/segmentos + Densidad `Auto/15/30/60/120/200` autoridad temporal.
  - B9.4 `4d475cefd6ef974c3baa57e65ecb4c7d962d9971` Reducida sin scroll horizontal propio.
  - B9.5 `4dcaae0e3400eaa065f115cf1ff70df649cfdb3b` Ajustada grilla.
  - B9.6 `24bd7a9e86d92925e57d71d6f94b458f3d1017fa` geometría responsive.
  - B9.7.1 `8c1ea0c6e5cec3c6bdf3cf9808a6ba959c30a790` doble clic temporal exacto Tira/Reducida/Ajustada.
  - B9.7.2 `4de180d43d1dfd4db819582cfaf56fea4325eb43` alineación estable + elipsis columna datos.
  - B9.7.3 `2e2335b795ce4d10ee55d600fd468bddecf8b825` actualización automática previews Ajustada (P06 autorepaint/retries).
  - B9.8 P18 `4909020e11e52121d0a2a13307964bed7247cbde` reubicación barra resumen B6.4 sobre miniaturas (sin reestructuración).
  - hover desactivable `41216a10edfed416d32df7a39e7eaccd77b9b5ae` sentinel `0` persistente (`FACTOR_VISTA_AMPLIADA_DESACTIVADO`).
  - B9.9 técnico `03fd856c9e43ee092ce09d87bad8791292e19eb3` corrección convergencia visual (pending agotado `retry>=3` filtrado; stale por `video_id+version+request_id` vigente; autorepaint estable).
  - cierre documental/identidad vía `v9.0-beta` (identidad `Beta 9 - B9.9`).
- Identidad: `configuracion.py` `VERSION_PRODUCTO="Beta 9"` `BUILD_IDENTIFICADOR="B9.9"` (`TEXTO_VERSION_BUILD "Beta 9 - B9.9"`) publicada; `prueba_version_build.py` alineada; ventana `etiqueta_version` muestra esa identidad.
- Estado Git: `beta9` HEAD `v9.0-beta`/`origin/beta9`, working tree con solo `?? videos_prueba/8/` y `?? videos_prueba/9/`, staged vacío, stash vacío; remoto `origin` con `beta9` y tag `v9.0-beta`; sin GitHub Release ni instalador público.

Para el historial completo ver `HISTORIAL_PROYECTO.md` (127/126/125/124/123/122).

## Último baseline aprobado

- Tag `v8.0-beta` sobre `e851c7c` (cierre Beta 8; `B8 Preparar identidad de publicación`; commit documental `38fbc88`, técnico `97cb2f7`).
- Rama `beta8` publicada en `origin/beta8` alineada con `v8.0-beta^{commit}` en `e851c7c2be1c3d12aac8ccb633e1aaecea2b7d3d`.
- Tag previo `v7.0-beta` sobre `f9976d3` (cierre funcional Beta 7) conservado como referencia histórica.
- Rama `beta7` `97e6fcf` incluye B7.0–B7.13 completas y reconciliación post-publicación.
- `main` `d04a7124dcb7741d16c015d88909d12851c58289` matriz documental V1.3 (divergida de `beta8`/`beta9`; NO usada como base de Beta 9).
- `beta9` nace exactamente de `v8.0-beta`/`e851c7c` (NO de `main`); HEAD publicado `v9.0-beta`/`origin/beta9` (último técnico `03fd856` previo al cierre).

## Estado funcional (Beta 9 cerrada y publicada)

- Aplicación abre sin crash; catálogo SQLite con metadatos FFprobe, miniaturas/previews FFmpeg, exploración temporal densa, marcadores/segmentos persistentes y clasificación por color (Beta 8 base).
- Centro de Navegación, operaciones de organización, exportación y trazabilidad de derivados (Beta 7/8) operativos.
- **B8.1**: tabla `videos` con `ruta_normalizada` (`rutas.normalizar_ruta_clave` = `abspath+normpath+normcase+strip`) + `UNIQUE(ruta_normalizada)`; `guardar_videos` dual-write y retorno por `ruta_normalizada`/`video_id`; pipeline guarda antes de miniaturas.
- **B8.2**: cache normal por `video_id` (`v<video_id>_<NN>.jpg` vía `ruta_miniatura_id`/`ruta_preview_id`), migración legacy no destructiva por copia, `TareaMiniaturasPorId`/`TareaPreviewsPorId` operativos.
- **B8.3**: `UNIQUE(nombre)` eliminado, `UNIQUE(ruta_normalizada)` vigente, homónimos `AAAA.mp4` en `A`/`B` coexisten con `video_id` distinto y `ruta_normalizada` distinta, `nombre` no único, `video_id` autoridad lógica, `ruta_normalizada` autoridad física, `AUTOINCREMENT` preservado, `guardar/upsert` por `ruta_normalizada`, sincronización y reutilización FFprobe por `ruta_normalizada`, cache canónica `v<id>` independiente.
- **B8.4**: migración DB existente cerrada, navegación `MADRE/A/B` sin `shrink` ancestro, descarte lecturas obsoletas por `generación`, `preparar_registros_basicos` con `basename` para `nombre`, `escanear_videos` recursivo corrige `A\AAAA.mp4` → `AAAA.mp4`, regresión 149 pruebas y validación humana `MADRE→A→MADRE→B→MADRE` aprobadas; HEAD técnico `97cb2f7`, cierre documental `38fbc88`.
- **B9.2**: tarjetas fijadas persistentes durante la vista; múltiples fijadas simultáneamente; colapsar manualmente desfija (corrige autocollapse).
- **B9.3**: Densidad `Auto/15/30/60/120/200` única autoridad temporal; Tira virtualizada horizontal, anotaciones temporales, marcadores/segmentos en tira.
- **B9.4**: Reducida sin scroll horizontal propio (cantidad reducida).
- **B9.5/6**: Ajustada en grilla responsive, virtualizada/acotada.
- **B9.7.1**: doble clic temporal exacto en Tira/Reducida/Ajustada.
- **B9.7.2**: columna de datos estable con elipsis.
- **B9.7.3/B9.9**: P06 autorepaint/retries acotados; B9.9 corrige pending agotado (`retry>=3`) y stale por `video_id+version+request_id`.
- **B9.8 P18**: solo reubicación de barra resumen B6.4 sobre miniaturas, sin reestructuración.
- **Hover**: ampliación puede desactivarse con sentinel `0` persistente (`FACTOR_VISTA_AMPLIADA_DESACTIVADO`, `41216a1`).

## Trabajo pendiente real

- **Beta 9 — cerrada y publicada** (sin GitHub Release ni instalador público; deudas B9 vigentes).
- **Beta 10/11** según `ROADMAP.md` (sin iniciar; Beta 10 próximo foco).

## Deuda técnica conocida

- **T01** crecimiento acumulativo de cache/miniaturas (nuevas ranuras sin limpieza; requiere autorización).
- **T02** reutilización metadata por `mtime` sin hash de integridad.
- **T06** duplicación de helpers/infraestructura de tests (`prueba_doble_clic.py` y otros duplican helpers) — deuda histórica.
- **T11** tests potencialmente no aislados; warnings `QMouseEvent`/`disconnect` no bloqueantes.
- **T15** coexistencia FFmpeg 8.1.1 (efectivo por PATH) / 9.0 en ProjectStorage — ambas funcionan; vigente si no produce fallo.
- **Deuda histórica** `prueba_doble_clic.py` T10/T12/T13/T14 (infra tests).
- **Deuda histórica** `prueba_pulido_ancho_layout.py` T08 (layout).
- **Deuda histórica** `prueba_carga_visual_b462.py` P02/P06 histórica ajena a P06 Beta 9.
- Vista Ajustada Densidad 120/200: validación humana detecta unas pocas miniaturas blancas permanentes; aceptado como deuda futura no bloqueante (registro B9.9).
- Rendimiento: densidad alta puede demorar bastante; generación FFmpeg secuencial por muestra faltante es costo dominante; optimización futura sin reducir N.
- Warnings PySide6 `QMouseEvent`/`disconnect` no bloqueantes (ya citado T11).

## Problemas conocidos

- Tests históricos con datos reales: aislar de `biblioteca.db`/`configuracion.json` (`RULES.md` 7).
- Fallo transitorio no reproducido de `prueba_copiar_rutas_seleccionados` (ya documentado; B9.9 añade cobertura).
- Coexistencia FFmpeg 8.1.1 (efectivo por PATH) / 9.0 — ambas funcionan (T15).
- Vista Ajustada 120/200: pocas miniaturas blancas permanentes (deuda aceptada).
- Densidad alta: demora por sparsificación FFmpeg secuencial (no bloqueante).

## Entorno pendiente relacionado

- No requiere instalar dependencias para consolidación/auditorías.
- Instalador Beta 7: build/artefacto aprobado; validación real no ejecutada por seguridad y no bloquea. Beta 9 no publica instalador/Release (decisión alcance personal).

## Próximos focos

1. **Beta 9 — cerrada y publicada `v9.0-beta` (completada).**
2. **Beta 10 — Vistas, navegación y organización personal (próximo foco).**
3. **Beta 11 — Relaciones y segmentos multivideo.**
