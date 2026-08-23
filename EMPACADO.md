# Procedimiento oficial de empaquetado

Procedimiento reproducible para generar el **ejecutable portable** (PyInstaller) y el
**instalador** (Inno Setup) del Visor de Videos. Debe ejecutarse en orden y en la raíz del
proyecto (`C:\prueba`). No depende de memoria ni de pasos manuales no documentados.

## Decisiones oficiales de la Beta3 (fijadas por el auditor)

Las decisiones de esta sección se conservan como **referencia histórica de la
Beta 3**. Las que afectan la desinstalación fueron **reemplazadas por
B6.1 — Preservación de datos del usuario al desinstalar** (ver "Comportamiento
vigente de la desinstalación" más abajo); las restantes reglas de instalación
siguen describiendo el procedimiento reproducible.

- **Nombre oficial de la versión**: `Beta3`.
- **Nombre visible**: Visor de Videos.
- **Carpeta de instalación**: `%LOCALAPPDATA%\Programs\VisorVideos`.
- **Instalación por usuario**, sin permisos de administrador (`PrivilegesRequired=lowest`).
- **AppId nuevo e independiente** de Beta1/Beta2 (GUID fijo del producto).
- **Desinstalación (decisión histórica de la Beta 3, NO vigente)**: la Beta 3 eliminaba
  el programa, `biblioteca.db`, `configuracion.json`, `miniaturas/` y cualquier dato
  generado por la aplicación (`[UninstallDelete]`). **Desde B6.1 esta regla quedó
  eliminada**: la desinstalación NO debe borrar los datos persistentes del usuario (ver
  "Comportamiento vigente de la desinstalación").
- **No incluir FFmpeg ni FFprobe** (se resuelven por PATH en la máquina destino).
- Incluir **únicamente una `biblioteca.db` vacía** con el esquema vigente.
- **No incluir** `configuracion.json` ni `miniaturas/` (se crean en tiempo de ejecución).
- Instalador: `VisorVideos_Beta3_Setup.exe` en `Distribucion\Beta3\`.

## Comportamiento vigente de la desinstalación (B6.1)

Desde la **B6.1 — Preservación de datos del usuario al desinstalar** (rama
`beta6`), desinstalar la aplicación **NO debe eliminar los datos persistentes
del usuario** (`biblioteca.db`, `configuracion.json`, `miniaturas/`, marcadores
y segmentos). El instalador actual (`instalador.iss`) instala `biblioteca.db`
con `uninsneveruninstall` y **no** utiliza un `[UninstallDelete]` recursivo
sobre `{app}`: la desinstalación elimina los binarios instalados desde `[Files]`
y **conserva** los datos del usuario para permitir una reinstalación sin pérdida
de datos.

Este comportamiento **no debe revertirse en versiones futuras** sin autorización
explícita: eliminar datos del usuario durante la desinstalación implica un riesgo
de pérdida irreversible. Los casos de upgrade/reinstalación conservadora y la
higiene de datos residuales quedan **fuera de lo demostrado por B6.1** y
requerirían su propia etapa si fueran necesarios.

## Prerrequisitos

- Windows x64.
- Python 3.13 (misma versión con la que se desarrolla).
- PyInstaller 6.x instalado en ese Python: `python -m pip install pyinstaller`.
- Inno Setup **6.7.3** instalado (`ISCC.exe` en
  `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` o, instalado por usuario, en
  `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`).
- FFmpeg y FFprobe **disponibles en el PATH** de la máquina **destino** (no se empaquetan).

## 1. Generar el ejecutable portable (PyInstaller)

Desde la raíz del proyecto (checkout limpio, sin `VisorVideos.spec` requerido):

```
python -m PyInstaller --onedir --windowed --name VisorVideos visor_videos.py
```

- Entrada: `visor_videos.py` (punto de entrada de producción, `main()`). No depende de `VisorVideos.spec` (archivo ignorado y regenerable; `VisorVideos.spec` no es requisito del pipeline).
- Resultado: `dist\VisorVideos\VisorVideos.exe` + `dist\VisorVideos\_internal\`.
- No se incluyen datos: `biblioteca.db`, `miniaturas/`, `configuracion.json` se crean en tiempo de ejecución junto al ejecutable (modo `sys.frozen` de `rutas.py`).
- No se incluyen FFmpeg/FFprobe (por PATH).
- No se usa monkey-patch de internals de PyInstaller ni `datas` con la `biblioteca.db` local.

## 2. Preparar la base de datos vacía para el instalador

El instalador incluye una `biblioteca.db` **vacía con el esquema vigente** (sin datos de
desarrollo). Generarla en la salida del build mediante el script versionado:

```
python preparar_empaquetado.py
```

El script crea `dist\VisorVideos\biblioteca.db` **nueva y vacía** usando la capa productiva `escanear_videos.conectar_bd` (esquema y migraciones vigentes), sin copiar la `biblioteca.db` local ignorada. Verifica `PRAGMA integrity_check=ok`, conteo `videos=0` (y `marcadores_video=0`, `segmentos_video=0`, derivadas vacías) y esquema vigente; falla con exit 1 si falta el directorio, la creación falla o la verificación no pasa.

Alternativa equivalente (sin script, mismo contrato): `python -c "import escanear_videos as e; c=e.conectar_bd(r'dist\VisorVideos\biblioteca.db'); c.commit(); c.close()"` y verificar manualmente.

Verificación: `dist\VisorVideos\biblioteca.db` existe tras el script, `PRAGMA integrity_check=ok` y no contiene videos (DB vacía ~60 KB, no 184320 bytes de la DB de desarrollo).

## 3. Generar el instalador (Inno Setup)

Compilar el script oficial con la versión y la etiqueta correspondientes a **Beta 7**:

```
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAplicacionVersion=7.0 /DBetaEtiqueta=Beta7 instalador.iss
```

- Entrada: `instalador.iss` (instalación por usuario en
  `%LOCALAPPDATA%\Programs\VisorVideos`, AppId independiente de Beta1/Beta2, desinstalación
  que **conserva los datos del usuario** desde B6.1, acceso directo, `biblioteca.db` vacía
  con `onlyifdoesntexist`, sin FFmpeg/FFprobe, sin `configuracion.json`, sin `miniaturas/`).
- Resultado: `Distribucion\Beta7\VisorVideos_Beta7_Setup.exe`.

> **Aclaración Beta 7:** actualizar la identidad (`AplicacionVersion 7.0` / `BetaEtiqueta Beta7`) y el procedimiento de empaquetado **no significa** que el instalador de **Beta 7** haya sido validado.
> - **Prueba estática de contrato:** `python prueba_instalador.py` (8 pruebas) verifica de forma estática `instalador.iss`/`rutas.py` (destino por usuario, `onlyifdoesntexist`/`uninsneveruninstall`, ausencia de `[UninstallDelete]` destructivo, rutas persistentes) — **no instala ni valida el artefacto real**.
> - **Generación de artefacto:** `PyInstaller` + `preparar_empaquetado.py` + `ISCC.exe /DAplicacionVersion=7.0 /DBetaEtiqueta=Beta7` → `Distribucion/Beta7/VisorVideos_Beta7_Setup.exe` y comprobación del artefacto.
> - **Validación real del instalador Beta 7:** ejecución aislada del artefacto `Distribucion/Beta7/VisorVideos_Beta7_Setup.exe` con instalación, primer inicio, desinstalación, verificación de `biblioteca.db`/`configuracion.json`/`miniaturas` preservados, reinstalación y ausencia de datos reales tocados — **PENDIENTE** como etapa posterior independiente.

## 4. Verificación

- Ejecutar el portable `dist\VisorVideos\VisorVideos.exe` (debe abrir sin consola).
- Instalar el `Setup.exe` en una máquina limpia: primer inicio desde el acceso directo,
  catálogo creado y desinstalación que **elimina los binarios de la aplicación y
  conserva los datos del usuario** (`biblioteca.db`, `configuracion.json`, `miniaturas/`).

### Validación real Beta 6 (resumen)

Packaging reproducible validado en entrega Beta 6 (ver `HISTORIAL_PROYECTO.md` ##115): `python -m PyInstaller --onedir --windowed --name VisorVideos visor_videos.py` + `python preparar_empaquetado.py` (DB seed vacía ~60 KB, `PRAGMA integrity_check=ok`, `videos/marcadores/segmentos/derivados=0`) + `ISCC.exe instalador.iss` (Inno Setup 6.7.3). Instalación/desinstalación/reinstalación **aislada validada** preservando `biblioteca.db`/`configuracion.json`/`miniaturas` (B6.1 `uninsneveruninstall` sin `[UninstallDelete]` destructivo). Beta 6 publicada: tag `v6.0-beta` anotado sobre `7d85e94bb8b617209a155e5b1086d1d38f4784f8`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios.

## Repetir para una versión futura

1. Cambiar la versión:
   `ISCC.exe /DAplicacionVersion=X.Y /DBetaEtiqueta=BetaN instalador.iss` (o editar los
   `#define AplicacionVersion` y `#define BetaEtiqueta` del script).
2. Repetir los pasos 1-4 con los mismos comandos (`python -m PyInstaller --onedir --windowed --name VisorVideos visor_videos.py` + `python preparar_empaquetado.py`).
3. Al adaptar el script para una versión futura, **conservar la regla de B6.1**:
   la desinstalación no debe eliminar los datos persistentes del usuario.

## Notas

- La versión de Inno Setup fijada por el proyecto es **6.7.3**.
- `configuracion.json` y `miniaturas/` se crean en tiempo de ejecución junto al ejecutable;
  el instalador no los incluye y, desde **B6.1**, la desinstalación **los conserva** (no se
  utilizan `[UninstallDelete]` destructivos).
- El nombre oficial de la aplicación es **Visor de Videos**; el ejecutable se llama
  `VisorVideos.exe`.
