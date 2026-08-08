# Procedimiento oficial de empaquetado

Procedimiento reproducible para generar el **ejecutable portable** (PyInstaller) y el **instalador** (Inno Setup) del Visor de Videos. Debe ejecutarse en orden y en la raiz del proyecto (`C:\Codex\VisorVideo`). No depende de memoria ni de pasos manuales no documentados. Las versiones del entorno se registran en `ENVIRONMENT.md`.

## Decisiones oficiales de la Beta3 (fijadas por el auditor)

- **Nombre oficial de la version**: `Beta3`.
- **Nombre visible**: Visor de Videos.
- **Carpeta de instalacion**: `%LOCALAPPDATA%\Programs\VisorVideos`.
- **Instalacion por usuario**, sin permisos de administrador (`PrivilegesRequired=lowest`).
- **AppId nuevo e independiente** de Beta1/Beta2 (GUID fijo del producto).
- **Desinstalacion completa**: elimina el programa, `biblioteca.db`, `configuracion.json`, `miniaturas/` y cualquier dato generado por la aplicacion (`[UninstallDelete]`).
- **No incluir FFmpeg ni FFprobe** (se resuelven por PATH en la maquina destino).
- Incluir **unicamente una `biblioteca.db` vacia** con el esquema vigente.
- **No incluir** `configuracion.json` ni `miniaturas/` (se crean en tiempo de ejecucion).
- Instalador: `VisorVideos_Beta3_Setup.exe` en `Distribucion\Beta3\`.

## Prerrequisitos

- Windows x64.
- Python 3.13 (misma version con la que se desarrolla; ver `ENVIRONMENT.md`).
- PyInstaller 6.x instalado en ese Python: `python -m pip install pyinstaller`.
- Inno Setup **6.7.3** instalado (`ISCC.exe` en `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` o, instalado por usuario, en `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`; en el entorno verificado esta ultima ruta es la presente).
- FFmpeg y FFprobe **disponibles en el PATH** de la maquina **destino** (no se empaquetan).

## 1. Generar el ejecutable portable (PyInstaller)

Desde la raiz del proyecto:

```text
python -m PyInstaller --onedir --windowed --name VisorVideos visor_videos.py
```

- Entrada: `visor_videos.py` (punto de entrada de produccion, `main()`).
- Resultado: `dist\VisorVideos\VisorVideos.exe` + `dist\VisorVideos\_internal\`.
- No se incluyen datos: `biblioteca.db`, `miniaturas/`, `configuracion.json` se crean en tiempo de ejecucion junto al ejecutable (modo `sys.frozen` de `rutas.py`).
- No se incluyen FFmpeg/FFprobe (por PATH).

## 2. Preparar la base de datos vacia para el instalador

El instalador incluye una `biblioteca.db` **vacia con el esquema vigente** (sin datos de desarrollo). Generarla en la salida del build:

```text
python -c "import escanear_videos as e; c=e.conectar_bd(r'dist\VisorVideos\biblioteca.db'); c.commit(); c.close()"
```

Verificacion: el archivo existe y no contiene videos.

## 3. Generar el instalador (Inno Setup)

Compilar el script oficial con la version y la etiqueta correspondientes:

```text
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAplicacionVersion=3.0 /DBetaEtiqueta=Beta3 instalador.iss
```

Si Inno Setup esta instalado por usuario:

```text
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DAplicacionVersion=3.0 /DBetaEtiqueta=Beta3 instalador.iss
```

- Entrada: `instalador.iss` (instalacion por usuario en `%LOCALAPPDATA%\Programs\VisorVideos`, AppId independiente de Beta1/Beta2, desinstalador completo, acceso directo, `biblioteca.db` vacia con `onlyifdoesntexist`, sin FFmpeg/FFprobe, sin `configuracion.json`, sin `miniaturas/`).
- Resultado: `Distribucion\Beta3\VisorVideos_Beta3_Setup.exe`.

## 4. Verificacion

- Ejecutar el portable `dist\VisorVideos\VisorVideos.exe` (debe abrir sin consola).
- Instalar el `Setup.exe` en una maquina limpia: primer inicio desde el acceso directo, catalogo creado, desinstalacion total (elimina programa y datos generados).

## Repetir para una version futura

1. Cambiar la version:
   `ISCC.exe /DAplicacionVersion=X.Y /DBetaEtiqueta=BetaN instalador.iss` (o editar los `#define AplicacionVersion` y `#define BetaEtiqueta` del script).
2. Repetir los pasos 1-4 con el mismo comando de PyInstaller.

## Notas

- La version de Inno Setup fijada por el proyecto es **6.7.3**.
- `configuracion.json` y `miniaturas/` se crean en tiempo de ejecucion junto al ejecutable; el instalador no los incluye y el desinstalador los elimina (`[UninstallDelete]`).
- El nombre oficial de la aplicacion es **Visor de Videos**; el ejecutable se llama `VisorVideos.exe`.
- Referencias: entorno y versiones en `ENVIRONMENT.md`; decisiones de empaquetado como decisiones duraderas en `ARCHITECTURE.md` (10.11).
