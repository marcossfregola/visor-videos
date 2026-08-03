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
la interfaz) y **eliminación controlada de los candidatos ausentes del
catálogo** (`eliminar_candidatos(plan, ruta_db=None)` en
`escanear_videos.py`: recibe el plan completo, valida antes de abrir
SQLite, elimina únicamente los registros de `candidatos_a_eliminar` con
una única transacción atómica —`rowcount` por candidato, un solo
`commit`, rollback total, `close` en `finally`—, no elimina archivos
físicos ni miniaturas, no toca `a_incorporar` ni `ya_sincronizados`,
devuelve `eliminados`/`nombres`/`incorporados` (informativo, derivado
del plan y puede ser `None`)/`restantes` y no está integrada al pipeline
ni a la interfaz) y **sincronización asíncrona del catálogo**
(`TareaSincronizacionCatalogo` en `tareas_videos.py`: orquesta en un
`QThread` la secuencia completa `detectar_diferencias` →
`preparar_plan_sincronizacion` → `aplicar_incorporaciones` →
`eliminar_candidatos`; las propiedades `carpeta`/`ruta_db` devuelven
directamente los valores actualmente inmutables (`str` o `None`) del
constructor; el `parent` es un padre Qt compatible con `QObject`; la
tarea no contiene SQL, no abre SQLite directamente, no almacena
conexiones, no usa `check_same_thread=False`, no ejecuta
FFprobe/FFmpeg/miniaturas/subprocesos ni accede a la interfaz; las
incorporaciones y la eliminación son transacciones independientes —si
falla la incorporación no se elimina, y si falla la eliminación las
incorporaciones confirmadas permanecen—; devuelve
`{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`)
y **la integración de la sincronización completa en la interfaz**
(`visor_videos.py` lanza `TareaSincronizacionCatalogo` con el mismo
`GestorTareas` **tras el guardado exitoso** del pipeline escaneo → FFprobe
→ miniaturas → guardado: `_sincronizacion_pendiente`/`tarea_sincronizacion`/
`resultado_sincronizacion`, mensajes `MENSAJE_SINCRONIZANDO`/
`MENSAJE_ERROR_SINCRONIZACION` y resumen final "Sincronización completa: N
incorporados, M eliminados, K candidatos restantes"; los registros ausentes
del disco se eliminan de SQLite y los presentes conservan intactos sus
metadatos FFprobe y `cantidad_miniaturas`; no se eliminan archivos físicos
ni miniaturas, no se recargan ni reconstruyen tarjetas y la GUI no abre
SQLite ni ejecuta SQL; la sincronización no se inicia si falla una fase
anterior y la interfaz queda recuperable tras éxito o error) aprobadas;
pendiente la **recarga asíncrona del catálogo con la actualización de
tarjetas tras una sincronización exitosa** (las tarjetas siguen mostrando
la carga inicial) y la deduplicación de nombres repetidos.

## Último commit aprobado

**Mensaje:** Integrar sincronización completa en la interfaz

**Etapa aprobada:** Integración de la sincronización completa en la
interfaz: `visor_videos.py` lanza `TareaSincronizacionCatalogo` con el
mismo `GestorTareas` **tras el guardado exitoso** del pipeline escaneo →
FFprobe → miniaturas → guardado (`TareaEscaneo` → `TareaFFprobe` →
`TareaMiniaturas` → `TareaGuardarVideos` → `TareaSincronizacionCatalogo`).
`_al_resultado_guardado` marca `_sincronizacion_pendiente = True` y
`_al_tarea_finalizada` (gestor `inactivo`) inicia la sincronización con
`_iniciar_sincronizacion()` (revalida la carpeta con `os.path.isdir` y
crea `TareaSincronizacionCatalogo(carpeta_seleccionada, ruta_db)`). Se
incorporan los atributos `_sincronizacion_pendiente`/`tarea_sincronizacion`/
`resultado_sincronizacion`, los handlers `_al_resultado_sincronizacion`/
`_al_error_sincronizacion`, las constantes `MENSAJE_SINCRONIZANDO`/
`MENSAJE_ERROR_SINCRONIZACION` y la función `texto_resumen_sincronizacion()`
(estado final "Sincronización completa: N incorporados, M eliminados, K
candidatos restantes"). Al terminar, los registros ausentes del disco se
eliminan de SQLite (`eliminar_candidatos` dentro de la tarea) y los
presentes **conservan intactos** sus metadatos FFprobe y
`cantidad_miniaturas`; **no se eliminan archivos físicos ni miniaturas**;
**no se recargan ni reconstruyen tarjetas** (siguen mostrando la carga
inicial); la GUI **no abre SQLite ni ejecuta SQL** (AST: sin `sqlite3`/
`connect` y sin las funciones de sincronización en la interfaz). La
sincronización **solo se lanza tras un guardado exitoso** (no se inicia si
falla cualquier fase anterior) y, ante un error de sincronización, la
interfaz queda recuperable con `MENSAJE_ERROR_SINCRONIZACION` y un nuevo
escaneo posible. Se agregó `prueba_sincronizacion_interfaz.py` (18
pruebas) y se actualizaron `prueba_escaneo_guardado.py` (24) y
`prueba_escaneo_interfaz.py` (36) a la cadena de 5 tareas. Regresiones
completas 355/355 OK. **Alcance**: la recarga asíncrona del catálogo con
la actualización de tarjetas tras la sincronización y la deduplicación de
nombres repetidos quedan pendientes. Aprobada con observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Integración de la sincronización completa en la interfaz: `visor_videos.py`
lanza `TareaSincronizacionCatalogo` con el **mismo** `GestorTareas`
**tras el guardado exitoso** del pipeline escaneo → FFprobe → miniaturas →
guardado (`TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas` →
`TareaGuardarVideos` → `TareaSincronizacionCatalogo`). `_al_resultado_guardado`
marca `_sincronizacion_pendiente = True` y `_al_tarea_finalizada` (gestor
`inactivo`) inicia la sincronización con `_iniciar_sincronizacion()`
(revalida la carpeta con `os.path.isdir` y crea la tarea con
`carpeta_seleccionada` y `ruta_db`). Estados nuevos
`_sincronizacion_pendiente`/`tarea_sincronizacion`/`resultado_sincronizacion`,
handlers `_al_resultado_sincronizacion` (conserva el resultado completo
`{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`
y muestra el resumen final) y `_al_error_sincronizacion` (muestra
`MENSAJE_ERROR_SINCRONIZACION`, gestor `inactivo`, interfaz recuperable),
constantes `MENSAJE_SINCRONIZANDO`/`MENSAJE_ERROR_SINCRONIZACION` y la
función `texto_resumen_sincronizacion()` (estado final "Sincronización
completa: N incorporados, M eliminados, K candidatos restantes"). Al
terminar, los registros ausentes del disco se eliminan de SQLite y los
presentes **conservan intactos** sus metadatos FFprobe y
`cantidad_miniaturas`; **no se eliminan archivos físicos ni miniaturas**;
**no se recargan ni reconstruyen tarjetas** (siguen mostrando la carga
inicial); la GUI **no abre SQLite ni ejecuta SQL** (AST). La sincronización
**solo se lanza tras un guardado exitoso** (no se inicia si falla cualquier
fase anterior). **Ausencia deliberada**: la recarga asíncrona del catálogo
con la actualización de tarjetas tras una sincronización exitosa y la
deduplicación de nombres repetidos continúan pendientes. Con suite nueva
`prueba_sincronizacion_interfaz.py` (18 pruebas) y suites actualizadas
`prueba_escaneo_guardado.py` (24) y `prueba_escaneo_interfaz.py` (36) a la
cadena de 5 tareas. Regresiones completas 355/355 OK. Aprobada con
observaciones.

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
    interfaz/escaneo/FFprobe/FFmpeg).
-   Eliminación controlada de candidatos ausentes del plan de
    sincronización (`eliminar_candidatos`; recibe el plan completo,
    valida antes de abrir SQLite con `_validar_plan_sincronizacion`
    (compartida con `aplicar_incorporaciones`), elimina únicamente los
    registros de `candidatos_a_eliminar` con una única transacción
    atómica (`rowcount` por candidato, un solo `commit`, rollback total,
    `close` en `finally`), no elimina archivos físicos ni miniaturas ni
    toca `a_incorporar`/`ya_sincronizados`; devuelve
    `eliminados`/`nombres`/`incorporados` (informativo, puede ser
    `None`)/`restantes`; sin pipeline/interfaz/escaneo/FFprobe/FFmpeg/
    `conectar_bd`/`guardar_videos`; la integración asíncrona queda
    pendiente).
-   Sincronización asíncrona del catálogo (`TareaSincronizacionCatalogo`
    en `tareas_videos.py`; encadena en un `QThread` la secuencia
    `detectar_diferencias` → `preparar_plan_sincronizacion` →
    `aplicar_incorporaciones` → `eliminar_candidatos` importando
    `escanear_videos` como módulo; `parent` compatible con `QObject`;
    propiedades `carpeta`/`ruta_db` que devuelven directamente los
    valores actualmente inmutables del constructor; sin SQL, sin abrir
    SQLite directamente, sin conexiones almacenadas, sin
    `check_same_thread=False`, sin FFprobe/FFmpeg/miniaturas/
    subprocesos/interfaz; incorporación y eliminación como transacciones
    independientes; devuelve `{"diferencias", "plan", "incorporaciones",
    "eliminaciones", "resumen"}`).
-   Integración de la sincronización completa en la interfaz
    (`visor_videos.py` lanza `TareaSincronizacionCatalogo` con el mismo
    `GestorTareas` **tras el guardado exitoso** del pipeline escaneo →
    FFprobe → miniaturas → guardado; estados
    `_sincronizacion_pendiente`/`tarea_sincronizacion`/
    `resultado_sincronizacion`, handlers `_al_resultado_sincronizacion`/
    `_al_error_sincronizacion`, constantes `MENSAJE_SINCRONIZANDO`/
    `MENSAJE_ERROR_SINCRONIZACION` y `texto_resumen_sincronizacion()`;
    al terminar elimina de SQLite los registros ausentes del disco,
    conserva intactos los metadatos FFprobe y `cantidad_miniaturas` de
    los presentes, **no elimina archivos físicos ni miniaturas**, **no
    recarga ni reconstruye tarjetas** y **no abre SQLite ni ejecuta SQL**
    desde la GUI; la sincronización solo se lanza tras un guardado
    exitoso y la interfaz queda recuperable tras éxito o error).
-   Pruebas automatizadas.

### En desarrollo

La sincronización completa del catálogo ya está integrada en la interfaz:
el pipeline (`TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas` →
`TareaGuardarVideos`) convierte los archivos detectados en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, y tras el guardado exitoso se lanza
`TareaSincronizacionCatalogo` (detección de diferencias
`detectar_diferencias`, preparación del plan
`preparar_plan_sincronizacion`, aplicación de incorporaciones
`aplicar_incorporaciones` y eliminación controlada de ausentes
`eliminar_candidatos`) con el mismo `GestorTareas`, que elimina de SQLite
los registros ausentes y conserva los presentes. Queda pendiente la
**recarga asíncrona del catálogo con la actualización de tarjetas tras una
sincronización exitosa** (las tarjetas siguen mostrando la carga inicial)
y la **deduplicación de nombres repetidos**. La carga inicial asíncrona de
la primera página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Recarga asíncrona del catálogo con la actualización de tarjetas tras
    una sincronización exitosa (la sincronización completa ya está
    integrada en la interfaz: `visor_videos.py` lanza
    `TareaSincronizacionCatalogo` con el mismo `GestorTareas` tras el
    guardado exitoso del pipeline, eliminando de SQLite los registros
    ausentes y conservando los presentes, pero las **tarjetas siguen
    mostrando la carga inicial**; falta recargar el catálogo en segundo
    plano y reconstruir/actualizar las tarjetas tras la sincronización,
    junto con la deduplicación de nombres repetidos).
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
con metadatos FFprobe y miniaturas y los escribe, y la **sincronización
completa ya está integrada en la interfaz** (`visor_videos.py` lanza
`TareaSincronizacionCatalogo` tras el guardado exitoso, que encadena en
un `QThread` la detección no destructiva de diferencias
(`detectar_diferencias`), el plan preparado de forma pura
(`preparar_plan_sincronizacion`, con `candidatos_a_eliminar`
únicamente informativos), la aplicación no destructiva de las
incorporaciones (`aplicar_incorporaciones`, que persiste solo
`a_incorporar` reutilizando `guardar_videos`) y la eliminación
controlada de los registros ausentes (`eliminar_candidatos`, con
validación previa y transacción atómica)), pero las **tarjetas siguen
mostrando la carga inicial**: falta la recarga asíncrona del catálogo
con la actualización de tarjetas tras una sincronización exitosa (junto
con la deduplicación de nombres repetidos); - `detectar_diferencias` compara
por nombre y no detecta movimientos ni renombrados (queda para etapas
futuras); - **no existe todavía deduplicación de nombres repetidos** en
el plan de sincronización; - el enrutado de resultados por
`_escaneo_pendiente`/`_ffprobe_pendiente`/`_miniaturas_pendiente`/
`_guardado_pendiente`/`_sincronizacion_pendiente` es suficiente para una
única tarea activa y debe revisarse si la interfaz incorpora más tipos de tarea; - el escaneo no
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

**Recarga asíncrona del catálogo con la actualización de tarjetas tras
una sincronización exitosa** (recargar el catálogo en segundo plano y
reconstruir/actualizar las tarjetas cuando `TareaSincronizacionCatalogo`
termina correctamente, con su deduplicación de nombres repetidos). Las
etapas anteriores (detección no destructiva de diferencias con
`detectar_diferencias`, preparación del plan con
`preparar_plan_sincronizacion`, aplicación no destructiva de las
incorporaciones con `aplicar_incorporaciones`, eliminación controlada de
los registros ausentes con `eliminar_candidatos`, la orquestación
asíncrona con `TareaSincronizacionCatalogo` y la integración de la
sincronización completa en la interfaz) quedaron aprobadas y
commiteadas; la **recarga asíncrona del catálogo con la actualización de
tarjetas tras la sincronización** y la deduplicación de nombres repetidos
siguen pendientes y se abordarán como próxima etapa, manteniendo el
alcance limitado: sin selección inteligente, sin múltiples miniaturas,
sin eliminación de archivos antiguos y sin recarga automática
inmediata más allá de la sincronización completada.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
