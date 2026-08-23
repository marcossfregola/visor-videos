# STATUS — Visor de Videos

## Fase actual

**Beta 7 — B7.13 cerrada y publicada.**

- Commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` (`B7 Cerrar Beta 7 B7.13`).
- Tag anotado `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3` (cierre funcional inmutable).
- Rama `beta7` conserva su historia y reconciliación documental posterior `97e6fcf1489c3999fbf1c82222ce584862970f5b` (`B7 Reconciliar documentación post-publicación`).
- `main` — rama vigente/canónica del estado actual del proyecto; este merge establece `main` como autoridad al incorporar la evolución completa hasta Beta 7 y la arquitectura documental V1.3 (merge `918cf67` ← `97e6fcf`, preservando ambas historias; producto funcional equivalente a Beta 7 salvo limpiezas whitespace).
- GitHub Release `v7.0-beta` prerelease publicada sin instalador público Beta 7.
- Repositorio **PUBLIC**, default branch `main`.
- Validación del instalador Beta 7: **contrato estático 8/8 APROBADO** (`python prueba_instalador.py` verifica `instalador.iss`/`rutas.py`); **build y artefacto Beta 7 APROBADOS** — portable `dist\VisorVideos\VisorVideos.exe` (inicia, no crash, cierre normal), DB seed `dist\VisorVideos\biblioteca.db` 61440 bytes `PRAGMA integrity_check=ok` vacía (`videos/marcadores/segmentos/derivados=0`, SHA256 `890CB0218DEE8CEBAE7A6DE88EC8E0F507CB4DD067009C926722D06E3B5EE9B3`), Setup `Distribucion/Beta7/VisorVideos_Beta7_Setup.exe` 33755374 bytes SHA256 `14A0D4D062AE44E3B4A9CD244869D866F1C9238952CF293D0A26CC25F084A471` (Inno Setup 6.7.3); **ciclo instalación/desinstalación/reinstalación NO EJECUTADO** por seguridad — preflight encontró instalación existente en `%LOCALAPPDATA%\Programs\VisorVideos` con `VisorVideos.exe`/`biblioteca.db`/`configuracion.json`/`unins000.exe` — detenido para no tocar datos del usuario. No es deuda bloqueante ni trabajo pendiente prioritario.
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

- **Consolidación de mejoras pendientes** (deuda no bloqueante: crecimiento de miniaturas, reutilización por `mtime` sin hash, retención de pixmaps — ver `ARCHITECTURE.md`).
- **Auditorías externas**.
- **Definición y priorización de Beta 8** — alcance todavía no definido (queda pendiente de consolidación + auditorías externas).
- Instalador: contrato estático 8/8 y build/artefacto Beta 7 aprobados; ciclo real instalación/desinstalación/reinstalación no ejecutado por seguridad y no bloquea el desarrollo — solo se retomará por pedido explícito del propietario.

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

- No requiere instalar dependencias para consolidación/auditorías/definición Beta 8.
- Instalador Beta 7: build/artefacto aprobado; validación real no ejecutada por seguridad y no bloquea (ver Fase actual).

## Próximos focos

1. Consolidación de mejoras pendientes.
2. Auditorías externas.
3. Definición y priorización de Beta 8.
