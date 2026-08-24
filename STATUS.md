# STATUS — Visor de Videos

## Fase actual

**Beta 8 — EN CURSO (beta8 local, no publicada).**

- B8.1 cerrada localmente: `d43c1b8e9c38d132c346933967e8e8bac7fdae9f` (2026-08-23).
- B8.2 cerrada localmente: `33da65066867026d9a72bb333216bfd9fdc4b626` (2026-08-24).
- Rama `beta8` HEAD `33da65066867026d9a72bb333216bfd9fdc4b626`; parent B8.1 `d43c1b8e9c38d132c346933967e8e8bac7fdae9f`.
- `beta8` **NO publicada**: sin `origin/beta8`, sin tag `v8.0-beta` ni Release B8.
- Próximo paso exacto: **B8.3 — Cutover de identidad** (elimina `UNIQUE(nombre)`, habilita homónimos).
- Posterior: **B8.4 — Regresión y cierre**.
- `T09` (identidad `UNIQUE(nombre)`) **sigue incompleto hasta B8.3**; B8.1/B8.2 solo prepararon identidad y cache (no habilitan homónimos).
- Baseline publicado estable sigue `v7.0-beta` / `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` y `main` documental `d04a7124dcb7741d16c015d88909d12851c58289`.
- Validación instalador Beta 7: contrato 8/8 y build/artefacto Beta 7 aprobados; ciclo instalación/desinstalación no ejecutado por seguridad, no bloquea.

Para el historial completo ver `HISTORIAL_PROYECTO.md` (123/122/121).

## Último baseline aprobado

- Tag `v7.0-beta` sobre `f9976d3` (cierre funcional Beta 7).
- Rama `beta7` `97e6fcf` incluye B7.0–B7.13 completas y reconciliación post-publicación.
- `main` reconciliada documental `d04a712` como base de esta rama `beta8` local.
- `main` matriz documental definitiva `PROJECT/STATUS/ARCHITECTURE/ENVIRONMENT/RULES/ROADMAP/BACKLOG/HISTORIAL/EMPACADO/METODOLOGIA` (V1.3).

## Estado funcional (Beta 7 + avances B8.1/B8.2 locales)

- Aplicación abre sin crash; catálogo SQLite con metadatos FFprobe, miniaturas/previews FFmpeg, exploración temporal densa, marcadores/segmentos persistentes y clasificación por color (Beta 7).
- Centro de Navegación, operaciones de organización, exportación y trazabilidad de derivados (Beta 7) operativos.
- **B8.1 (local)**: tabla `videos` con `ruta_normalizada` (`rutas.normalizar_ruta_clave` = `abspath+normpath+normcase+strip`) + `UNIQUE(ruta_normalizada)`; mantiene `UNIQUE(nombre)` transicional; `guardar_video`/`guardar_videos` dual-write `ruta`+`ruta_normalizada` y retorno por `ruta_normalizada`/`video_id`; pipeline guarda antes de miniaturas; `cantidad_miniaturas` se actualiza puntualmente por `video_id`.
- **B8.2 (local)**: cache normal por `video_id` (`v<video_id>_<NN>.jpg` y `v<video_id>_preview_<NN>.jpg` vía `ruta_miniatura_id`/`ruta_preview_id`); migración legacy no destructiva por copia (`migrar_cache_legacy_a_id`) sin borrar legacy, sin fallback ambiguo por nombre; renombrar/mover dejan de depender del nombre para cache normal; `TareaMiniaturasPorId`/`TareaPreviewsPorId`/`TareaMigrarCacheLegacy` y `asegurar_miniaturas_por_id`/`generar_previews_faltantes_por_id` operativos; UI resuelve cache por id fuera de UI.
- `UNIQUE(nombre)` todavía vigente; homónimos aún no habilitados (requiere B8.3).
- Cache densa `miniaturas/exploracion` (B4.x) permanece separada por `video_id`/fingerprint, no afectada por B8.2.
- Suites B8.1/B8.2 aprobadas y validación manual real previa al commit (evidencia local); B8 sin push/tag/release.

## Trabajo pendiente real

- **B8.3 — Cutover de identidad** — próximo paso inmediato (eliminar `UNIQUE(nombre)`, `UNIQUE` por `ruta_normalizada`, homónimos, upsert por ruta, sincronización y reutilización por ruta normalizada).
- **B8.4 — Regresión y cierre** (migración DB, homónimos, cache, FFprobe, sincronización, lote/drag&drop, marcadores/segmentos/derivados).
- `T09` núcleo técnico de Beta 8 incompleto hasta B8.3.
- Beta 8 definida y priorizada (B8.1–B8.4), B8.1/B8.2 cerradas localmente, sin publicación.

## Deuda técnica conocida

- Crecimiento y duplicación de infraestructura entre suites de prueba (heredado).
- Estado de "escaneada" por sesión vive en memoria y se pierde al reiniciar.
- Crecimiento acumulativo de miniaturas (nuevas ranuras sin limpieza; requiere autorización).
- Criterio de reutilización por `mtime` sin hash de integridad.
- Coincidencia de miniaturas por prefijo (`startswith`) en cache legacy (mitigada por B8.2 al pasar a `video_id` para cache normal).

## Problemas conocidos

- Tests históricos con datos reales: aislar de `biblioteca.db`/`configuracion.json` (`RULES.md` 7).
- Fallo transitorio no reproducido de `prueba_copiar_rutas_seleccionados` (ya documentado).
- Coexistencia FFmpeg 8.1.1 (efectivo por PATH) / 9.0 en ProjectStorage — ambas funcionan.

## Entorno pendiente relacionado

- No requiere instalar dependencias para consolidación/auditorías/definición Beta 8.
- Instalador Beta 7: build/artefacto aprobado; validación real no ejecutada por seguridad y no bloquea (ver Fase actual).

## Próximos focos

1. **B8.3 — Cutover de identidad** — próximo paso exacto.
2. **B8.4 — Regresión y cierre**.
3. Posterior: Beta 9–11 según `ROADMAP.md`.
