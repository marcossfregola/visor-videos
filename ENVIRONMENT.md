# ENVIRONMENT — Visor de Videos

Entorno verificado del proyecto (baseline registrado y actualizado post-Beta 7). No se instala, desinstala ni limpia nada sin autorizacion; la coexistencia FFmpeg se documenta tal como existe.

## Sistema

- SO: Windows (`Windows_NT`, `Microsoft Windows NT 10.0.26200.0`).

## Runtime y dependencias

- Python: **3.13.14** (`C:\Program Files\Python313\python.exe`).
- PySide6: **6.11.1**.
- Qt: **6.11.1**.
- SQLite (embedded de Python 3.13): **3.50.4**.
- PyInstaller: **6.21.0** (verificado `python -m PyInstaller --version`; requerido para empaquetado, ver `EMPACADO.md`).

## Herramientas

- Git: **2.53.0.windows.2**.
- FFmpeg/FFprobe efectivos por PATH: **8.1.1** (`C:\Users\Marcos Casa\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build-shared\bin` — verificado `ffmpeg -version` / `ffprobe -version`).
- FFmpeg/FFprobe adicionales: **9.0** (`C:\ProjectStorage\VisorVideo\tools\ffmpeg\bin`) — coexistencia documentada, no corregida sin autorización.
- Inno Setup: **6.7.3** (`ISCC.exe` en `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` — verificado `DisplayVersion 6.7.3` en `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall` — `DisplayName Inno Setup versión 6.7.3`, `InstallLocation C:\Users\Marcos Casa\AppData\Local\Programs\Inno Setup 6\`; `ISCC.exe /?` operativo; `FileVersion/ProductVersion 0.0.0.0` no versiona; versión requerida/fijada por proyecto 6.7.3).

> PyInstaller 6.21.0 está disponible (verificado). En baseline de adopción figuraba como ausente; ahora presente para empaquetado. Coexistencia FFmpeg 8.1.1 / 9.0: ambas funcionan; efectiva es 8.1.1 por PATH.

## Ubicaciones

- Workspace actual: `C:\prueba` (repo Git, rama `beta8`, HEAD `33da65066867026d9a72bb333216bfd9fdc4b626`; parent B8.1 `d43c1b8e9c38d132c346933967e8e8bac7fdae9f`; base documental `d04a712`; `beta8` local no publicada, sin `origin/beta8`, sin tag/release B8).
- Workspace histórico: `C:\Codex\VisorVideo` (baseline de adopción).
- Almacenamiento externo: `C:\ProjectStorage\VisorVideo` (backups `source-protect` / `adoption-baseline`, `tools\ffmpeg`).

## Ejecucion

Ejecucion verificada:

```text
python visor_videos.py
```

Escaneo por CLI:

```text
python escanear_videos.py
```

Verificaciones puntuales realizadas: `python --version`, `python -c "import PySide6; print(PySide6.__version__)"`, `ffmpeg -version`, `ffprobe -version`, `python -m PyInstaller --version`, `Get-Location` → `C:\prueba`, `Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` (Inno Setup 6.7.3) y `ISCC.exe /?`.

FFmpeg/FFprobe deben estar disponibles en el PATH de la maquina destino (no se empaquetan en el instalador).

## Reproducibilidad

Para reproducir el entorno: Python 3.13 con PySide6 6.11.1 y FFmpeg/FFprobe 8.1.1 por PATH, PyInstaller 6.x e Inno Setup 6.7.3. Procedimiento de empaquetado en `EMPACADO.md`.
