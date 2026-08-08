# ENVIRONMENT — Visor de Videos

Entorno verificado del proyecto (baseline registrado durante la adopcion metodologica). No se instala, desinstala ni limpia nada sin autorizacion; la coexistencia FFmpeg se documenta tal como existe.

## Sistema

- SO: Windows (`Windows_NT`, `Microsoft Windows NT 10.0.26200.0`).

## Runtime y dependencias

- Python: **3.13.14** (`C:\Program Files\Python313\python.exe`).
- PySide6: **6.11.1**.
- Qt: **6.11.1**.
- SQLite (embedded de Python 3.13): **3.50.4**.

## Herramientas

- Git: **2.53.0.windows.2**.
- FFmpeg/FFprobe efectivos por PATH: **8.1.1** (`C:\Users\Marcos Casa\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build-shared\bin`).
- FFmpeg/FFprobe adicionales: **9.0** (`C:\ProjectStorage\VisorVideo\tools\ffmpeg\bin`).
- Inno Setup: `ISCC.exe` en `C:\Users\Marcos Casa\AppData\Local\Programs\Inno Setup 6\ISCC.exe` (version declarada por el proyecto: 6.7.3; el compilador no se ejecuto en la verificacion).
- PyInstaller: **ausente** (necesario solo para generar el ejecutable portable; ver `EMPACADO.md`).

> Coexistencia FFmpeg 8.1.1 / 9.0: ambas versiones funcionan. La version efectiva del PATH es 8.1.1; la 9.0 vive en ProjectStorage. No se corrige ni se limpia sin autorizacion.

## Ubicaciones

- Workspace actual: `C:\Codex\VisorVideo`.
- Almacenamiento externo: `C:\ProjectStorage\VisorVideo`.
  - `backups\source-protect`: copia persistente de proteccion del origen.
  - `backups\adoption-baseline`: baseline protegido antes de la adopcion metodologica.
  - `archives`: historicos (auditorias, Beta 1, `Visor.rar`).
  - `methodology`: protocolos V1.3 y Legacy Handoff.
  - `tools\ffmpeg\bin`: FFmpeg/FFprobe 9.0 adicionales.

## Ejecucion

Ejecucion verificada (apertura real de la aplicacion en la fase `MIGRATION_VERIFIED`, modo aislado, sin crash; titulo "Biblioteca de videos", 23 tarjetas cargadas, contador "23 videos"):

```text
python visor_videos.py
```

Escaneo por CLI (backend del catalogo):

```text
python escanear_videos.py
```

FFmpeg/FFprobe deben estar disponibles en el PATH de la maquina destino (no se empaquetan en el instalador).

## Reproducibilidad

Para reproducir el entorno de desarrollo: Python 3.13 con PySide6 6.11.1 y FFmpeg/FFprobe 8.1.1 por PATH. PyInstaller 6.x e Inno Setup 6.7.3 se requieren unicamente para empaquetar (ver `EMPACADO.md`). No existen manifests de dependencias; el procedimiento de empaquetado esta documentado en `EMPACADO.md`.
