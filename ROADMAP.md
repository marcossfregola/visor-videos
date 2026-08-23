# ROADMAP — Visor de Videos

Trabajo futuro **decidido** y priorizado. Separacion obligatoria: `ROADMAP = decidido`, `BACKLOG = quiza`. Las ideas tentativas viven en `BACKLOG.md`; lo ya implementado queda registrado en `HISTORIAL_PROYECTO.md` y en `STATUS.md`.

## Estado post-Beta 7

**Beta 7 — "Organización y operaciones de archivos" (B7.13) cerrada y publicada.** Commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` (`B7 Cerrar Beta 7 B7.13`); tag `v7.0-beta` → `f9976d3`; rama `beta7` publicada (reconciliación posterior `97e6fcf`); Release `v7.0-beta` prerelease PUBLIC; `main` reconciliada mediante este cierre (V1.3 + Beta 7). Capacidades entregadas: exploración temporal, marcadores/segmentos, clasificación por color, exportación y trazabilidad de derivados, organización de archivos (renombrado individual/masivo, mover/copiar/eliminar por lote, crear carpetas, modo Organización/Explorer con doble panel y drag & drop). Validación específica del instalador Beta 7 **PENDIENTE**. Historial completo en `HISTORIAL_PROYECTO.md` (119).

**Beta 8 todavía no está definida ni priorizada.** La planificación de Beta 8 queda pendiente de consolidación de mejoras, auditorías externas y priorización explícita. No se compromete funcionalidad en este documento hasta esa planificación.

## Prioridad inmediata

1. **Auditoría final del estado reconciliado** (`main` reconciliada mediante este cierre con `beta7` preservando estructura V1.3 y producto Beta7).
2. **Validación específica del instalador Beta 7** — prueba estática de contrato `python prueba_instalador.py` (8/8, no instala) + validación real del artefacto `Distribucion/Beta7/VisorVideos_Beta7_Setup.exe` (instalación/desinstalación/reinstalación preservando `biblioteca.db`/`configuracion.json`/`miniaturas` en entorno aislado) — **PENDIENTE** como etapa posterior.
3. **Consolidación de mejoras + auditorías externas** (deuda no bloqueante y pendientes técnicos de `STATUS.md`/`ARCHITECTURE.md`).
4. **Definición y priorización de Beta 8** — todavía no definida ni comprometida; recién después de 1–3.

## Pendientes técnicos comprometidos (post-Beta 7)

Herencia de deuda no bloqueante registrada en `STATUS.md`/`ARCHITECTURE.md`:

- Deduplicación completa de nombres repetidos en el plan de sincronización (parcialmente abordado).
- Cancelación del escaneo (diferida desde Beta 3).
- Filtrado del catálogo desde el árbol (Etapa 2.10 diferida).
- Optimización de rendimiento con colecciones grandes (B4.5/B4.6 mejoraron carga, queda deuda RAM pixmaps).
- Validación del instalador Beta 7 (pendiente).

## Criterio

Las funcionalidades pasan de este documento o de `BACKLOG.md` al desarrollo solo cuando existe una etapa aprobada para implementarlas. `ROADMAP` no es historial; el historial es `HISTORIAL_PROYECTO.md`.
