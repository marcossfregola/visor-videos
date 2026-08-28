# Visor de Videos

Visor de escritorio para Windows que permite explorar, organizar y analizar grandes colecciones de videos mediante miniaturas y previews representativas, sin abrir cada archivo.

## Estado actual

**Beta 9 — CERRADA Y PUBLICADA `v9.0-beta` (rama `beta9`/`origin/beta9`; último commit técnico B9.9 `03fd856c9e43ee092ce09d87bad8791292e19eb3` previo al cierre).** B9.2 `d81fc93fe5f12d4ab3367a8fefb459851d77e67a`, B9.3 `431f1fa8f142e6d776713a6cfe7c17ab3645945d`, B9.4 `4d475cefd6ef974c3baa57e65ecb4c7d962d9971`, B9.5 `4dcaae0e3400eaa065f115cf1ff70df649cfdb3b`, B9.6 `24bd7a9e86d92925e57d71d6f94b458f3d1017fa`, B9.7.1 `8c1ea0c6e5cec3c6bdf3cf9808a6ba959c30a790`, B9.7.2 `4de180d43d1dfd4db819582cfaf56fea4325eb43`, B9.7.3 `2e2335b795ce4d10ee55d600fd468bddecf8b825`, B9.8 P18 `4909020e11e52121d0a2a13307964bed7247cbde`, hover desactivable `41216a10edfed416d32df7a39e7eaccd77b9b5ae`, B9.9 técnico `03fd856c9e43ee092ce09d87bad8791292e19eb3`; identidad `Beta 9 - B9.9` publicada vía tag anotado `v9.0-beta` en `origin/beta9`; baseline publicado `v8.0-beta`/`e851c7c` (`origin/beta8` alineado) y `main` documental `d04a712`; sin GitHub Release ni instalador público; próximo foco Beta 10. Para el estado profundo ver `STATUS.md`, entorno ver `ENVIRONMENT.md`, índice documental V1.3 intacto. Uso personal/sin objetivo de distribución pública; repo público es independiente.

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
