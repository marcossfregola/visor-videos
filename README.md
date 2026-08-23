# Visor de Videos

Visor de escritorio para Windows que permite explorar, organizar y analizar grandes colecciones de videos mediante miniaturas y previews representativas, sin abrir cada archivo.

## Estado actual

**Beta 7 — B7.13 cerrada y publicada.** Commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` (`B7 Cerrar Beta 7 B7.13`); tag anotado `v7.0-beta` publicado y resolviendo permanentemente a ese commit; rama `beta7` publicada (reconciliación documental posterior `97e6fcf` en `beta7`); GitHub Release `v7.0-beta` prerelease publicada sin instalador público Beta 7; repositorio **PUBLIC** (default branch `main`); validación específica del instalador Beta 7 **PENDIENTE**. Para el estado completo, deuda y pendientes ver `STATUS.md`.

## Stack

- Python 3.13 y PySide6 (Qt 6).
- SQLite (catalogo).
- FFmpeg y FFprobe (fotogramas y metadatos; no se empaquetan, deben estar en el PATH).
- Inno Setup 6 (instalador por usuario).

## Ejecucion

```text
python visor_videos.py
```

Para escanear por CLI: `python escanear_videos.py`. Detalles de entorno en `ENVIRONMENT.md`.

## Distribucion

El procedimiento oficial de empaquetado (PyInstaller + Inno Setup) y los instaladores publicados se documentan en `EMPACADO.md`; los instaladores oficiales se publican en la seccion Releases del repositorio.

## Licencia

Pendiente de definir.

## Indice documental

| Documento | Contenido |
| --- | --- |
| `PROJECT.md` | Identidad, vision, alcance y principios del producto |
| `STATUS.md` | Estado actual, deuda y problemas conocidos |
| `ARCHITECTURE.md` | Arquitectura vigente y decisiones duraderas |
| `ENVIRONMENT.md` | Entorno verificado y reproduccion |
| `RULES.md` | Reglas permanentes del proyecto |
| `ROADMAP.md` | Trabajo futuro decidido/priorizado |
| `BACKLOG.md` | Ideas futuras no comprometidas |
| `HISTORIAL_PROYECTO.md` | Registro historico de etapas aprobadas |
| `EMPACADO.md` | Procedimiento de empaquetado y distribucion |
| `METODOLOGIA_DESARROLLO.md` | Metodología y protocolo de desarrollo |
