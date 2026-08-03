# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), **lectura paginada del catálogo SQLite**
(`TareaLecturaCatalogoPaginada` con `LIMIT`/`OFFSET`/`COUNT` en SQL),
escritura individual asíncrona (`TareaGuardarVideo`), escritura de
colección asíncrona (`TareaGuardarVideos`), **integración asíncrona de
la primera carga del catálogo en la interfaz** (`visor_videos.py`
consume `TareaLecturaCatalogoPaginada` mediante `GestorTareas` para la
primera página, con estado de carga y manejo de errores sin bloquear la
ventana), **selección de carpeta desde la interfaz** (`visor_videos.py`
permite elegir la carpeta de videos con `QFileDialog`, la normaliza a
ruta absoluta, la valida y la conserva en la sesión sin escanearla),
**escaneo manual y asíncrono de la carpeta elegida desde la interfaz**
(`visor_videos.py` escanea la carpeta con `TareaEscaneo` mediante el
mismo `GestorTareas`, muestra la cantidad de videos detectados y no
ejecuta FFmpeg ni genera miniaturas) y **pipeline escaneo → FFprobe →
miniaturas → guardado** (`TareaEscaneo` → `TareaFFprobe` →
`combinar_registros_con_ffprobe` → `TareaMiniaturas` →
`combinar_registros_con_miniaturas` → `TareaGuardarVideos`, encadenado
desde la interfaz con el mismo gestor; los archivos detectados se
guardan en SQLite con metadatos FFprobe (duración, resolución, codec;
`NULL` ante vacíos/incompletos/fallos individuales) y cantidad de
miniaturas por video mediante el upsert transaccional existente,
conservando los registros preexistentes) y **detección no destructiva de
diferencias entre la carpeta y el catálogo SQLite** (`detectar_diferencias`
en `escanear_videos.py`: compara por nombre lo que hay en disco con lo que
hay en la base y devuelve `presentes_en_ambos`/`nuevos`/`ausentes_del_disco`;
solo lectura, no inserta, actualiza ni elimina, no está integrada al
pipeline ni a la interfaz, no detecta movimientos ni renombrados y no
recorre subcarpetas) aprobadas; pendiente la integración funcional completa
del catálogo: la sincronización completa SQLite (escritura masiva con
detección de archivos y la eliminación controlada de registros ausentes,
y su integración asíncrona).

## Último commit aprobado

**Mensaje:** Detectar diferencias entre el catálogo y el disco

**Etapa aprobada:** Detección no destructiva de diferencias entre la
carpeta de videos y el catálogo SQLite: nueva función
`detectar_diferencias(carpeta, ruta_db=None)` en `escanear_videos.py`
(capa de catálogo). Compara **por nombre** los archivos de video de la
carpeta (`escanear_videos`) con los registros de la base (`SELECT nombre
FROM videos`) y devuelve el dict `{"carpeta", "presentes_en_ambos",
"nuevos", "ausentes_del_disco"}` con listas ordenadas. **Solo lectura**:
no inserta, no actualiza ni elimina registros y no modifica
miniaturas. Validaciones: `carpeta` debe ser una ruta de texto no vacía
(`ValueError`); carpeta inexistente o base inexistente → `FileNotFoundError`
sin crear archivos. **No integrada**: no forma parte del pipeline ni de la
interfaz, no detecta movimientos ni renombrados y no recorre subcarpetas.
Pendiente para la sincronización completa: la eliminación controlada de
registros ausentes y su integración asíncrona. Con suite nueva
`prueba_detectar.py` (15 pruebas). Aprobada con observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Detección no destructiva de diferencias entre la carpeta de videos y el
catálogo SQLite: `detectar_diferencias(carpeta, ruta_db=None)` en
`escanear_videos.py` (capa de catálogo, ubicada entre `listar_videos` y
`listar_videos_paginado`). Valida `carpeta` (texto no vacío; `ValueError`
en caso contrario) y la existencia de la carpeta y de la base
(`FileNotFoundError` "Carpeta no encontrada: ..." / "Base de datos no
encontrada: ...", sin crear archivos). Lista los archivos de video de la
carpeta con `escanear_videos` (solo `.mp4`/`.mkv`/`.avi`, extensión en
minúsculas) y los registros de la base con un único `SELECT nombre FROM
videos` sobre una conexión propia abierta y cerrada en `finally`;
devuelve `{"carpeta", "presentes_en_ambos", "nuevos", "ausentes_del_disco"}`
con listas ordenadas (determinista). **Solo lectura**: no inserta,
actualiza ni elimina registros, no modifica miniaturas y no llama a
FFprobe/FFmpeg/`asegurar_miniaturas`/`contar_miniaturas`/
`sincronizar_bd`. **Ausencia deliberada**: no está integrada al pipeline
ni a la interfaz (no se lanza desde el encadenamiento ni desde la ventana),
compara por **nombre** (no detecta movimientos ni renombrados, no usa
ruta/hash) y **no recorre subcarpetas**. Pendiente para la sincronización
completa: la eliminación controlada de registros ausentes y la
integración asíncrona. Con suite nueva `prueba_detectar.py` (15 pruebas:
compilación, AST de separación, ambos vacíos, nuevos, ausentes,
coincidencia, mixto, base/carpeta intactas y bytes idénticos, orden
determinista, validaciones con base no creada, cero llamadas a
FFprobe/FFmpeg/subprocess/asegurar/contar/generar/sincronizar, datos
reales intactos, consistencia matemática y filtrado por extensión).
Aprobada con observaciones.

## Estado de la arquitectura

### Completado

-   Arquitectura general.
-   Git.
-   Documentación técnica.
-   Resolución centralizada de rutas.
-   Preservación de archivos.
-   Generación inicial de miniaturas.
-   Infraestructura reutilizable de trabajos.
-   Procesamiento asíncrono de FFprobe.
-   Escaneo asíncrono de videos.
-   Lectura asíncrona del catálogo.
-   Lectura paginada asíncrona del catálogo.
-   Escritura individual asíncrona.
-   Escritura de colección asíncrona.
-   Integración asíncrona de la primera carga del catálogo en la
    interfaz.
-   Selección de carpeta desde la interfaz.
-   Escaneo manual y asíncrono de la carpeta elegida desde la interfaz.
-   Pipeline escaneo → FFprobe → guardado (encadenado desde la interfaz
    con el mismo gestor; los registros se guardan con metadatos FFprobe).
-   Generación asíncrona de miniaturas integrada en el pipeline
    (escaneo → FFprobe → miniaturas → guardado; `TareaMiniaturas` en
    segundo plano con el mismo gestor; `cantidad_miniaturas` persistida).
-   Detección no destructiva de diferencias entre la carpeta y el
    catálogo SQLite (`detectar_diferencias`; compara por nombre, solo
    lectura, sin integración al pipeline ni a la interfaz).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaMiniaturas`
→ `combinar_registros_con_miniaturas` → `TareaGuardarVideos`) ya
convierte los archivos detectados por la interfaz en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, y la **detección de diferencias** disco ↔
BD ya existe de forma no destructiva (`detectar_diferencias`), pero la
**sincronización completa** —la escritura masiva con detección de
archivos y la **eliminación controlada de registros ausentes** con su
integración asíncrona— sigue pendiente. La carga inicial asíncrona de la
primera página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización completa SQLite asíncrona (la detección de diferencias
    ya existe en `detectar_diferencias` —solo lectura, por nombre—; falta
    la escritura masiva con detección de archivos, la eliminación
    controlada de registros ausentes y su integración asíncrona).
2.  Integración SQLite asíncrona en el pipeline (encadenado).
3.  Actualización asíncrona de la interfaz (tarjetas dinámicas).
4.  FFmpeg asíncrono.
5.  Varias miniaturas por video.
6.  Selección inteligente de miniaturas.
7.  Barra de progreso.
8.  Caché avanzada.
9.  Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana (la carga inicial
asíncrona ya usa `GestorTareas` y cierra de forma ordenada en
`closeEvent`, aunque `closeEvent` puede esperar hasta 5 s por una tarea
activa); - el pipeline ya convierte los archivos detectados en registros
con metadatos FFprobe y miniaturas y los escribe, y existe la detección
no destructiva de diferencias (`detectar_diferencias`), pero la
sincronización completa sigue pendiente (escritura masiva con detección
de archivos y eliminación controlada de registros ausentes, con su
integración asíncrona); - `detectar_diferencias` compara por nombre y no
detecta movimientos ni renombrados (queda para etapas futuras); - el
enrutado de resultados por
`_escaneo_pendiente`/`_ffprobe_pendiente`/`_miniaturas_pendiente`/
`_guardado_pendiente` es suficiente para una única tarea activa y debe
revisarse si la interfaz incorpora más tipos de tarea; - el escaneo no
incluye subcarpetas; - decisión pendiente sobre si `%` y `_` como
comodines `LIKE` en la búsqueda de `listar_videos_paginado` se aceptan
como contrato; - la generación de miniaturas corre en segundo plano
dentro de `TareaMiniaturas` (FFmpeg ya no se ejecuta en el hilo
principal, aunque la extracción de fotograma sigue siendo una llamada
síncrona dentro de la tarea); - siguen pendientes progreso y cancelación; -
limpieza controlada de miniaturas antiguas.

## Deuda técnica

-   Crecimiento y duplicación de infraestructura entre las suites de
    prueba: cada suite (`prueba_escaneo.py`, `prueba_lectura.py`,
    `prueba_guardar.py`, `prueba_guardar_videos.py`, etc.) define sus
    propios helpers y versiones de conectores/falsificaciones
    (`ConectorConHilo`, `ConectorConFallo`, `Captura`, `correr`, bases
    temporales) en lugar de reutilizar una infraestructura común.
-   El patrón repetido de construir una base temporal + ejecutar con
    `GestorTareas`/`QThread` + verificar eventos/`error`/hilos se
    duplica en cada nueva suite.

## Próxima etapa

**Sincronización completa del catálogo** (escritura masiva con detección
de archivos y **eliminación controlada de registros ausentes**, con su
integración asíncrona). La etapa anterior (detección no destructiva de
diferencias con `detectar_diferencias`) quedó aprobada y commiteada; la
eliminación de registros ausentes y la integración asíncrona siguen
pendientes y se abordarán como próxima etapa, manteniendo el alcance
limitado: sin selección inteligente, sin múltiples miniaturas, sin
eliminación de archivos antiguos y sin recarga automática de la
interfaz.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
