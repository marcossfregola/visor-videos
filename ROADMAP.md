# ROADMAP

## Objetivo

Este documento reúne las funcionalidades previstas para el Visor de
Videos. No representa el estado actual del proyecto, sino la dirección
de desarrollo. El orden podrá cambiar según las decisiones
arquitectónicas.

------------------------------------------------------------------------

# Prioridad inmediata

-   Escaneo asíncrono — **completado** (`TareaEscaneo`).
-   Lectura asíncrona del catálogo SQLite — **completado**
    (`TareaLecturaCatalogo`).
-   Lectura paginada del catálogo SQLite — **completado**
    (`listar_videos_paginado` / `TareaLecturaCatalogoPaginada`):
    consulta paginada (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro,
    ambos en SQL, con búsqueda parcial por `LIKE` parametrizada.
-   Integración de la lectura asíncrona paginada con la interfaz —
    **completado** (`visor_videos.py` consume `TareaLecturaCatalogoPaginada`
    mediante `GestorTareas`): la primera página del catálogo se carga en
    segundo plano con estado de carga, manejo de errores y apagado
    ordenado, sin bloquear la ventana.
-   Carga manual de una página adicional del catálogo — **completado**
    (`visor_videos.py` + `TareaLecturaCatalogoPaginada` + `GestorTareas`):
    el botón "Cargar más" (`boton_cargar_mas`/`cargar_mas`) agrega la
    página siguiente con `OFFSET = len(self.tarjetas)`, usando la misma
    tarea de lectura (`_crear_tarea_lectura(desplazamiento)`) y el mismo
    gestor; las tarjetas nuevas se agregan debajo de las existentes sin
    reemplazarlas y sin duplicados (`_agregar_tarjetas`, deduplicación
    por `nombre`), se actualiza `_total_catalogo` y, ante un error de
    página, se conservan las tarjetas ya cargadas y se muestra
    `MENSAJE_ERROR_PAGINA`. El botón se habilita solo con carga inicial
    terminada, tarjetas por cargar y gestor inactivo sin cadena activa.
    La paginación automática (scroll infinito), la búsqueda en SQL desde
    la interfaz y el ordenamiento configurable siguen pendientes.
-   Presentación del catálogo en filas horizontales — **completado**
    (`visor_videos.py` muestra una **tarjeta horizontal por video** en una
    única columna, una fila por video): cada `Tarjeta` usa `QHBoxLayout`
    con la miniatura (o el recuadro "Sin miniatura") a la izquierda y los
    cinco campos (nombre, duración, resolución, codec, miniaturas) a la
    derecha (`columna_campos = QVBoxLayout()`, `addLayout(..., 1)`); se
    elimina la grilla de 2 columnas y la constante `COLUMNAS`.
    **Aclaración de alcance**: sí se muestra la primera miniatura por
    video, pero **no** hay 4/6 imágenes por video y **no** hay generación
    progresiva de miniaturas; el tamaño de archivo por fila **se incorporó
    después** en la etapa "Incorporar y mostrar el tamaño de los archivos
    de video" (ver el siguiente punto), los **tres previews por video con
    generación progresiva** **se incorporaron después** en la etapa
    "Previews progresivas para la Beta 1.0" y la **apertura por doble
    clic** **se incorporó después** en la etapa "Apertura del video por
    doble     clic" (ver más abajo). La **persistencia de la última carpeta
    seleccionada** **se incorporó después** en la etapa "Persistencia de
    la última carpeta seleccionada" (ver más abajo).
-   Mostrar el tamaño de los archivos de video — **completado**
    (`escanear_videos.py` añade `tamano_bytes INTEGER` a `COLUMNAS_EXTRA`
    con migración idempotente e incorpora `obtener_tamanos_archivos`/
    `combinar_registros_con_tamanos`; `tareas_videos.py` añade
    `TareaTamanosArchivos`; `visor_videos.py` inserta el paso de tamaños
    entre el escaneo y FFprobe —cadena de 7 tareas—, persiste
    `tamano_bytes` y muestra el campo "Tamaño" en cada fila con
    `formatear_tamano` en B/KB/MB/GB): **cada fila del catálogo muestra el
    tamaño del archivo de video**. La **apertura por doble clic** **se
    incorporó después** en la etapa "Apertura del video por doble clic"
    (ver más abajo); la **persistencia de la última carpeta** **se
    incorporó después** en la etapa "Persistencia de la última carpeta
    seleccionada" (ver más abajo).
-   Previews progresivas para la Beta 1.0 — **completado**:
    `escanear_videos.py` genera **tres previews por video** con
    **generación progresiva** (`CANTIDAD_PREVIEWS = 3`; convención
    `miniaturas/<prefijo>_preview_NN.jpg`; `ruta_preview`,
    `previews_existentes`, `previews_faltantes`, `calcular_tiempo_preview`,
    `generar_preview` y `generar_previews_faltantes`); `tareas_videos.py`
    añade `TareaPreviewsProgresivas`; `visor_videos.py` integra la
    generación en segundo plano con un `GestorTareas` propio, cola por
    lotes (`TAMANIO_LOTE_PREVIEWS = 3`) y actualización incremental de las
    tarjetas a medida que llega cada preview; la miniatura principal y el
    conteo de miniaturas **excluyen** los archivos `_preview_`. La
    **apertura por doble clic** **se incorporó después** en la etapa
    "Apertura del video por doble clic" (ver el siguiente punto); la
    **persistencia de la última carpeta** **se incorporó después** en la
    etapa "Persistencia de la última carpeta seleccionada" (ver más abajo).
-   Apertura del video por doble clic — **completado**
    (`visor_videos.py` detecta el **doble clic con el botón izquierdo**
    sobre una tarjeta con la señal `Tarjeta.doble_clic = Signal(str)` y la
    sobrescritura de `mouseDoubleClickEvent`; `_abrir_video(nombre)`
    invoca el **módulo de servicio `apertura_videos.py`** con
    `abrir_video_con_aplicacion_predeterminada(nombre, carpeta)` —valida
    `nombre`/`carpeta` como texto no vacío (`ValueError`), resuelve la
    ruta absoluta con `os.path.abspath`/`os.path.isfile`
    (`FileNotFoundError`) y abre el video con `os.startfile`, siendo el
    **único punto del proyecto que ejecuta `os.startfile`**—; ante un
    fallo de apertura (`ValueError`/`FileNotFoundError`/`OSError`) muestra
    `MENSAJE_ERROR_ABRIR` y no propaga excepciones; la conexión a
    `_abrir_video` se realiza en `_crear_tarjetas` **y** `_agregar_tarjetas`,
    de modo que el doble clic funciona en las tarjetas de la carga inicial
    y de las páginas adicionales; suite `prueba_doble_clic.py` con 14
    pruebas, incluido el AST de `visor_videos.py` con cero referencias a
    `os.path.isfile`/`os.startfile`). La **persistencia de la última
    carpeta** **se incorporó después** en la etapa "Persistencia de la
    última carpeta seleccionada" (ver el siguiente punto).
-   Persistencia de la última carpeta seleccionada — **completado**
    (`configuracion.py` es un **servicio de persistencia de configuración**
    ajeno a la GUI, a SQLite, a FFprobe/FFmpeg y a `subprocess`;
    `guardar_ultima_carpeta(carpeta, ruta_config=None)` y
    `obtener_ultima_carpeta(ruta_config=None)` sobre `configuracion.json`
    gitignored): la carpeta elegida se **persiste** y se **restaura
    automáticamente al iniciar** la aplicación. La persistencia está activa
    **por defecto para el usuario final** (`python visor_videos.py` lee y
    escribe el JSON automáticamente, sin banderas); el aislamiento de las
    pruebas usa la **variable de entorno `VISOR_CONFIG`** (redirección de
    ubicación, no una bandera de depuración), que la usan **solo las suites
    de prueba** para no tocar el archivo real del usuario. `configuracion.py`
    define `CLAVE_CARPETA = "ultima_carpeta"`, `VARIABLE_ENTORNO =
    "VISOR_CONFIG"` y `_resolver_ruta_config(ruta_config)` (orden: `ruta_config`
    explícita → entorno `VISOR_CONFIG` → `ruta_configuracion()`);
    `guardar_ultima_carpeta` valida texto no vacío tras `strip()` (`None`,
    `""`, solo espacios o un no-texto → `ValueError`), absolutiza la ruta y la
    valida con `os.path.isdir` (si no es un directorio devuelve `None` sin
    escribir) y escribe de forma **atómica** (`<ruta>.tmp` + `os.replace`,
    `os.makedirs(..., exist_ok=True)`); `obtener_ultima_carpeta` es
    **tolerante** (JSON ausente/corrupto, clave inválida o carpeta inexistente
    → `None` sin lanzar ni crear el archivo). `rutas.py` añade
    `ruta_configuracion()` → `configuracion.json` en la raíz; `visor_videos.py`
    amplía el constructor a `__init__(self, ruta_db=None, parent=None,
    ruta_config=None)`, **restaura** en el arranque y **persiste** al
    seleccionar; los 11 módulos de prueba añaden `_CONFIG_TEMPORAL` +
    `VISOR_CONFIG` para el aislamiento; suite `prueba_persistencia_carpeta.py`
    con **20 pruebas**. La persistencia de **preferencias generales**
    (más allá de la última carpeta) sigue pendiente.
-   Separación del punto de entrada de producción y del arnés de smoke
    tests — **completado**: `visor_videos.py` `main()` queda como
    **bootstrap puro de la interfaz** (solo `QApplication(sys.argv)`,
    `VisorVideos()`, `resize(900, 600)`, `show()` y
    `sys.exit(app.exec())`) y **no ejecuta pruebas al iniciar**; el
    **smoke test se independizó en `prueba_smoke.py`** (arnés de
    **ejecución explícita** con `python prueba_smoke.py`, que verifica el
    pipeline completo —paginación, escaneo + carpeta + sincronización,
    previews, doble clic y persistencia— con una base SQLite temporal) y
    las suites de interfaz `prueba_escaneo_interfaz.py`,
    `prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`,
    `prueba_pagina_siguiente.py` y `prueba_recarga_catalogo.py` pasan a
    invocarlo por `subprocess`. El arranque normal queda **preparado para
    el empaquetado de la Beta** sin ejecutar pruebas.
-   Ejecutable portable — **completado** (PyInstaller 6.21.0
    `--onedir --windowed`: carpeta autocontenida `VisorVideos.exe` +
    `_internal/`; `rutas.py` resuelve la raíz en modo congelado con
    `sys.frozen` —`os.path.dirname(sys.executable)`—; FFmpeg/FFprobe por
    `PATH`; portable validado con el driver funcional completo —catálogo,
    miniaturas, previews, persistencia, doble clic y pipeline—).
-   Instalador Beta — **completado** (Inno Setup 6.7.3 genera
    `VisorVideos_Beta1.0_Setup.exe`: instalación por usuario en
    `{localappdata}\Programs` sin permisos de administrador, copia
    recursiva del portable, `miniaturas/` garantizada, `biblioteca.db`
    vacía de esquema vigente, accesos directos y desinstalador automático
    con `[UninstallDelete]`; **pruebas de instalación y desinstalación
    superadas**).
-   Escritura individual asíncrona — **completado** (`TareaGuardarVideo`).
-   Escritura de colección asíncrona — **completado**
    (`TareaGuardarVideos`): persiste colecciones de registros preparados
    en una única transacción atómica.
-   Selección de carpeta desde la interfaz — **completado**
    (`visor_videos.py`): el usuario elige la carpeta de videos con
    `QFileDialog`; la ruta se normaliza a absoluta, se valida que exista
    y sea un directorio, se muestra y se conserva durante la sesión sin
    escanearla.
-   Escaneo real y asíncrono de la carpeta seleccionada — **completado**
    (`visor_videos.py` + `TareaEscaneo` + `GestorTareas`): el botón
    "Escanear carpeta" escanea la carpeta elegida en segundo plano
    (mismo gestor de la ventana) y presenta la cantidad de videos
    detectados, sin tocar SQLite, FFprobe, FFmpeg ni miniaturas, y sin
    recorrer subcarpetas.
-   Detección de diferencias entre la carpeta y el catálogo — **completado
    (etapa no destructiva)** (`detectar_diferencias` en `escanear_videos.py`):
    compara por nombre los archivos de video de la carpeta con los
    registros de la base y devuelve `presentes_en_ambos`/`nuevos`/
    `ausentes_del_disco`. Solo lectura (no inserta, actualiza ni elimina),
    no integrada al pipeline ni a la interfaz, no detecta movimientos/
    renombrados y no recorre subcarpetas. La eliminación de registros
    ausentes y la integración asíncrona quedan pendientes.
-   Preparación del plan de sincronización — **completado (etapa de
    preparación)** (`preparar_plan_sincronizacion` en `escanear_videos.py`):
    recibe el resultado de `detectar_diferencias` y devuelve
    `a_incorporar` (registros básicos con `preparar_registros_basicos`; la
    `fecha_importacion` se genera en la preparación, no durante la
    detección)/`ya_sincronizados`/`candidatos_a_eliminar` (informativos).
    Operación pura: no inserta, actualiza ni elimina, no accede a SQLite,
    no ejecuta FFprobe/FFmpeg y no está integrada al pipeline ni a la
    interfaz. La aplicación de las incorporaciones ya existe
    (`aplicar_incorporaciones`); la eliminación controlada de registros
    ausentes y la deduplicación de nombres repetidos quedan pendientes.
-   Aplicación de incorporaciones del plan — **completado (etapa no
    destructiva)** (`aplicar_incorporaciones` en `escanear_videos.py`):
    recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados",
    "candidatos_a_eliminar"}` y persiste únicamente `a_incorporar`
    reutilizando la escritura transaccional `guardar_videos` (misma
    atomicidad: un solo `commit`, `rollback` total ante fallos). Valida
    el plan completo antes de abrir SQLite; no elimina
    `candidatos_a_eliminar`, no modifica `ya_sincronizados` ni los
    preexistentes sincronizados; devuelve `incorporados`/`nombres`/
    `pendientes_eliminacion`. No integrada al pipeline ni a la interfaz,
    sin escaneo/FFprobe/FFmpeg/miniaturas/subprocesos.
-   Eliminación controlada de registros ausentes — **completado (etapa
    controlada)** (`eliminar_candidatos` en `escanear_videos.py`):
    recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados",
    "candidatos_a_eliminar"}` y elimina únicamente los registros de
    `candidatos_a_eliminar` con una transacción atómica (un solo
    `commit`, `rollback` total ante fallos y `close` en `finally`; el
    `rowcount` por candidato cuenta solo las eliminaciones reales).
    Valida el plan completo antes de abrir SQLite (validación compartida
    con `aplicar_incorporaciones`); no elimina archivos físicos ni
    miniaturas, no toca `a_incorporar`/`ya_sincronizados`; devuelve
    `eliminados`/`nombres`/`incorporados` (informativo, puede ser
    `None`)/`restantes`. No integrada al pipeline ni a la interfaz, sin
    escaneo/FFprobe/FFmpeg/miniaturas/subprocesos. La integración
    asíncrona de la sincronización completa queda pendiente.
-   Sincronización asíncrona del catálogo — **completado (etapa de
    orquestación)** (`TareaSincronizacionCatalogo` en `tareas_videos.py`):
    encadena en segundo plano (un `QThread` con `TareaBase` +
    `GestorTareas`) la secuencia exacta `detectar_diferencias` →
    `preparar_plan_sincronizacion` → `aplicar_incorporaciones` →
    `eliminar_candidatos`, importando `escanear_videos` como módulo.
    Constructor con `carpeta` y `ruta_db` opcional (por defecto cada
    función delega su default `ruta_biblioteca()`) y `parent` compatible
    con `QObject`; propiedades `carpeta`/`ruta_db` que devuelven
    directamente los valores actualmente inmutables (`str` o `None`) del
    constructor. Devuelve `{"diferencias", "plan", "incorporaciones",
    "eliminaciones", "resumen"}`. Sin SQL, sin abrir SQLite directamente,
    sin conexiones almacenadas, sin `check_same_thread=False`, sin
    FFprobe/FFmpeg/miniaturas/subprocesos y sin acceso a la interfaz.
    Incorporación y eliminación como transacciones independientes (si
    falla la incorporación no se elimina; si falla la eliminación las
    incorporaciones confirmadas permanecen). **Integrada con el flujo de
    la interfaz**: se lanza tras el guardado exitoso del pipeline (ver
    "Sincronización completa del catálogo") y, al terminar, dispara la
    **recarga asíncrona del catálogo** (ver "Recarga automática del
    catálogo tras la sincronización"); la deduplicación de nombres
    repetidos queda pendiente.

1.  Opción de incluir o excluir subcarpetas — **pendiente** (configurar
    si el escaneo de la carpeta elegida recorre las subcarpetas).
2.  Preparación y escritura de registros detectados — **completado**
    (el pipeline `TareaEscaneo` → `TareaFFprobe` →
    `combinar_registros_con_ffprobe` → `TareaMiniaturas` →
    `combinar_registros_con_miniaturas` → `TareaGuardarVideos`, encadenado
    desde la interfaz, convierte los archivos detectados en registros
    con metadatos FFprobe y cantidad de miniaturas y los escribe en
    SQLite con el upsert transaccional, conservando los registros
    preexistentes).
3.  Sincronización completa del catálogo — **completado (detección,
    preparación, aplicación de incorporaciones, eliminación controlada,
    orquestación asíncrona e integración con la interfaz)**: la detección
    no destructiva de diferencias existe (`detectar_diferencias`, por
    nombre y solo lectura), el plan ya se prepara de forma pura
    (`preparar_plan_sincronizacion`, con
    `a_incorporar`/`ya_sincronizados`/`candidatos_a_eliminar` y
    candidatos informativos), las incorporaciones ya se aplican de forma
    no destructiva (`aplicar_incorporaciones`, persistiendo únicamente
    `a_incorporar` con `guardar_videos`), los registros ausentes ya se
    eliminan de forma controlada (`eliminar_candidatos`, transacción
    atómica y validación previa), la secuencia completa ya se orquesta
    en segundo plano (`TareaSincronizacionCatalogo` con `QThread` +
    `GestorTareas`) y `visor_videos.py` ya lanza la tarea tras el
    guardado exitoso del pipeline (estado final con incorporados/
    eliminados/candidatos restantes; ausentes eliminados de SQLite,
    presentes conservados, sin borrado de archivos físicos ni
    miniaturas); **tras una sincronización exitosa se recarga el
    catálogo en segundo plano** (`visor_videos.py` relee la primera
    página con `TareaLecturaCatalogoPaginada` y reemplaza las tarjetas
    con `_reemplazar_tarjetas`); quedan pendientes la **paginación
    completa automática** (scroll infinito, búsqueda en SQL desde la
    interfaz y ordenamiento configurable — no existen todavía; hoy existe
    la **carga manual de una página adicional** con el botón "Cargar más")
    y la deduplicación de nombres repetidos.
4.  FFprobe integrado en el pipeline — **completado** (el pipeline
    escaneo → guardado completa duración, resolución y codec antes de
    escribir o actualizar los registros; `NULL` ante vacíos, incompletos
    o fallos individuales).
5.  FFmpeg y miniaturas — **completado (etapa limitada)**: generación asíncrona de una miniatura básica por video
    integrada en el pipeline (`TareaMiniaturas` con el mismo
    `GestorTareas`, reutilizando `asegurar_miniatura`/`contar_miniaturas`
    existentes; `cantidad_miniaturas` persistida). Quedan fuera del
    alcance: selección inteligente, múltiples miniaturas y eliminación de
    archivos antiguos. La recarga automática de la interfaz tras la
    sincronización ya está implementada (ver "Recarga automática del
    catálogo tras la sincronización"). La limpieza
    controlada de versiones antiguas sigue pendiente.
6.  Eliminación de registros ausentes — **completado (aplicación
    controlada, orquestación asíncrona e integración con la interfaz)**
    (sincronizar la
    BD con los archivos que dejaron de existir; la detección de los
    ausentes ya existe de forma no destructiva en `detectar_diferencias`,
    el plan ya los expone como `candidatos_a_eliminar` en
    `preparar_plan_sincronizacion` (únicamente informativos), las
    incorporaciones ya se aplican en `aplicar_incorporaciones` sin tocar
    a los candidatos, la **aplicación controlada de la eliminación** ya
    existe en `eliminar_candidatos` (transacción atómica y validación
    previa), la **orquestación asíncrona completa** ya existe en
    `TareaSincronizacionCatalogo` y la interfaz ya la lanza tras el
    guardado exitoso del pipeline, eliminando de SQLite los registros
    ausentes y conservando los presentes).
7.  Recarga automática del catálogo tras la sincronización — **completado**
    (`visor_videos.py` recarga el catálogo en segundo plano **solo tras
    una sincronización exitosa** con la misma
    `TareaLecturaCatalogoPaginada`/`GestorTareas` y **reemplaza las
    tarjetas** con `_reemplazar_tarjetas`: las tarjetas viejas se
    conservan hasta el resultado válido y completo, luego se liberan
    (`removeWidget` + `deleteLater`), se vacía `self.tarjetas`, se crean
    las nuevas en la misma grilla y se reaplica el filtro, conservando
    `resultado_sincronizacion`; ante un error de recarga se conservan las
    tarjetas viejas y no se revierte la sincronización ya confirmada en
    SQLite. La recarga muestra únicamente la primera página; la **carga
    manual de una página adicional** con el botón "Cargar más" ya existe,
    y la paginación automática, la búsqueda en SQL desde la interfaz y el
    ordenamiento configurable siguen pendientes).
8.  Progreso — **pendiente** (barra de progreso y estado de las tareas
    en curso).
9.  Persistencia de configuración — **completado (parcial: última carpeta
    seleccionada)** (recordar entre sesiones la carpeta seleccionada y las
    preferencias). La **última carpeta seleccionada** ya se persiste en
    `configuracion.json` (servicio `configuracion.py`, escritura atómica,
    restauración automática al iniciar y aislamiento de pruebas con
    `VISOR_CONFIG`; ver "Persistencia de la última carpeta seleccionada" en
    "Prioridad inmediata"). Las **preferencias generales** (más allá de la
    última carpeta) siguen pendientes.
10. Pruebas de la Beta en equipos externos — **pendiente (siguiente hito)**:
    la Beta ya está **empaquetada y distribuible** —**ejecutable portable
    validado** e **instalador funcional** `VisorVideos_Beta1.0_Setup.exe`
    (ver "Ejecutable portable" e "Instalador Beta" en "Prioridad
    inmediata"); las **pruebas de instalación y desinstalación fueron
    superadas**—. Queda pendiente probar la Beta en equipos externos
    (instalación, arranque, catálogo, miniaturas/previews, doble clic y
    desinstalación en máquinas ajenas) y la **revisión del mecanismo de
    búsqueda de miniaturas** (esta última, posterior a la Beta).

------------------------------------------------------------------------

# Experiencia de usuario

-   Barra de progreso.
-   Cancelación de tareas.
-   Reanudación de trabajos.
-   Configuración persistente.
-   Mejor navegación entre videos.

------------------------------------------------------------------------

# Calidad de miniaturas

-   Selección inteligente de fotogramas.
-   Evitar pantallas negras.
-   Evitar fundidos.
-   Evitar créditos.
-   Evitar imágenes repetidas.
-   Cantidad configurable de miniaturas.

------------------------------------------------------------------------

# Organización

-   Etiquetas.
-   Favoritos.
-   Puntuaciones.
-   Carpetas virtuales.
-   Filtros avanzados.
-   Búsqueda avanzada.

------------------------------------------------------------------------

# Administración

-   Detección de archivos movidos.
-   Renombrado masivo.
-   Organización automática.
-   Detección de duplicados.

------------------------------------------------------------------------

# Futuro

-   IA para descripción de videos.
-   IA para clasificación automática.
-   Reconocimiento de escenas.
-   OCR.
-   Reconocimiento de rostros y objetos.
-   Plugins o extensiones.
-   Múltiples vistas del catálogo.

------------------------------------------------------------------------

# Criterio

Las funcionalidades solo pasarán de este documento al desarrollo cuando
exista una etapa aprobada para implementarlas.
