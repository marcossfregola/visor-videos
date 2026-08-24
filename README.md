# Visor de Videos

Visor de escritorio para Windows que permite explorar, organizar y analizar grandes colecciones de videos mediante miniaturas y previews representativas, sin abrir cada archivo.

## Estado actual

**Beta 8 — EN CURSO (beta8 local, no publicada).** B8.1 cerrada localmente `d43c1b8e9c38d132c346933967e8e8bac7fdae9f` (2026-08-23), B8.2 cerrada localmente `33da65066867026d9a72bb333216bfd9fdc4b626` (2026-08-24); próximo paso exacto **B8.3 — Cutover de identidad**, B8.4 posterior; rama `beta8` HEAD `33da650`, sin `origin/beta8`, sin tag/release B8; baseline estable `v7.0-beta`/`f9976d3` y `main` documental `d04a712`. Para el estado profundo ver `STATUS.md`, entorno ver `ENVIRONMENT.md`, índice documental V1.3 intacto. Uso personal/sin objetivo de distribución pública; repo público es independiente.

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
