# Visor de Videos

Visor de escritorio para Windows que permite explorar, organizar y analizar grandes colecciones de videos mediante miniaturas y previews representativas, sin abrir cada archivo.

## Estado actual

**Beta 3: terminada, validada y publicada.** El estado detallado y la deuda conocida se registran en `STATUS.md`.

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
