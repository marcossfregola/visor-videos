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
ejecuta FFmpeg ni genera miniaturas) y **pipeline escaneo → tamaños →
FFprobe → miniaturas → guardado** (`TareaEscaneo` →
`TareaTamanosArchivos` → `TareaFFprobe` →
`combinar_registros_con_ffprobe` → `TareaMiniaturas` →
`combinar_registros_con_miniaturas` → `combinar_registros_con_tamanos`
→ `TareaGuardarVideos`, encadenado desde la interfaz con el mismo gestor;
los archivos detectados se guardan en SQLite con el tamaño de archivo,
metadatos FFprobe (duración, resolución, codec; `NULL` ante
vacíos/incompletos/fallos individuales) y cantidad de miniaturas por
video mediante el upsert transaccional existente, conservando los
registros preexistentes), **detección no destructiva de
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
`GestorTareas` **tras el guardado exitoso** del pipeline escaneo → tamaños
→ FFprobe → miniaturas → guardado: `_sincronizacion_pendiente`/`tarea_sincronizacion`/
`resultado_sincronizacion`, mensajes `MENSAJE_SINCRONIZANDO`/
`MENSAJE_ERROR_SINCRONIZACION` y resumen final "Sincronización completa: N
incorporados, M eliminados, K candidatos restantes"; los registros ausentes
del disco se eliminan de SQLite y los presentes conservan intactos sus
metadatos FFprobe y `cantidad_miniaturas`; no se eliminan archivos físicos
ni miniaturas y la GUI no abre SQLite ni ejecuta SQL; la sincronización no
se inicia si falla una fase anterior y la interfaz queda recuperable tras
éxito o error) y **la recarga asíncrona del catálogo tras la
sincronización** (`visor_videos.py` recarga la primera página del catálogo
con la **misma** `TareaLecturaCatalogoPaginada`/`GestorTareas` **solo tras
una sincronización exitosa** y reemplaza las tarjetas con
`_reemplazar_tarjetas` —libera las tarjetas viejas (`removeWidget` +
`deleteLater`), vacía `self.tarjetas`, crea las nuevas en la misma grilla y
reaplica el filtro, conservando `resultado_sincronizacion`; ante un error
de recarga conserva las tarjetas viejas, muestra `MENSAJE_ERROR_RECARGA` y
no revierte la sincronización ya confirmada; sin FFprobe/FFmpeg/miniaturas
 y sin SQL en la GUI—) y **la carga manual de una página adicional del
catálogo** (`visor_videos.py` agrega una página más con el botón "Cargar
más" —`boton_cargar_mas`/`cargar_mas`— con la **misma**
`TareaLecturaCatalogoPaginada`/`GestorTareas` y `OFFSET = len(self.tarjetas)`,
**agregando** tarjetas nuevas debajo de las existentes sin reemplazarlas
ni duplicarlas, actualizando `_total_catalogo` y rearmando el botón según
las tarjetas por cargar; ante un error de página conserva las tarjetas ya
cargadas y muestra `MENSAJE_ERROR_PAGINA`; sin SQL en la GUI—) y **la
presentación del catálogo en filas horizontales** (`visor_videos.py` muestra
una **tarjeta horizontal por video** —miniatura a la izquierda y cinco campos
de texto a la derecha— dispuesta **una por fila en una única columna** dentro
del `QScrollArea`; se elimina la grilla de 2 columnas, la constante
`COLUMNAS` y `setColumnStretch(1, 1)`; `_crear_tarjetas`/`_agregar_tarjetas`
colocan cada tarjeta en la fila siguiente con columna 0; **solo se muestra la
primera miniatura por video**, sin 4/6 miniaturas por video y sin generación
progresiva de miniaturas; la **generación progresiva de previews** se incorporó
después en la etapa "Previews progresivas para la Beta 1.0" y la **apertura del
video por doble clic** se incorporó después en la etapa "Apertura del video por
doble clic"; la **persistencia de la última carpeta seleccionada** se incorporó
después en la etapa "Persistencia de la última carpeta seleccionada") y **la
incorporación y visualización del tamaño de los
archivos de video** (`escanear_videos.py` añade `tamano_bytes INTEGER` a
`COLUMNAS_EXTRA` con migración idempotente de bases existentes,
`obtener_tamanos_archivos` y `combinar_registros_con_tamanos`;
`tareas_videos.py` añade `TareaTamanosArchivos`; `visor_videos.py` inserta el
paso de tamaños **entre el escaneo y FFprobe**, extendiendo la cadena a 7
tareas (`TareaEscaneo` → `TareaTamanosArchivos` → `TareaFFprobe` →
`TareaMiniaturas` → `TareaGuardarVideos` → `TareaSincronizacionCatalogo` →
`TareaLecturaCatalogoPaginada`), persiste `tamano_bytes` (NULL si el archivo
no existe o no es legible) y muestra el campo "Tamaño" en cada fila con
`formatear_tamano` en B/KB/MB/GB y "Desconocido" para valores ausentes o
inválidos; suite nueva `prueba_tamano_archivo.py` con 15 pruebas y
correcciones de aislamiento T15/T27 sobre copia de `biblioteca.db`) aprobadas)
y **la generación de previews progresivas por video** (`escanear_videos.py`
define `CANTIDAD_PREVIEWS = 3`, `ruta_preview` (convención
`miniaturas/<prefijo>_preview_NN.jpg`), `_es_archivo_preview`,
`previews_existentes`, `previews_faltantes`, `calcular_tiempo_preview`
(tiempos proporcionales 25/50/75 % con `indice` en 1..3), `generar_preview`
(FFmpeg `-ss`/`-frames:v 1`) y `generar_previews_faltantes` (genera **solo los
índices faltantes**, reutiliza la miniatura principal válida como base si
FFmpeg falla y **nunca sobrescribe ni elimina** archivos); `contar_miniaturas`/
`miniatura_reutilizable`/`miniatura_principal` **excluyen** los archivos
`_preview_`; `tareas_videos.py` añade `TareaPreviewsProgresivas` (genera en
segundo plano en `_trabajo()`); y `visor_videos.py` integra la generación
**progresiva** con un **segundo `GestorTareas` propio** (`gestor_previews`),
cola `_cola_previews`, lotes de `TAMANIO_LOTE_PREVIEWS = 3`, temporizador
`_timer_previews` (300 ms) y **actualización incremental** de cada tarjeta a
medida que llega cada preview (`Tarjeta.actualizar_previews`), apoyándose en
`previews_de`/`previews_existentes`; suite nueva `prueba_previews_progresivas.py`
con **16 pruebas**) y **la apertura del video por doble clic** (`visor_videos.py`
detecta el **doble clic con el botón izquierdo** sobre una tarjeta mediante la
nueva señal `Tarjeta.doble_clic` y la sobrescritura de `mouseDoubleClickEvent`,
y `_abrir_video` invoca el **módulo de servicio nuevo `apertura_videos.py`**
—`abrir_video_con_aplicacion_predeterminada(nombre, carpeta)`, que valida
`nombre`/`carpeta` como texto no vacío (si no → `ValueError`), resuelve la ruta
**absoluta** con `os.path.abspath`/`os.path.isfile` (archivo inexistente →
`FileNotFoundError`) y abre el video con `os.startfile`, siendo el **único punto
del proyecto que ejecuta `os.startfile`**; la conexión a `_abrir_video` se
realiza en `_crear_tarjetas` **y** `_agregar_tarjetas`, de modo que el doble clic
funciona en las tarjetas de la carga inicial y de las páginas adicionales; ante
un fallo de apertura (`ValueError`/`FileNotFoundError`/`OSError`) se muestra
`MENSAJE_ERROR_ABRIR` y la interfaz nunca propaga excepciones; suite nueva
`prueba_doble_clic.py` con **14 pruebas**) y **la persistencia de la última
carpeta seleccionada** (`configuracion.py` es un **servicio de persistencia de
configuración** ajeno a la GUI, a SQLite, a FFprobe/FFmpeg y a `subprocess`:
`CLAVE_CARPETA = "ultima_carpeta"`, `VARIABLE_ENTORNO = "VISOR_CONFIG"`
(redirige la ruta del archivo de configuración y la usan **solo las suites de
prueba** para no tocar el archivo real del usuario; no es una bandera de
depuración), `_resolver_ruta_config(ruta_config)` (orden: `ruta_config`
explícita → entorno `VISOR_CONFIG` → `ruta_configuracion()`),
`guardar_ultima_carpeta(carpeta, ruta_config=None)` (valida texto no vacío
tras `strip()` → `ValueError`; absolutiza y valida con `os.path.isdir` —si no
es un directorio devuelve `None` sin escribir—; **escritura atómica** con
`<ruta>.tmp` + `os.replace` y `os.makedirs(..., exist_ok=True)`) y
`obtener_ultima_carpeta(ruta_config=None)` (ruta absoluta; JSON
ausente/corrupto, clave inválida o carpeta inexistente → `None` sin lanzar);
`rutas.py` añade `ruta_configuracion()` → `configuracion.json` en la raíz;
`visor_videos.py` amplía el constructor a `__init__(self, ruta_db=None,
parent=None, ruta_config=None)`, **restaura** en el arranque
(`obtener_ultima_carpeta(self._ruta_config)`) y **persiste** al seleccionar
(`guardar_ultima_carpeta(ruta_absoluta, self._ruta_config)`); `.gitignore`
ignora `configuracion.json`; los **11 módulos de prueba** añaden
`_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()` + `os.environ["VISOR_CONFIG"]`
para el aislamiento (el archivo real del usuario nunca se toca); suite nueva
`prueba_persistencia_carpeta.py` con **20 pruebas**) aprobadas;
quedan pendientes la **deduplicación de nombres repetidos** y la
**paginación completa** (scroll infinito, búsqueda en SQL desde la
interfaz y ordenamiento configurable), que todavía no existen.

**Separación del punto de entrada de producción y del arnés de smoke
tests** (etapa aprobada y commiteada): `visor_videos.py` `main()` queda
como **bootstrap puro de la interfaz** (solo `QApplication`,
`VisorVideos()`, `resize(900, 600)`, `show()` y `sys.exit(app.exec())`);
el **smoke test se independizó en `prueba_smoke.py`** (arnés de
**ejecución explícita** con `python prueba_smoke.py`, con base SQLite
temporal y las fases de paginación, escaneo + carpeta + sincronización,
previews, doble clic y persistencia) y las cinco suites de interfaz que
lo invocaban por `subprocess` (`prueba_escaneo_interfaz.py`,
`prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`,
`prueba_pagina_siguiente.py`, `prueba_recarga_catalogo.py`) pasan a
llamar a `prueba_smoke.py`. **El arranque normal ya no ejecuta pruebas
automáticamente** y la aplicación queda **preparada para el empaquetado
de la Beta 1.0 sin ejecutar pruebas al iniciar**.

## Último commit aprobado

**Mensaje:** Separar punto de entrada y smoke tests

**Etapa aprobada:** Separación del punto de entrada de producción y del arnés
de smoke tests. `visor_videos.py` `main()` queda como **bootstrap puro de la
interfaz** (solo `QApplication(sys.argv)`, `VisorVideos()`, `resize(900, 600)`,
`show()` y `sys.exit(app.exec())`) y **no ejecuta pruebas al iniciar**; el
**smoke test se independizó en `prueba_smoke.py`** (arnés de **ejecución
explícita** con `python prueba_smoke.py`, con la base SQLite temporal y las
fases de paginación, escaneo + carpeta + sincronización, previews, doble clic
y persistencia; el cuerpo se movió verbatim y el único ajuste es el parcheo de
la fase de doble clic, que ahora apunta a
`visor_videos.abrir_video_con_aplicacion_predeterminada`). Las suites
`prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`,
`prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py` y
`prueba_recarga_catalogo.py` pasan a invocar `prueba_smoke.py` vía `subprocess`.
**El arranque normal ya no ejecuta el smoke test** y la aplicación queda
**preparada para el empaquetado de la Beta 1.0 sin ejecutar pruebas al iniciar**.
Regresiones: 36/36, 26/26, 29/29, 20/20 y 19/20 OK (el T13 de
`prueba_recarga_catalogo.py` es preexistente, reproducido en la línea base;
flakiness de tiempo, no lógico). Aprobada.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Separación del punto de entrada de producción y del arnés de smoke tests:
`visor_videos.py` `main()` queda como **bootstrap puro de la interfaz** (solo
`QApplication(sys.argv)`, `VisorVideos()`, `resize(900, 600)`, `show()` y
`sys.exit(app.exec())`) y **no ejecuta pruebas al iniciar**. El **smoke test se
independizó en `prueba_smoke.py`** (arnés de **ejecución explícita** con
`python prueba_smoke.py`), con:
- El mismo cuerpo del smoke test anterior, movido verbatim: base SQLite temporal
  reutilizando el esquema existente (`conectar_bd(ruta_db)`) y las fases de
  **paginación** (150 registros → `primera_pagina=100`, "Cargar más" →
  `total_tras_cargar_mas=150`, `duplicados_tras_cargar_mas=0`),
  **escaneo + carpeta + sincronización** (`videos_detectados=3`,
  `guardado_total=3`, `resumen_sincronizacion` sin incorporados/eliminados),
  **previews progresivos** (carpeta real `videos_prueba/`, gestor `inactivo`),
  **doble clic** (`QTest.mouseDClick` con `abrir_video_con_aplicacion_predeterminada`
  parcheado) y **persistencia** (configuración temporal `VISOR_CONFIG` con
  `persistencia_restaurada`).
- Ejecución **solo a demanda** (`python prueba_smoke.py`); la aplicación normal
  no lo ejecuta al iniciar.
- Las suites de interfaz `prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`,
  `prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py` y
  `prueba_recarga_catalogo.py` pasan a invocar `prueba_smoke.py` vía `subprocess`
  (en lugar de `visor_videos.py`).

**Consecuencia**: el arranque normal (`python visor_videos.py`) ya no ejecuta
pruebas automáticamente y la aplicación queda **preparada para el empaquetado de
la Beta 1.0**. Se resolvió la deuda futura de la etapa 15 (el smoke test debía
separarse del arranque normal antes de distribuir una beta). Regresiones: 36/36,
26/26, 29/29, 20/20 y 19/20 OK (el T13 de `prueba_recarga_catalogo.py` es
preexistente, reproducido en la línea base; flakiness de tiempo, no lógico).
**Sin cambios en los datos reales** (`biblioteca.db`, `miniaturas/` y
`videos_prueba/` intactos) y sin avisos `QThread: Destroyed`. Aprobada.

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
    tamaños → FFprobe → miniaturas → guardado; estados
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
-   Recarga asíncrona del catálogo tras la sincronización
    (`visor_videos.py` recarga la primera página con la **misma**
    `TareaLecturaCatalogoPaginada`/`GestorTareas` **solo tras una
    sincronización exitosa** y reemplaza las tarjetas con
    `_reemplazar_tarjetas`: estados `_recarga_catalogo_pendiente`/
    `tarea_recarga_catalogo`, handlers `_al_resultado_recarga`/
    `_al_error_recarga`, constante `MENSAJE_ERROR_RECARGA` y factoría
    `_crear_tarea_lectura`; las tarjetas viejas se conservan hasta el
    resultado válido y completo, luego se liberan (`removeWidget` +
    `deleteLater`), se vacía `self.tarjetas`, se crean las nuevas en la
    **misma grilla y el mismo `QScrollArea` reutilizados** y se reaplica
    el filtro — sin tarjetas ocultas obsoletas —; `resultado_sincronizacion`
    se conserva; ante un error de recarga se conservan las tarjetas viejas,
    se muestra `MENSAJE_ERROR_RECARGA`, el gestor queda `INACTIVO`, el botón
     de escaneo se rehabilita y **no se revierte la sincronización ya
     confirmada en SQLite**; fase de solo lectura de la primera página sin
     FFprobe/FFmpeg/miniaturas y sin SQL en la GUI).
-   Carga manual de una página adicional del catálogo (`visor_videos.py`
    agrega una página más con el botón "Cargar más" —`boton_cargar_mas`/
    `cargar_mas`— con la **misma** `TareaLecturaCatalogoPaginada`/
    `GestorTareas` y `OFFSET = len(self.tarjetas)`; `_crear_tarea_lectura
    (desplazamiento)` parametrizada; estados `_pagina_pendiente`/
    `tarea_pagina` y `_total_catalogo`; handlers `_al_resultado_pagina`
    (agrega tarjetas con `_agregar_tarjetas` en la misma grilla sin
    liberar las existentes y sin duplicados por `nombre`) y
    `_al_error_pagina` (conserva las tarjetas ya cargadas, muestra
    `MENSAJE_ERROR_PAGINA` y rearma el botón); botón habilitado solo con
    carga inicial terminada, `_total_catalogo` conocido, tarjetas por
    cargar y gestor inactivo sin cadena activa; sin SQL en la GUI; el
    reemplazo de tarjetas sigue siendo exclusivo de la recarga tras la
    sincronización).
-   Presentación del catálogo en filas horizontales (`visor_videos.py`
    muestra una **tarjeta horizontal por video** —`Tarjeta` con
    `QHBoxLayout`, miniatura o recuadro "Sin miniatura" a la izquierda y
    columna derecha `columna_campos = QVBoxLayout()` con los cinco campos
    (nombre, duración, resolución, codec, miniaturas) vía
    `layout.addLayout(columna_campos, 1)`— dispuesta **una por fila en una
    única columna**; se elimina la constante `COLUMNAS = 2` y
    `setColumnStretch(1, 1)`; `_crear_tarjetas`/`_agregar_tarjetas`
    agregan cada tarjeta en la fila siguiente con columna 0;
     `_reemplazar_tarjetas` libera las anteriores (`removeWidget` +
     `deleteLater`) y reconstruye; la recarga sigue siendo la única vía que
     reemplaza tarjetas; **solo se muestra la primera miniatura por video**,
     sin 4/6 miniaturas por video y sin generación progresiva de miniaturas
     (la **apertura por doble clic** **se incorporó después** en la etapa
     "Apertura del video por doble clic"); la **persistencia de la última
     carpeta seleccionada** **se incorporó después** en la etapa
     "Persistencia de la última carpeta seleccionada";
     suite `prueba_filas_horizontales.py` con 16 pruebas; datos reales
     intactos).
-   Incorporación y visualización del tamaño de los archivos de video
    (`escanear_videos.py` añade `("tamano_bytes", "INTEGER")` a
    `COLUMNAS_EXTRA` con migración idempotente de bases existentes,
    incorpora `obtener_tamanos_archivos(videos, carpeta)` y
    `combinar_registros_con_tamanos(registros, resultado_tamanos)`;
    `tareas_videos.py` añade `TareaTamanosArchivos`; `visor_videos.py`
    inserta el paso de tamaños **entre el escaneo y FFprobe** —cadena de 7
    tareas con el mismo `GestorTareas`—, persiste `tamano_bytes` (NULL si
    el archivo no existe o no es legible) y muestra el campo "Tamaño" en
    cada fila con `formatear_tamano` (B/KB/MB/GB; "Desconocido" para
    valores ausentes o inválidos); `listar_videos`/`listar_videos_paginado`
    devuelven tuplas de siete campos; suite `prueba_tamano_archivo.py` con
    15 pruebas; aislamiento T15/T27 sobre copia de `biblioteca.db`; datos
    reales intactos).
-   Previews progresivas para la Beta 1.0 (`escanear_videos.py` define
    `CANTIDAD_PREVIEWS = 3` y añade `ruta_preview` (convención
    `miniaturas/<prefijo>_preview_NN.jpg`), `_es_archivo_preview`,
    `previews_existentes`, `previews_faltantes`, `calcular_tiempo_preview`
    (proporcional 25/50/75 %), `generar_preview` (FFmpeg) y
    `generar_previews_faltantes` (genera solo los índices faltantes; ante
    un fallo reutiliza la miniatura principal válida como base; nunca
    sobrescribe ni elimina); `contar_miniaturas`/`miniatura_reutilizable`/
    `miniatura_principal` excluyen los archivos `_preview_`;
    `tareas_videos.py` añade `TareaPreviewsProgresivas`; `visor_videos.py`
    integra la generación progresiva con un **segundo `GestorTareas`**
    (`gestor_previews`), cola `_cola_previews`, lotes de
    `TAMANIO_LOTE_PREVIEWS = 3`, temporizador `_timer_previews` (300 ms) y
    actualización incremental de cada tarjeta (`Tarjeta.actualizar_previews`);
    suite `prueba_previews_progresivas.py` con 16 pruebas; datos reales
    intactos).
-   Apertura del video por doble clic (`visor_videos.py` detecta el
    **doble clic con el botón izquierdo** sobre una tarjeta con la señal
    `Tarjeta.doble_clic = Signal(str)` y la sobrescritura de
    `mouseDoubleClickEvent`; `_abrir_video(nombre)` invoca el **módulo de
    servicio `apertura_videos.py`** —`abrir_video_con_aplicacion_predeterminada
    (nombre, carpeta)`: valida `nombre`/`carpeta` como texto no vacío
    (`ValueError`), resuelve la ruta absoluta con
    `os.path.abspath`/`os.path.isfile` (`FileNotFoundError`) y abre con
    `os.startfile`, siendo el **único punto del proyecto que ejecuta
    `os.startfile`**—; ante un fallo de apertura muestra `MENSAJE_ERROR_ABRIR`
    y no propaga excepciones; conexión en `_crear_tarjetas` y
    `_agregar_tarjetas` (carga inicial y páginas adicionales); suite
    `prueba_doble_clic.py` con 14 pruebas, incluido el AST de
    `visor_videos.py` con cero referencias a `os.path.isfile`/`os.startfile`;
    datos reales intactos).
-   Persistencia de la última carpeta seleccionada (`configuracion.py` es un
    **servicio de persistencia de configuración** ajeno a la GUI/SQLite/
    FFprobe/FFmpeg/`subprocess`: `CLAVE_CARPETA = "ultima_carpeta"`,
    `VARIABLE_ENTORNO = "VISOR_CONFIG"` (redirige la ruta del archivo de
    configuración; la usan solo las suites de prueba para no tocar el archivo
    real del usuario), `_resolver_ruta_config` (orden: `ruta_config` explícita
    → entorno `VISOR_CONFIG` → `ruta_configuracion()`),
    `guardar_ultima_carpeta(carpeta, ruta_config=None)` (valida texto no
    vacío → `ValueError`; absolutiza y valida con `os.path.isdir`; si no es un
    directorio devuelve `None` sin escribir; **escritura atómica** con
    `<ruta>.tmp` + `os.replace` y `os.makedirs(..., exist_ok=True)`) y
    `obtener_ultima_carpeta(ruta_config=None)` (ruta absoluta; JSON
    ausente/corrupto, clave inválida o carpeta inexistente → `None` sin
    lanzar ni crear el archivo); `rutas.py` añade `ruta_configuracion()` →
    `configuracion.json` en la raíz; `visor_videos.py` amplía el constructor a
    `ruta_config`, **restaura** en el arranque (`obtener_ultima_carpeta`) y
    **persiste** al seleccionar (`guardar_ultima_carpeta`); `.gitignore`
    ignora `configuracion.json`; los 11 módulos de prueba añaden
    `_CONFIG_TEMPORAL` + `VISOR_CONFIG` (aislamiento; el archivo real del
    usuario nunca se toca); suite `prueba_persistencia_carpeta.py` con 20
    pruebas; datos reales intactos).
-   Separación del punto de entrada de producción del arnés de smoke tests
    (`visor_videos.py` `main()` queda como **bootstrap puro de la interfaz**,
    sin ejecutar pruebas; el smoke test se independizó en `prueba_smoke.py`,
    arnés de ejecución explícita con `python prueba_smoke.py`; las cinco
    suites de interfaz que invocaban el smoke por `subprocess` pasan a llamar
    a `prueba_smoke.py`; el arranque normal ya no ejecuta pruebas y la app
    queda preparada para el empaquetado de la Beta).
-   Pruebas automatizadas.

### En desarrollo

La sincronización completa del catálogo ya está integrada en la interfaz:
el pipeline (`TareaEscaneo` → `TareaTamanosArchivos` → `TareaFFprobe` →
`TareaMiniaturas` → `TareaGuardarVideos`) convierte los archivos detectados
en registros con tamaño de archivo, metadatos FFprobe y cantidad de
miniaturas y los escribe en SQLite
conservando los preexistentes, tras el guardado exitoso se lanza
`TareaSincronizacionCatalogo` (detección de diferencias
`detectar_diferencias`, preparación del plan
`preparar_plan_sincronizacion`, aplicación de incorporaciones
`aplicar_incorporaciones` y eliminación controlada de ausentes
`eliminar_candidatos`) con el mismo `GestorTareas`, que elimina de SQLite
los registros ausentes y conserva los presentes, y **tras una
sincronización exitosa se recarga el catálogo en segundo plano**
(`TareaLecturaCatalogoPaginada` con el mismo gestor) y se **reemplazan las
tarjetas** con la primera página actualizada (`_reemplazar_tarjetas`).
Quedan pendientes la **deduplicación de nombres repetidos** y la
**paginación completa automática** del catálogo (scroll infinito, búsqueda
en SQL desde la interfaz y ordenamiento configurable, que todavía no
existen): la carga inicial y la recarga muestran únicamente la primera
página, y **ya existe la carga manual de una página adicional** con el
botón "Cargar más" (se agregan tarjetas debajo de las existentes sin
reemplazarlas). El catálogo se presenta con **una tarjeta horizontal por
video, una fila por video en una única columna**, cada fila **muestra el
tamaño de archivo** (campo "Tamaño" con `formatear_tamano`), cada tarjeta
**muestra tres previews progresivos** generados en segundo plano con un
gestor propio y un **doble clic sobre la tarjeta abre el video** con la
aplicación predeterminada del sistema (módulo `apertura_videos.py` con
`os.startfile`; etapas de presentación, tamaño, previews y doble clic
aprobadas).

## Pendientes prioritarios

1.  Paginación completa del catálogo en la interfaz (páginas posteriores
    con scroll automático/infinito, búsqueda en SQL desde la interfaz y
    ordenamiento configurable). **No existe todavía** la paginación
    automática: la carga inicial y la recarga tras la sincronización
    muestran únicamente la primera página (`TAMANIO_PAGINA_INICIAL = 100`);
    ya existe la **carga manual de una página adicional** con el botón
    "Cargar más" (`visor_videos.py`, con la misma
    `TareaLecturaCatalogoPaginada`/`GestorTareas` y
    `OFFSET = len(self.tarjetas)`, agregando tarjetas sin reemplazarlas
    ni duplicarlas); la recarga tras una sincronización exitosa ya está
    implementada (`visor_videos.py` relee la primera página con la misma
    `TareaLecturaCatalogoPaginada`/`GestorTareas` y reemplaza las tarjetas
    con `_reemplazar_tarjetas`).
2.  Deduplicación de nombres repetidos en el plan de sincronización.
3.  Integración SQLite asíncrona en el pipeline (encadenado).
4.  Actualización asíncrona de la interfaz (tarjetas dinámicas).
5.  FFmpeg asíncrono.
6.  Selección inteligente de miniaturas (la generación de **tres previews
    progresivos por video** ya está implementada).
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
validación previa y transacción atómica)), **tras una sincronización
exitosa se recarga el catálogo en segundo plano** (`visor_videos.py`
relee la primera página con `TareaLecturaCatalogoPaginada` y reemplaza
las tarjetas con `_reemplazar_tarjetas`, liberando las viejas y creando
las nuevas en la misma grilla); quedan pendientes la **paginación
completa automática** (scroll infinito, búsqueda en SQL desde la interfaz
y ordenamiento configurable — no existen todavía; hoy existe la **carga
manual de una página adicional** con el botón "Cargar más") y la
deduplicación de nombres repetidos; - `detectar_diferencias` compara
por nombre y no detecta movimientos ni renombrados (queda para etapas
futuras); - **no existe todavía deduplicación de nombres repetidos** en
el plan de sincronización; - el enrutado de resultados por
`_escaneo_pendiente`/`_tamanos_pendiente`/`_ffprobe_pendiente`/
`_miniaturas_pendiente`/
`_guardado_pendiente`/`_sincronizacion_pendiente`/
`_recarga_catalogo_pendiente`/`_pagina_pendiente` es suficiente para una
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

**Aún no definida**: la etapa de **separación del punto de entrada de
producción y del arnés de smoke tests** ya quedó aprobada y commiteada
("Separar punto de entrada y smoke tests"): el arranque normal (`python
visor_videos.py`) solo inicia la interfaz y **ya no ejecuta pruebas**; el
smoke test se independizó en `prueba_smoke.py` (ejecución explícita) y las
cinco suites de interfaz lo invocan por `subprocess`. La aplicación queda
**preparada para el empaquetado de la Beta 1.0**. No se inicia ninguna etapa
nueva en esta entrega. Los siguientes candidatos (todavía no definidos ni
iniciados por ChatGPT) son la **paginación completa automática del catálogo
en la interfaz** (scroll infinito, búsqueda en SQL desde la interfaz y
ordenamiento configurable) y la **deduplicación de nombres repetidos** en el
plan de sincronización, manteniendo el alcance limitado. Para **Beta 1.0**
quedan pendientes únicamente: el **empaquetado de la Beta**, las **pruebas
sobre una instalación limpia** y la **revisión del mecanismo de búsqueda de
miniaturas** (esta última, posterior a la Beta). La definición de la
siguiente etapa inmediata queda pendiente de aprobación por ChatGPT.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
