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
conservando los registros preexistentes), **detección no destructiva de
diferencias entre la carpeta y el catálogo SQLite** (`detectar_diferencias`
en `escanear_videos.py`: compara por nombre lo que hay en disco con lo que
hay en la base y devuelve `presentes_en_ambos`/`nuevos`/`ausentes_del_disco`;
solo lectura, no inserta, actualiza ni elimina, no está integrada al
pipeline ni a la interfaz, no detecta movimientos ni renombrados y no
recorre subcarpetas), **preparación del plan de sincronización**
(`preparar_plan_sincronizacion` en `escanear_videos.py`: operación pura
que recibe el resultado de `detectar_diferencias` y devuelve
`a_incorporar` (registros básicos con `preparar_registros_basicos`; la
`fecha_importacion` se genera en la preparación, no durante la
detección)/`ya_sincronizados`/`candidatos_a_eliminar` (informativos); no
inserta, actualiza ni elimina, no accede a SQLite, no ejecuta
FFprobe/FFmpeg y no está integrada al pipeline ni a la interfaz) y
**aplicación no destructiva de las incorporaciones del plan**
(`aplicar_incorporaciones(plan, ruta_db=None)` en `escanear_videos.py`:
valida el plan completo antes de abrir SQLite, persiste únicamente
`a_incorporar` reutilizando la escritura transaccional `guardar_videos`,
no elimina `candidatos_a_eliminar`, no modifica `ya_sincronizados` ni
los registros preexistentes sincronizados y devuelve `incorporados`/
`nombres`/`pendientes_eliminacion`; no está integrada al pipeline ni a
la interfaz) aprobadas; pendiente la integración funcional completa del
catálogo: la **eliminación controlada de los registros ausentes**
(`candidatos_a_eliminar`) y su integración asíncrona.

## Último commit aprobado

**Mensaje:** Aplicar incorporaciones del plan de sincronización

**Etapa aprobada:** Aplicación de incorporaciones del plan de
sincronización: nueva función `aplicar_incorporaciones(plan,
ruta_db=None)` en `escanear_videos.py` (capa de catálogo, ubicada entre
`preparar_plan_sincronizacion` y `listar_videos_paginado`). Recibe el
plan `{"carpeta", "a_incorporar", "ya_sincronizados",
"candidatos_a_eliminar"}` y persiste **únicamente** `a_incorporar`,
reutilizando `guardar_videos` (misma transacción atómica: un solo
`connect`, todos los upserts, un solo `commit`, `rollback` total ante
fallos y `close` en `finally`). **Validación completa previa** antes de
abrir SQLite: `plan` no-dict → `TypeError`; claves obligatorias
faltantes → `ValueError`; `carpeta` texto no vacío; `a_incorporar` no
texto e iterable; `ya_sincronizados`/`candidatos_a_eliminar` como
colecciones de nombres (`_coleccion_nombres`); los registros se validan
también dentro de `guardar_videos` antes de SQLite. **No destructivo**:
no elimina registros, no modifica `ya_sincronizados` ni los
preexistentes sincronizados y no aplica `candidatos_a_eliminar` (solo
informa su cantidad). Devuelve `{"incorporados", "nombres",
"pendientes_eliminacion"}`. No está integrada al pipeline ni a la
interfaz y no ejecuta escaneo/FFprobe/FFmpeg/miniaturas/subprocesos.
Pendiente: la eliminación controlada de `candidatos_a_eliminar`, su
integración asíncrona y la deduplicación de nombres repetidos. Con suite
nueva `prueba_aplicar_incorporaciones.py` (15 pruebas). Aprobada.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Aplicación de incorporaciones del plan de sincronización:
`aplicar_incorporaciones(plan, ruta_db=None)` en `escanear_videos.py`
(capa de catálogo, ubicada entre `preparar_plan_sincronizacion` y
`listar_videos_paginado`). Recibe el plan `{"carpeta", "a_incorporar",
"ya_sincronizados", "candidatos_a_eliminar"}` y persiste **únicamente**
`a_incorporar`, delegando en `guardar_videos` (misma transacción
atómica: un solo `connect`, todos los upserts, un solo `commit`,
`rollback` total ante fallos y `close` en `finally`). **Validación
completa previa** antes de abrir SQLite: `plan` no-dict → `TypeError`;
claves obligatorias faltantes (`carpeta`, `a_incorporar`,
`ya_sincronizados`, `candidatos_a_eliminar`) → `ValueError`; `carpeta`
texto no vacío → `ValueError`; `a_incorporar` no texto e iterable →
`TypeError`; `ya_sincronizados`/`candidatos_a_eliminar` como colecciones
de nombres (`_coleccion_nombres`); los registros de `a_incorporar` se
validan también dentro de `guardar_videos` (`_validar_registro_video`)
antes de SQLite. **No destructivo**: no elimina registros, no modifica
`ya_sincronizados` ni los preexistentes sincronizados y **no aplica
`candidatos_a_eliminar`** (solo informa su cantidad). Devuelve el
resultado simple y estable `{"incorporados", "nombres",
"pendientes_eliminacion"}`. No ejecuta escaneo/FFprobe/FFmpeg/
miniaturas/subprocesos y **no está integrada todavía al pipeline ni a la
interfaz**. **Ausencia deliberada**: la eliminación controlada de
`candidatos_a_eliminar` y la deduplicación de nombres repetidos
continúan pendientes. Con suite nueva `prueba_aplicar_incorporaciones.py`
(15 pruebas). Aprobada.

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
-   Preparación del plan de sincronización del catálogo
    (`preparar_plan_sincronizacion`; pura, sin SQLite/FFprobe/FFmpeg/
    pipeline/interfaz; candidatos a eliminación informativos; la
    deduplicación de nombres repetidos queda pendiente).
-   Aplicación de incorporaciones del plan de sincronización
    (`aplicar_incorporaciones`; valida el plan completo antes de abrir
    SQLite, persiste únicamente `a_incorporar` reutilizando
    `guardar_videos` con su atomicidad existente, no elimina
    `candidatos_a_eliminar`, no modifica `ya_sincronizados`; devuelve
    `incorporados`/`nombres`/`pendientes_eliminacion`; sin pipeline/
    interfaz/escaneo/FFprobe/FFmpeg; la eliminación controlada queda
    pendiente).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaMiniaturas`
→ `combinar_registros_con_miniaturas` → `TareaGuardarVideos`) ya
convierte los archivos detectados por la interfaz en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, la **detección de diferencias** disco ↔
BD ya existe de forma no destructiva (`detectar_diferencias`), el
**plan de sincronización** ya se prepara de forma pura
(`preparar_plan_sincronizacion`, sin efectos ni integración) y la
**aplicación de las incorporaciones** ya existe de forma no destructiva
(`aplicar_incorporaciones`: valida el plan antes de abrir SQLite y
persiste únicamente `a_incorporar` reutilizando `guardar_videos`), pero
la **sincronización completa** —la **eliminación controlada de los
registros ausentes** (`candidatos_a_eliminar`) y su integración
asíncrona— sigue pendiente. La carga inicial asíncrona de la primera
página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización completa SQLite asíncrona (la detección de diferencias
    ya existe en `detectar_diferencias` —solo lectura, por nombre—, el
    plan ya se prepara en `preparar_plan_sincronizacion` —puro, sin
    efectos— y las incorporaciones ya se aplican en
    `aplicar_incorporaciones` —no destructivo, reutilizando
    `guardar_videos`—; falta la **eliminación controlada de los registros
    ausentes** (`candidatos_a_eliminar`) y su integración asíncrona).
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
con metadatos FFprobe y miniaturas y los escribe, y existen la detección
no destructiva de diferencias (`detectar_diferencias`), el plan de
sincronización preparado de forma pura (`preparar_plan_sincronizacion`,
con `candidatos_a_eliminar` únicamente informativos) y la aplicación
no destructiva de las incorporaciones (`aplicar_incorporaciones`, que
persiste solo `a_incorporar` reutilizando `guardar_videos`), pero la
sincronización completa sigue pendiente (eliminación controlada de
registros ausentes, con su integración asíncrona); - `detectar_diferencias` compara
por nombre y no detecta movimientos ni renombrados (queda para etapas
futuras); - **no existe todavía deduplicación de nombres repetidos** en
el plan de sincronización; - el enrutado de resultados por
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

**Eliminación controlada de registros ausentes** (aplicar de forma
controlada los `candidatos_a_eliminar` del plan de sincronización, con
su integración asíncrona). Las etapas anteriores (detección no
destructiva de diferencias con `detectar_diferencias`, preparación del
plan con `preparar_plan_sincronizacion` y aplicación no destructiva de
las incorporaciones con `aplicar_incorporaciones`) quedaron aprobadas y
commiteadas; la **eliminación controlada de los registros ausentes**
(`candidatos_a_eliminar`, con su integración asíncrona) sigue pendiente
y se abordará como próxima etapa, manteniendo el alcance limitado: sin
selección inteligente, sin múltiples miniaturas, sin eliminación de
archivos antiguos y sin recarga automática de la interfaz.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
