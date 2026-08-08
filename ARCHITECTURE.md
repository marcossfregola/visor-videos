# ARCHITECTURE — Visor de Videos

Arquitectura vigente del proyecto (condensada del documento tecnico heredado y de las decisiones tecnicas verificadas). No es un changelog ni un manual linea por linea; el detalle de implementacion que ya refleja el codigo fuente no se duplica aqui.

## 1. Estructura general

Workspace: `C:\Codex\VisorVideo` (repo Git, rama `main`, remote `origin` = `https://github.com/marcossfregola/visor-videos.git`).

```text
visor_videos.py          Interfaz grafica PySide6 (ventana, tarjetas, previews, navegacion)
escanear_videos.py       Backend / logica del catalogo: escaneo, SQLite, FFprobe, FFmpeg, sincronizacion
arbol_navegacion.py      Arbol de navegacion del panel izquierdo (Este equipo -> discos -> carpetas)
configuracion.py         Servicio de persistencia de preferencias (configuracion.json)
tareas.py                Infraestructura generica de trabajos en segundo plano (QThread / GestorTareas)
tareas_videos.py         Tareas asincronas especificas de video (FFprobe, escaneo, miniaturas, lectura, guardado, sincronizacion)
operaciones.py           Logica pura de operaciones sobre archivos (copiar, pegar, eliminar)
seleccion_carpetas.py    Conjunto de carpetas seleccionadas por ruta (Seleccion personalizada)
rutas.py                 Resolucion centralizada de rutas, independiente del CWD (soporta PyInstaller)
apertura_videos.py       Servicio de apertura con la aplicacion predeterminada (unico modulo que ejecuta os.startfile)
main.py                  Punto de entrada de produccion
instalador.iss           Script Inno Setup oficial del instalador (ver EMPACADO.md)
biblioteca.db            Catalogo SQLite (ignorado; regenerable)
configuracion.json       Preferencias locales del usuario (ignorado)
miniaturas/              Miniatura/previews JPG (ignorado; derivado de los videos)
videos_prueba/           Videos de prueba (tracked)
Distribucion/            Instaladores de Beta 2 y Beta 3 (ignorado)
prueba_*.py              77 suites de pruebas
```

Mantenidos como ajenos al visor (artefactos de prueba preservados): `main.py` (script de prueba de operaciones), `operaciones.py` (logica pura usada por el visor), `prueba_agente.py`, `datos.txt`.

## 2. Responsabilidades por modulo

- `escanear_videos.py`: unico modulo con responsabilidad sobre el dominio y los datos. Escaneo de archivos (`.mp4`, `.mkv`, `.avi`), preparacion de registros, acceso SQLite con migracion idempotente, integracion FFprobe/FFmpeg con `CREATE_NO_WINDOW`, reutilizacion/generacion de miniaturas y previews (nunca sobrescribe ni elimina), deteccion de diferencias disco-BD, plan de sincronizacion, incorporaciones y eliminacion controlada de registros, lectura paginada con busqueda SQL parametrizada.
- `visor_videos.py`: interfaz grafica. Carga inicial asincrona de la primera pagina, "Cargar mas", filtro en vivo, tarjetas con miniaturas/previews, seleccion (simple, Ctrl, Shift, modo checks), menu contextual, operaciones, apertura por doble clic, escaneo asincrono, pipeline encadenado, sincronizacion y recarga del catalogo. No abre SQLite directamente ni ejecuta FFprobe/FFmpeg en el hilo principal.
- `arbol_navegacion.py`: panel izquierdo con nodo raiz "Este equipo", discos y carpetas con carga diferida, seleccion funcional, indicadores de escaneo, modo seleccion multicarpeta con herramientas rapidas.
- `rutas.py`: resolucion centralizada de rutas (raiz, BD, miniaturas, videos) independiente del CWD, con soporte para modo empaquetado (`sys.frozen`).
- `configuracion.py`: persistencia de preferencias en `configuracion.json` (carpeta, incluir subcarpetas, cantidad de previews, escaneo automatico, tamanos, vista ampliada).
- `tareas.py`: infraestructura generica de tareas en segundo plano (`TareaBase` + `GestorTareas` con `QThread` por ejecucion; unica tarea activa por gestor).
- `tareas_videos.py`: tareas especificas (escaneo, FFprobe, tamanos, miniaturas, lectura y lectura paginada, guardado individual/coleccion, previews progresivas, sincronizacion del catalogo).
- `operaciones.py`: logica pura de operaciones sobre archivos (copiar, pegar, eliminar a Papelera).
- `seleccion_carpetas.py`: conjunto de carpetas seleccionadas por ruta para el alcance multicarpeta.
- `apertura_videos.py`: apertura del video con la aplicacion predeterminada (`os.startfile`), unico punto de apertura.
- `instalador.iss` + `EMPACADO.md`: empaquetado oficial (PyInstaller + Inno Setup por usuario).

## 3. Separacion de responsabilidades

- UI separada de logica: la interfaz no accede directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada; todo se encola como tarea en segundo plano.
- El catalogo (`escanear_videos.py`) contiene capas puras de transformacion (registros basicos, combinacion con FFprobe/miniaturas/tamanos) separadas del acceso a SQLite y de los subprocesos FFmpeg/FFprobe.
- La apertura de archivos esta aislada en un unico servicio.
- La resolucion de rutas esta centralizada y es independiente del CWD.

## 4. Catalogos y sincronizacion (SQLite)

- Tabla `videos` con columnas base y extras (`duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`, `tamano_bytes`, `ruta`).
- Migracion idempotente por `PRAGMA table_info` + `ALTER TABLE` cuando la columna falta.
- Escritura transaccional: colecciones en una unica transaccion atomica; rollback total ante error; base inexistente -> `FileNotFoundError` sin crear archivos.
- Lectura paginada con `LIMIT/OFFSET` y `COUNT` parametrizados; la primera pagina se carga asincrona y las siguientes con "Cargar mas".
- Sincronizacion: `detectar_diferencias` (no destructiva) -> `preparar_plan_sincronizacion` -> `aplicar_incorporaciones` -> `eliminar_candidatos`, ejecutada en segundo plano; tras exito, recarga asincrona del catalogo con reemplazo de tarjetas.
- Cada video transporta su `ruta` real; el alcance del catalogo (carpetas seleccionadas) es distinto de la carpeta activa de navegacion.

## 5. Escaneo, FFprobe y FFmpeg

- Escaneo de archivos de video por extension, con modo recursivo configurable ("Incluir subcarpetas") y nombres planos seguros para miniaturas.
- FFprobe: metadatos (duracion, ancho, alto, codec) en segundo plano con timeout de 30 s; `None` ante fallo individual.
- FFmpeg: generacion de miniaturas y previews en segundo plano, con reutilizacion por `mtime` (miniatura valida si su mtime >= al del video) y escritura en la siguiente ranura libre (`miniaturas/<prefijo>_NN.jpg`, previews `_preview_NN.jpg`). Nunca sobrescribe ni elimina archivos existentes.
- Videos vacios (0 bytes) no generan miniatura.
- Subprocesos con `CREATE_NO_WINDOW` para evitar consolas emergentes.

## 6. Tareas en segundo plano

- `TareaBase` + `GestorTareas`: un `QThread` por ejecucion, una tarea activa por gestor, senales `inicio/resultado/error/finalizada`, apagado ordenado con `cerrar(timeout)`.
- Pipeline encadenado del catalogo: escaneo -> tamanos -> FFprobe -> miniaturas -> guardado -> sincronizacion -> recarga, con el mismo gestor.
- Previews progresivas con gestor independiente y lotes por carpeta.

## 7. Pruebas

- 77 suites `prueba_*.py` en la raiz (smoke, escaneo, lectura/paginacion, previews/miniaturas, seleccion, sincronizacion, operaciones, persistencia, progreso, interfaz asincrona, recarga de catalogo).
- Arnés de smoke tests (`prueba_smoke.py`) con base SQLite temporal; ejecucion explicita.
- Fallos historicos conocidos y fallo transitorio no reproducido: ver `STATUS.md` (Problemas conocidos). Los tests no deben modificar el estado real del usuario (`RULES.md` 7).

## 8. Puntos de extension previstos

- Generacion de miniaturas/previews con reutilizacion por `mtime` y preservacion de archivos.
- Infraestructura asincrona reutilizable para escaneo, FFprobe, miniaturas, lectura y escritura.
- Modulo de configuracion completo (centralizar rutas, extensiones, tamanos, columnas).
- Cache formal de miniaturas/metadatos.
- Vistas del catalogo: orden, agrupacion y filtros sobre `listar_videos`/`listar_videos_paginado` (paginacion automatica y busqueda SQL desde la interfaz pendientes).
- Resolucion de rutas con soporte PyInstaller.
- Paneles adicionales (propiedades, favoritos, etiquetas, IA) sobre la infraestructura QSplitter existente.

## 9. Direccion arquitectonica futura

- Interfaz hacia un sistema de paneles independientes y configurables (base QSplitter implementada).
- Centro de navegacion permanente con estructura extensible (catalogo, Este equipo, favoritos, etiquetas, colecciones, recientes, ultimos escaneos).
- Los cambios futuros se hacen por etapas pequenas; cada etapa extiende la arquitectura solo en la medida de su alcance aprobado.

## 10. Decisiones arquitectonicas duraderas

Formato: Decision / Razon / Alternativas descartadas.

### 10.1 PySide6 sobre PyQt6
- **Decision:** el stack es PySide6 (Qt 6).
- **Razon:** decision conversacional vigente; PyQt6 es referencia historica superada.
- **Alternativas descartadas:** PyQt6, Tkinter, wxPython.

### 10.2 Separacion estricta UI / logica
- **Decision:** la interfaz nunca accede directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada.
- **Razon:** evita bloqueos, acoplamiento y errores de estado; el catalogo es la unica capa de dominio/datos.
- **Alternativas descartadas:** UI con acceso directo a la BD (causo problemas historicos de duplicacion de nombres de BD y bloqueos).

### 10.3 Trabajo pesado fuera del hilo principal
- **Decision:** toda tarea costosa usa `QThread`/`GestorTareas`.
- **Razon:** la fluidez de la interfaz es requisito del producto.
- **Alternativas descartadas:** ejecucion síncrona en el hilo principal (bloqueaba el escaneo y FFprobe).

### 10.4 Pipeline por carpeta, no paralelismo agresivo
- **Decision:** el soporte multicarpeta reutiliza el pipeline secuencialmente, una carpeta por vez.
- **Razon:** menor riesgo; evita reescribir tareas y pipelines simultaneos compitiendo.
- **Alternativas descartadas:** pipelines paralelos simultaneos.

### 10.5 Carpeta activa != alcance del catalogo; cada video transporta su ruta
- **Decision:** cada registro del catalogo lleva su `ruta` real; los previews/miniaturas se resuelven por esa ruta, no por la carpeta de navegacion.
- **Razon:** el bug critico final de Beta 3 fue consecuencia de usar estado de navegacion para una operacion que necesitaba la ruta real del video.
- **Alternativas descartadas:** resolver por `carpeta_seleccionada` (corregida).

### 10.6 Seleccion personalizada materializada como rutas
- **Decision:** la seleccion multicarpeta es un conjunto explicito de rutas; los comandos de rango son herramientas para construirlo.
- **Razon:** evita semantica ambigua si cambia el contenido u orden de las carpetas.
- **Alternativas descartadas:** representacion interna por intervalos.

### 10.7 Operaciones de archivos seguras
- **Decision:** copiar = copia fisica; pegar = portapapeles interno; nunca sobrescribir silenciosamente; eliminar = Papelera nativa de Windows (`SHFileOperationW` via `ctypes`); nunca borrado permanente desde el producto; operaciones en segundo plano.
- **Razon:** seguridad y previsibilidad; comportamiento recuperable; sin dependencias externas.
- **Alternativas descartadas:** `os.remove`/borrado permanente, sobrescritura directa.

### 10.8 Incrementalidad despues de operaciones
- **Decision:** copiar/pegar/eliminar no provocan reescaneos completos cuando la actualizacion incremental es posible.
- **Razon:** coherente con la actualizacion parcial; menor costo en bibliotecas grandes.
- **Alternativas descartadas:** reescaneo completo tras cada operacion.

### 10.9 Reutilizacion de miniaturas por mtime y ranuras sin sobrescribir
- **Decision:** se reutiliza la miniatura valida (mtime >= video); la generacion escribe en la siguiente ranura libre; nunca se sobrescribe ni elimina.
- **Razon:** preservacion de datos y cache; convivencia con miniaturas preexistentes.
- **Alternativas descartadas:** sobrescritura de la miniatura existente, regeneracion total.

### 10.10 Resolucion centralizada de rutas
- **Decision:** `rutas.py` centraliza las rutas del proyecto independientemente del CWD, con soporte para modo empaquetado.
- **Razon:** la app fallaba al lanzarse desde otra ubicacion; el empaquetado exige rutas relativas al ejecutable.
- **Alternativas descartadas:** rutas relativas al CWD.

### 10.11 Instalador por usuario, sin FFmpeg empaquetado
- **Decision:** instalacion por usuario (`%LOCALAPPDATA%\Programs\VisorVideos`, `PrivilegesRequired=lowest`), AppId independiente por version, `biblioteca.db` vacia con `onlyifdoesntexist`, desinstalacion completa de datos generados; FFmpeg/FFprobe se resuelven por PATH, no se empaquetan.
- **Razon:** sin permisos de administrador; preserva el catalogo del usuario en reinstalaciones; los binarios multimedia pesan y varian por maquina.
- **Alternativas descartadas:** instalacion por maquina (administrador), empaquetado de FFmpeg dentro del instalador.
