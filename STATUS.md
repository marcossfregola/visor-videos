# STATUS — Visor de Videos

## Fase actual

**Beta 7 — B7.13 cerrada y publicada.**

- Commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` (`B7 Cerrar Beta 7 B7.13`).
- Tag anotado `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3` (cierre funcional inmutable).
- Rama `beta7` conserva su historia y reconciliación documental posterior `97e6fcf1489c3999fbf1c82222ce584862970f5b` (`B7 Reconciliar documentación post-publicación`).
- `main` — rama vigente/canónica del estado actual del proyecto; este merge establece `main` como autoridad al incorporar la evolución completa hasta Beta 7 y la arquitectura documental V1.3 (merge `918cf67` ← `97e6fcf`, preservando ambas historias; producto funcional equivalente a Beta 7 salvo limpiezas whitespace).
- GitHub Release `v7.0-beta` prerelease publicada sin instalador público Beta 7.
- Repositorio **PUBLIC**, default branch `main`.
- Validación específica del instalador Beta 7 **PENDIENTE**: prueba estática de contrato `python prueba_instalador.py` (8/8 verifica `instalador.iss`/`rutas.py`, no instala artefacto) + validación real del artefacto `Distribucion/Beta7/VisorVideos_Beta7_Setup.exe` (instalación/desinstalación/reinstalación preservando datos, en entorno aislado) — pendiente y separada.
- Beta 8 todavía no definida.

Para el historial completo ver `HISTORIAL_PROYECTO.md` (119).

## Último baseline aprobado

- Tag `v7.0-beta` sobre `f9976d3` (cierre funcional Beta 7).
- Rama `beta7` `97e6fcf` incluye B7.0–B7.13 completas y la reconciliación post-publicación que separa commit/tag inmutable de HEAD de rama.
- `main` reconciliada mediante este merge: integra `main` previo `918cf67` (estructura V1.3) y `beta7` `97e6fcf` preservando ambas historias; matriz documental definitiva `PROJECT/STATUS/ARCHITECTURE/ENVIRONMENT/RULES/ROADMAP/BACKLOG/HISTORIAL/EMPACADO/METODOLOGIA`.

## Estado funcional (Beta 7)

- Aplicación abre sin crash; catálogo SQLite con metadatos FFprobe, miniaturas/previews FFmpeg, exploración temporal densa, marcadores/segmentos persistentes y clasificación por color.
- Centro de Navegación: árbol Este equipo, expansión diferida, selección, persistencia, escaneo automático y multicarpeta.
- Operaciones de organización: renombrado individual/masivo, mover/copiar/eliminar por lote, crear carpetas, modo Organización/Explorer con doble panel y drag & drop interno prevalidado.
- Exportación: un segmento, lote y unión con trazabilidad de derivados (`videos_derivados`).
- Suites: `prueba_integracion_b612` 14/14, `prueba_reescaneo_preserva_metadatos_b612` 3/3, `prueba_derivados_b611` 15/15, `prueba_version_build` 3/3 (Beta 7 - B7.13) y amplia suite previa en verde. Estado técnico verificado prevalece.

## Trabajo pendiente real

- **Auditoría final** del `main` reconciliado (Git/GitHub/documentación).
- **Validación del instalador Beta 7**: instalación/desinstalación/reinstalación preservando `biblioteca.db`/`configuracion.json`/`miniaturas`.
- **Consolidación de mejoras + auditorías externas** (deuda no bloqueante y pendientes técnicos).
- **Definición y priorización de Beta 8** — alcance todavía no definido (queda pendiente de la consolidación).
- Deuda no bloqueante: crecimiento de miniaturas, reutilización por `mtime` sin hash, retención de pixmaps — ver `ARCHITECTURE.md`.

## Deuda técnica conocida

- Crecimiento y duplicación de infraestructura entre suites de prueba (heredado).
- Estado de "escaneada" por sesión vive en memoria y se pierde al reiniciar.
- Crecimiento acumulativo de miniaturas (nuevas ranuras sin limpieza; requiere autorización).
- Criterio de reutilización por `mtime` sin hash de integridad.
- Coincidencia de miniaturas por prefijo (`startswith`).

## Problemas conocidos

- Tests históricos con datos reales: aislar de `biblioteca.db`/`configuracion.json` (`RULES.md` 7).
- Fallo transitorio no reproducido de `prueba_copiar_rutas_seleccionados` (ya documentado).
- Coexistencia FFmpeg 8.1.1 (efectivo por PATH) / 9.0 en ProjectStorage — ambas funcionan.

## Entorno pendiente relacionado

- Validación instalador Beta 7 pendiente (no bloquea merge).
- No requiere instalar dependencias para reconciliación documental.

## Próximos focos

1. Auditoría final Git/GitHub/documentación del `main` reconciliado.
2. Validación específica del instalador Beta 7 (etapa específica).
3. Consolidación de mejoras + auditorías externas.
4. Definición y priorización de Beta 8.
