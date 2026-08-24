# STATUS — Visor de Videos

## Fase actual

**Beta 8 — CERRADA FUNCIONALMENTE (beta8 local, validación humana aprobada).**

- B8.1 cerrada localmente: `d43c1b8e9c38d132c346933967e8e8bac7fdae9f` (2026-08-23).
- B8.2 cerrada localmente: `33da65066867026d9a72bb333216bfd9fdc4b626` (2026-08-24).
- B8.3 cerrada localmente: `e4104ae53cf205811e57e582350733552aaa8740` (2026-08-24).
- B8.4 cerrada localmente: `97cb2f7f30853ed3a80ac310b7112cac80440158` (2026-08-24).
- Rama `beta8` HEAD `97cb2f7f30853ed3a80ac310b7112cac80440158`; parent B8.3 `e4104ae53cf205811e57e582350733552aaa8740`.
- `beta8` **NO publicada**: sin `origin/beta8`, sin tag `v8.0-beta` ni Release B8.
- Próximo paso exacto: **Beta 9 — Exploración visual avanzada** (según ROADMAP).
- `T09` (identidad `UNIQUE(nombre)`) **cerrado en B8.3** (cutover `ruta_normalizada` `UNIQUE`).
- Baseline publicado estable sigue `v7.0-beta` / `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` y `main` documental `d04a7124dcb7741d16c015d88909d12851c58289`.
- Validación humana final B8.4 aprobada: `MADRE→A→MADRE→B→MADRE` sin escanear, navegación, homónimos, operaciones y FFmpeg real verificados; **sin tag/push**.

Para el historial completo ver `HISTORIAL_PROYECTO.md` (124/123/122/121).

## Último baseline aprobado

- Tag `v7.0-beta` sobre `f9976d3` (cierre funcional Beta 7).
- Rama `beta7` `97e6fcf` incluye B7.0–B7.13 completas y reconciliación post-publicación.
- `main` reconciliada documental `d04a712` como base de esta rama `beta8` local.
- `main` matriz documental definitiva `PROJECT/STATUS/ARCHITECTURE/ENVIRONMENT/RULES/ROADMAP/BACKLOG/HISTORIAL/EMPACADO/METODOLOGIA` (V1.3).

## Estado funcional (Beta 8 cerrada)

- Aplicación abre sin crash; catálogo SQLite con metadatos FFprobe, miniaturas/previews FFmpeg, exploración temporal densa, marcadores/segmentos persistentes y clasificación por color (Beta 7).
- Centro de Navegación, operaciones de organización, exportación y trazabilidad de derivados (Beta 7) operativos.
- **B8.1**: tabla `videos` con `ruta_normalizada` (`rutas.normalizar_ruta_clave` = `abspath+normpath+normcase+strip`) + `UNIQUE(ruta_normalizada)`; `guardar_videos` dual-write y retorno por `ruta_normalizada`/`video_id`; pipeline guarda antes de miniaturas.
- **B8.2**: cache normal por `video_id` (`v<video_id>_<NN>.jpg` vía `ruta_miniatura_id`/`ruta_preview_id`), migración legacy no destructiva por copia, `TareaMiniaturasPorId`/`TareaPreviewsPorId` operativos.
- **B8.3**: `UNIQUE(nombre)` eliminado, `UNIQUE(ruta_normalizada)` vigente, homónimos `AAAA.mp4` en `A`/`B` coexisten con `video_id` distinto y `ruta_normalizada` distinta, `nombre` no único, `video_id` autoridad lógica, `ruta_normalizada` autoridad física, `AUTOINCREMENT` preservado, `guardar/upsert` por `ruta_normalizada`, sincronización y reutilización FFprobe por `ruta_normalizada`, cache canónica `v<id>` independiente.
- **B8.4**: migración DB existente cerrada, navegación `MADRE/A/B` sin `shrink` ancestro, descarte lecturas obsoletas por `generación`, `preparar_registros_basicos` con `basename` para `nombre`, `escanear_videos` recursivo corrige `A\AAAA.mp4` → `AAAA.mp4`, regresión 149 pruebas y validación humana `MADRE→A→MADRE→B→MADRE` aprobadas; `beta8` HEAD `97cb2f7` sin publicación.
- Suites B8.1–B8.4 y B8.4A/B/C/D verificadas; `beta8` sin push/tag/release.

## Trabajo pendiente real

- **Beta 9 — Exploración visual avanzada** — próximo paso (P01–P09, P18, P23, T04).
- **Beta 10/11** según `ROADMAP.md`.
- Beta 8 cerrada, sin pendientes de identidad/cache.

## Deuda técnica conocida

- Crecimiento y duplicación de infraestructura entre suites de prueba (heredado).
- Estado de "escaneada" por sesión vive en memoria y se pierde al reiniciar.
- Crecimiento acumulativo de miniaturas (nuevas ranuras sin limpieza; requiere autorización).
- Criterio de reutilización por `mtime` sin hash de integridad.
- Coincidencia de miniaturas por prefijo (`startswith`) en cache legacy (mitigada por B8.2).

## Problemas conocidos

- Tests históricos con datos reales: aislar de `biblioteca.db`/`configuracion.json` (`RULES.md` 7).
- Fallo transitorio no reproducido de `prueba_copiar_rutas_seleccionados` (ya documentado).
- Coexistencia FFmpeg 8.1.1 (efectivo por PATH) / 9.0 en ProjectStorage — ambas funcionan.

## Entorno pendiente relacionado

- No requiere instalar dependencias para consolidación/auditorías.
- Instalador Beta 7: build/artefacto aprobado; validación real no ejecutada por seguridad y no bloquea.

## Próximos focos

1. **Beta 9 — Exploración visual avanzada**.
2. **Beta 10 — Vistas, navegación y organización personal**.
3. **Beta 11 — Relaciones y segmentos multivideo**.
