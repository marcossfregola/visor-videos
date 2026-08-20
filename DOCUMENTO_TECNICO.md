# Documento técnico — Visor de Videos

---

## 1. Árbol de directorios

```
prueba/
├── biblioteca.db          Base de datos SQLite del catálogo
├── configuracion.json     Configuración local del usuario (última carpeta seleccionada; generada por la app, gitignored)
├── datos.txt              Salida del script de prueba main.py (ajeno al visor)
├── main.py                Script de prueba de operaciones (ajeno al visor)
├── operaciones.py         Lógica pura de operaciones sobre archivos (copiar B3.14, pegar B3.15, eliminar B3.16)
├── seleccion_carpetas.py  Conjunto de carpetas seleccionadas por ruta (Selección personalizada, Bloque 4)
├── instalador.iss         Script oficial Inno Setup 6.7.3 del instalador (instalación por usuario; ver `EMPACADO.md`)
├── EMPACADO.md            Procedimiento oficial de empaquetado (PyInstaller + Inno Setup, reproducible)
├── prueba_agente.py       Artifacto de prueba (ajeno al visor)
├── escanear_videos.py     CLI / backend: escaneo + SQLite + FFprobe
├── rutas.py               Resolución centralizada de rutas del proyecto (independiente del CWD); incluye `ruta_carpeta_exploracion()` (`miniaturas/exploracion`, B4.3.1) y `ruta_video_existente()` (resolución/validación de existencia de la ruta de video delegada por la UI, B4.12)
├── tareas.py              Infraestructura reutilizable de trabajos en segundo plano (QThread)
├── tareas_videos.py       Tareas de video asíncronas (TareaFFprobe, TareaEscaneo, TareaTamanosArchivos, TareaLecturaCatalogo, TareaLecturaCatalogoPaginada, TareaGuardarVideo, TareaGuardarVideos, TareaMiniaturas, TareaPreviewsProgresivas, TareaSincronizacionCatalogo, y desde B4.2 TareaListarMarcadores, TareaGuardarMarcador, TareaEliminarMarcador; desde B4.3.2 TareaExploracionDensa — cobertura densa en dos fases: 15 prioritarios + densidad secundaria adaptativa; desde B4.3.3 con `objetivo_manual` y conjunto permitido explícito; desde B4.4 TareaListarMarcadoresVarios — lectura asíncrona de marcadores de varios videos; desde B4.5 TareaMiniaturas/TareaPreviewsProgresivas aceptan `duraciones` (evitan FFprobe interno cuando la duración ya es conocida) y `TareaFFprobe` acepta `nombres`/`stats`/`ruta_db` para reutilizar metadata de videos sin cambios (B4.5 Etapa 3))
├── prueba_tareas.py       Pruebas automatizadas de la infraestructura de trabajos
├── prueba_ffprobe.py      Pruebas automatizadas de TareaFFprobe
├── prueba_escaneo.py      Pruebas automatizadas de TareaEscaneo
├── prueba_lectura.py      Pruebas automatizadas de TareaLecturaCatalogo
├── prueba_lectura_paginada.py  Pruebas automatizadas de TareaLecturaCatalogoPaginada
├── prueba_interfaz_asincrona.py  Pruebas automatizadas de la integración asíncrona de la interfaz (29)
├── prueba_seleccion_carpeta.py  Pruebas automatizadas de la selección de carpeta en la interfaz (26)
├── prueba_guardar.py      Pruebas automatizadas de TareaGuardarVideo
├── prueba_guardar_videos.py  Pruebas automatizadas de TareaGuardarVideos
├── prueba_escaneo_interfaz.py  Pruebas automatizadas del escaneo asíncrono desde la interfaz (36)
├── prueba_escaneo_guardado.py  Pruebas automatizadas del encadenamiento escaneo → tamaños → FFprobe → miniaturas → guardado (24)
├── prueba_detectar.py      Pruebas automatizadas de la detección de diferencias disco ↔ BD (15)
├── prueba_plan_sincronizacion.py  Pruebas automatizadas de la preparación del plan de sincronización (12)
├── prueba_aplicar_incorporaciones.py  Pruebas automatizadas de la aplicación de incorporaciones del plan de sincronización (15)
├── prueba_eliminar_candidatos.py  Pruebas automatizadas de la eliminación controlada de candidatos del plan de sincronización (16)
├── prueba_sincronizacion_asincrona.py  Pruebas automatizadas de la sincronización asíncrona del catálogo (27)
├── prueba_sincronizacion_interfaz.py  Pruebas automatizadas de la sincronización completa integrada en la interfaz (18)
├── prueba_recarga_catalogo.py  Pruebas automatizadas de la recarga asíncrona del catálogo tras la sincronización (20)
├── prueba_pagina_siguiente.py  Pruebas automatizadas de la carga manual de una página adicional del catálogo en la interfaz (20)
├── prueba_tamano_archivo.py  Pruebas automatizadas del tamaño de archivo (15)
├── prueba_previews_progresivas.py  Pruebas automatizadas de los previews progresivos (16)
├── apertura_videos.py     Servicio de apertura de videos con la aplicación predeterminada del sistema (único módulo que ejecuta `os.startfile`)
├── playlist_vlc.py       Integración de playlists VLC (B4.4): localiza `vlc.exe`, genera el `.m3u` temporal con `#EXTVLCOPT:start-time` por entrada (encoding UTF-8), limpia playlists propias anteriores y lanza VLC una única vez; sin HTTP ni libVLC
├── prueba_doble_clic.py   Pruebas automatizadas de la apertura del video por doble clic (14)
├── prueba_menu_contextual.py  Pruebas automatizadas del menú contextual con clic derecho (14)
├── prueba_restauracion_seleccion.py  Pruebas automatizadas de la restauración de selección tras reemplazo de tarjetas (15)
├── prueba_shift_clic.py  Pruebas automatizadas de la selección por rango con Shift+clic (28)
├── prueba_copiar_rutas_seleccionados.py  Pruebas automatizadas de la copia de rutas de seleccionados al portapapeles (8)
├── prueba_abrir_carpetas_seleccionados.py  Pruebas automatizadas de la apertura de carpetas de seleccionados (10)
├── prueba_escaneo_subcarpetas.py  Pruebas automatizadas del escaneo recursivo con subcarpetas (12)
├── prueba_persistencia_subcarpetas.py  Pruebas automatizadas de la persistencia de "Incluir subcarpetas" (10)
├── prueba_cantidad_previews.py  Pruebas automatizadas de la cantidad configurable de previews (11)
├── prueba_version_build.py  Pruebas automatizadas de la identificación visible de versión/build (B4.12, 3): constantes, texto exacto `Beta 4 — B4.12` y etiqueta visible en la status bar
├── configuracion.py       Servicio de persistencia de configuración (última carpeta seleccionada en `configuracion.json`) + constantes centrales de versión/build (`VERSION_PRODUCTO`, `BUILD_IDENTIFICADOR`, `TEXTO_VERSION_BUILD` → `Beta 4 — B4.12`)
├── prueba_persistencia_carpeta.py  Pruebas automatizadas de la persistencia de la última carpeta seleccionada (20)
├── arbol_navegacion.py  Árbol de navegación del panel izquierdo (nodo raíz "Este equipo", discos y carpetas con carga diferida, selección funcional, sincronización y persistencia/restauración de la carpeta activa); Etapa 2.5 del bloque de trabajo 2, desacoplado del catálogo. Bloque 4: modo de selección de carpetas con checkboxes + herramientas de selección rápida (Etapas 2-3)
├── prueba_arbol_navegacion.py  Pruebas automatizadas del árbol de navegación del panel izquierdo (Etapa 2.1)
├── prueba_expansion_carpetas.py  Pruebas automatizadas de la expansión de discos y carpetas con carga diferida (Etapa 2.2)
├── prueba_seleccion_arbol.py  Pruebas automatizadas de la selección funcional del árbol de navegación (Etapa 2.3)
├── prueba_carpeta_actual.py  Pruebas automatizadas de la integración de la selección del árbol con la carpeta activa de la aplicación (Etapa 2.4)
├── prueba_persistencia_arbol.py  Pruebas automatizadas de la persistencia y restauración del árbol (Etapa 2.5)
├── prueba_escaneo_arbol.py  Pruebas automatizadas del disparo automático del escaneo desde el árbol y el diálogo (Etapa 2.6)
├── prueba_subcarpetas_arbol.py  Pruebas de verificación de la paridad árbol/botón/diálogo respecto de "Incluir subcarpetas" (Etapa 2.7)
├── prueba_escaneo_automatico.py  Pruebas automatizadas de la preferencia independiente de "Escaneo automático" y sus cuatro combinaciones con "Incluir subcarpetas" (Etapa 2.8)
├── prueba_indicador_escaneado.py  Pruebas automatizadas de los indicadores visuales de carpetas escaneadas (Etapa 2.9)
├── exploracion_cache.py    Motor de caché temporal versionada y reanudable en disco (B4.3.1): estructura `miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` + `f{ms:010d}.jpg`), fingerprint sin hash, reanudación y escritura atómica; densidad secundaria provisional centralizada (`objetivo_total_densidad`, 1/30 s, mín 15, máx 200) para B4.3.2 Etapa 2; sin UI ni SQLite
├── visor_videos.py        Interfaz gráfica (PySide6): panel izquierdo con árbol de navegación (`ArbolNavegacion`) + carga asíncrona de la primera página + carga manual de una página adicional ("Cargar más") + selección de carpeta + persistencia de la última carpeta seleccionada (servicio `configuracion`) + escaneo asíncrono de la carpeta elegida + encadenamiento escaneo → tamaños → FFprobe → miniaturas → registros con tamaño/metadatos → guardado → sincronización completa del catálogo → recarga asíncrona del catálogo (reemplazo de tarjetas) + generación progresiva de previews con gestor propio + apertura del video por doble clic (señal `Tarjeta.doble_clic` → `_abrir_video` → servicio `apertura_videos`) + **persistencia de marcadores temporales con gestor dedicado `gestor_marcadores` (B4.2)** (la `Tarjeta` recibe `video_id`, carga marcadores al expandir y persiste altas/bajas sin SQLite directo, con reconciliación de la carga como snapshot antiguo) + **cobertura densa de exploración temporal integrada con la tarjeta (B4.3.2)**: `TareaExploracionDensa` con `resultado_parcial` progresivo, decodificación `QImage` en el worker y conversión `QPixmap` en la GUI, fallback a previews normales, selección en RAM durante `mouseMove`, cancelación cooperativa, aislamiento A→B, colapso que libera RAM y reexpansión que reutiliza la caché; **densidad secundaria adaptativa en segundo plano (Etapa 2)** y **prioridad visual dinámica + densidad manual (B4.3.3)** y **reproducción de marcadores en VLC (B4.4)**: acción de menú contextual "Reproducir marcadores en VLC" que recolecta los videos seleccionados en orden visible, lee sus marcadores (gestor dedicado `gestor_reproduccion`), dialoga sobre videos sin marcadores, omite archivos inexistentes y abre VLC una única vez con una playlist temporal; y **carga diferida de previews cacheadas (B4.6)**: las tarjetas parten con placeholders y las previews se incorporan progresivamente; **identificación visible de versión/build en la status bar inferior (`Beta 4 — B4.12`)**; `main()` es el **punto de entrada de producción** (solo UI, sin pruebas)
├── prueba_smoke.py        Arnés de smoke tests (ejecución explícita con `python prueba_smoke.py`): verifica el pipeline completo (paginación, escaneo + carpeta + sincronización, previews, doble clic y persistencia) con una base SQLite temporal; no se ejecuta al iniciar la aplicación
├── prueba_exploracion_cache_b431.py  Pruebas automatizadas del motor de caché temporal (B4.3.1, 29)
├── prueba_exploracion_b432.py  Pruebas de la cobertura rápida integrada con la UI (B4.3.2 Etapa 1, 20)
├── prueba_exploracion_densidad_b432.py  Pruebas de la densidad secundaria adaptativa (B4.3.2 Etapa 2, 12)
├── prueba_exploracion_b433.py  Pruebas de prioridad visual dinámica y densidad manual (B4.3.3, 22)
├── prueba_reproduccion_marcadores_b44.py  Pruebas de la reproducción de marcadores en VLC (B4.4, 24)
├── DOCUMENTO_TECNICO.md   Este documento
├── miniaturas/            Imágenes de miniatura (JPG, generadas automáticamente)
│   └── <prefijo>_<NN>.jpg  Convención de nombres; caché ignorada, contenido variable
├── videos_prueba/         Videos de prueba (datos de ejemplo)
│   ├── video_01.mp4       (0 bytes)
│   ├── video_03.avi       (0 bytes)
│   ├── video_04.mp4       (0 bytes)
│   └── video_real.mp4     (5756 bytes, 640x360 h264 5s)
└── __pycache__/           Compilados de Python (generados, no versionados)
```

> Nota: `miniaturas/` es una caché ignorada por Git; su contenido cambia con cada escaneo. Actualmente existen dos archivos locales de prueba (`video_real_01.jpg` y `video_real_02.jpg`), pero no forman parte estable de la arquitectura. La convención general de nombres es `miniaturas/<prefijo>_<NN>.jpg`.

## 2. Propósito de cada carpeta

| Carpeta | Propósito |
| --- | --- |
| `miniaturas/` | Almacena las miniaturas generadas de cada video. El visor lee de aquí para mostrar la tarjeta. El backend **genera** las miniaturas durante el escaneo y las **preserva**: nunca las sobrescribe ni las elimina automáticamente. |
| `miniaturas/exploracion/` | Caché densa de exploración temporal (B4.3.1): por video y por versión de fingerprint (`<video_id>/<version_fingerprint>/`), con `meta.json` + `f*.jpg`. Ignorada por Git, regenerable y **nunca borrada automáticamente** (las versiones antiguas quedan en disco hasta una limpieza futura, fuera de alcance). |
| `videos_prueba/` | Dataset de prueba con el que `escanear_videos.py` sincroniza el catálogo. Contiene archivos vacíos (sin metadatos) y un video real. |
| `__pycache__/` | Caché de bytecode de Python. Generado automáticamente, debe ignorarse en VCS. |

## 3. Propósito de cada módulo

### `escanear_videos.py` — backend / lógica del catálogo
Único módulo con responsabilidad sobre el **dominio** y los **datos**:

- `escanear_videos(carpeta)` — escaneo de archivos: lista archivos del directorio filtrando por extensión (`.mp4`, `.mkv`, `.avi`), ordenados. Soporta un modo recursivo controlado por el flag `_ESCANEO_RECURSIVO` (configurable mediante `configurar_escaneo_recursivo(activado)`): cuando está activado, recorre todas las subcarpetas con `os.walk` y devuelve rutas relativas (respecto a `carpeta`); cuando está desactivado, solo lista la carpeta raíz con `os.listdir`. El modo se controla desde la interfaz mediante la casilla `Incluir subcarpetas`. La función `_nombre_seguro(nombre)` reemplaza los separadores de ruta por `_` para que los nombres de archivo de miniaturas y previews sigan siendo planos incluso cuando el nombre del video incluye subcarpetas.
- `preparar_registros_basicos(videos, carpeta)` — **preparación de registros básicos del catálogo** a partir de los archivos detectados por el escaneo. Recibe la lista de nombres de archivos y la carpeta escaneada; devuelve una lista de registros con las claves exactas `{nombre, ruta, extension, fecha_importacion}`. `ruta` es la ruta **absoluta** del archivo dentro de la carpeta escaneada (`os.path.join(carpeta, nombre)`), `extension` es la extensión en minúsculas y `fecha_importacion` es una marca de tiempo ISO (`datetime.now().isoformat()`) común a los registros de la preparación. **Validación previa**: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vacía (`ValueError` en caso contrario).   No detecta archivos, no abre SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas: es la capa de transformación entre el escaneo y la escritura (`guardar_videos`).
- `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)` — **combinación de registros con metadatos FFprobe**: capa de catálogo **pura** que transforma los archivos detectados por el escaneo y el resultado de `TareaFFprobe` en registros con metadatos. Parte de `preparar_registros_basicos` (claves básicas `{nombre, ruta, extension, fecha_importacion}`) y luego integra los metadatos de FFprobe por ruta: para cada registro busca el `datos` asociado a su `ruta` dentro de `resultado_ffprobe["resultados"]` (los ítems que no son `dict` o no tienen `ruta` se ignoran; un `datos` no-dict se trata como `None`) y aplica las claves de `CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")`; si el video no tiene `datos` (resultado vacío, incompleto o fallo individual), las claves se escriben como `NULL` (`None`). Las rutas se comparan con la normalización interna `_normalizar_ruta` (`os.path.normcase(os.path.normpath(ruta))`; `None` si la entrada es `None`). No abre SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas ni toca la interfaz: es la capa de transformación entre el escaneo y la escritura (`guardar_videos`).
- `conectar_bd(ruta_db=None)` — acceso a SQLite: crea la tabla `videos` si no existe y aplica **migración idempotente** de columnas extras (`COLUMNAS_EXTRA`): `duracion_segundos REAL`, `ancho INTEGER`, `alto INTEGER`, `codec_video TEXT`, `cantidad_miniaturas INTEGER` y **`tamano_bytes INTEGER`**. Por cada columna, `PRAGMA table_info(videos)` decide si ya existe y solo entonces ejecuta `ALTER TABLE ... ADD COLUMN`; repetir la conexión no duplica columnas ni toca los datos existentes. **Etapa B4.2**: además ejecuta la **migración aditiva** de la tabla `marcadores_video` (`_asegurar_tabla_marcadores`): crea la tabla y su índice si no existen, idempotente y **sin** activar `PRAGMA foreign_keys` ni usar `ON DELETE CASCADE` (los marcadores son datos del usuario y su coherencia con `videos.id` se gestiona en la capa de servicio, no por borrado automático). Acepta una ruta de base opcional (por defecto `ruta_biblioteca()`); el arnés de smoke tests (`prueba_smoke.py`) reutiliza este esquema para crear una base SQLite temporal válida sin depender de `biblioteca.db`.
- `obtener_datos_ffprobe(ruta)` — integración con **FFprobe**: extrae duración, ancho, alto y codec del primer stream de video. Timeout 30 s; devuelve `None` ante cualquier fallo. En Windows, todos los `subprocess.run` (FFprobe, FFmpeg en `generar_miniatura` y `generar_preview`) usan `creationflags=subprocess.CREATE_NO_WINDOW` mediante `_ARGS_SIN_CONSOLA` para evitar ventanas de consola emergentes.
- `ffmpeg_disponible()` — integración con **FFmpeg**: verifica disponibilidad del ejecutable (`shutil.which`).
- `ruta_miniatura(video, indice=1)` — ruta canónica `miniaturas/<prefijo>_<NN>.jpg`.
- `calcular_tiempo_miniatura(duracion)` — tiempo representativo para extraer el fotograma (10 % de la duración, acotado entre 0.1 y 10 s; 1 s si se desconoce).
- `miniatura_vigente(ruta_video, ruta_miniatura)` — criterio de reutilización por `mtime`: la miniatura es válida si existe y su `mtime` es ≥ al del video.
- `generar_miniatura(ruta_video, ruta_miniatura, duracion_segundos=None)` — extrae un fotograma con FFmpeg (`-ss`, `-frames:v 1`). Timeout 30 s; devuelve `False` ante cualquier fallo. **Etapa B4.5**: si `duracion_segundos` es una duración utilizable (`_duracion_utilizable`: número real finito > 0) la usa directamente para calcular el tiempo objetivo **sin ejecutar FFprobe interno**; si es inválida/ausente, ejecuta `obtener_datos_ffprobe` como fallback (comportamiento anterior). El FFmpeg y el archivo resultante son idénticos.
- `siguiente_indice_libre(video)` — primer índice `_NN` sin archivo existente.
- `miniatura_reutilizable(video, ruta_video)` — primera miniatura existente del video que sea válida (orden alfabético) o `None`. **Excluye los archivos `_preview_`** (`_es_archivo_preview`): los previews progresivos no cuentan como miniaturas reutilizables.
- `asegurar_miniatura(video, ruta_video, duracion_segundos=None)` — reutiliza una miniatura válida si existe; si no, genera una nueva en la **siguiente ranura libre** (pasando la duración conocida a `generar_miniatura`, B4.5). Nunca sobrescribe ni elimina archivos.
- `asegurar_miniaturas(videos, carpeta, on_progreso=None, duraciones=None)` — **aseguramiento de miniaturas por colección** para el pipeline: capa de catálogo que orquesta `asegurar_miniatura` + `contar_miniaturas` por archivo. **Validación previa**: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vacía (`ValueError`). Para cada nombre construye la ruta absoluta (`os.path.join(carpeta, nombre)`); si el archivo no existe registra `asegurada=0` y `cantidad_miniaturas=0`; si existe, invoca `asegurar_miniatura` y luego `contar_miniaturas`. **Etapa B4.5**: `duraciones` (mapa por ruta o por nombre) se propaga a `asegurar_miniatura`/`generar_miniatura`, que evitan el FFprobe interno cuando la duración es utilizable. Devuelve el resumen `{"rutas": [...], "resultados": [{"ruta", "asegurada", "cantidad_miniaturas"}...], "procesados": n, "con_miniatura": n, "sin_miniatura": n}`. **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` tras procesar cada nombre (incluidos los inexistentes); si es `None` el comportamiento es idéntico. Sin Qt; no abre SQLite ni toca la interfaz.
- `combinar_registros_con_miniaturas(registros, resultado_miniaturas)` — **combinación de registros con cantidad de miniaturas**: capa de catálogo **pura** que transforma los registros ya preparados (básicos + FFprobe) y el resultado de `TareaMiniaturas` en registros con `cantidad_miniaturas`. Para cada registro busca el ítem de `resultado_miniaturas["resultados"]` por ruta normalizada (`_normalizar_ruta`; los ítems que no son `dict` o no tienen `ruta` se ignoran); si el valor de `cantidad_miniaturas` no es un entero se escribe como `None`; si no hay coincidencia o el resultado es `None`, también `None`. Devuelve **copias** de los registros con la clave agregada. No abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `contar_miniaturas(video)` — cuenta miniaturas existentes en `miniaturas/` cuyo nombre empieza con el prefijo del video. **Excluye los archivos `_preview_`** (`_es_archivo_preview`): los previews progresivos no alteran `cantidad_miniaturas`.
- `CANTIDAD_PREVIEWS_POR_DEFECTO = 3`, `CANTIDAD_PREVIEWS` (mutable, configurable con `configurar_cantidad_previews(n)`) — cantidad de previews por video. A diferencia de la versión original (constante), ahora la cantidad puede modificarse en tiempo de ejecución desde la interfaz mediante un `QComboBox` con opciones 3, 5, 7 y 9. La preferencia se persiste en `configuracion.json` (clave `cantidad_previews`) y se restaura al iniciar. La interfaz crea esa cantidad de etiquetas por `Tarjeta`; si existen más previews que etiquetas, solo se muestran las que caben; si existen menos, se muestran las disponibles. La generación de nuevos previews respeta la cantidad configurada (sin forzar regeneración de los ya existentes).
- `ruta_preview(video, indice)` — ruta canónica `miniaturas/<prefijo>_preview_NN.jpg` del preview `indice`.
- `_es_archivo_preview(nombre, video)` — `True` si el nombre de archivo empieza con el prefijo del video seguido de `_preview_` (permite excluir los previews de la lógica de miniaturas).
- `previews_existentes(video)` — lista de rutas de los índices 1..3 que ya existen en `miniaturas/` (en orden); `[]` si no hay previews.
- `previews_faltantes(video)` — lista de índices 1..3 sin archivo en `miniaturas/` (generación incremental: solo los índices que faltan).
- `calcular_tiempo_preview(duracion, indice=None)` — tiempo representativo para extraer el fotograma del preview: proporcional `indice / (CANTIDAD_PREVIEWS + 1)` de la duración (25/50/75 % con `indice` en 1..3), acotado entre 0.1 s y `0.95 × duración`; 1 s si se desconoce la duración o el índice no es 1..3 (entero, no bool).
- `generar_preview(ruta_video, destino, indice=None, duracion_segundos=None)` — extrae un fotograma con FFmpeg (`-ss <tiempo>`, `-frames:v 1`, `-q:v 3`) en el `tiempo` calculado. Timeout 30 s; devuelve `False` ante cualquier fallo. **Etapa B4.5**: con `duracion_segundos` utilizable usa esa duración **sin FFprobe interno** (mismo tiempo objetivo y FFmpeg); si es inválida/ausente, fallback a `obtener_datos_ffprobe`.
- `generar_previews_faltantes(videos, carpeta, duraciones=None)` — **generación de previews progresivos por colección**: capa de catálogo que orquesta `previews_faltantes` + `generar_preview` por archivo. **Validación previa**: `videos` no texto (`str`/`bytes`/`bytearray`) ni no iterable (`TypeError`); `carpeta` texto no vacío (`ValueError`). Para cada nombre construye la ruta absoluta (`os.path.join(carpeta, nombre)`), calcula los índices **faltantes** y genera **solo esos**: si el archivo existe y no está vacío intenta `generar_preview` (con la duración de `duraciones` si está disponible, B4.5); si FFmpeg falla y existe una miniatura principal válida (`miniatura_reutilizable`) la copia como base (`shutil.copyfile`); si el archivo no existe o no hay base cuenta un error. **Nunca sobrescribe ni elimina archivos** (un índice existente no se regenera). Devuelve el resumen `{"rutas": [...], "resultados": [{"nombre", "ruta", "previews", "generados", "reutilizados", "errores", "completos"}...], "procesados": n, "con_previews": n, "sin_previews": n}`, donde `completos` indica si ya existen los 3 previews. No abre SQLite ni toca la interfaz.
- `obtener_tamanos_archivos(videos, carpeta, on_progreso=None)` — **estadística de archivo por colección** para el pipeline: capa de catálogo que, para cada nombre de video, construye la ruta absoluta (`os.path.join(carpeta, nombre)`) y consulta con **un único `os.stat` por archivo** su tamaño y `mtime_ns` (`st_size` y `st_mtime_ns`; **B4.5 Etapa 3**, evita `getsize`+`stat` por separado). Un archivo legible se registra con `tamano_bytes` y `mtime_ns`; un archivo inexistente o ilegible (`OSError`) registra ambos como `None`. Devuelve el resumen `{"rutas": [...], "resultados": [{"ruta", "tamano_bytes", "mtime_ns"}...], "procesados": n, "con_tamano": n, "sin_tamano": n}`. **Validación previa**: `carpeta` texto no vacío (`ValueError`); carpeta inexistente → `FileNotFoundError`; `videos` no texto ni no iterable (`TypeError`). **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` se invoca tras procesar cada archivo; si es `None` el comportamiento es idéntico. Sin Qt; no abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `combinar_registros_con_tamanos(registros, resultado_tamanos)` — **combinación de registros con tamaño de archivo**: capa de catálogo **pura** que transforma los registros ya preparados (básicos + FFprobe + miniaturas) y el resultado de `TareaTamanosArchivos` en registros con `tamano_bytes`. Para cada registro busca el ítem de `resultado_tamanos["resultados"]` por ruta normalizada (`_normalizar_ruta`; los ítems que no son `dict` o no tienen `ruta` se ignoran); si el valor de `tamano_bytes` no es un entero se escribe como `None`; si no hay coincidencia o el resultado es `None`, también `None`. Devuelve **copias** de los registros con la clave agregada. No abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `insertar_video`, `actualizar_datos`, `sincronizar_bd` — lógica de sincronización disco ↔ BD: inserta nuevos, actualiza metadatos (incluida `cantidad_miniaturas` tras `asegurar_miniatura`), elimina de la BD los que ya no están en disco. Operan sobre una conexión administrada por el llamador (el `commit` lo hace `main()`).
- `guardar_video(datos, ruta_db=None)` — **escritura individual transaccional** de un único registro. Recibe el registro ya preparado como `dict` con las claves de las columnas reales. Obligatorias: `nombre`, `ruta`, `extension`, `fecha_importacion`; opcionales (se guardan como `NULL` si faltan o son `None`): `duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`, `tamano_bytes`. Reutiliza la validación y el upsert internos compartidos (`_validar_registro_video`, `_upsert_video`) con `guardar_videos`; no duplica SQL ni validación. **Validación previa a SQL**: si `datos` no es un `dict` lanza `TypeError`; si falta una clave obligatoria lanza `ValueError` con el nombre de la clave; ambas se verifican **antes de conectar** (no se abre ni modifica la base). Inserta si `nombre` no existe o actualiza el mismo registro (`ON CONFLICT(nombre) DO UPDATE`), sin duplicar. Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos (mismo contrato que `listar_videos`). Ciclo: abre la conexión, ejecuta el upsert, hace `commit` solo si la operación terminó correctamente, hace `rollback` ante cualquier error y cierra siempre en `finally`. Devuelve `{"guardado": True, "nombre": ...}`. No ejecuta escaneo, FFprobe ni FFmpeg; no modifica miniaturas.
- `guardar_videos(datos_videos, ruta_db=None, on_progreso=None)` — **escritura de colección transaccional** en una **única transacción atómica**. Recibe una colección materializable de registros con el mismo contrato de `guardar_video` (una lista/tupla/iterable de `dict`; se rechaza el texto). **Validación completa previa**: la entrada debe ser iterable y no texto (`TypeError` en caso contrario), se materializa en una lista, se validan **todos** los registros (`_validar_registro_video`: no-dict → `TypeError`; clave obligatoria ausente → `ValueError`) y se toman **copias superficiales** de cada uno; si un registro es inválido se rechaza la colección completa **sin abrir SQLite**. Inserta o actualiza cada registro (mismo upsert `ON CONFLICT(nombre) DO UPDATE` que `guardar_video`, sin duplicar SQL). **Ciclo atómico**: abre **una sola** conexión, ejecuta **todos** los upserts, realiza **un solo** `commit` al terminar, ejecuta `rollback` ante cualquier excepción (ningún registro anterior persiste; los preexistentes conservan sus valores originales; no queda transacción abierta) y cierra siempre en `finally`. **Colección vacía**: devuelve éxito con cero registros y no modifica la base. **Base inexistente**: `FileNotFoundError` sin crear archivos. Devuelve el resumen simple `{"guardados": <cantidad>, "nombres": [nombres en el orden de la colección]}`. **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` tras cada upsert del bucle de escritura; si es `None` el comportamiento es idéntico. Sin Qt. No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg, no genera miniaturas, **no elimina registros** y no compara disco ↔ base: la sincronización del catálogo sigue pendiente.
- `listar_videos(ruta_db=None)` — **capa de lectura** que consume la interfaz: devuelve las filas del catálogo (nombre, duración, ancho, alto, codec, cantidad de miniaturas, tamaño en bytes, ruta e `id`) ordenadas por nombre, como tuplas de **nueve campos** `(nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id)` (la columna `ruta` se incorporó en la corrección de cierre de la Beta 3 para que el catálogo transporte la carpeta real de cada video y el subsistema de previews no dependa de la navegación; la columna `id` —`videos.id`— se incorporó en la **B4.2** como última columna para relacionar los marcadores persistentes con el video). Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. Abre y cierra su propia conexión en el hilo que la invoca (sin `check_same_thread=False`). **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar; si la base no existe (falta el archivo o el directorio padre), lanza `FileNotFoundError` sin crear archivos. La lectura nunca crea la base; la creación es responsabilidad de `conectar_bd()`/`main()`.
- `detectar_diferencias(carpeta, ruta_db=None, carpetas_protegidas=None)` — **detección no destructiva de diferencias** entre la carpeta de videos y el catálogo SQLite: primera parte de la sincronización completa. Compara los archivos de video de la carpeta (`escanear_videos(carpeta)`, solo `.mp4`/`.mkv`/`.avi` con extensión en minúsculas) con los registros de la base (un único `SELECT nombre, ruta FROM videos` sobre una conexión propia abierta y cerrada en `finally`; sin `check_same_thread=False`) y devuelve el dict `{"carpeta", "presentes_en_ambos", "nuevos", "ausentes_del_disco"}` con listas ordenadas (determinista). **Validación previa**: `carpeta` debe ser una ruta de texto no vacía (`ValueError`); carpeta inexistente → `FileNotFoundError` "Carpeta no encontrada: ..."; base inexistente → `FileNotFoundError` "Base de datos no encontrada: ...", en ambos casos **sin crear archivos**; `carpetas_protegidas` (si se pasa) debe ser una colección no texto (`TypeError`). **Modo tradicional** (sin `carpetas_protegidas`): idéntico al anterior — los ausentes son los registros **por nombre** no presentes en disco. **Modo multicarpeta** (Etapa 5, con `carpetas_protegidas`): un registro solo es ausente si su **ruta pertenece a la carpeta** (`_es_subcarpeta`/`os.path.commonpath`) y no está en disco — así los registros de otras raíces del alcance nunca se eliminan por error, y en carpetas solapadas los borrados dentro de cada carpeta sí se reconcilian. **Solo lectura**: no inserta, no actualiza ni elimina registros, no modifica miniaturas, no ejecuta FFprobe/FFmpeg y no llama a `sincronizar_bd`. **Ausencia deliberada**: no detecta movimientos ni renombrados (compara por nombre, sin hash ni identidad estable) y no recorre subcarpetas por sí misma.
- `preparar_plan_sincronizacion(diferencias)` — **preparación del plan de sincronización**: operación pura de la capa de catálogo que recibe el resultado de `detectar_diferencias()` y devuelve el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`. `a_incorporar` contiene los **registros básicos** de los videos nuevos preparados con `preparar_registros_basicos(nuevos, carpeta)` (claves `{nombre, ruta, extension, fecha_importacion}`, ruta absoluta); **`fecha_importacion` se genera al preparar esos registros** (marca ISO única del momento de la preparación), no durante `detectar_diferencias`. `ya_sincronizados` y `candidatos_a_eliminar` son listas ordenadas de nombres (los candidatos a eliminación son **únicamente informativos**). **Validación previa**: `diferencias` debe ser un dict (`TypeError`); faltar `carpeta`, `presentes_en_ambos`, `nuevos` o `ausentes_del_disco` → `ValueError` ("falta la clave obligatoria: ..."); `carpeta` texto no vacío (`ValueError`); las colecciones no pueden ser texto ni no iterables (`TypeError`, helper interno `_coleccion_nombres`). Las claves extra se ignoran. **Sin efectos**: el plan no inserta, actualiza ni elimina registros, **no accede a SQLite**, no ejecuta FFprobe ni FFmpeg y no está integrado al pipeline ni a la interfaz. **Ausencia deliberada**: la aplicación real del plan continúa pendiente y **no existe todavía deduplicación de nombres repetidos**.
- `aplicar_incorporaciones(plan, ruta_db=None)` — **aplicación no destructiva de las incorporaciones del plan de sincronización**: recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` producido por `preparar_plan_sincronizacion` y persiste **únicamente** `a_incorporar`, delegando en la escritura de colección `guardar_videos` (misma transacción atómica: un solo `connect`, todos los upserts, un solo `commit`, `rollback` total ante cualquier fallo, `close` en `finally`). **Validación completa previa** (antes de delegar y de abrir SQLite): `plan` no-dict → `TypeError`; falta de `carpeta`, `a_incorporar`, `ya_sincronizados` o `candidatos_a_eliminar` → `ValueError`; `carpeta` texto no vacío (`ValueError`); `a_incorporar` no texto e iterable (validación sin consumirla; `TypeError` en caso contrario); `ya_sincronizados` y `candidatos_a_eliminar` se validan como colecciones de nombres (helper interno `_coleccion_nombres`). Cada registro de `a_incorporar` se valida también dentro de `guardar_videos` (`_validar_registro_video`) antes de abrir SQLite. **No destructivo**: no elimina registros, **no modifica `ya_sincronizados`** ni reescribe los registros preexistentes que estén sincronizados y **no aplica `candidatos_a_eliminar`** (solo informa su cantidad). No altera las colecciones recibidas ni expone referencias internas mutables. Devuelve el resultado simple y estable `{"incorporados": <cantidad>, "nombres": [nombres en el orden de la colección], "pendientes_eliminacion": <cantidad de candidatos>}`. No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg/miniaturas/subprocesos y **no está integrada todavía al pipeline ni a la interfaz**: la eliminación controlada de `candidatos_a_eliminar` y la deduplicación de nombres repetidos continúan pendientes.
- `eliminar_candidatos(plan, ruta_db=None)` — **eliminación controlada de los candidatos ausentes del plan de sincronización**: recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` producido por `preparar_plan_sincronizacion` y elimina **únicamente** los registros nombrados en `candidatos_a_eliminar`, con el mismo patrón atómico de escritura: **una sola conexión**, un `DELETE FROM videos WHERE nombre = ?` por candidato (con `cursor.rowcount` para contar solo las eliminaciones reales), **un solo `commit`**, `rollback` total ante cualquier fallo y `close` en `finally`. La **validación completa previa** (compartida con `aplicar_incorporaciones` mediante el helper `_validar_plan_sincronizacion`) se ejecuta antes de abrir SQLite: `plan` no-dict → `TypeError`; falta de `carpeta`, `a_incorporar`, `ya_sincronizados` o `candidatos_a_eliminar` → `ValueError`; `carpeta` texto no vacío (`ValueError`); `a_incorporar` no texto e iterable (`TypeError`); `ya_sincronizados` y `candidatos_a_eliminar` como colecciones de nombres (helper `_coleccion_nombres`, que las devuelve **ordenadas**; por eso el orden procesado y devuelto es el **orden determinista de la validación actual**, no necesariamente el orden original de la colección del plan). El recorrido de eliminación usa esa colección ordenada. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos. **Solo registros**: no elimina archivos físicos ni miniaturas, no modifica `ya_sincronizados` ni los preexistentes sincronizados y no incorpora `a_incorporar`. Un candidato que no existe en la base no cuenta como eliminado y queda en `restantes`. **Colección vacía de candidatos**: válida, devuelve cero eliminaciones y **no modifica la base** (bytes y contenido idénticos). Devuelve el resultado `{"eliminados": <cantidad real>, "nombres": [eliminados en el orden determinista de la validación], "incorporados": <cantidad de `a_incorporar` o `None`>, "restantes": <candidatos no encontrados/no eliminados>}`; `incorporados` es **informativo y derivado del plan** (`len(plan["a_incorporar"])`, o `None` si no se puede medir, p. ej. una colección no materializable) y **no representa incorporaciones ejecutadas por esta función**. No ejecuta escaneo/FFprobe/FFmpeg/miniaturas/subprocesos, no reutiliza `conectar_bd`/`guardar_videos`/`sincronizar_bd` y **no está integrada todavía al pipeline ni a la interfaz**: la integración asíncrona de la sincronización completa sigue pendiente.
- `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` — **lectura paginada del catálogo**, claramente diferenciada de `listar_videos()` y preparada para que la interfaz consuma catálogos de decenas de miles de videos sin cargar todos los registros en memoria. Ejecuta en SQLite dos consultas con el **mismo filtro**: una consulta paginada (`SELECT ... FROM videos ORDER BY nombre LIMIT ? OFFSET ?`) y un `COUNT(*)`. Sin texto de búsqueda, cuenta y lista todo el catálogo; con texto, aplica a ambas consultas una coincidencia **parcial de nombre** (`LIKE` con patrón `%texto%`). Todos los valores (límite, desplazamiento, patrón) se pasan mediante **parámetros SQL**; nunca se interpola el texto buscado en el SQL. No lee primero toda la tabla, no cambia el esquema, no crea índices y no implementa ordenamiento configurable. **Validación previa a SQL**: `limite` debe ser entero positivo (bool → `TypeError`; ≤ 0 → `ValueError`); `desplazamiento` debe ser entero ≥ 0 (bool → `TypeError`; < 0 → `ValueError`); `texto` debe ser `None` o texto (`TypeError` en caso contrario). Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos. Devuelve la estructura estable `{"videos": [...], "total": <int>, "limite": <int>, "desplazamiento": <int>}`, donde cada elemento de `videos` conserva exactamente los mismos campos y el mismo formato que `listar_videos()` (tuplas de **nueve campos** `(nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id)`; `tamano_bytes` es `NULL`/`None` si el tamaño no se obtuvo; el `id` es la última columna, incorporada en la **B4.2**). Abre y cierra su propia conexión en el hilo que la invoca (sin `check_same_thread=False`). **Limitación conocida**: `%` y `_` del texto actúan como comodines SQL `LIKE` (no como caracteres literales); la comilla simple sí se trata literalmente. Pendiente de decisión si se acepta como contrato.
- `_asegurar_tabla_marcadores(conn)` — **migración aditiva e idempotente** de la tabla de
  marcadores (B4.2): `CREATE TABLE IF NOT EXISTS marcadores_video (id INTEGER PRIMARY KEY
  AUTOINCREMENT, video_id INTEGER NOT NULL, tiempo REAL NOT NULL)` e
  `idx_marcadores_video_video_id_tiempo`. **B6.3**: además añade la columna `color` mediante
  `_asegurar_columna_color`. Se invoca desde `conectar_bd` y desde la conexión
  del repositorio de marcadores. No activa `PRAGMA foreign_keys` ni usa `ON DELETE CASCADE`.
- `listar_marcadores(video_id, ruta_db=None)` — marcadores persistidos de un video, ordenados
  por tiempo; devuelve tuplas `(id, video_id, tiempo, color)` de la tabla `marcadores_video`
  (`WHERE video_id = ?`); `color` (B6.3) es una clave estable de `COLORES_CLASIFICACION` o
  `None` (color histórico rojo). **Validación previa**: `video_id` entero positivo (bool →
  `TypeError`; ≤ 0 → `ValueError`). Abre y cierra su propia conexión (mismo patrón que
  `listar_videos`); base inexistente → `FileNotFoundError` sin crear archivos. No ejecuta
  FFprobe/FFmpeg ni toca la interfaz.
- `guardar_marcador(video_id, tiempo, ruta_db=None, color=None)` — persiste un marcador y
  devuelve su **`id` de la base** (`cursor.lastrowid`). **B6.3**: `color` es opcional (clave
  estable o `None`) y se inserta en el mismo `INSERT`, nunca en una segunda escritura; los
  callers históricos sin color quedan en `NULL`. **Validación previa**: `video_id` entero
  positivo; `tiempo` numérico no negativo (bool → `TypeError`; < 0 → `ValueError`); `color`
  validado con `_validar_color_clasificacion`. Ciclo transaccional:
  conexión propia, `INSERT`, `commit` solo si terminó correctamente, `rollback` ante error y
  `close` en `finally`. No ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `eliminar_marcador(marcador_id, ruta_db=None)` — elimina un marcador por su `id`; devuelve
  `True` si se eliminó una fila (`rowcount > 0`) y `False` si no existía. **Validación previa**:
  `marcador_id` entero positivo. Ciclo transaccional propio (patrón de `guardar_marcador`).
- **Paleta cerrada de clasificación por color (B6.3).** `COLORES_CLASIFICACION` — paleta de 6
  colores `(clave, r, g, b)` (rojo, naranja, amarillo, verde, azul, violeta), **única fuente de
  verdad** del subsistema de clasificación (la UI y la configuración solo expresan colores
  mediante estas claves). La misma paleta sirve para **marcadores y segmentos**; `NULL`
  conserva los colores históricos (marcador rojo, segmento azul). API: `CLAVES_COLOR_CLASIFICACION`
  (frozenset de claves), `color_rgb(clave)` (RGB o `None`) y `_validar_color_clasificacion(clave)`
  (`None` aceptado = quitar color; no-texto → `TypeError`; clave ajena a la paleta → `ValueError`).
- `_asegurar_columna_color(conn, tabla)` — **migración aditiva e idempotente** de la columna
  `color TEXT NULL` (B6.3), invocada desde `_asegurar_tabla_marcadores`,
  `_asegurar_tabla_segmentos` y los conectores de los repositorios. Consulta
  `PRAGMA table_info(tabla)` y ejecuta `ALTER TABLE ... ADD COLUMN` solo si falta; no toca los
  datos existentes (los registros históricos quedan en `NULL`).
- `asignar_color_marcador(marcador_id, clave, ruta_db=None)` — asigna o quita (`clave=None`)
  el color de clasificación de un marcador persistido (B6.3): `UPDATE marcadores_video SET
  color = ? WHERE id = ?` en ciclo transaccional propio (`commit`/`rollback`/`close`); devuelve
  la fila persistida `(id, video_id, tiempo, color)` si el marcador existía (`rowcount > 0`) o
  `None` si no. **Validación previa**: `marcador_id` entero positivo y clave con
  `_validar_color_clasificacion`.
- **Segmentos con color (B6.3).** Las funciones del repositorio de segmentos
  (`listar_segmentos`, `listar_segmentos_de`, `guardar_segmento`) siguen el mismo esquema que
  sus equivalentes de marcadores: `color` como último campo de la tupla (B6.3) y parámetro
  opcional de creación en el mismo `INSERT`, con `None` que conserva el color histórico azul.
  `asignar_color_segmento(segmento_id, clave, ruta_db=None)` es el análogo de
  `asignar_color_marcador` (devuelve la fila `(id, inicio, fin, color)` o `None`).
- `main()` — CLI: sincroniza el catálogo contra `videos_prueba/` (ruta resuelta por `rutas.py`).

### `rutas.py` — capa centralizada de resolución de rutas
Único módulo responsable de derivar las rutas del proyecto a partir de su ubicación real, sin depender del directorio de trabajo. La raíz se resuelve con `_directorio_base()`: en **modo PyInstaller** (`getattr(sys, "frozen", False)` verdadero) usa `os.path.dirname(sys.executable)` —la carpeta del ejecutable empaquetado—; ejecutándose desde el código fuente usa `os.path.dirname(os.path.abspath(__file__))`. Así los datos (`biblioteca.db`, `miniaturas/`, `configuracion.json`) se crean junto al ejecutable portable o junto al proyecto de desarrollo según el modo:

- `ruta_raiz()` — directorio raíz del proyecto.
- `ruta_biblioteca()` — ruta de `biblioteca.db`.
- `ruta_carpeta_miniaturas()` — ruta de `miniaturas/`.
- `ruta_carpeta_videos()` — ruta de `videos_prueba/`.
- `ruta_configuracion()` — ruta de `configuracion.json` (configuración local del usuario).

Diseñado como punto único de extensión para futuras rutas de configuración; no constituye todavía un módulo de configuración completo.

### `apertura_videos.py` — servicio de apertura de videos
Módulo **de servicio** que separa de la interfaz la apertura de un video con la aplicación predeterminada de Windows. Es el **único módulo que ejecuta `os.startfile`** (verificado por AST de `visor_videos.py` en `prueba_doble_clic.py`):

- `abrir_video_con_aplicacion_predeterminada(nombre, carpeta)` — recibe el **nombre** del video y la **carpeta** en la que se encuentra; **valida ambos** como texto no vacío (tras `strip()`; `None`, `""`, solo espacios o un no-texto → `ValueError`), construye la **ruta absoluta** (`os.path.abspath(os.path.join(carpeta, nombre))`) **fuera de la interfaz**, valida con `os.path.isfile` que el archivo exista (si no → `FileNotFoundError` con la ruta) y abre el video con `os.startfile(ruta)`. Devuelve la ruta absoluta. Un fallo del propio `os.startfile` (p. ej. falta la aplicación asociada) propaga `OSError`. No abre SQLite, no ejecuta FFprobe/FFmpeg, no usa subprocesos (`Popen`/`subprocess`) y no toca la interfaz.

### `playlist_vlc.py` — integración de playlists VLC (B4.4)
Módulo **de servicio** que aísla de la interfaz la integración con **VLC** mediante **playlists puras** (una entrada por marcador). Sin HTTP, sin libVLC, sin automatización de teclas ni de botones:

- `localizar_vlc()` — resuelve `vlc.exe` en orden: `%ProgramFiles%\VideoLAN\VLC\vlc.exe`, `%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe` y `shutil.which("vlc")`. Sin registro ni búsquedas recursivas de discos; devuelve `None` si no se encuentra.
- `formatear_tiempo_vlc(segundos)` — texto de `start-time` conservando **precisión decimal** razonable (p. ej. `12.437`), recortando el ruido de punto flotante (`0.30000000000000004` → `0.3`). No modifica los datos persistidos.
- `formatear_titulo_marcador(nombre, segundos)` — título descriptivo tipo `video.mp4 — 00:01:12.437` (`H:MM:SS.mmm`), limpiando saltos de línea.
- `limpiar_playlists_anteriores(directorio)` — elimina **solo** las playlists propias previas `visor_marcadores_*.m3u` del directorio indicado (un solo nivel, sin subdirectorios). Un archivo bloqueado se ignora (`except OSError: pass`) y la limpieza continúa. Nunca toca `.m3u` ajenos ni recorre el árbol.
- `generar_m3u(entradas, ruta_destino)` — escribe el `.m3u` en **UTF-8 explícito** (soporta espacios, acentos y Unicode). **Primero** limpia las playlists propias anteriores de `os.path.dirname(ruta_destino)` y **después** escribe la nueva (no borra la playlist recién lanzada). Cada entrada `{ruta, nombre, tiempo}` se serializa como `#EXTINF:-1,<título>` + `#EXTVLCOPT:start-time=<segundos>` + `<ruta absoluta>`.
- `abrir_playlist_en_vlc(ruta_m3u, ruta_vlc)` — lanza **VLC una única vez** con la playlist completa (`subprocess.Popen([ruta_vlc, ruta_m3u])`), sin loop automático.

### `configuracion.py` — servicio de persistencia de configuración
Módulo **de servicio** que separa de la interfaz la persistencia de la configuración local del usuario en un archivo JSON (`configuracion.json` en la raíz del proyecto, gitignored). Persiste la **última carpeta seleccionada**. No abre SQLite, no ejecuta FFprobe/FFmpeg y no toca la interfaz:

- `CLAVE_CARPETA = "ultima_carpeta"` — clave del JSON con la carpeta persistida.
- `VARIABLE_ENTORNO = "VISOR_CONFIG"` — variable de entorno que redirige la ruta del archivo de configuración; la usan **solo las suites de prueba** para aislarse del archivo real del usuario. No es una bandera de depuración: es una redirección de ubicación y el arnés de pruebas la emplea para no tocar `configuracion.json`.
- `_resolver_ruta_config(ruta_config)` — orden de resolución de la ruta: si se recibe una `ruta_config` explícita se usa esa; si no, la variable de entorno `VISOR_CONFIG` (absolutizada); si tampoco hay entorno, `ruta_configuracion()`.
- `guardar_ultima_carpeta(carpeta, ruta_config=None)` — persiste la carpeta. **Validación previa**: `carpeta` texto no vacío tras `strip()` (si no → `ValueError`); la ruta se **absolutiza** (`os.path.abspath`) y se comprueba con `os.path.isdir` que exista y sea un directorio (si no → devuelve `None` sin escribir). Escritura **atómica**: lee el JSON existente (o `{}`), añade `CLAVE_CARPETA` y escribe en un archivo temporal `<ruta>.tmp` que luego se **reemplaza** con `os.replace` (no quedan archivos parciales). Crea el directorio padre con `os.makedirs(..., exist_ok=True)`. Devuelve la ruta absoluta guardada.
- `obtener_ultima_carpeta(ruta_config=None)` — restaura la carpeta persistida. **Tolerante**: si el archivo no existe, el JSON es corrupto (`OSError`/`ValueError`), no es un diccionario, la clave no es texto no vacío o la carpeta dejó de existir, devuelve `None` sin lanzar y sin crear el archivo. Devuelve la ruta **absoluta**.
- Internos: `_leer(ruta_config)` (JSON a `dict` o `None` ante ausencia/corrupción) y `_escribir(datos, ruta_config)` (escritura atómica con `.tmp` + `os.replace`). Persiste además la preferencia `incluir_subcarpetas` (booleano) mediante `guardar_preferencia_subcarpetas(activado, ruta_config)` y `obtener_preferencia_subcarpetas(ruta_config)` (devuelve `False` por defecto), y la preferencia **`escaneo_automatico`** (booleano) mediante `CLAVE_ESCANEO_AUTOMATICO = "escaneo_automatico"`, `guardar_preferencia_escaneo_automatico(activado, ruta_config)` y `obtener_preferencia_escaneo_automatico(ruta_config)` (**devuelve `True` por defecto**, preservando el comportamiento previo y la compatibilidad con archivos de configuración antiguos sin la clave). **Etapa B3.3**: además persiste el **tamaño de las miniaturas** mediante `CLAVE_TAMANIO_MINIATURAS = "tamano_miniaturas"`, `guardar_tamano_miniaturas(nombre, ruta_config)` (valida `pequeno`/`mediano`/`grande`; valor inválido → `None` sin escribir) y `obtener_tamano_miniaturas(ruta_config)` (**devuelve `"mediano"` por defecto**; si el valor almacenado no es texto o no es uno de los tres tamaños válidos vuelve automáticamente a `"mediano"`), con el mismo patrón atómico. **Etapa B3.5**: además persiste el **retardo de la vista ampliada** mediante `CLAVE_RETARDO_VISTA_AMPLIADA = "retardo_vista_ampliada_ms"`, `guardar_retardo_vista_ampliada(ms, ruta_config)` (valida los valores discretos `-1/0/250/400/600`; `-1` = "Desactivado" desde la Etapa B3.14a; valor inválido → `None` sin escribir) y `obtener_retardo_vista_ampliada(ruta_config)` (**devuelve `400` por defecto**; valor almacenado inválido → `400`), aditivo y sin migración para configuraciones antiguas. **Etapa B3.7**: además persiste el **factor de la vista ampliada** mediante `CLAVE_TAMANO_VISTA_AMPLIADA = "tamano_vista_ampliada"`, `guardar_tamano_vista_ampliada(factor, ruta_config)` (valida `1.2/1.6/2.0/2.5/3.0/3.5`, con 3.0 y 3.5 incorporados en la Etapa B3.14b; valor inválido → `None` sin escribir) y `obtener_tamano_vista_ampliada(ruta_config)` (**devuelve `1.6` por defecto**; valor almacenado inválido → `1.6`), también aditivo.

- **Nombres globales de colores de la clasificación (B6.3).** Persiste en el mismo
  `configuracion.json` los nombres visibles opcionales por clave de paleta, **sin cambiar las
  claves estables**: `CLAVE_NOMBRES_COLORES = "nombres_colores"` (clave raíz del JSON),
  `LIMITE_LONGITUD_NOMBRE_COLOR = 40` y `NOMBRES_COLORES_POR_DEFECTO` (de fábrica). API:
  `guardar_nombre_color(clave, nombre, ruta_config=None)` (permite solo claves de la paleta y
  texto ≤ 40 tras `strip()`; un nombre vacío elimina la entrada y restaura el de fábrica;
  devuelve el texto efectivo o `None`), `obtener_nombres_colores(ruta_config=None)` (solo
  claves válidas, recortadas y dentro del límite) y `texto_color(clave, ruta_config=None)`
  (nombre configurado o el de fábrica; `None` para claves ajenas). Mismo patrón atómico
  `.tmp` + `os.replace`; aditivo, sin migración (configuraciones antiguas sin la clave usan
  los nombres de fábrica).

### `arbol_navegacion.py` — árbol de navegación del panel izquierdo
Módulo **de interfaz** que encapsula el árbol del panel izquierdo, base del futuro Centro de Navegación. Separado en un módulo propio para no mezclar la lógica de archivos con el resto de la interfaz:

- `TEXTO_RAIZ = "Este equipo"` — texto del nodo raíz del árbol.
- `discos_disponibles()` — devuelve las unidades disponibles del sistema (solo Windows). Recorre `string.ascii_uppercase` y conserva las letras cuya raíz `X:\` existe (`os.path.exists`). Lógica pura: sin Qt, sin SQLite, sin subprocesos y sin dependencias externas.
- `carpetas_de(ruta)` — **función pura** que devuelve los subdirectorios inmediatos de `ruta` (solo directorios, sin archivos), ordenados alfabéticamente de forma insensible a mayúsculas (`sorted(..., key=str.lower)`). Tolerante: cualquier error de acceso al sistema de archivos (`OSError` en general: permiso denegado, ruta inexistente, archivo) devuelve `[]` sin interrumpir la exploración.
- `ROL_RUTA = Qt.UserRole + 1` / `ROL_CARGADO = Qt.UserRole + 2` / `ROL_PLACEHOLDER = Qt.UserRole + 3` / `ROL_ESTADO = Qt.UserRole + 4` — roles de datos de cada nodo: ruta absoluta, estado de carga, marcador de hijo placeholder y estado visual (valor de `EstadoNodo`).
- `EstadoNodo(IntEnum)` — estados visuales del nodo, preparados para crecer sin cambiar la API pública: `SIN_ESCANEAR = 0`, `ESCANEADA = 1`, `PARCIAL = 2`, `CAMBIOS_PENDIENTES = 3`, `ERROR = 4` (en esta etapa solo se usan `SIN_ESCANEAR` y `ESCANEADA`).
- `ArbolNavegacion(QTreeWidget)` — widget del árbol (Etapa 2.9): `setHeaderHidden(True)` (sin encabezado), `setSelectionMode(QAbstractItemView.SingleSelection)` (selección funcional de discos y carpetas), nodo raíz `TEXTO_RAIZ` expandido y un hijo por disco (`discos_disponibles()`). **Carga diferida por placeholder**: cada disco y cada carpeta lleva un hijo ficticio marcado con `ROL_PLACEHOLDER` (y `Qt.NoItemFlags`) para mostrar el indicador de expansión; `itemExpanded` conectado **internamente** a `_al_expandir` → `_cargar`, que al expandir un nodo **quita el placeholder y consulta únicamente sus hijos inmediatos** (un solo nivel, sin recorrer el árbol completo ni precalcular niveles posteriores). El estado de carga se guarda **en el propio nodo** (`ROL_CARGADO`), por lo que re-expandir no recarga ni duplica; la ruta absoluta de cada nodo queda en `ROL_RUTA`. Una carpeta sin subdirectorios queda sin hijos y sin flecha. **Selección funcional**: el método público **`carpeta_actual()`** es la interfaz oficial para consultar la carpeta seleccionada (ruta absoluta almacenada en `_ruta_actual`, o `None`); la señal de clase **`ruta_seleccionada = Signal(str)`** solo **notifica** cambios de selección. El handler `_al_cambiar_actual` (conectado a `currentItemChanged`) valida el nodo con `_ruta_valida()`: el nodo raíz "Este equipo" (sin `ROL_RUTA`) y los placeholders (`ROL_PLACEHOLDER`) **nunca son selección válida** — no modifican `carpeta_actual()` ni emiten rutas. Al contraer un ancestro, si el ítem previamente seleccionado queda oculto (`anterior.isHidden()`), se **conserva `_ruta_actual`** sin reemitir; no hay restauración visual automática de la selección (decisión de diseño). **Sincronización app → árbol**: el método público **`seleccionar_ruta(ruta)`** busca **solo entre los nodos ya cargados** (recursión en memoria, sin recorrer el sistema de archivos ni cargar carpetas nuevas), expande los ancestros ya cargados y hace `setCurrentItem`; si la ruta no está presente, no modifica la selección ni lanza. **Restauración de la carpeta persistida**: el método público **`revelar_ruta(ruta)`** reconstruye **estrictamente de forma incremental** la rama necesaria para volver a mostrar una carpeta: ubica el disco que contiene la ruta (`_buscar_disco` por prefijo común), expande cada nivel (disparando la carga diferida existente) y busca únicamente el siguiente componente (`_buscar_hijo_por_ruta`, comparación insensible a mayúsculas con `os.path.normcase`), sin recorrer el árbol ni el disco completos ni cargar ramas ajenas al camino; selecciona la carpeta destino o devuelve `False` sin lanzar si no puede reconstruirla (disco ausente, carpeta eliminada, camino cambiado). **Fuente única de verdad**: el árbol puede cambiar la carpeta activa de la aplicación y reflejarla (el visor conecta `ruta_seleccionada` a `_al_carpeta_actual_arbol`), pero `carpeta_actual()` representa únicamente el estado interno del widget; el árbol no escanea, no toca el catálogo, SQLite ni el panel derecho. **Indicadores visuales (Etapa 2.9)**: el método público **`marcar_carpeta_escaneada(ruta)`** marca una carpeta como escaneada (agrega la ruta a `_carpetas_escaneadas` y actualiza su indicador; si el nodo aún no está cargado, el indicador se aplica al crearse por carga diferida). El estado de cada nodo se deriva por pertenencia en `_estado_de(item)` y se almacena **solo como valor** en `ROL_ESTADO` (`int`); la representación visual se calcula **exclusivamente** en `_icono_para(estado)` (checkmark estándar `QStyle.SP_DialogApplyButton` para `ESCANEADA`; sin ícono para `SIN_ESCANEAR`) — no se almacenan objetos `QIcon` en los datos del nodo. Marcar una carpeta **no altera** la selección, la expansión ni la navegación. El árbol **no conoce SQLite ni el catálogo**: recibe únicamente un conjunto de rutas. Se instancia en el constructor de `VisorVideos` como `self.arbol_navegacion` (contenido del panel izquierdo del `QSplitter`).

- **Modo de selección de carpetas y herramientas rápidas** (Bloque de trabajo 4, **Etapas 2-3, entrega conjunta**): `ArbolNavegacion(parent=None, seleccion=None)` recibe una referencia a **`SeleccionCarpetas`** (única fuente de verdad). `set_modo_seleccion(activo)` activa el modo: cada carpeta cargada muestra un **checkbox** cuyo estado refleja el conjunto (`_aplicar_check`, con guard `_sincronizando_checks` para ignorar emisiones espurias de `itemChanged` — los `QTreeWidgetItem` de PySide6 nacen checkables por defecto y `_crear_nodo_disco`/`_crear_nodo_carpeta` quedan envueltos en el guard); marcar/desmarcar modifica **solo** `SeleccionCarpetas` (`_al_item_cambiado` compara el estado con el conjunto y solo sincroniza si difiere), **sin** cambiar la carpeta activa, **sin** iniciar escaneos y **sin** alterar la navegación. Con el modo desactivado el árbol se comporta **exactamente igual que antes** (sin checkboxes; la raíz se limpia al construirse). **Herramientas de selección rápida**: `seleccionar_todas_nivel()` (hijos cargados del nivel actual), `deseleccionar_todas()` (vacía el conjunto), `invertir_nivel()` (invierte solo el nivel conservando lo externo, vía `_reemplazar_seleccion` = `limpiar` + `seleccionar_todas`), y por menú contextual (solo en modo selección) `seleccionar_hasta`/`deseleccionar_hasta`/`seleccionar_desde`/`deseleccionar_desde` sobre la **lista ordenada de hermanos** (`_hijos_ordenados`, orden visual = orden de `carpetas_de` = alfabético case-insensitive; `_rango_hasta`/`_rango_desde`). **Todas** las acciones solo materializan **rutas** en `SeleccionCarpetas` (sin intervalos ni estructuras paralelas) y refrescan los checks con `_refrescar_checks`.

### `visor_videos.py` — interfaz gráfica

**Infraestructura de paneles (QSplitter):** La ventana principal se divide en dos paneles permanentes mediante un `QSplitter` horizontal (`Qt.Horizontal`). El panel izquierdo (`QWidget`, minWidth=80, maxWidth=400) contiene el árbol de navegación (`ArbolNavegacion`, de `arbol_navegacion.py`) **más el toggle "Modo selección" y una fila de acciones rápidas** ("Seleccionar todas", "Deseleccionar todas", "Invertir", oculta salvo en modo selección) del Bloque 4 (Etapas 2-3): al activar el modo, el árbol muestra checkboxes sincronizados con `SeleccionCarpetas` y las acciones masivas operan sobre el nivel actual; en modo normal el árbol se comporta igual que antes. El árbol, en la Etapa 2.9, muestra el nodo raíz "Este equipo", los discos y sus carpetas (carga diferida por nivel), permite seleccionar discos y carpetas, **persiste y restaura** la carpeta activa, al seleccionar una carpeta válida **inicia automáticamente el escaneo solo si la preferencia "Escaneo automático" está activa** (el mismo `iniciar_escaneo()` del botón) y muestra un **indicador visual de carpetas escaneadas** (Etapa 2.9); la selección del árbol actualiza la **carpeta activa de la aplicación** (`carpeta_seleccionada` y `etiqueta_carpeta`) y el catálogo se actualiza mediante el pipeline existente, sin afectar el panel derecho. **Preferencia independiente (Etapa 2.8)**: "Escaneo automático al seleccionar carpeta" es independiente de "Incluir subcarpetas", soportando las cuatro combinaciones (escaneo automático × subcarpetas). **Verificación (Etapa 2.7)**: árbol, botón y diálogo comparten `iniciar_escaneo()` y respetan de forma **idéntica** el estado de "Incluir subcarpetas" (`configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())`); verificado por `prueba_subcarpetas_arbol.py`. El panel derecho contiene toda la interfaz existente sin cambios, encapsulada en la clase `PanelPrincipal` (ver abajo). El splitter utiliza `handleWidth=8` para garantizar que la barra divisoria pueda tomarse cómodamente con el mouse, y el cursor `Qt.SplitHCursor` se asigna exclusivamente al `QSplitterHandle` (no al splitter completo) mediante `splitter.handle(1).setCursor(Qt.SplitHCursor)`. El `setStretchFactor(0, 0)` y `setStretchFactor(1, 1)` hacen que solo el panel derecho se expanda al redimensionar la ventana.

**`PanelPrincipal(QWidget)`:** Subclase explícita del panel derecho (`visor_videos.py:285-302`). Redefine `minimumSizeHint()` para devolver `QSize(0, 0)`. Esta decisión arquitectónica fue necesaria porque el `minimumSizeHint` por defecto (~720 px) está dominado por la barra de herramientas `fila_carpeta` (9 widgets: botones, checkboxes, combo, labels) cuyo `minimumSizeHint` combinado fuerza un mínimo de ~703 px + márgenes. Sin la anulación, el QSplitter usa ese valor como tamaño mínimo efectivo del panel derecho, bloqueando el arrastre del divisor hacia la derecha porque el panel ya está en su mínimo. Al devolver `(0, 0)`, el splitter solo respeta el `minimumWidth` explícito del panel izquierdo (80 px), permitiendo que el divisor se arrastre libremente en ambas direcciones.

- `VisorVideos(QMainWindow)` — constructor `__init__(self, ruta_db=None, parent=None, ruta_config=None)`; ventana principal: `QSplitter` horizontal con panel izquierdo (árbol de navegación `ArbolNavegacion` con el nodo "Este equipo" y los discos) y panel derecho (`PanelPrincipal`) con fila de selección de carpeta (botón + etiqueta de ruta), barra de búsqueda, contador, botón "Cargar más", tarjetas horizontales (una por video, una fila por video en una única columna) dentro de un `QScrollArea`. Se construye **sin consultas SQLite**; la primera página del catálogo se carga en segundo plano mediante `GestorTareas` + `TareaLecturaCatalogoPaginada` (constantes `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO = "Cargando catálogo…"`, `MENSAJE_ERROR = "No se pudo cargar el catálogo"`, `MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"`, `MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"`, `MENSAJE_ERROR_TAMANOS = "No se pudieron obtener los tamaños de los archivos"`, `MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"`, `MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"`, `MENSAJE_ERROR_MINIATURAS = "No se pudieron generar las miniaturas"`, `MENSAJE_SINCRONIZANDO = "Sincronizando catálogo…"`, `MENSAJE_ERROR_SINCRONIZACION = "No se pudo sincronizar el catálogo"`, `MENSAJE_ERROR_RECARGA = "No se pudo actualizar el catálogo"`, `MENSAJE_ERROR_PAGINA = "No se pudo cargar la página"`, `MENSAJE_ERROR_ABRIR = "No se pudo abrir el video"`). Se construye **sin consultas SQLite**; la primera página del catálogo se carga en segundo plano y, tras una sincronización exitosa, se **recarga en segundo plano y se reconstruyen las tarjetas**; además el usuario puede **cargar manualmente una página adicional** con el botón "Cargar más", que agrega las tarjetas nuevas debajo de las ya cargadas **sin reemplazarlas** y **sin duplicados**. El pipeline de escaneo es `TareaEscaneo` → `TareaTamanosArchivos` → `TareaFFprobe` → `TareaMiniaturas` → `TareaGuardarVideos`, y tras el guardado exitoso se encadena la **sincronización completa** (`TareaSincronizacionCatalogo`) y la **recarga asíncrona del catálogo`. Tras cada carga inicial, recarga o página adicional, un **segundo `GestorTareas`** (`gestor_previews`) genera en segundo plano, en lotes de a 3 videos y mediante `TareaPreviewsProgresivas`, los **tres previews progresivos** de cada tarjeta (con un `QTimer` de 300 ms que evita competir con la carga del catálogo); cada tarjeta muestra sus previews de forma incremental a medida que se generan.
- `carpeta_seleccionada` — atributo con la carpeta elegida; comienza como `None` y, en el arranque, `obtener_ultima_carpeta(self._ruta_config)` **restaura la última carpeta persistida** si existe (si la carpeta persistida ya no existe o el JSON está ausente/corrupto devuelve `None` sin lanzar). **Es la única fuente de verdad de la carpeta activa de la aplicación**: el árbol puede cambiarla y reflejarla, y el diálogo también la cambia y persiste.
- `self.arbol_navegacion` / `_al_carpeta_actual_arbol(ruta)` — el árbol se guarda como atributo y su señal `ruta_seleccionada` se conecta a `_al_carpeta_actual_arbol`: valida `os.path.isdir`, ignora selecciones repetidas (`if self.carpeta_seleccionada == ruta: return`), asigna `carpeta_seleccionada = ruta`, actualiza `etiqueta_carpeta`, limpia `mensaje_carpeta`, **persiste** la carpeta con `guardar_ultima_carpeta(ruta, self._ruta_config)` (misma clave y escritura atómica que el diálogo), rearma botones (`_actualizar_botones_carpeta`) y **dispara el escaneo solo si la preferencia de escaneo automático está activa** (`_disparar_escaneo_si_automatico()` → `iniciar_escaneo()` si `self.escaneo_automatico.isChecked()`). El guard de repetición impide el disparo durante la restauración de arranque y la sincronización con el diálogo. **Sin** catálogo ni panel derecho. En el arranque, la carpeta restaurada se reconstruye con `self.arbol_navegacion.revelar_ruta(carpeta_guardada)`; si la ruta no puede reconstruirse, la aplicación queda **sin carpeta seleccionada** (`carpeta_seleccionada = None` y etiqueta `MENSAJE_SIN_CARPETA`) de forma consistente.
- `seleccionar_carpeta()` — el diálogo conserva su comportamiento intacto (validación, normalización, persistencia) y, tras seleccionar, llama `self.arbol_navegacion.seleccionar_ruta(ruta_absoluta)` para que el árbol refleje la carpeta elegida (solo si el nodo ya está cargado; si no, la aplicación sigue funcionando sin construir el árbol). Al finalizar dispara **un único escaneo solo si la preferencia de escaneo automático está activa** (`_disparar_escaneo_si_automatico()`); la sincronización posterior con el árbol no produce un segundo escaneo (guard de repetición).
- `boton_seleccionar_carpeta` / `etiqueta_carpeta` / `mensaje_carpeta` — botón "Seleccionar carpeta" (`QPushButton`), etiqueta de solo lectura con la ruta elegida (`QLabel` con `Qt.TextSelectableByMouse`) y etiqueta de mensajes de error, integrados en una fila superior sin rediseñar la ventana.
- `seleccionar_carpeta()` — abre `QFileDialog.getExistingDirectory`; si el usuario cancela, conserva la selección anterior; si la ruta es válida, la **normaliza con `os.path.abspath`** (ruta absoluta), la **valida con `os.path.isdir`** (existe y es directorio), la muestra en la etiqueta, la guarda en `carpeta_seleccionada` y la **persiste** llamando a `guardar_ultima_carpeta(ruta_absoluta, self._ruta_config)` (escritura atómica en `configuracion.json`); si la ruta no existe o no es un directorio, rechaza la selección, conserva la anterior y muestra `MENSAJE_RUTA_INVALIDA` sin cerrar la ventana. **Etapa 2.8**: seleccionar una carpeta válida (por el diálogo o por el árbol) **inicia automáticamente el escaneo solo si la preferencia "Escaneo automático" está activa** (mediante `_disparar_escaneo_si_automatico()` → el mismo punto de entrada `iniciar_escaneo()` del botón "Escanear carpeta"); con la preferencia desactivada, la carpeta queda seleccionada sin escanear (exactamente un disparo por acción del usuario; el guard de repetición evita dobles disparos). No accede a SQLite/FFprobe/FFmpeg directamente: todo ocurre en el pipeline existente. La selección **persiste** entre ejecuciones (restaurada al iniciar) **sin** escaneo automático en la restauración.
- `boton_escanear` / `incluir_subcarpetas` / `escaneo_automatico` / `estado_escaneo` — botón "Escanear carpeta" (`QPushButton`), casillas "Incluir subcarpetas" y "Escaneo automático" (`QCheckBox`) y etiqueta de estado del escaneo (`QLabel`), integrados en la fila de selección de carpeta. El botón queda habilitado solo si existe una carpeta válida y el gestor está `inactivo`. Al iniciar el escaneo, el estado de la casilla de subcarpetas se comunica al módulo `escanear_videos` mediante `configurar_escaneo_recursivo()`. Ambas casillas persisten al cambiar (`stateChanged` → `guardar_preferencia_subcarpetas` / `guardar_preferencia_escaneo_automatico`) y se restauran al iniciar (`obtener_preferencia_subcarpetas` / `obtener_preferencia_escaneo_automatico`). El botón "Escanear carpeta" **ignora** la preferencia de escaneo automático (siempre escanea).
- `barra_progreso` — `QProgressBar` visible bajo la barra de búsqueda durante el pipeline. **Modo indeterminado (rango 0-0)** para las etapas sin avance real (escaneo, sincronización, recarga): muestra solo el texto de la etapa. **Modo determinado** durante tamaños, FFprobe, miniaturas y guardado (Etapa B3.21) y durante Copiar/Pegar/Eliminar (Etapa B3.22): `_mostrar_progreso()` restablece siempre el rango `(0,0)` al iniciar cada paso (no arrastra el rango de la etapa anterior), guarda el texto en `self._texto_progreso` y reinicia `self._progreso_detallado`; el handler `_al_progreso_pipeline(procesado, total)` (conectado tanto a `gestor.tarea_progreso` como a `gestor_operaciones.tarea_progreso`) fija `setRange(0, total)` + `setValue(procesado)` y, **solo la primera vez de cada etapa** (Etapa B3.23), aplica el formato detallado `"{texto} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar` (nombre de la etapa + "N de M" + porcentaje). Muestra la etapa actual mediante `setFormat()` con los textos "Escaneando…", "Obteniendo tamaños…", "Leyendo metadatos…", "Generando miniaturas…", "Guardando…", "Sincronizando…", "Actualizando catálogo…", "Copiando…", "Pegando…" y "Eliminando…". Se oculta al finalizar (`_al_resultado_recarga`, `_al_resultado_*` de operaciones) o ante cualquier error (`_limpiar_cadena`). **Exclusión mutua** (Etapa B3.22): las operaciones no pueden iniciarse mientras el pipeline principal esté activo (`self.gestor.activo`) — guard en `_iniciar_copia/pegar/eliminar` y reflejado en `_actualizar_boton_copiar/pegar/eliminar`. Controlada por la bandera `_pipeline_activo` y los métodos privados `_mostrar_progreso(texto)` y `_ocultar_progreso()`.
- `Tarjeta.seleccionada` / `Tarjeta.seleccion_por_rango` / `Tarjeta.menu_contextual` / `_nombres_seleccionados` — selección visual de filas con `mousePressEvent` en la clase `Tarjeta`. Un clic izquierdo sin modificadores emite `seleccionada(nombre, ctrl)` hacia `_al_seleccionar_tarjeta`. Sin Ctrl: selecciona una única fila y deselecciona las demás. Con Ctrl: agrega o quita la fila de la selección múltiple. Con Shift (`Qt.ShiftModifier`): emite `seleccion_por_rango(nombre)` hacia `_al_seleccion_por_rango`, que selecciona todas las filas del rango comprendido entre el ancla (`_ancla_seleccion`) y la fila clickeada, según el orden visible (`self.visibles`). Si no existe un ancla o el ancla ya no está visible, Shift+clic equivale a un clic normal (selecciona una y establece nuevo ancla). El ancla se actualiza en cada selección simple, Ctrl+clic y Shift+clic sin ancla previa; no se modifica durante un rango Shift+clic. `_reemplazar_tarjetas` limpia el ancla. El clic derecho (`Qt.RightButton`) emite la señal `menu_contextual(nombre)`; si la tarjeta no estaba seleccionada, primero la selecciona (deseleccionando las demás); si ya pertenecía a una selección múltiple, la conserva intacta. El método `_mostrar_menu_contextual` construye un `QMenu` con cinco acciones —"Abrir" (reutiliza `_abrir_video`, idéntico al doble clic), "Abrir carpeta" (abre la carpeta seleccionada con `os.startfile`), "Copiar ruta" (copia la ruta completa del video sobre el que se abrió el menú), "Copiar rutas de los seleccionados" (copia todas las rutas, una por línea, en orden visible) y "Abrir carpetas de los seleccionados" (abre las carpetas de todos los videos seleccionados, deduplicando para no abrir la misma carpeta más de una vez)— y lo muestra con `menu.exec(QCursor.pos())`. El conjunto `_nombres_seleccionados` (expuesto como `@property nombres_seleccionados`) rastrea los nombres seleccionados. `Tarjeta.marcar_seleccionada(True/False)` aplica o remueve un borde azul de 3px (`ESTILO_SELECCIONADA`). La selección persiste al filtrar y se restaura automáticamente al reconstruir tarjetas (`_reemplazar_tarjetas`): los nombres que siguen existiendo en el nuevo conjunto se vuelven a marcar (estado interno y estilo visual sincronizados); los nombres que ya no aparecen se descartan. El doble clic (`mouseDoubleClickEvent`) no interfiere con la selección.
- `videos_detectados` — atributo de la operación de escaneo: lista de archivos de video detectados en la última ejecución exitosa; comienza como `None` (aún no se escaneó) y no persiste entre ejecuciones.
- `iniciar_escaneo(carpetas=None)` — **punto de entrada único del escaneo**, usado por el botón "Escanear carpeta" (`boton_escanear.clicked`, **incondicional**, conectado con lambda para no pasar el `bool` de `clicked`) y, mediante `_disparar_escaneo_si_automatico()` (solo si la preferencia "Escaneo automático" está activa), por la selección de una carpeta en el árbol (`_al_carpeta_actual_arbol`) y por el diálogo (`seleccionar_carpeta`). **Alcance (Etapas 4-6, Bloque 4):** la fuente de verdad del alcance es el **selector de modo** (`_modo_alcance`, Etapa 6): "Solo carpeta actual" → `[carpeta_seleccionada]` sin recursión; "Carpeta actual y todas las subcarpetas" → `[carpeta_seleccionada]` con recursión; "Selección personalizada" → `seleccion_carpetas.obtener_seleccion()` con recursión. Además acepta `carpetas=None` (→ según el modo), una cadena (una carpeta) o una **lista de carpetas** (escaneo multicarpeta); filtra carpetas inexistentes y **deduplica** (`dict.fromkeys`). Luego **normaliza el alcance efectivo** (`_alcance_efectivo`, Etapa 5): si la recursión está **desactivada**, conserva la lista tal cual; si está **activada**, elimina las **raíces descendientes redundantes** (cualquier carpeta contenida en otra del alcance, detectada con `_ruta_contiene`/`os.path.commonpath` sobre rutas normalizadas — comparación robusta que no confunde prefijos como `C:\Videos` y `C:\Videos2`), de modo que el mismo archivo físico nunca se escanea dos veces. Para cada carpeta del alcance efectivo ejecuta la cadena completa existente (`_iniciar_escaneo_carpeta`: escaneo → tamaños → FFprobe → miniaturas → guardado → **sincronización** → recarga) **secuencialmente** mediante la cola `_cola_carpetas_escaneo`; `_al_tarea_finalizada` avanza a la siguiente carpeta al terminar cada cadena, y la **unión** queda materializada en el catálogo global. Con una sola carpeta el comportamiento es **idéntico** al anterior. El checkbox "Incluir subcarpetas" queda únicamente como **adaptador de compatibilidad oculto** (`incluir_subcarpetas`, no visible): su estado se sincroniza bidireccionalmente con el modo (una llamada `setChecked(True)` equivale a elegir "Carpeta actual + subcarpetas") para no romper llamadas existentes; `_sincronizar_alcance_desde_modo`, `_al_cambiar_modo_alcance` y `_al_cambiar_subcarpetas` mantienen la sincronización con guard de reentrada.
- `_al_resultado_escaneo(videos)` — al recibir la lista, la copia en `videos_detectados`, limpia `_escaneo_pendiente`, **marca `_ffprobe_pendiente = True`** (para que el resultado/error siguiente pertenezca a FFprobe) y muestra el conteo en `estado_escaneo` ("1 video detectado" / "N videos detectados"). No crea tarjetas ni recarga el catálogo.
- `_al_error_escaneo(mensaje)` — ante un fallo (carpeta inexistente, ruta que no es carpeta, etc.): limpia `_escaneo_pendiente` y `_guardado_pendiente` y muestra `MENSAJE_ERROR_ESCANEO` ("No se pudo escanear la carpeta"). **El último resultado exitoso se conserva**: `videos_detectados` no se borra si ya tenía un valor previo.
- `_tamanos_pendiente` / `tarea_tamanos` / `resultado_tamanos` — atributos del **paso de tamaño de archivo** del encadenamiento: estado interno que enruta el resultado/error de `TareaTamanosArchivos`, la tarea en curso y el último resumen de `obtener_tamanos_archivos` (`None` hasta que termina).
- `_iniciar_tamanos()` — se lanza al recibir `tarea_finalizada` del escaneo (gestor `inactivo` y `_tamanos_pendiente` activo): valida que existan `tarea_escaneo` y `videos_detectados`, crea `TareaTamanosArchivos(videos_detectados, tarea_escaneo.carpeta)` y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena. Solo consulta el sistema de archivos (`os.path.getsize`); no abre SQLite ni ejecuta FFprobe/FFmpeg.
- `_al_resultado_tamanos(resultado)` — al recibir el resumen de `TareaTamanosArchivos`: limpia `_tamanos_pendiente`, **marca `_ffprobe_pendiente = True`** (para que el resultado/error siguiente pertenezca a FFprobe), guarda el resultado en `resultado_tamanos` y libera `tarea_tamanos`. No crea tarjetas ni recarga el catálogo.
- `_al_error_tamanos(mensaje)` — ante un fallo de la obtención de tamaños (carpeta inexistente, contrato inválido, etc.): limpia la cadena y muestra `MENSAJE_ERROR_TAMANOS` ("No se pudieron obtener los tamaños de los archivos"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el último resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_ffprobe_pendiente` / `tarea_ffprobe` / `resultado_ffprobe` — atributos del **paso de metadatos FFprobe** del encadenamiento: estado interno que enruta el resultado/error de FFprobe, la tarea `TareaFFprobe` en curso y el último resultado de FFprobe (`None` hasta que termina).
- `_iniciar_ffprobe()` — se lanza al recibir `tarea_finalizada` del escaneo (gestor `inactivo` y `_ffprobe_pendiente` activo): construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta, nombre)`) de los videos detectados y crea `TareaFFprobe(rutas, nombres=self.videos_detectados, stats=self.resultado_tamanos, ruta_db=self._ruta_db)` (**B4.5 Etapa 3**: la clasificación ocurre en el worker, la UI no consulta SQLite) y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena.
- `_al_resultado_ffprobe(resultado)` — al recibir el resumen de `TareaFFprobe`: limpia `_ffprobe_pendiente`, **marca `_miniaturas_pendiente = True`** (para que el resultado/error siguiente pertenezca a las miniaturas), guarda el resultado en `resultado_ffprobe` y libera `tarea_ffprobe`. No crea tarjetas ni recarga el catálogo.
- `_al_error_ffprobe(mensaje)` — ante un fallo global de FFprobe (subproceso ausente, error del ejecutable, etc.): limpia la cadena y muestra `MENSAJE_ERROR_FFPROBE` ("No se pudieron obtener los metadatos"). **El último resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_miniaturas_pendiente` / `tarea_miniaturas` / `resultado_miniaturas` — atributos del **paso de miniaturas** del encadenamiento: estado interno que enruta el resultado/error de `TareaMiniaturas`, la tarea en curso y el último resumen de `asegurar_miniaturas` (`None` hasta que termina).
- `_iniciar_miniaturas()` — se lanza al recibir `tarea_finalizada` de FFprobe (gestor `inactivo` y `_miniaturas_pendiente` activo): valida que existan `tarea_escaneo` y `videos_detectados`, construye el mapa de duraciones desde `self.resultado_ffprobe` (`_duraciones_desde_ffprobe`, **B4.5**), crea `TareaMiniaturas(videos_detectados, tarea_escaneo.carpeta, duraciones=duraciones)` y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena. FFmpeg se ejecuta únicamente dentro de la tarea (nunca en el hilo principal ni directamente desde la interfaz).
- `_al_resultado_miniaturas(resultado)` — al recibir el resumen de `TareaMiniaturas`: limpia `_miniaturas_pendiente`, **marca `_guardado_pendiente = True`** (para que el resultado/error siguiente pertenezca al guardado), guarda el resultado en `resultado_miniaturas` y libera `tarea_miniaturas`. No crea tarjetas ni recarga el catálogo.
- `_al_error_miniaturas(mensaje)` — ante un fallo de la generación de miniaturas (FFmpeg ausente, error del ejecutable, etc.): limpia la cadena y muestra `MENSAJE_ERROR_MINIATURAS` ("No se pudieron generar las miniaturas"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el último resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_guardado_pendiente` / `tarea_guardado` / `registros_guardados` — atributos del **encadenamiento de guardado**: estado interno que enruta el resultado/error del guardado, la tarea `TareaGuardarVideos` en curso y la cantidad de registros persistidos (`None` hasta que termina el guardado).
- `_al_tarea_finalizada()` — **dispara el paso siguiente de la cadena al terminar cada tarea**: cuando el gestor vuelve a `inactivo` (el gestor solo admite una tarea a la vez), enruta según el flag activo: si `_escaneo_pendiente` está activo no hace nada (el resultado del escaneo ya marcó el siguiente flag); si `_tamanos_pendiente` está activo inicia `TareaTamanosArchivos` (ver `_iniciar_tamanos`); si `_ffprobe_pendiente` está activo inicia `TareaFFprobe` (ver `_iniciar_ffprobe`); si `_miniaturas_pendiente` está activo inicia `TareaMiniaturas` (ver `_iniciar_miniaturas`); si `_guardado_pendiente` está activo inicia `TareaGuardarVideos` (ver `_iniciar_guardado`); si no hay flag activo y el gestor vuelve a `inactivo`, limpia la cadena.
- `_iniciar_guardado()` — se lanza al recibir `tarea_finalizada` de las miniaturas (gestor `inactivo` y `_guardado_pendiente` activo): valida que existan `tarea_escaneo`, `videos_detectados`, `resultado_tamanos`, `resultado_ffprobe` y `resultado_miniaturas`, prepara los registros con `combinar_registros_con_ffprobe(videos_detectados, tarea_escaneo.carpeta, resultado_ffprobe)` (claves básicas + metadatos FFprobe; `NULL` si faltan), luego los combina con `combinar_registros_con_miniaturas(registros, resultado_miniaturas)` (clave `cantidad_miniaturas` por ruta; `None` si no hay coincidencia o el resultado es `None`) y finalmente con `combinar_registros_con_tamanos(registros, resultado_tamanos)` (clave `tamano_bytes` por ruta; `None` si no hay coincidencia o el archivo no es legible), y persiste el resultado con `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo `GestorTareas`; si el inicio falla, limpia la cadena. No se ejecuta FFmpeg ni FFprobe en este paso.
- `_al_resultado_guardado(resultado)` — al recibir `{"guardados": n, "nombres": [...]}`: limpia `_guardado_pendiente`, libera `resultado_ffprobe` y `resultado_miniaturas`, guarda la cantidad en `registros_guardados` y habilita de nuevo el botón de escaneo (gestor `inactivo`). No crea tarjetas ni recarga el catálogo.
- `_al_error_guardado(mensaje)` — ante un fallo de escritura (base inexistente, base corrupta, contrato inválido): limpia `_guardado_pendiente` y muestra `MENSAJE_ERROR_GUARDADO` ("No se pudieron guardar los videos"). El gestor queda `inactivo` y la interfaz es recuperable: se puede iniciar un nuevo escaneo. No se eliminan registros preexistentes ni se recarga el catálogo.
- `_sincronizacion_pendiente` / `tarea_sincronizacion` / `resultado_sincronizacion` — atributos del **paso de sincronización** del encadenamiento: estado interno que enruta el resultado/error de `TareaSincronizacionCatalogo`, la tarea en curso y el **resultado completo** `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}` de la última sincronización exitosa (`None` hasta que termina o si no se sincronizó).
- `_iniciar_sincronizacion(carpeta=None)` — se lanza al recibir `tarea_finalizada` del guardado (gestor `inactivo` y `_sincronizacion_pendiente` activo). **Criterio de resolución de carpeta** (Etapa B3.18): usa, en orden, el parámetro opcional `carpeta` → el override temporal `_carpeta_sincronizacion` (si está fijado) → `self.carpeta_seleccionada`. Consume y limpia el override en el arranque para evitar reutilizaciones accidentales. Revalida la carpeta con `os.path.isdir` y crea `TareaSincronizacionCatalogo(carpeta, self._ruta_db, carpetas_protegidas=...)`; en **modo multicarpeta** (`_alcance_sincronizacion`, Etapa 5) las carpetas protegidas son las demás raíces del alcance efectivo, de modo que cada carpeta sincroniza sus propios registros **por ruta** sin eliminar los de otras raíces. La inicia con el **mismo** `GestorTareas` de la ventana; si el gestor rechaza la tarea o la carpeta dejó de ser válida, limpia la cadena. Muestra `MENSAJE_SINCRONIZANDO` ("Sincronizando catálogo…") y bloquea los controles mientras corre.
- `_al_resultado_sincronizacion(resultado)` — al recibir el resultado completo: limpia `_sincronizacion_pendiente`, libera `tarea_sincronizacion`, **conserva el resultado en `resultado_sincronizacion`** y muestra el resumen final en `estado_escaneo` mediante `texto_resumen_sincronizacion(resultado["resumen"])` ("Sincronización completa: N incorporados, M eliminados, K candidatos restantes"). **Etapa 2.9**: toma la carpeta escaneada de `resultado["diferencias"]["carpeta"]`, la agrega a `self.carpetas_escaneadas` y llama `self.arbol_navegacion.marcar_carpeta_escaneada(carpeta)` (actualiza el indicador visual del árbol). El gestor queda `inactivo`, los botones se rearman y **marca `_recarga_catalogo_pendiente = True`** para que `_al_tarea_finalizada` inicie la recarga del catálogo (`_iniciar_recarga_catalogo`). No crea tarjetas en este punto.
- `_al_error_sincronizacion(mensaje)` — ante un fallo de la sincronización: limpia la cadena y muestra `MENSAJE_ERROR_SINCRONIZACION` ("No se pudo sincronizar el catálogo"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el último resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_recarga_catalogo_pendiente` / `tarea_recarga_catalogo` — atributos del **paso de recarga del catálogo** del encadenamiento: estado interno que enruta el resultado/error de la recarga y la tarea `TareaLecturaCatalogoPaginada` de la recarga en curso (`None` cuando no hay recarga activa).
- `_crear_tarea_lectura(desplazamiento=0)` — factoría de la tarea de lectura `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, desplazamiento, None, ruta_db)`; la **misma** tarea se usa para la carga inicial (`_iniciar_carga`, desplazamiento 0), para la recarga tras la sincronización (`_iniciar_recarga_catalogo`, desplazamiento 0) y para la **carga manual de una página adicional** (`cargar_mas`, desplazamiento = cantidad de tarjetas ya cargadas).
- `_iniciar_recarga_catalogo()` — se lanza al recibir `tarea_finalizada` de la sincronización (gestor `inactivo` y `_recarga_catalogo_pendiente` activo): crea `_crear_tarea_lectura()` y la inicia con el **mismo** `GestorTareas` de la ventana, guardándola en `tarea_recarga_catalogo`; si el gestor rechaza la tarea, limpia la cadena y muestra `MENSAJE_ERROR_RECARGA`. La recarga **solo se lanza tras una sincronización exitosa** y **no ejecuta FFprobe, FFmpeg ni miniaturas**: solo relee la primera página del catálogo.
- `_al_resultado_recarga(resultado)` — al recibir el resultado de la recarga: limpia `_recarga_catalogo_pendiente`, libera `tarea_recarga_catalogo`, **actualiza `_total_catalogo`** con el `total` del resultado y llama `_reemplazar_tarjetas(resultado.get("videos", []))`. `resultado_sincronizacion` se **conserva intacto** (el resumen mostrado no se pierde con la recarga).
- `_al_error_recarga(mensaje)` — ante un fallo de la recarga: limpia la cadena, muestra `MENSAJE_ERROR_RECARGA` ("No se pudo actualizar el catálogo"), el gestor queda `inactivo`, el botón de escaneo se rehabilita y un nuevo escaneo es posible. **Conserva las tarjetas viejas** y **no revierte** la sincronización ya confirmada en SQLite.
- `_reemplazar_tarjetas(filas)` — al llegar un resultado válido de la recarga: **quita las tarjetas antiguas de la grilla** (`cuadricula.removeWidget` + `tarjeta.deleteLater()` para liberar los widgets Qt), **vacía `self.tarjetas` y `self.visibles`**, crea las tarjetas nuevas con `_crear_tarjetas(filas)` (primera página) en la **misma `QGridLayout` y el mismo `QScrollArea` reutilizados** y reaplica el filtro vigente. No quedan tarjetas ocultas obsoletas.
- `_total_catalogo` — total de registros del catálogo (`COUNT`) conocido hasta ahora; `None` hasta que llega el primer resultado de lectura. Lo actualizan la carga inicial, la recarga tras la sincronización y cada página adicional; habilita/deshabilita el botón "Cargar más".
- `_pagina_pendiente` / `tarea_pagina` — atributos de la **carga manual de una página adicional**: estado interno que enruta el resultado/error de la página y la tarea `TareaLecturaCatalogoPaginada` de la página en curso (`None` cuando no hay carga de página activa).
- `boton_cargar_mas` — botón "Cargar más" (`QPushButton`) en la barra de búsqueda, **deshabilitado al inicio**; habilitado solo cuando la carga inicial terminó (`_carga_completada`), se conoce `_total_catalogo`, quedan tarjetas por cargar (`len(self.tarjetas) < self._total_catalogo`), el gestor está `inactivo` y no hay cadena activa (`_actualizar_botones_carpeta`).
- `cargar_mas()` — acción manual del botón "Cargar más": si el gestor está ocupado o la carga inicial no terminó, retorna; calcula el **`OFFSET` como la cantidad de tarjetas ya cargadas** (`len(self.tarjetas)`), crea `_crear_tarea_lectura(len(self.tarjetas))` y la inicia con el **mismo** `GestorTareas`; marca `_pagina_pendiente = True` y guarda la tarea en `tarea_pagina`. Si `gestor.iniciar()` rechaza la tarea, limpia los flags y rearma los botones. **No reemplaza tarjetas**: el reemplazo sigue siendo exclusivo de la recarga posterior a la sincronización (`_reemplazar_tarjetas`).
- `_al_resultado_pagina(resultado)` — al recibir `{"videos", "total", "limite", "desplazamiento"}`: limpia `_pagina_pendiente`, libera `tarea_pagina`, actualiza `_total_catalogo` y **agrega las tarjetas nuevas debajo de las ya cargadas** con `_agregar_tarjetas`, **descartando las filas cuyo `nombre` ya está cargado** (deduplicación por nombre; `nombre` es `UNIQUE` en SQLite, por lo que en la carga real no se producen filas repetidas; la deduplicación cubre páginas falsas/duplicadas de las pruebas). Reaplica el filtro vigente y rearma los botones.
- `_al_error_pagina(mensaje)` — ante un fallo de la página: limpia la cadena (`_limpiar_cadena`), muestra `MENSAJE_ERROR_PAGINA` ("No se pudo cargar la página"), el gestor queda `INACTIVO`, las tarjetas ya cargadas se **conservan** y el botón "Cargar más" se rearma (un nuevo intento es posible).
- `_agregar_tarjetas(filas)` — agrega una `Tarjeta` por fila **en la misma `QGridLayout`** en las posiciones siguientes a las ya ocupadas (fila `len(self.tarjetas) + indice`, columna 0; una fila por video), **conecta la señal `doble_clic` de cada tarjeta a `_abrir_video`**, las agrega a `self.tarjetas`/`self.visibles` y reaplica el filtro vigente. A diferencia de `_reemplazar_tarjetas`, **no libera ninguna tarjeta existente**.
- `texto_resumen_sincronizacion(resumen)` — formatea el resumen final de la sincronización: `"Sincronización completa: {incorporados} incorporados, {eliminados} eliminados, {candidatos_restantes} candidatos restantes"`; si `resumen` es `None` o faltan claves, usa `0` para cada cantidad.
- `_mostrar_estado_escaneo()` — pluraliza el conteo: `videos_detectados is None` → `MENSAJE_SIN_ESCANEO` ("Sin escanear"); 1 → "1 video detectado"; n → "n videos detectados".
- `_actualizar_botones_carpeta()` — mantiene habilitado el botón "Escanear carpeta" solo con carpeta válida y gestor `inactivo`; habilita el botón "Cargar más" solo con carga inicial terminada, `_total_catalogo` conocido, tarjetas por cargar (`len(self.tarjetas) < self._total_catalogo`), gestor `inactivo` y sin cadena activa; mientras el escaneo (o la carga inicial o una página adicional) está en curso, los botones de la fila quedan deshabilitados.
- Enrutado por estado: `_al_resultado` / `_al_error` reenvían el resultado/error a los handlers de escaneo (`_al_resultado_escaneo` / `_al_error_escaneo`) **cuando `_escaneo_pendiente` está activo**, a los de tamaños (`_al_resultado_tamanos` / `_al_error_tamanos`) **cuando `_tamanos_pendiente` está activo**, a los de FFprobe (`_al_resultado_ffprobe` / `_al_error_ffprobe`) **cuando `_ffprobe_pendiente` está activo**, a los de miniaturas (`_al_resultado_miniaturas` / `_al_error_miniaturas`) **cuando `_miniaturas_pendiente` está activo**, a los de guardado (`_al_resultado_guardado` / `_al_error_guardado`) **cuando `_guardado_pendiente` está activo** y a los de sincronización (`_al_resultado_sincronizacion` / `_al_error_sincronizacion`) **cuando `_sincronizacion_pendiente` está activo** y a los de recarga (`_al_resultado_recarga` / `_al_error_recarga`) **cuando `_recarga_catalogo_pendiente` está activo** y a los de una página adicional (`_al_resultado_pagina` / `_al_error_pagina`) **cuando `_pagina_pendiente` está activo**; la cadena se produce porque el escaneo, los tamaños, FFprobe, las miniaturas, el guardado, la sincronización, la recarga y la carga de una página adicional son tareas sucesivas con el mismo gestor (el paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior, no en el handler del resultado); **antes de abortar** por `_carga_completada`, los handlers reenvían primero a la página si `_pagina_pendiente` está activo (la carga inicial termina una sola vez; una página adicional puede llegar después). Es suficiente para una única tarea activa a la vez y debe revisarse si la interfaz incorpora más tipos de tarea. **Los previews progresivos no se enrutan por este mecanismo**: usan un **segundo `GestorTareas`** (`gestor_previews`) con señales y handlers propios (`_al_resultado_previews` / `_al_error_previews` / `_al_previews_finalizada`), de modo que el enrutado del gestor principal queda sin cambios. **Ausencia deliberada**: el pipeline escribe registros con metadatos FFprobe (duración, resolución, codec; `NULL` si FFprobe no puede obtenerlos), `cantidad_miniaturas` (por ruta; `None` si no hay coincidencia) y `tamano_bytes` (por ruta; `None` si el archivo no existe o no es legible) mediante el upsert transaccional existente, conservando los registros preexistentes; tras el guardado exitoso se lanza la sincronización completa (`TareaSincronizacionCatalogo`) que elimina de SQLite únicamente los registros ausentes del disco, conserva intactos los metadatos y la cantidad de miniaturas de los presentes y **no elimina archivos físicos ni miniaturas**; **tras una sincronización exitosa se recarga el catálogo en segundo plano** (`TareaLecturaCatalogoPaginada` con el mismo gestor) y se **reemplazan las tarjetas** (se liberan las viejas y se crean las nuevas con la primera página en la misma grilla), conservando `resultado_sincronizacion`; no recorre subcarpetas y no ejecuta FFmpeg directamente desde la interfaz (la generación ocurre dentro de `TareaMiniaturas`).
- `TAMANIOS_MINIATURAS` / `TAMANIO_MINIATURAS_ACTUAL` / `configurar_tamano_miniaturas(nombre)` / `dimensiones_miniatura()` / `texto_tamano_miniaturas(nombre)` / `clave_tamano_miniaturas(texto)` — **tamaño configurable de las imágenes de la tarjeta** (Etapa B3.3). Cuatro presets de caja de escalado: `pequeno` (260×146), `mediano` (320×180, **valor actual y predeterminado**), `grande` (400×225) y `muy_grande` (**512×288**, incorporado en la **Etapa B3.6** como ampliación de A3; se integró solo ampliando los datos, sin lógica nueva). `dimensiones_miniatura()` devuelve la caja vigente; las claves inválidas se ignoran. El escalado es **solo en memoria** reutilizando los pixmaps ya cargados (sin FFmpeg, sin relectura de disco, sin regeneración ni reescaneo). La preferencia se persiste en `configuracion.json` (clave `tamano_miniaturas`, default `"mediano"`) y se restaura al iniciar; la restauración usa `blockSignals` para no escribir la configuración en el arranque.
- `VistaAmpliada(QFrame)` / `RETARDO_VISTA_AMPLIADA_MS` / `RETARDO_OCULTAR_VISTA_MS` / `FACTOR_VISTA_AMPLIADA` / `FACTOR_VISTA_AMPLIADA_ACTUAL` / `configurar_factor_vista_ampliada(factor)` — **vista ampliada al posar el mouse** (Etapa B3.4). Un **único popup por `VisorVideos`** (ventana de nivel superior con flags `Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`, un `QLabel` interno), reutilizado continuamente (nunca se crea ni destruye por hover). `preparar(pixmap)` escala el pixmap original ya cargado en memoria a **`FACTOR_VISTA_AMPLIADA_ACTUAL` × `dimensiones_miniatura()`** (proporcional al tamaño de la miniatura) y, si ya está visible mostrando el mismo pixmap, solo reutiliza (evita parpadeos). El factor es configurable desde la **Etapa B3.7** (valores `1.2/1.6/2.0/2.5`, default `1.6` = comportamiento previo; la **Etapa B3.14b** agrega `3.0/3.5`, quedando el máximo en `3.5` — la vista ampliada puede ocupar prácticamente toda la pantalla, siempre acotada por `_posicion_vista`; sin tratamiento especial para los nuevos factores). `ocultar()` limpia y oculta. **Etapa B3.9**: `_al_vista_solicitada` oculta de inmediato el popup si ya está visible y la nueva miniatura es distinta (transición limpia; la misma imagen no oculta). `Tarjeta` instala `installEventFilter(self)` sobre `_imagen_miniatura` y cada preview; en `QEvent.Enter` emite `vista_solicitada(pixmap_original)` y en `QEvent.Leave` emite `vista_abandonada()`. La ventana maneja: retardo `QTimer` single-shot (configurable desde B3.5, default 400 ms, verifica el objetivo; **Etapa B3.14a**: se agrega el valor discreto "Desactivado" (`-1`) que impide que se active el mecanismo — `_al_vista_solicitada` retorna de inmediato, no se inicia el timer ni aparece el popup; `_aplicar_retardo_vista_ampliada(-1)` además detiene el timer y oculta un popup visible; `self._retardo_vista_ampliada` conserva el valor vigente y, al restaurar, solo se fija el intervalo si no es `-1`; volver a cualquier retardo reactiva la funcionalidad), ocultado programado (150 ms al salir), ocultado por scroll (`valueChanged` del scrollbar), por reconstrucción (`_reemplazar_tarjetas`) y en `closeEvent`. Posicionamiento con `_posicion_vista()`: offset respecto del cursor (evita ciclos enter/leave) y acotado a la geometría disponible de la pantalla. Comportamiento idéntico para miniatura principal y previews. Sin lecturas de disco, sin procesos externos, sin SQLite ni pipeline.
- `PreferenciasDialog(QDialog)` / `RETARDOS_VISTA_AMPLIADA` / `TEXTOS_RETARDO_VISTA_AMPLIADA` / `FACTORES_VISTA_AMPLIADA` / `TEXTOS_FACTOR_VISTA_AMPLIADA` — **preferencias de miniaturas** (Etapa B3.5, ampliada en B3.7). Diálogo modal abierto por el botón "Preferencias…" (`_abrir_preferencias`), con dos preferencias: **retardo** de la vista ampliada (valores discretos `Desactivado (-1)`, incorporado en la **Etapa B3.14a**; `Inmediato (0)`, `250 ms`, `400 ms` predeterminado, `600 ms`) y **tamaño** de la vista ampliada (factores `1.2x/1.6x/2.0x/2.5x/3.0x/3.5x`, default `1.6`, incorporado en la **Etapa B3.7** y ampliado en la **B3.14b**). `retardo_seleccionado()` y `factor_vista_seleccionado()` devuelven los valores de los combos; al **Aceptar** se llaman `_aplicar_retardo_vista_ampliada(ms)` y `_aplicar_tamano_vista_ampliada(factor)`, que persisten con la infraestructura de `configuracion.py` y aplican de inmediato (`_timer_vista_mostrar.setInterval(ms)` y `configurar_factor_vista_ampliada(factor)`), sin reiniciar, sin reconstruir el catálogo y sin alterar selección/scroll. Con `-1` (`Desactivado`) `_aplicar_retardo_vista_ampliada` detiene el timer y oculta un popup visible. Los controles **Previews** y **Tamaño** permanecen con acceso directo en la barra principal (decisión de la auditoría: priorizar la velocidad de uso). Las claves `retardo_vista_ampliada_ms` y `tamano_vista_ampliada` son aditivas: configuraciones antiguas sin la clave o con valor inválido usan los defaults (`400 ms` y `1.6`) sin migración.
- `PreviewConTiempo(QLabel)` — etiqueta de preview con **tiempo superpuesto** (Etapa B3.1) y **tamaño redimensionable** (Etapa B3.3): mismo widget por slot y mismo layout que el placeholder original (sin alterar tamaños de tarjeta, de miniaturas ni el scroll). `poner_preview(pixmap, tiempo)` almacena el pixmap original (`_pixmap_original`), escala a `dimensiones_miniatura()` con `KeepAspectRatio` y guarda el texto del instante; `paintEvent` conserva el fondo y el borde del placeholder, dibuja el fotograma centrado y, **solo si hay tiempo**, superpone en la esquina inferior derecha un rectángulo redondeado semitransparente oscuro (`rgba(0,0,0,150)`) con texto claro (`rgba(255,255,255,235)`). `reajustar()` reescala el original en memoria al tamaño vigente (también actualiza la altura de los placeholders sin imagen). Si `tiempo` es `None` (duración desconocida o inválida) dibuja únicamente el fotograma, **sin valores por defecto**.
- `formatear_tiempo(segundos)` — formatea un instante en segundos como `"m:ss"` o `"h:mm:ss"` (redondeado al segundo). Devuelve `None` si el valor no es numérico (incluido `bool`) o es negativo. Usos: **B3.1** en `_colocar_preview` (si devuelve `None` la interfaz **no dibuja overlay**); **B3.2** en el campo "Duración" de la tarjeta, donde `None` se respalda con el texto "No disponible".
- `_duracion_valida(duracion)` — helper reutilizable (Etapa B3.9) que centraliza el criterio de "duración válida" (numérico no `bool` y `> 0`; la duración **0 es inválida**); se usa en el texto de duración de la tarjeta y en el overlay, eliminando la duplicación sin cambiar comportamiento. En la refinación de la Etapa 5 se cambió accidentalmente a `>= 0` (duración 0 tratada como válida → tarjetas "0:00" y overlays en duración 0); la **auditoría de la Etapa 7** lo detectó y se restauró el criterio `> 0` (regresión corregida).
- `LIMITE_ORIGINAL_MINIATURA` / `_pixmap_acotado(pixmap)` — **acotado de los pixmaps originales retenidos en memoria** (Etapa B3.9). Al cargar una preview o la miniatura principal se almacena el original con el lado mayor acotado a `LIMITE_ORIGINAL_MINIATURA = 1280` (cubre la mayor salida: Muy grande 512 × factor 2.5 = 1280). Imágenes ≤ 1280 se conservan tal cual (mismo objeto). Se mantiene el reescalado en memoria sin releer disco ni regenerar, y la calidad de todos los tamaños y de la vista ampliada queda preservada.
- `Tarjeta(QFrame)` — tarjeta horizontal por video (layout `QHBoxLayout`): **columna de datos a la izquierda** (`maxWidth=240`, seis campos con word wrap: nombre, duración, resolución, codec, miniaturas y tamaño) + **contenedor horizontal de imágenes** (`QHBoxLayout` con spacing 6, stretch=1) que agrupa consecutivamente cuatro imágenes del mismo nivel —miniatura principal y tres previews— con `setFixedHeight(ALTO_TARJETA)` y ancho ajustado automáticamente al pixmap real escalado (manteniendo relación de aspecto), más un `addStretch()` final que concentra el espacio sobrante a la derecha. La fila se desempaqueta como tupla `nombre, duracion, ancho, alto, codec, miniaturas, tamano, *_resto = fila` (**siete campos básicos**; `*_resto` captura las columnas opcionales del catálogo si están presentes —`_resto[0]` = columna `ruta` (última en la corrección de cierre de la Beta 3) y `_resto[1]` = columna `id` (`videos.id`, incorporada como última en la **B4.2**), con las filas de `listar_videos`/`listar_videos_paginado` de **nueve columnas**, y compatibilidad con filas de 7 columnas en pruebas); la carpeta real del video (`self._carpeta_video`) se deriva de esa `ruta` restándole el nombre relativo (base de escaneo) y es la fuente de la carpeta para la generación de previews (corrección de cierre de la Beta 3); **`self._video_id`** se toma de `_resto[1]` (B4.2) y es la identidad del video para cargar/crear/eliminar marcadores persistentes (una tarjeta sin `id` no persiste marcadores); el tamaño se presenta con `formatear_tamano(tamano)` y la duración con `formatear_tiempo(duracion)` (**B3.2 — duración simplificada**: `m:ss` si es menor a una hora, `h:mm:ss` si es una hora o más, y `"No disponible"` si la duración no existe o no es válida; cambio solo de presentación, el valor `duracion_segundos` permanece numérico). Cada preview se actualiza de forma **incremental** con `actualizar_previews(rutas)` / `_colocar_preview(indice, ruta)`, reemplazando el placeholder "Generando preview…" por el pixmap escalado cuando el archivo ya existe y es cargable. **B4.6 Etapa 2 — carga diferida**: la tarjeta conserva `_previews_completas` (estado interno no persistido) que marca si los primeros `CANTIDAD_PREVIEWS` slots tienen pixmap; `actualizar_previews` lo actualiza y, si la tarjeta está expandida, llama `_renderizar_marcadores()` (los marcadores obtienen su miniatura cuando llegan previews). por el pixmap escalado cuando el archivo ya existe y es cargable. **Etapa B3.1 (tiempo sobre las previews)**: cada slot de preview es un `PreviewConTiempo`; la tarjeta conserva `self._duracion = duracion` (duración del catálogo) y `_colocar_preview` deriva el instante con `calcular_tiempo_preview(duracion, indice + 1)` y `formatear_tiempo` — **sin FFprobe adicional, sin pipeline, sin cambios de esquema ni persistencia de tiempos**. Si la duración es `None` o inválida, no se dibuja overlay. **Etapa B3.3 (tamaño configurable)**: el escalado de la miniatura principal y de las previews usa `dimensiones_miniatura()` (presets Pequeño/Mediano/Grande); la tarjeta conserva el pixmap original (`_miniatura_original`, `_imagen_miniatura`) y el recuadro "Sin miniatura" (`_recuadro_sin_miniatura`), y `aplicar_tamano()` reescala **en memoria** las imágenes y actualiza alturas cuando cambia el tamaño (cambio inmediato, sin reescaneo, sin regeneración, sin reconstrucción; se conservan selección, scroll y overlays). Las previews existentes en disco se cargan inmediatamente al construir cada tarjeta (`_crear_tarjetas` y `_agregar_tarjetas`), antes de cualquier generación asíncrona, para conservarlas tras el reescaneo de una carpeta ya procesada. **Apertura por doble clic**: la clase declara la señal de clase `doble_clic = Signal(str)` y sobrescribe `mouseDoubleClickEvent(event)` (llama a `super().mouseDoubleClickEvent(event)` y emite `self.doble_clic.emit(self._nombre)`), de modo que **cualquier doble clic con el botón izquierdo sobre la tarjeta emite el nombre del video**; la interfaz conecta esa señal a `_abrir_video` tanto en la carga inicial (`_crear_tarjetas`) como en las páginas adicionales (`_agregar_tarjetas`).
- `formatear_tamano(valor)` — presentación legible del tamaño en bytes: enteros ≥ 0 → `B` (menos de 1024), `KB` (un decimal), `MB` (un decimal) o `GB` (un decimal) según el umbral; un valor no-entero (`None`, texto, float, `bool`) o negativo → `"Desconocido"`.
- `_iniciar_carga()` — crea la tarea de lectura con `_crear_tarea_lectura(desplazamiento=0)` (`TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)`) y la inicia con `gestor.iniciar(tarea)`.
- `gestor_previews` — **segundo `GestorTareas`** propio, independiente del gestor principal, dedicado a la generación **progresiva** de previews. Sus señales se conectan a `_al_resultado_previews` / `_al_error_previews` / `_al_previews_finalizada`; se cierra en `closeEvent` junto con el gestor principal.
- `_cola_previews` — cola de **pares `(nombre, carpeta)`** de video pendientes de generar previews; la carpeta es la **carpeta real del propio video** (de su registro del catálogo), no la carpeta de navegación. Evita re-encolar los que ya tienen previews o ya están en cola.
- `_timer_previews` — `QTimer` single-shot de 300 ms que arranca la cola de previews al terminar cada carga/recarga/página (`_programar_previews`), para no competir con la carga del catálogo.
- `previews_de(nombre)` — función del módulo: devuelve `previews_existentes(nombre)` (rutas de los previews ya generados, en orden 1..3).
- `_programar_previews()` / `_iniciar_previews()` — tras cada carga inicial, recarga o página adicional: si la carga terminó, arranca el temporizador; al dispararse, encola los nombres de las tarjetas (`_encolar_previews`) y lanza el primer lote (`_al_previews_finalizada`). **No dependen de `carpeta_seleccionada`** (corrección de cierre de la Beta 3): cada video aporta su propia carpeta.
- `_encolar_previews(nombres)` — agrega a `_cola_previews` los nombres de las tarjetas **no completas** (flag `Tarjeta._previews_completas`, B4.6 Etapa 2) que no estén pendientes, encolando cada uno con la carpeta de su tarjeta (`tarjeta._carpeta_video`, derivada de la columna `ruta` del catálogo); descarta los videos sin carpeta resoluble. De este modo **también las previews cacheadas** entran a la cola y se aplican progresivamente (0 FFmpeg). **Etapa B3.8**: al aumentar la cantidad configurada, `_al_cambiar_cantidad_previews` llama `_programar_previews()` al final, de modo que la cola existente encola automáticamente solo los videos incompletos y genera **únicamente los índices faltantes** (`generar_previews_faltantes`), sin escanear ni releer el catálogo; al disminuir no se genera nada (solo se ocultan previews).
- `_siguiente_lote_previews()` — si el gestor de previews está libre, agrupa la cola por carpeta y toma hasta `TAMANIO_LOTE_PREVIEWS = 3` nombres de una **única carpeta**, construye el mapa de duraciones de las tarjetas del lote (`Tarjeta._duracion`, **B4.5**), crea `TareaPreviewsProgresivas(lote, carpeta, duraciones=duraciones)` y la inicia con `gestor_previews`, re-encolando el resto; al terminar cada lote (`_al_previews_finalizada`) se procesa el siguiente, encadenando lotes hasta vaciar la cola. Así cada lote genera siempre contra la carpeta correcta de sus videos y con la duración ya conocida (evita FFprobe interno).
- `Tarjeta._carpeta_video` — carpeta real del video derivada de su registro del catálogo (la columna `ruta`, que `listar_videos`/`listar_videos_paginado` ahora incluyen como última columna, menos el nombre relativo del video). Es la fuente de la carpeta para la generación de previews, de modo que la navegación (`carpeta_seleccionada`) ya no interviene.
- `Tarjeta._asegurar_slots_previews(cantidad)` / `ajustar_previews(cantidad)` — **crecimiento dinámico de slots** (Etapa B3.8): si la tarjeta fue creada con menos etiquetas que la cantidad solicitada, se crean `PreviewConTiempo` adicionales (con `dimensiones_miniatura()`, `eventFilter` y colocados antes del `addStretch()`), sin reconstruir la tarjeta; conservan selección, overlays, tamaño configurado y vista ampliada. `ajustar_previews` crece los slots, luego muestra/oculta y actualiza las previews existentes; disminuir la cantidad solo oculta (sin trabajo en segundo plano).
- `_aplicar_previews(resultado)` / `_al_resultado_previews(resultado)` — al llegar el resultado de un lote, recorre `resultados` y llama `actualizar_previews(nombre, previews)` sobre la tarjeta correspondiente, **mostrando cada preview a medida que se genera**. **B4.6 Etapa 2 — protección de resultados tardíos**: antes de aplicar valida que la carpeta del video del resultado (`item["ruta"]`) corresponda a la `_carpeta_video` de la tarjeta actual; un resultado tardío de otra carpeta (cambio A→B) se ignora sin imágenes cruzadas.
- `TAMANIO_LOTE_PREVIEWS` — constante de la interfaz: tamaño de lote (3 videos) de la generación de previews.
- `_al_resultado(resultado)` — al recibir el resultado: oculta el estado de carga, **actualiza `_total_catalogo`** con el `total`, crea las tarjetas (`_crear_tarjetas`) y marca `_carga_completada`.
- `_al_error(mensaje)` — al fallar la lectura: muestra `MENSAJE_ERROR` sin cerrar la ventana.
- `_crear_tarjetas(filas)` — construye una `Tarjeta` por fila en la `QGridLayout` (una sola columna, una fila por video), **conecta la señal `doble_clic` de cada tarjeta a `_abrir_video`** y reaplica el filtro vigente. **B4.6 Etapa 2 — carga diferida de previews**: ya **no** carga las previews cacheadas al construir (las tarjetas parten con textos + miniatura principal + placeholders); las previews se incorporan después progresivamente por la tubería existente.
- `_abrir_video(nombre)` — **apertura por doble clic**: toma `nombre` de la señal y `self.carpeta_seleccionada` como carpeta, e invoca `abrir_video_con_aplicacion_predeterminada(nombre, self.carpeta_seleccionada)` (de `apertura_videos.py`, que resuelve y valida la ruta y ejecuta `os.startfile`). Si el servicio **falla** (`ValueError`, `FileNotFoundError` u `OSError`) muestra `MENSAJE_ERROR_ABRIR` en la etiqueta de estado; en éxito deja la etiqueta en blanco. Nunca propaga excepciones al gestor de eventos.
- `filtrar(texto)` — filtrado por coincidencia de nombre **sobre todas las tarjetas actualmente cargadas en la interfaz**, sean de la primera página o de páginas agregadas manualmente con el botón "Cargar más"; mantiene `visibles` y actualiza el contador.
- `actualizar_contador()` — muestra "N videos" / "1 video" según las tarjetas visibles.
- `_actualizar_resumen_seleccion()` / `resumen_seleccion` — **resumen permanente de selección** (Etapa B3.11): una etiqueta en la barra de búsqueda muestra "X de Y seleccionados", donde **Y = tarjetas visibles** (`self.visibles`) y **X = visibles seleccionadas** (intersección con `_nombres_seleccionados`). Método único y centralizado; se invoca desde dos puntos de enganche que cubren todos los cambios: `_marcar_tarjeta` (selección simple/Ctrl/Shift, deselección, restauración) y `filtrar` (búsqueda, carga inicial, "Cargar más", reconstrucción del catálogo), más el cierre de `_limpiar_seleccion`. Refleja únicamente las tarjetas visibles (nunca el catálogo completo); no altera layout, no produce parpadeos ni modifica el comportamiento de selección.
- **Modo Selección + Checks por fila** (Etapa B3.12) — `boton_modo_seleccion` (toggle checkable en la barra) y `_modo_seleccion`; cada `Tarjeta` incorpora un `QCheckBox` (`_check`) en el índice 0 del layout raíz, **oculto por defecto**, visible solo cuando el modo está activo (`mostrar_check`). La sincronización es **bidireccional y centralizada en `_marcar_tarjeta`**: toda mutación de selección actualiza el check (`set_check`, con `blockSignals` para evitar reentradas) y el check emite `seleccion_check(nombre, marcado)` → `_al_check_tarjeta` (muta `_nombres_seleccionados` y llama `_marcar_tarjeta`). `_nombres_seleccionados` permanece como **única fuente de verdad**; activar/desactivar el modo solo alterna la visibilidad de los checks, conservando la selección y el resumen (B3.11) intactos. En   `_crear_tarjetas`/`_agregar_tarjetas` se conecta la señal y se aplica el modo. Nota de implementación: `_al_check_cambiar` usa `self._check.isChecked()` (no `estado == Qt.Checked`) por la semántica enum/int de PySide6.
- **Atajos básicos de selección** (Etapa B3.13) — dos `QShortcut` sobre la ventana principal: **Ctrl+A** (`_atajo_ctrl_a`) y **Esc** (`_atajo_esc`). `_atajo_seleccionar_todo`: si el foco está en el `QLineEdit` de búsqueda, replica su comportamiento nativo (`selectAll()`) sin tocar las tarjetas; en caso contrario, `_seleccionar_todo_visible()` itera **`self.visibles`** (respeta el filtro activo), agrega a `_nombres_seleccionados` y llama `_marcar_tarjeta(nombre, True)`, cerrando con `_actualizar_resumen_seleccion()` (idempotente). `_atajo_salir_modo_seleccion`: si el modo está activo, `boton_modo_seleccion.setChecked(False)` (oculta solo los checks y conserva la selección y el resumen); si está inactivo, no hace nada. Se preserva el comportamiento del buscador y `_nombres_seleccionados` sigue siendo la única fuente de verdad.
- **Atajos de operaciones** (Etapa B3.17) — tres `QShortcut` con el mismo patrón de B3.13: **Ctrl+C** (`_atajo_copiar`), **Ctrl+V** (`_atajo_pegar`) y **Supr** (`_atajo_eliminar`, `QKeySequence("Del")`). Cada handler (`_atajo_operacion_copiar`/`_atajo_operacion_pegar`/`_atajo_operacion_eliminar`) **reutiliza directamente** los handlers de los botones (`_iniciar_copia()`, `_iniciar_pegar()`, `_iniciar_eliminar()`), sin lógica paralela ni validaciones duplicadas (sin selección, sin portapapeles, gestor ocupado y carpeta inválida ya están cubiertos por esos métodos). Criterio de foco idéntico a Ctrl+A: si la búsqueda tiene foco se **preserva el comportamiento nativo del `QLineEdit`** replicándolo (`copy()`, `paste()` y `del_()`, este último el nombre de PySide6 para el slot `del`) y no se inicia ninguna operación.
- **Operación Copiar** (Etapa B3.14) — `TareaCopiarArchivos(TareaBase)` ejecuta en segundo plano la lógica pura `operaciones.copiar_archivos(origen, archivos, destino, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22), usando un tercer gestor dedicado **`gestor_operaciones`** (independiente del pipeline y de las previews; se cierra en `closeEvent`). El botón **"Copiar…"** en la barra (`_actualizar_boton_copiar` lo habilita con selección + carpeta válida + gestores inactivos, incluida la **exclusión mutua** con el pipeline) abre `QFileDialog.getExistingDirectory`; si el usuario cancela no hace nada. La tarea emite por `tarea_resultado` el resumen `{"copiados", "omitidos", "errores"}`; el slot `_al_resultado_copia` oculta la barra de progreso y muestra en `estado_escaneo` "Copiado: X — Omitidos: Y — Errores: Z" (sin atributos de estado permanentes). `copiar_archivos` copia con `shutil.copy2`, crea subdirectorios para nombres anidados, **omite** destinos ya existentes (nunca sobrescribe), registra errores por archivo y continúa. El catálogo no se resincroniza (la copia exporta a otra carpeta sin alterar la escaneada).
- **Operación Pegar** (Etapa B3.15) — usa un **portapapeles interno** (`self._portapapeles`, lista de rutas absolutas de los archivos copiados con éxito, alimentada en `_al_resultado_copia` desde `resumen["copiados"]`) y un botón **"Pegar…"** en la barra (`_actualizar_boton_pegar` lo habilita con portapapeles no vacío + carpeta válida + `gestor_operaciones` inactivo). `_iniciar_pegar` detecta colisiones (destino ya existente por `basename`) y, si las hay, muestra **un único diálogo modal** con botones "Omitir"/"Cancelar" (nunca sobrescribe); si el usuario cancela no inicia ninguna tarea. `TareaPegarArchivos(TareaBase)` ejecuta en segundo plano `operaciones.pegar_archivos(archivos, destino, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22) reutilizando el **mismo `gestor_operaciones`** de Copiar; un despachador (`_operacion_archivos` + `_al_resultado_operaciones`/`_al_error_operaciones`) enruta el resultado a `_al_resultado_pegar`/`_al_error_pegar`. `_al_resultado_pegar` oculta la barra de progreso, muestra el resumen "Pegado: X — Omitidos: Y — Errores: Z" en `estado_escaneo` y, si hubo copias, dispara la **resincronización incremental** `_procesar_archivos_pegados(nombres)`: reutiliza la cadena existente (tamaños → FFprobe → miniaturas → guardado → sincronización → recarga) fijando `videos_detectados` a los archivos pegados y usando un `TareaEscaneo(carpeta)` como portador de `.carpeta` (no iniciado); solo los archivos pegados pasan por FFprobe/miniaturas, sin reescaneo completo. **Corrección de carrera (Etapa B3.18):** la carpeta se **captura al inicio** de `_procesar_archivos_pegados` y se fija en el override temporal `_carpeta_sincronizacion`, que `_iniciar_sincronizacion` consume en el paso de sincronización; así la sincronización usa **exactamente la carpeta capturada** aunque el usuario cambie de carpeta durante la cadena, evitando que se eliminen del catálogo los registros recién pegados. `_carpeta_sincronizacion` se limpia automáticamente (en `_iniciar_sincronizacion`, `_limpiar_cadena` e `iniciar_escaneo`).
- **Operación Eliminar** (Etapa B3.16) — botón **"Eliminar…"** en la barra (`_actualizar_boton_eliminar` lo habilita con selección + carpeta válida + `gestor_operaciones` inactivo). `_iniciar_eliminar` muestra **un único diálogo modal** de confirmación que indica la cantidad de archivos seleccionados, que serán enviados a la Papelera de reciclaje y que podrán restaurarse desde allí; botones "Eliminar"/"Cancelar" (default Cancelar; si cancela no inicia ninguna tarea). `TareaEliminarArchivos(TareaBase)` ejecuta en segundo plano `operaciones.eliminar_archivos(archivos, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22) reutilizando el **mismo `gestor_operaciones`** de Copiar/Pegar; el despachador (`_operacion_archivos` + `_al_resultado_operaciones`/`_al_error_operaciones`) enruta a `_al_resultado_eliminar`/`_al_error_eliminar`. `_al_resultado_eliminar` muestra el resumen "Eliminado: X — Omitidos: Y — Errores: Z" y, si hubo eliminaciones, dispara (diferido con `QTimer.singleShot(0)`, para que el resumen sea visible) la **actualización incremental del catálogo** `_procesar_archivos_eliminados`: reutiliza el **paso de sincronización existente** (`TareaSincronizacionCatalogo`, que detecta los archivos ausentes y los elimina) seguido de la recarga, **sin reescaneo completo** (no pasa por FFprobe ni miniaturas). **Corrección de carrera (Etapa B3.18):** igual que en Pegar, `_procesar_archivos_eliminados` **captura la carpeta al inicio** y la fija en `_carpeta_sincronizacion`, de modo que la sincronización opera sobre la carpeta de la operación y no sobre `carpeta_seleccionada` si ésta cambió.
- `seleccion_carpetas.py` — **conjunto de carpetas seleccionadas por ruta** (Bloque de trabajo 4, "Selección personalizada", primera etapa). Clase pura `SeleccionCarpetas(ruta_config=None)`: mantiene el conjunto como **única fuente de verdad** (`set` de rutas absolutas), sin dependencia del árbol ni de Qt. API: `seleccionar(ruta)` (agrega solo carpetas existentes; ignora inexistentes/valores inválidos), `deseleccionar(ruta)`, `alternar(ruta)` (devuelve el estado resultante), `limpiar()`, `seleccionar_todas(lista)` (agrega las existentes sin duplicar; devuelve la cantidad), `obtener_seleccion()` (devuelve una **copia**). Persiste en configuración (clave `carpetas_seleccionadas`, patrón atómico `.tmp`+`os.replace`) tras cada cambio real y **restaura en el constructor descartando rutas inexistentes**. `visor_videos.py` lo instancia al iniciar (`self.seleccion_carpetas`). Sin intervalos internos, sin UI, sin cambios en escaneo/SQLite/pipeline. `configuracion.py` expone `guardar_seleccion_carpetas(rutas, ruta_config=None)` (normaliza y deduplica, conserva las demás claves) y `obtener_seleccion_carpetas(ruta_config=None)` (descarta rutas inexistentes; configs anteriores/inválidas → lista vacía).
- `configuracion.py` — **modo de alcance del escaneo** (Etapa 6): constantes `MODO_ALCANCE_SOLO`/`MODO_ALCANCE_SUBCARPETAS`/`MODO_ALCANCE_SELECCION` (`MODOS_ALCANCE_VALIDOS`), `CLAVE_MODO_ALCANCE`, `guardar_modo_alcance(modo, ruta_config=None)` (persiste el modo y mantiene sincronizada la clave booleana `incluir_subcarpetas` para compatibilidad) y `obtener_modo_alcance(ruta_config=None)` con **migración retrocompatible**: si no hay modo válido, migra desde el booleano `incluir_subcarpetas` (True → "con_subcarpetas", False → "solo_carpeta"); default "solo_carpeta". `visor_videos.py` lo restaura al iniciar (`self._modo_alcance`) y lo expone en `combo_modo_alcance` (única fuente de verdad visible); el checkbox "Incluir subcarpetas" queda como adaptador de compatibilidad oculto.
- `operaciones.py` — módulo de **lógica pura de operaciones sobre archivos** (incorporado a la arquitectura en B3.14; conserva `sumar`): `copiar_archivos(origen, archivos, destino, on_progreso=None)` valida los argumentos (`origen`/`destino` texto no vacío; `archivos` colección no texto), copia con `shutil.copy2` preservando metadatos, crea directorios padre, omite archivos existentes, captura `OSError` por archivo y devuelve el resumen `{"copiados": [rutas], "omitidos": [rutas], "errores": [(ruta, mensaje)]}`. `pegar_archivos(archivos, destino, on_progreso=None)` (B3.15) copia cada ruta de origen con `shutil.copy2` a `os.path.join(destino, os.path.basename(ruta))`, **omite** destinos ya existentes (nunca sobrescribe), registra errores por archivo (`OSError` o origen inexistente) y continúa, devolviendo el mismo resumen. `eliminar_archivos(archivos, on_progreso=None)` (B3.16) envía cada ruta a la **Papelera de reciclaje de Windows mediante la API nativa `SHFileOperationW` a través de `ctypes`** (`_SHFILEOPSTRUCTW` con `FO_DELETE` + `FOF_ALLOWUNDO`, `FOF_NOCONFIRMATION`, `FOF_NOERRORUI` y `FOF_SILENT`; `pFrom` con lista de doble NUL), una invocación por archivo para aislar errores y continuar; **nunca borra permanentemente**; origen inexistente o archivo bloqueado se registran como errores; devuelve `{"eliminados": [rutas], "omitidos": [], "errores": [(ruta, mensaje)]}`. **Callback de progreso opcional** (Etapa B3.22): las tres funciones emiten `on_progreso(indice + 1, total)` **una vez por archivo** (incluyendo omitidos y errores); sin callback, el comportamiento es idéntico. **Sin dependencias externas** y sin Qt, SQLite ni pipeline.
- `closeEvent(event)` — apagado ordenado: detiene `_timer_previews`, llama `gestor.cerrar()`, `gestor_previews.cerrar()` y `gestor_marcadores.cerrar()` (timeout por defecto 5000 ms) y acepta el evento.
- **Clasificación visual por color (B6.3) en la interfaz.** La `Tarjeta` incorpora un selector
  `_selector_color` (QComboBox "Sin clasificar" + los 6 colores de la paleta, textos con
  `texto_color`); el color activo se adjunta a los marcadores y segmentos nuevos que se crean
  en esa tarjeta. Los **menús contextuales** de marcador y de segmento incluyen el submenú
  **"Asignar color"** (6 colores + "Sin clasificar", deshabilitado si el ítem ya no tiene
  color); en el marcador el clic derecho ya **no elimina** directamente (ofrece "Eliminar
  marcador" dentro del menú). Las operaciones se enrutan como tipo `"color"` en la cola de
  los gestores dedicados y, ante error, se **revierte el color previo**; la marca/banda local
  se recolorea de inmediato (`set_marcadores`/`set_segmentos`). **Corrección del defecto
  PySide/QMenu**: los submenús se crean con el menú como padre `QObject`
  (`QMenu("Asignar color", menu)`) y se conservan las referencias
  (`_submenu_marcador_color_actual` / `_submenu_segmento_color_actual`), evitando que PySide
  libere el submenú antes de mostrarlo. `PreferenciasDialog` gana la sección **"Nombres de
  colores de la clasificación"** (muestra del color + `QLineEdit` por clave, límite de 40, y
  al aceptar persiste con `guardar_nombre_color`); `_refrescar_textos_colores` actualiza los
  textos del selector y los menús se construyen por demanda con `texto_color`.
- `miniatura_principal(nombre)` — ubica la primera miniatura cuyo prefijo coincide con el video, **excluyendo los archivos `_preview_`** (`_es_archivo_preview`), de modo que la miniatura principal nunca es un preview.
- `main()` — **punto de entrada de producción**: solo inicia la interfaz gráfica —`QApplication(sys.argv)`, `VisorVideos()`, `resize(900, 600)`, `show()` y `sys.exit(app.exec())`—. **No ejecuta pruebas automáticamente**: el arranque normal ya no lanza el smoke test, que se independizó en el arnés `prueba_smoke.py` (ver la sección siguiente).

### `prueba_smoke.py` — arnés de smoke tests (ejecución explícita)
Arnés independiente del arranque normal: contiene el **smoke test del pipeline completo** que vivía dentro de `visor_videos.main()`, movido sin cambios de comportamiento (el único ajuste es el parcheo de la fase de doble clic, que ahora apunta a `visor_videos.abrir_video_con_aplicacion_predeterminada`). Se ejecuta **explícitamente** con `python prueba_smoke.py`; la aplicación normal no lo ejecuta al iniciar. Crea una **base SQLite temporal** reutilizando el esquema existente (`conectar_bd(ruta_db)` + `commit()` + `close()`, sin depender de `biblioteca.db`) y verifica el pipeline completo por fases:
- **Fase de paginación** — inserta 150 registros (`guardar_videos`) y verifica la carga inicial (`primera_pagina=100`, `contador_primera_pagina=100 videos`, `cargar_mas_habilitado=True`), dispara "Cargar más" (`boton_cargar_mas.click()`), espera el fin de la página y comprueba `total_tras_cargar_mas=150`, **cero duplicados** (`duplicados_tras_cargar_mas=0`), `primeras_conservadas=True` y `contador_tras_cargar_mas=150 videos`.
- **Fase de escaneo + carpeta + sincronización** — verifica el estado inicial sin carpeta ("Sin escanear" y botón de escanear deshabilitado), simula la selección y la cancelación de una carpeta temporal (diálogo inyectado y siempre restaurado) con archivos de video y no-video, espera la carga asíncrona, dispara el escaneo real con `boton_escanear.click()`, espera la cadena completa escaneo → tamaños → FFprobe → miniaturas → guardado → sincronización y comprueba `videos_detectados` (3 videos), `guardado_total=3`, `resumen_sincronizacion=Sincronización completa: 0 incorporados, 0 eliminados, 0 candidatos restantes`, el estado final y el filtro con "real".
- **Fase de previews progresivos** — con la **carpeta real `videos_prueba/`** ejecuta la cadena completa del pipeline y espera a que el gestor de previews quede `inactivo` (cola vacía y temporizador parado); imprime `previews_archivos` (archivos `_preview_` presentes en `miniaturas/`), `previews_pixmaps` (etiquetas con pixmap) y `previews_tarjetas`.
- **Fase de doble clic** — `QTest.mouseDClick` real sobre la tarjeta del video real de `videos_prueba/` con `abrir_video_con_aplicacion_predeterminada` **parcheado** (se captura la invocación y se restaura después); imprime `abrir_nombre`, `abrir_ruta`, `abrir_mensaje` y `abrir_con_aplicacion`.
- **Fase de persistencia** — con una configuración temporal (`VISOR_CONFIG`) verifica la restauración de la última carpeta; imprime `config_ruta`, `persistencia_restaurada` y `persistencia_sin_carpeta`.
- `main()` termina con `exit 0` solo si todas las fases pasan, **sin avisos `QThread: Destroyed`**. Las suites de interfaz `prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py` y `prueba_recarga_catalogo.py` invocan este arnés vía `subprocess` (`["prueba_smoke.py"]`).

### `tareas.py` — infraestructura genérica de trabajos en segundo plano
- `Estado` — estados del ciclo de vida: `inactivo`, `ocupado`, `finalizando`, `cerrado`.
- `TareaBase(QObject)` — clase base de tareas asíncronas; señales `inicio`, `finalizada`, `error(str)`, `resultado(object)` y **`progreso(int, int)`** (infraestructura de progreso, Etapa B3.20). `ejecutar()` emite `inicio`, invoca `_trabajo()` y emite `resultado(valor)`; ante una excepción emite `error(f"{Tipo}: {msg}")`; siempre emite `finalizada`. Las subclases implementan `_trabajo()`. La emisión de `progreso` es **opcional y aditiva** (`ejecutar()` no se modifica y ninguna tarea existente emite progreso todavía); `reportar_progreso(procesado, total)` es un helper que convierte a `int` (ignora inválidos), ignora `total <= 0` (indeterminado), acota `procesado` a `[0, total]` y emite `self.progreso` — las subclases pueden también emitir `self.progreso.emit(...)` directamente.
- `GestorTareas(QObject)` — orquesta cada tarea en un `QThread` propio. Señales `tarea_iniciada`, `tarea_resultado(object)`, `tarea_error(str)`, `tarea_finalizada`, **`tarea_progreso(int, int)`** y `actividad_cambiada(bool)`. `iniciar(tarea)` valida la tarea, crea el `QThread`, la mueve a él y lo arranca; conecta `tarea.progreso → relay.al_progreso` (reenvío con el mismo criterio del token `_vigente`, descartando emisiones tardías tras cerrar o reemplazar la tarea); el hilo termina cuando la tarea emite `finalizada`. `cerrar(timeout_ms)` permite el apagado ordenado.

### `tareas_videos.py` — tareas asíncronas específicas de video
Capa de **tareas asíncronas**: no define lógica de catálogo ni de datos. Re-exporta desde `escanear_videos.py` las funciones que la interfaz necesita importar (entre ellas `preparar_registros_basicos`, `combinar_registros_con_ffprobe`, `combinar_registros_con_tamanos`, `obtener_tamanos_archivos`, `previews_existentes`, `calcular_tiempo_preview`, `generar_previews_faltantes` y `conectar_bd`), lo que evita que `visor_videos.py` dependa directamente del backend de catálogo.
- `rutas_videos()` — rutas absolutas de los videos de `videos_prueba/` detectados por `escanear_videos`.
- `TareaFFprobe(TareaBase)` — ejecuta `obtener_datos_ffprobe` sobre una lista de rutas en segundo plano; devuelve un diccionario con `rutas`, `resultados`, `procesados`, `con_datos` y `con_error`. Cada resultado contiene `ruta`, `datos` y `error` por archivo. **Progreso real** (Etapa B3.21): recorre las rutas con un bucle explícito y emite `reportar_progreso(indice + 1, total)` tras cada ruta. **B4.5 Etapa 3 — reutilización de metadata**: acepta además `nombres`, `stats` (resultado de `obtener_tamanos_archivos` con `tamano_bytes`/`mtime_ns` por ruta) y `ruta_db`; si están presentes, consulta los registros previos por lote (`listar_registros_por_nombres`), clasifica con `_metadata_reutilizable` (criterio ruta normalizada + tamaño + `mtime_ns` + metadata válida) y ejecuta FFprobe **solo** para los videos nuevos/cambiados/sin `mtime_ns`/con metadata inválida; los reutilizables emiten `datos` con la metadata de la BD. El resultado final tiene el mismo formato para todos (indistinguible por origen). Sin esos parámetros conserva el comportamiento anterior (FFprobe para todas las rutas).
- `TareaEscaneo(TareaBase)` — recibe una carpeta y devuelve la misma lista ordenada de archivos de video que `escanear_videos(carpeta)`. Una carpeta inexistente (`FileNotFoundError`) o una ruta que no es carpeta (`NotADirectoryError`) se propaga mediante la señal `error` de la infraestructura.
- `TareaTamanosArchivos(TareaBase)` — recibe la lista de nombres de video y la carpeta escaneada, conserva una instantánea (`list(...)`; `None` → lista vacía, texto → lista de un elemento) y expone las propiedades de solo lectura `videos` (copia) y `carpeta`. `_trabajo()` invoca `obtener_tamanos_archivos(videos, carpeta, self.reportar_progreso)` (progreso real por video, Etapa B3.21) y devuelve su resumen `{"rutas", "resultados", "procesados", "con_tamano", "sin_tamano"}` (un `dict` con `tamano_bytes` y `mtime_ns` por ruta, obtenidos con un único `os.stat` — B4.5 Etapa 3; `None` si el archivo no existe o es ilegible). Los errores de contrato (`TypeError`/`ValueError`) y `FileNotFoundError` se convierten en la señal `error` gestionada por `TareaBase`. No abre SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas ni toca la interfaz.
- `TareaMiniaturas(TareaBase)` — recibe la lista de nombres de video, la carpeta escaneada y, desde **B4.5**, un mapa opcional `duraciones` (por ruta o por nombre); conserva una instantánea (`list(...)`), y `_trabajo()` invoca `asegurar_miniaturas(videos, carpeta, self.reportar_progreso, self._duraciones)` (progreso real por video, Etapa B3.21) y devuelve su resumen `{"rutas", "resultados", "procesados", "con_miniatura", "sin_miniatura"}`. Con duraciones disponibles evita el FFprobe interno de `generar_miniatura` (B4.5). Los errores de contrato (`TypeError`/`ValueError`) se convierten en la señal `error` gestionada por `TareaBase`. Ejecuta FFmpeg y FFprobe únicamente dentro de la tarea (nunca en el hilo principal); no abre SQLite ni toca la interfaz. Re-exporta `asegurar_miniaturas` y `combinar_registros_con_miniaturas` desde `escanear_videos`.
- `TareaPreviewsProgresivas(TareaBase)` — genera los **previews progresivos** de una lista de videos en segundo plano: conserva una instantánea de los nombres (`list(...)`) y la carpeta, expone las propiedades de solo lectura `videos` (copia) y `carpeta`, y `_trabajo()` invoca `generar_previews_faltantes(videos, carpeta, self._duraciones)` (con el mapa opcional `duraciones` desde **B4.5**) devolviendo su resumen `{"rutas", "resultados", "procesados", "con_previews", "sin_previews"}` (cada resultado incluye `nombre`, `previews` —rutas de los 1..3 existentes—, `generados`, `reutilizados`, `errores` y `completos`). Con duraciones disponibles evita el FFprobe interno de `generar_preview` (B4.5). Los errores de contrato (`TypeError`/`ValueError`) se convierten en la señal `error` gestionada por `TareaBase`. FFmpeg se ejecuta únicamente dentro de la tarea (nunca en el hilo principal); no abre SQLite, no consulta la BD ni toca la interfaz. La interfaz la ejecuta con un **segundo `GestorTareas`** (`gestor_previews`) en lotes de a 3 videos.
- `TareaLecturaCatalogo(TareaBase)` — lee el catálogo en segundo plano invocando `listar_videos(ruta_db)`; devuelve la misma estructura que la lectura síncrona. Acepta una ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Regla de conexión SQLite por hilo**: la conexión se abre y se cierra dentro del hilo de trabajo, se usa únicamente en ese hilo, no se almacena como atributo persistente de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores de lectura (`FileNotFoundError` si la base no existe, `sqlite3.OperationalError`, `sqlite3.DatabaseError`, etc.) se convierten en la señal `error` gestionada por `TareaBase`. La lectura no crea archivos: si la base no existe, se comunica `FileNotFoundError` sin crear la base.
- `TareaLecturaCatalogoPaginada(TareaBase)` — lectura **paginada** del catálogo en segundo plano. Recibe los mismos parámetros que `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` (ruta de base opcional; por defecto `ruta_biblioteca()`). El constructor conserva una instantánea de los parámetros (escalares inmutables) y expone las propiedades `limite`, `desplazamiento`, `texto` y `ruta_db`. `_trabajo()` invoca `listar_videos_paginado` y devuelve exactamente su resultado `{"videos", "total", "limite", "desplazamiento"}`. **Regla de conexión SQLite por hilo**: la conexión se abre y se cierra dentro del hilo de trabajo (mediante la función síncrona), se usa únicamente en ese hilo, no se almacena como atributo y no se usa `check_same_thread=False`. Los errores de contrato (`TypeError`/`ValueError`), `FileNotFoundError` si la base no existe y `sqlite3.DatabaseError` si la base está corrupta se convierten en la señal `error` gestionada por `TareaBase`. No accede a la interfaz, no escanea archivos, no ejecuta FFprobe ni FFmpeg y no escribe en SQLite. `TareaLecturaCatalogo` conserva su contrato sin cambios.
- `TareaGuardarVideo(TareaBase)` — guarda un único registro de video en segundo plano invocando `guardar_video(datos, ruta_db)`; devuelve el resultado simple `{"guardado": True, "nombre": ...}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instantánea del registro**: el constructor toma una copia superficial (`self._datos = dict(datos)`), de modo que mutaciones posteriores del diccionario original del llamador no afectan la ejecución; la propiedad `datos` devuelve una copia y nunca expone el diccionario interno. Un valor que `dict()` no pueda copiar se conserva como `datos` inválido y `_trabajo()` lo comunica mediante `error` (`TypeError`) sin tocar la base. **Regla de conexión SQLite por hilo**: la conexión se abre dentro de `_trabajo()` (mediante la función síncrona), se usa únicamente en ese hilo, el `commit` se ejecuta en el hilo de trabajo solo si toda la operación terminó correctamente, se ejecuta `rollback` ante cualquier error posterior al inicio de la transacción, se cierra siempre en `finally`, no se almacena como atributo de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores (`FileNotFoundError` si la base no existe, `sqlite3.DatabaseError` si la base está corrupta, `ValueError`/`TypeError` por contrato inválido, etc.) se convierten en la señal `error`. No sincroniza el catálogo, no elimina registros, no encadena tareas y no se conecta a la interfaz.
- `TareaGuardarVideos(TareaBase)` — guarda una **colección de registros** en segundo plano invocando `guardar_videos(datos_videos, ruta_db, self.reportar_progreso)` (progreso real por registro, Etapa B3.21); devuelve el resumen `{"guardados": <cantidad>, "nombres": [...]}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instantánea de la colección y de cada registro**: el constructor materializa la colección (`list(...)`) y toma una **copia superficial por registro** (`dict(d)`) al construirse; no conserva la colección mutable original, de modo que mutaciones posteriores de la lista o de los diccionarios del llamador no afectan la ejecución; la propiedad `datos` devuelve copias frescas y nunca expone el estado interno. **El constructor nunca lanza ante entradas inválidas**: si la colección no es iterable, es texto, contiene un elemento no copiable, o incluso si su materialización falla a mitad de la iteración (p. ej. un generador que lanza una excepción), la tarea se construye igualmente, se conserva la causa como colección inválida y `_trabajo()` la comunica mediante `error` (un `TypeError` que envuelve la causa) sin tocar la base; los errores de contrato que solo `guardar_videos` detecta al validar (p. ej. una clave obligatoria ausente en un registro ya copiado) también se comunican por `error` durante la ejecución. **Regla de conexión SQLite por hilo**: la conexión se abre dentro de `_trabajo()` (mediante la función síncrona) y realiza un único `commit` por colección en el hilo de trabajo; `rollback` ante cualquier error; se cierra siempre en `finally`; no se almacena como atributo de la tarea; sin `check_same_thread=False`. Los errores (`FileNotFoundError`, `sqlite3.DatabaseError`, `ValueError`/`TypeError` por contrato inválido, fallo durante el registro intermedio con rollback total) se convierten en la señal `error`. No sincroniza el catálogo, no elimina registros, no encadena tareas, no implementa escritura por lotes concurrentes y no se conecta a la interfaz.
- `TareaSincronizacionCatalogo(TareaBase)` — **sincronización asíncrona del catálogo**: orquesta en segundo plano la sincronización disco ↔ BD encadenando las cuatro operaciones de la capa de catálogo en la secuencia exacta `detectar_diferencias` → `preparar_plan_sincronizacion` → `aplicar_incorporaciones` → `eliminar_candidatos`. El constructor recibe `carpeta` (ruta de texto de la carpeta de videos) y `ruta_db` **opcional** (ruta SQLite; por defecto se delega el default a las funciones de `escanear_videos`, es decir `ruta_biblioteca()`), más `parent` como **padre Qt compatible con `QObject`** (no específicamente un `QWidget`) y `carpetas_protegidas` **opcional** (Etapa 5: raíces del alcance multicarpeta a proteger); conserva ambos valores y los expone mediante las propiedades de solo lectura `carpeta` y `ruta_db`, que **devuelven directamente los valores actualmente inmutables (`str` o `None`) recibidos en el constructor** — no realizan copias generales ni devuelven nuevas copias. `_trabajo()` invoca las cuatro funciones mediante el módulo `escanear_videos` en el orden exacto indicado (pasando `carpetas_protegidas` a `detectar_diferencias`) y devuelve el resultado `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`; `resumen` contiene `nuevos`, `ya_sincronizados`, `incorporados`, `eliminados` y `candidatos_restantes` (no se afirma que el resultado completo sea inmutable). **La tarea no contiene SQL, no abre SQLite directamente, no almacena conexiones y no usa `check_same_thread=False`**: todo el acceso a la base ocurre dentro de las funciones síncronas de `escanear_videos`, cada una con su propia conexión abierta y cerrada en el hilo de trabajo. **No ejecuta FFprobe, FFmpeg, miniaturas ni subprocesos y no accede a la interfaz.** **Atomicidad**: la incorporación y la eliminación son **transacciones independientes**, no una única transacción global; si falla la incorporación **no se ejecuta la eliminación** (la excepción propaga y `TareaBase` emite `error`); si falla la eliminación, las **incorporaciones ya confirmadas permanecen** y la eliminación fallida revierte **únicamente su propia transacción** (rollback interno de `eliminar_candidatos`), sin revertir las incorporaciones previas. Se ejecuta en segundo plano por la infraestructura `tareas.py` (`TareaBase` + `GestorTareas` en un `QThread` por ejecución) con las señales `inicio`, `resultado`, `error` y `finalizada`; el hilo de trabajo es distinto del principal. **No está integrada todavía con `visor_videos.py`**: la tarea existe como pieza orquestadora y la **próxima etapa pendiente es integrar esta tarea con el flujo de la interfaz**.

- `TareaListarMarcadores(TareaBase)` — **lectura asíncrona de marcadores** (B4.2): recibe
  `video_id` (y `ruta_db` opcional) y `_trabajo()` invoca `listar_marcadores(video_id, ruta_db)`,
  devolviendo su resultado (lista de tuplas `(id, video_id, tiempo, color)` desde **B6.3**).
  Expone las propiedades
  de solo lectura `video_id` y `ruta_db`. Los errores de contrato y de lectura se convierten
  en la señal `error` gestionada por `TareaBase`. Conexión abierta y cerrada en el hilo de
  trabajo (patrón de `TareaLecturaCatalogo`).
- `TareaGuardarMarcador(TareaBase)` — **persistencia asíncrona de un marcador** (B4.2): recibe
  `video_id`, `tiempo` y `ruta_db` opcional; **B6.3** acepta además `color` (clave estable o
  `None`, persistido en el mismo `INSERT`). `_trabajo()` invoca
  `guardar_marcador(video_id, tiempo, ruta_db, color)` y devuelve el **`id` de la base**. El
  `commit` y el `rollback` ocurren dentro del hilo de trabajo. Expone las propiedades
  `video_id`, `tiempo`, `color` y `ruta_db`.
- `TareaEliminarMarcador(TareaBase)` — **eliminación asíncrona de un marcador** (B4.2): recibe
  `marcador_id` (y `ruta_db` opcional); `_trabajo()` invoca
  `eliminar_marcador(marcador_id, ruta_db)` y devuelve `True`/`False`. Expone las propiedades
  `marcador_id` y `ruta_db`. La interfaz la ejecuta con un **gestor dedicado**
  (`gestor_marcadores`, cuarto gestor), no con el gestor principal ni el de previews.
- `TareaAsignarColorMarcador(TareaBase)` — **asignación asíncrona de color a un marcador**
  (B6.3): recibe `marcador_id`, `color` (clave estable o `None` = quitar) y `ruta_db`
  opcional; `_trabajo()` invoca `asignar_color_marcador(marcador_id, color, ruta_db)` y
  devuelve la fila persistida `(id, video_id, tiempo, color)` o `None`. Expone las propiedades
  `marcador_id`, `color` y `ruta_db`. Mismo gestor dedicado que las demás operaciones de
  marcadores.
- `TareaAsignarColorSegmento(TareaBase)` — **asignación asíncrona de color a un segmento**
  (B6.3): recibe `segmento_id`, `color` (clave estable o `None` = quitar) y `ruta_db`
  opcional; `_trabajo()` invoca `asignar_color_segmento(segmento_id, color, ruta_db)` y
  devuelve la fila persistida `(id, inicio, fin, color)` o `None`. Expone las propiedades
  `segmento_id`, `color` y `ruta_db`. Mismo patrón que la instrucción de segmentos del gestor
  dedicado de la interfaz.
- `TareaExploracionDensa(TareaBase)` — **cobertura densa de exploración temporal de un video**
  (B4.3.2 / B4.3.3): recibe `video_id`, `ruta_video`, `duracion`, `parent` y, desde B4.3.3,
  `objetivo_manual` (None = Auto); captura **instantáneas inmutables** y expone las propiedades
  de solo lectura `video_id`, `ruta_video`, `duracion` y `objetivo_manual`. `_trabajo()` calcula
  el objetivo total como `objetivo_manual` si es positivo o `objetivo_total_densidad(duración)`
  en Auto, y genera en **dos fases secuenciales**: la **fase rápida** produce los
  **`FOTOGRAMAS_INICIALES = 15`** prioritarios y, solo después de terminar y sin cancelarse, la
  **fase secundaria** completa hasta el objetivo reutilizando lo existente (un FFmpeg por
  objetivo, serial, sin batch). En cada fase se construye explícitamente el **conjunto
  permitido** `tiempos_objetivo(duración, cantidad_actual)` y la emisión (`resultado_parcial`)
  y la cola final **solo decodifican/emiten ese subconjunto**: la caché en disco puede contener
  un **superset** (densidades manuales previas) y la tarea decide qué subconjunto utiliza. En
  ambas fases emite **resultados parciales progresivos** a través de la señal
  **`resultado_parcial = Signal(object)`** (un diccionario con `video_id`, `version` y una lista
  `(ms, QImage)` ya decodificada en el worker) y termina con la cola final
  `{"imagenes": [(ms, QImage), ...]}` de los fotogramas aún no emitidos. La decodificación de
  los JPEG (`QImage`) ocurre **en el hilo de trabajo**; la conversión a `QPixmap` y su
  aplicación se delega a la GUI. Usa la **cancelación cooperativa** de la caché para abortar la
  generación al cambiar de video/tarjeta (la fase secundaria no arranca si la tarea fue
  cancelada). No abre SQLite y no toca la interfaz.

### `exploracion_temporal.py` — lógica pura de exploración temporal (B4.1 y B4.3.1)
Módulo **puro** (sin Qt, sin FFmpeg, sin SQLite, sin archivos ni caché persistente) que
concentra el mapeo espacial/temporal, la selección de la preview existente más cercana y la
**densidad/orden de la caché densa de exploración** (B4.3.1):

- `ancho_valido(ancho)` / `duracion_valida(duracion)` — validación de ancho (px) y duración (s)
  como números positivos no `bool`.
- `normalizar_posicion(posicion, ancho)` — acota la posición horizontal al intervalo `[0, ancho]`
  (devuelve `None` si el ancho o la posición no son válidos).
- `posicion_a_tiempo(posicion, ancho, duracion)` — **mapeo posición → instante**: `x=0 → 0`,
  `x=ancho → duracion`, proporcional en el medio; fuera de rango se acota. Es la base de la
  conversión del cursor en la superficie temporal.
- `tiempo_a_posicion(instante, ancho, duracion)` — inversa (instante → px), usada para dibujar el
  marcador móvil, las marcas persistentes y posicionar la preview móvil.
- `preview_mas_cercana(instantes, instante)` — índice de la preview (dentro de la lista original)
  cuyo **tiempo real** es el más cercano al instante solicitado por distancia temporal absoluta;
  descarta `None` y en empate elige el menor índice. No es "posición dentro de la lista": usa el
  tiempo asociado a cada preview.
- `agregar_marcador_ordenado(instante, marcadores, tolerancia)` — inserta el instante real
  conservando el orden temporal y evitando duplicados absurdamente cercanos.
- `cantidad_fotogramas(duracion)` — **densidad de la caché densa** (B4.3.1):
  `clamp(round(duración / PASO_SEGUNDOS), MINIMO_FOTOGRAMAS, MAXIMO_FOTOGRAMAS)` con
  `PASO_SEGUNDOS = 2.0`, piso 40 y techo 200 (aprobados provisionalmente en el diseño de B4.3);
  duración inválida → 0 (sin caché posible).
- `tiempos_objetivo(duracion, cantidad)` — instantes objetivo en **milisegundos enteros** en
  **orden progresivo de cobertura** (B4.3.1): la cobertura crece por **bisección de huecos**
  (primero el punto medio 50 %, luego los cuartos 25/75 %, luego los octavos 12.5/37.5/62.5/
  87.5 %, y así), de izquierda a derecha en cada nivel. Es el orden de generación recomendado:
  pocos fotogramas bien repartidos al inicio y densidad creciente después (base de la estrategia
  híbrida de B4.3.2). Descarta duplicados por redondeo.
- `fotograma_mas_cercano(ms_existentes, instante)` — milisegundo del fotograma existente más
  cercano al instante pedido (segundos → ms) por **`bisect`**; en empate de distancia elige el
  fotograma anterior (menor instante).

### `scrubber.py` — superficie temporal y miniatura de marcador (B4.1)
Módulo **de interfaz** con dos clases:

- `FranjaExploracion(QWidget)` — la **superficie temporal**: toda la segunda fila expandida
  representa la duración completa del video (izquierda = 0 %, derecha = 100 %). Convierte el
  movimiento del mouse (usa **solo la coordenada X**; la altura es irrelevante) en la señal
  `instante_seleccionado(float)`, el clic izquierdo en `marcador_solicitado(float)` y el clic
  derecho sobre una marca en `marcador_contextual_solicitado(float)` (**B6.3**; antes
  `marcador_eliminar_solicitado`, por el menú contextual). Dibuja la pista, el marcador
  móvil azul del cursor, las marcas persistentes (color de clasificación o rojo histórico,
  B6.3) y el texto del tiempo. No conoce videos,
  previews, FFmpeg, SQLite ni caché.
- `MiniaturaMarcador(QLabel)` — miniatura fijada de un marcador: recibe el **clic derecho** y
  emite `contextual_solicitado(tiempo)` (**B6.3**; antes `eliminar_solicitado`, porque el clic
  derecho ya no elimina directamente sino que abre el menú contextual del marcador); el clic
  izquierdo queda reservado (no crea ni elimina);
  reenvía el movimiento del mouse a la superficie en coordenadas de la superficie para que el
  scrubbing continúe aunque el cursor pase por encima de la miniatura.
- **Render del color de clasificación (B6.3).** `FranjaExploracion` recibe además los colores
  de los marcadores (`set_marcadores(marcadores, colores=None)`, mapa `tiempo → clave`) y
  pinta cada marca con `_color_marca_para(tiempo)` (QColor de la paleta vía `color_rgb`, o el
  rojo histórico `_COLOR_MARCA` si la clave falta o es `NULL`). Las bandas de segmento se
  dibujan con `_color_fondo_segmento(seg)` / `_color_borde_segmento(seg)`: si el segmento es
  un `dict` con `color` de la paleta, usan ese color (fondo con la alpha histórica); cualquier
  otro caso conserva el azul histórico (`_COLOR_SEGMENTO` / `_COLOR_SEGMENTO_BORDE`).

**Integración con `Tarjeta` (`visor_videos.py`):** la tarjeta conserva el **estado de los
marcadores** (`_marcadores` = lista de `{"tiempo": float, "pixmap": QPixmap, "etiqueta": QLabel}`,
con el **tiempo real como fuente de verdad**), decide **qué pixmap mostrar**
(`preview_mas_cercana` sobre los tiempos reales de las previews cargadas) y **dónde mostrarlo**
(`tiempo_a_posicion` del instante solicitado, con clamp para mantener la imagen dentro de la
superficie). La separación **"qué imagen / dónde"** es explícita: la posición de la preview móvil
depende **solo del instante solicitado**, nunca del tiempo propio de la preview elegida; el label
de la preview se ajusta al tamaño real del pixmap (compatible con previews horizontales y
verticales, sin huecos internos). La superficie se acota al ancho visible del `QScrollArea`
(`_limitar_ancho_superficie`) para que el extremo derecho (100 %) siempre sea alcanzable.
**`mouseMove` = cero FFmpeg + cero acceso a disco + cero creación innecesaria de pixmaps** (se
reutilizan pixmaps ya cargados en memoria). Los marcadores son **solo en memoria** (persisten
mientras vive la tarjeta durante la sesión); la **persistencia queda deliberadamente fuera de
B4.1** y será responsabilidad de B4.2.

### Persistencia de marcadores (B4.2)

**Persistencia.** Los marcadores temporales creados por el usuario se almacenan
**permanentemente en SQLite**: se relacionan mediante **`videos.id`**, reaparecen entre
sesiones, pueden eliminarse permanentemente y recuperan su representación visual usando las
previews disponibles.

**Tabla `marcadores_video`:**

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `video_id INTEGER NOT NULL`
- `tiempo REAL NOT NULL`

Índice: `idx_marcadores_video_video_id_tiempo`.

**Sin:** cascade automático (`PRAGMA foreign_keys` desactivado y sin `ON DELETE CASCADE`),
nombre/ruta como identidad, imagen persistida, nota/color/tipo ni JSON. La coherencia con
`videos.id` se gestiona en la capa de servicio.

**Política de conservación (deliberada):**

- Reescaneo del mismo registro → **conserva** los marcadores.
- Cambios de metadatos → **conserva**.
- Reemplazo silencioso manteniendo el mismo registro → actualmente **conserva**.
- Si el registro de video desaparece → los marcadores **NO** se eliminan automáticamente;
  pueden quedar **marcadores huérfanos**.
- No existe aún **reasociación** de movidos/renombrados, ni se intenta reasociar por nombre o
  ruta.

Esto es deliberado para **evitar la pérdida automática de datos creados por el usuario**.

**Arquitectura en la interfaz (`visor_videos.py`, B4.2):**

- `Tarjeta` recibe `video_id` (de la columna `id` del registro del catálogo) y **no ejecuta
  SQLite directamente**.
- Mantiene la **representación optimista en memoria** (`_marcadores` con
  `{"id", "tiempo", "pixmap", "etiqueta", "eliminada"}`; `marcador_id` = identidad técnica
  persistente; `id=None` mientras no se confirma el INSERT).
- **Carga** los marcadores al expandir (`marcadores_solicitados` emitido por `Tarjeta` →
  `_solicitar_carga_marcadores`, una sola vez por tarjeta).
- **Persiste** altas/bajas mediante el **gestor dedicado `gestor_marcadores`** (cuarto
  `GestorTareas`, independiente del pipeline, de previews y de operaciones; cola serializada
  `_cola_marcadores` + `_procesar_siguiente_marcador`, se cierra en `closeEvent`). Los
  handlers `_al_marcador_creado` / `_al_marcador_eliminado` encolan operaciones de tipo
  `"crear"` / `"eliminar"` / `"cargar"`; `_al_resultado_marcadores` aplica el `id` de la base
  al registro local (y encola un DELETE compensatorio si el marcador ya fue eliminado) y
  `_al_error_marcadores` deshace la marca local de eliminación pendiente y vuelve a cargar
  tras un DELETE fallido.
- **Reconciliación asíncrona.** La carga desde SQLite se trata como un **snapshot
  potencialmente antiguo**: **NO reemplaza ciegamente** el estado local. `_aplicar_marcadores_cargados`
  conserva las **altas locales** ocurridas mientras la carga estaba pendiente, respeta las
  **bajas locales** (`_marcadores_eliminados_carga`, con DELETE compensatorio de la fila
  persistida), conserva los **IDs persistentes existentes** y **deduplica por la misma
  tolerancia temporal** usada por la interacción (`_tolerancia_marcadores` = duración / ancho
  × 0.5), cancelando el INSERT redundante cuando una fila de la carga coincide con un marcador
  local sin `id`.
- **Carreras cubiertas:**
  - **Crear y borrar antes de terminar el INSERT**: si el `CREATE` sigue en la cola se
    cancela (`_cancelar_crear_pendiente`); si ya se ejecutó, el DELETE compensatorio lo
    elimina.
  - **Cargar + crear**: la carga tardía no elimina la nueva marca.
  - **Carga + marcador equivalente**: se conserva un solo marcador, se adopta el ID
    persistente y se cancela el INSERT redundante.
  - **Carga + baja local**: el snapshot viejo no resucita el marcador; puede ejecutarse un
    DELETE compensatorio.
  - **Recuperación tras DELETE fallido**: se vuelve a consultar (`"cargar"`) y no se destruyen
    altas locales pendientes.

### `exploracion_cache.py` — motor de caché temporal versionada y reanudable (B4.3.1)
Módulo **puro** (sin Qt, sin SQLite y sin acoplamiento con `escanear_videos`) que materializa
en disco la caché densa de exploración temporal:

- **Estructura:** `miniaturas/exploracion/<video_id>/<version_fingerprint>/` con `meta.json` +
  `f{ms:010d}.jpg` (altura 120 px, JPEG). El `video_id` identifica la carpeta contenedora y no
  se repite en el nombre del JPG. `video_id_desde_ruta` deriva un id del nombre base saneado
  (limitación documentada: dos rutas con el mismo nombre base colisionan; la integración real
  B4.3.2 deberá pasar el `video_id` de la base de datos).
- **Fingerprint de metadatos baratos:** ruta normalizada (`normcase` + `normpath` + `abspath`) +
  tamaño + `mtime_ns` + duración → `version_id_de_fingerprint` = **SHA-256 reducido a 16 hex**.
  **NO** es un hash del contenido del video; **limitación aceptada**: dos archivos con la misma
  ruta, tamaño, mtime y duración no son distinguibles sin hash de contenido (no se intenta
  resolver en B4.3.1). Costo de `version_actual` ≈ **13 µs** (un `os.stat` + SHA-256); impacto
  CPU/RAM despreciable.
- **Identidad y completitud separadas:** la carpeta de versión identifica a qué fingerprint
  pertenecen sus JPEGs; la completitud se deriva de `objetivos - existentes`. Una versión
  parcial sigue siendo reconocible y **reanudable** sin repetir FFmpeg para los JPEGs ya
  terminados (cada JPEG se escribe **atómicamente**: temporal → `os.replace`; un `f*.jpg`
  presente está completo). `meta.json` solo se escribe cuando la generación termina sin
  cancelarse y **completa** (`faltantes == 0`).
- **Invalidación no destructiva:** cualquier cambio en el fingerprint produce una **versión
  distinta**; las versiones antiguas quedan en disco (no se borra nada automáticamente; la
  limpieza queda para una etapa futura, fuera de alcance). Una versión nunca utiliza ni lista
  JPEGs de otra. `.tmp` y archivos de preparación/fallidos quedan fuera del índice y de la
  lista (`listar_fotogramas_version` filtra por el conjunto objetivo de la duración).
- **Generación:** `generar_fotogramas(video_id, ruta_video, duracion=None, cantidad=None, ...)`
  consulta la duración con ffprobe si no se pasa (timeout 30 s), usa la densidad
  `cantidad_fotogramas` y la cobertura `tiempos_objetivo`, reutiliza los JPEGs ya presentes y
  emite una **invocación de FFmpeg por fotograma** (`-ss` + `-frames:v 1` + reducción de
  resolución durante la extracción, timeout 30 s, sin ventana de consola) — **serial, un FFmpeg
  a la vez**. Callbacks opcionales `on_progreso(indice, total)` y cancelación cooperativa
  `cancelar()`. Devuelve un resumen con `generados`, `reutilizados`, `errores`, `cancelado`,
  `faltantes`, `version` y `fotogramas`.
- **Densidad secundaria (B4.3.2 Etapa 2, provisional):** constantes centralizadas
  `FOTOGRAMAS_INICIALES = 15`, `PASO_SEGUNDOS_DENSIDAD = 30.0`,
  `MINIMO_FOTOGRAMAS_DENSIDAD = 15` y `MAXIMO_FOTOGRAMAS_DENSIDAD = 200`, y la función
  `objetivo_total_densidad(duración)` = `clamp(max(15, ceil(d/30)), 15, 200)` (duración
  inválida/cero/negativa/bool → 0). Son **provisionales** (30 s / mín 15 / máx 200) y NO se
  exponen en la interfaz; la arquitectura permite configurarlos después (p. ej. 60 / 30 / 15 s)
  en una etapa separada.
- **API para consumidores** (sin gestionar versiones): `listar_fotogramas`, `faltantes`,
  `cache_vigente`, `fotograma_mas_cercano_en_cache`, `ruta_carpeta_actual`, `version_actual`.
  `fotograma_mas_cercano_en_cache` consulta **solo la versión vigente**, nunca fotogramas de
  otras versiones ni sobrantes ajenos al conjunto objetivo.

**Benchmarks (B4.3.1, PC de desarrollo — no garantizan rendimiento en el hardware objetivo):**
fuente sintética `testsrc2` 640×360 @ 24 fps, 300 s (~28 MB). FFmpeg por fotograma:
20 → **1.20 s**, 40 → **2.38 s**, 100 → **6.02 s**, 200 → **12.04 s**; primera imagen
individual ≈ **0.06 s**; cobertura de 15 puntos ≈ **0.88 s**. Modo lote (solo **medición de
referencia**, no implementado en B4.3.1): 40 → **0.70 s**, 100 → **0.72 s**; primera imagen
del lote ≈ **0.054 s**. El **hardware objetivo** (notebook 16 GB RAM, Intel Core i7-7500U @
2.70 GHz, NVIDIA GeForce 940MX 2 GB, Intel HD Graphics 620) debe priorizar **agilidad y
fluidez**; antes de congelar MAX / cantidad inicial / lote / concurrencia se requiere una
**prueba real en esa notebook**.

### Cobertura densa integrada con la UI (`visor_videos.py`, B4.3.2)

**Consumo de la caché densa en la tarjeta.** La superficie temporal de B4.1 consume la caché de
B4.3.1 mediante la tarea asíncrona `TareaExploracionDensa`, ejecutada con el **gestor principal
de tareas** (un solo lanzamiento por tarjeta): mientras no existe caché la superficie conserva el
**fallback a las previews normales** y, en cuanto la tarea emite parciales, la cobertura mejora
**progresivamente** sin bloquear la interfaz. El flujo en `visor_videos.py`:
`_procesar_siguiente_exploracion` conecta la señal `resultado_parcial` y
`_al_resultado_parcial_exploracion` la consume; `_aplicar_exploracion_densa` (compatible con
`(ms, QImage)` y con deduplicación de repeticiones) convierte la `QImage` del worker en
`QPixmap` **en el hilo de la GUI** y la aplica al fotograma temporal.

**Reglas de integración:**
- **Selección exclusivamente en RAM durante `mouseMove`**: el cursor nunca lanza FFmpeg ni
  accede al disco; elige la imagen **más cercana** entre las previews normales y los fotogramas
  densos cargados (la preview normal gana el empate; los fotogramas densos solo entran cuando
  mejoran la distancia temporal).
- **Prioridad visual dinámica (B4.3.3)**: durante el hover la preview dinámica queda **por
  encima** de las miniaturas fijas de marcadores (`raise_()` en `_al_instante_exploracion`); al
  salir de la superficie (`QEvent.Leave` en el `eventFilter` del franja) se aplica `lower()` y
  las fijas vuelven a su orden visual normal. Los marcadores conservan tiempo/id; un marcador
  nunca tapa el instante que se explora activamente. Solo z-order de widgets, sin trabajo pesado
  en `mouseMove`.
- **Dos fases secuenciales (Etapa 2):** `_trabajo()` primero genera la **fase rápida** con los
  **`FOTOGRAMAS_INICIALES = 15`** prioritarios (Etapa 1) y, solo después de terminar y sin
  cancelarse, la **fase secundaria** completa hasta el objetivo de densidad reutilizando lo
  existente y generando únicamente los faltantes. **Sin solapamiento**: una imagen secundaria no
  aparece antes de finalizar la fase rápida. Generación **individual y secuencial, un FFmpeg por
  objetivo, sin batch y sin paralelismo**.
- **Densidad manual (B4.3.3):** `QComboBox` "Densidad:" (`Auto | 15 | 30 | 60 | 120 | 200`,
  constante `DENSIDADES_DISPONIBLES`) en la tarjeta expandida. `Auto` usa
  `objetivo_total_densidad(duración)`; los valores manuales son el **total objetivo
  independiente de la duración** (video de 30 s: Auto → 15, manual 60 → 60, manual 120 → 120),
  con los **15 prioritarios siempre primero**. La tarea recibe `objetivo_manual` (None = Auto) y
  en cada fase construye el **conjunto permitido** `tiempos_objetivo(duración, cantidad_actual)`:
  la caché en disco puede contener un **superset** y la tarea/UI decide el subconjunto — la
  RAM/UI se limita al conjunto objetivo actual; **aumentar** reutiliza lo existente (15→60,
  60→120); **disminuir** no borra disco ni regenera; **volver a Auto** recalcula y conserva los
  extras de disco. El valor es **por tarjeta/sesión** (se conserva en colapso/reexpansión de la
  misma tarjeta; vuelve a Auto si se reconstruye por recarga); **sin SQLite ni persistencia en
  `configuracion.json`** (la persistencia futura queda separada).
- **`FOTOGRAMAS_INICIALES = 15` y parámetros Auto provisionales**: la cobertura inicial y el
  objetivo automático (`PASO_SEGUNDOS_DENSIDAD`, mínimo y máximo) NO están congelados ni se
  exponen en la interfaz; están centralizados en `exploracion_cache.py` para configurarlos
  después (p. ej. 60 / 30 / 15 s) en una etapa separada. El control manual (B4.3.3) sí expone
  cantidades fijas.
- **Decodificación en el worker**: los JPEG se leen y decodifican a `QImage` dentro del hilo de
  trabajo y viajan por señal; la conversión a `QPixmap` (objeto ligado a la GUI) y su pintado
  ocurren en el hilo principal. Aplica a ambas fases.
- **Cancelación cooperativa**: al cambiar de video/tarjeta o de densidad, la tarea anterior se
  cancela de forma cooperativa (la caché aborta la generación entre fotogramas; la fase
  secundaria no arranca si la tarea fue cancelada); el estado de la tarjeta sigue el video
  correcto. Cambiar o colapsar detiene la continuación del trabajo y lo ya generado queda
  reutilizable.
- **Aislamiento A→B**: cada tarjeta usa su propia caché (`video_id` + versión vigente); la
  cobertura de una tarjeta nunca se aplica a la vecina.
- **Colapso que libera RAM**: al colapsar la tarjeta se sueltan las referencias a los `QPixmap`
  densos (queda el `QPixmap` de la miniatura/previews y el estado de marcadores); la caché en
  disco no se borra.
- **Reexpansión que reutiliza**: al reexpandir, si la versión sigue vigente, no se regenera
  nada (la fase rápida recupera primero los 15 y la secundaria completa hasta el objetivo actual
  sin FFmpeg si ya están en disco); si el video cambió (nuevo fingerprint) se genera una
  versión nueva sin tocar la anterior.
- **Marcadores**: conservan su tiempo e `id` y pueden **mejorar visualmente** su miniatura al
  llegar fotogramas densos más cercanos a su instante (incluidos los secundarios y manuales).

**Medidas de referencia (B4.3.2/B4.3.3, PC de desarrollo — no garantizan rendimiento en el
hardware objetivo):** video sintético de ~56 min (1280×720, 30 fps), objetivo Auto 112.
Primer fotograma prioritario ≈ **0.10 s**; **15 prioritarios ≈ 1.13 s**; **primer secundario
(16.º) ≈ 1.21 s** (después de la fase rápida, sin solapamiento); **total 112 ≈ 8.39 s**;
reexpansión con caché completa ≈ **0.08 s** (sin regenerar); scrub desde RAM sin lectura de
disco. Con un video de 30 s y densidad manual 60/120 la generación es rápida (fotogramas ya en
disco se reutilizan; FFmpeg = 0 al bajar densidad). La **notebook objetivo** (i7-7500U / 16 GB /
940MX) validó la **Etapa 1** y posteriormente **B4.3 en conjunto** con un video real de ~56 min.
**NO se requiere una campaña adicional de benchmarks exhaustivos**; el **batch NO está
implementado** (decisión de producto: generación individual y secuencial).

### Módulos ajenos al visor (preservados, no forman parte de la arquitectura)
- `main.py` — prueba que escribe el resultado en `datos.txt`.
- `prueba_agente.py` — artifacto de validación del agente.

## 4. Separación de responsabilidades

| Responsabilidad | Módulo | Observación |
| --- | --- | --- |
| Interfaz | `visor_videos.py` | Debe ser agnóstica a SQLite (corregido). |
| Lógica del catálogo | `escanear_videos.py` | `sincronizar_bd`, `actualizar_datos`. |
| Acceso a SQLite | `escanear_videos.py` | Único punto de acceso a la BD (corregido). |
| Escaneo de archivos | `escanear_videos.escanear_videos` | Filtro por extensión. |
| FFprobe | `escanear_videos.obtener_datos_ffprobe` | Metadatos de video. |
| FFmpeg | `escanear_videos.generar_miniatura` | Extrae un fotograma del video; genera la miniatura automáticamente (se ejecuta dentro de `TareaMiniaturas`). Desde B4.5 acepta `duracion_segundos` (válida → sin FFprobe interno). |
| Generación de miniaturas | `escanear_videos.asegurar_miniatura` / `asegurar_miniaturas` | Genera o reutiliza; escribe solo en la siguiente ranura libre y preserva los archivos existentes; `asegurar_miniaturas` orquesta la colección del pipeline. Desde B4.5 propaga `duraciones` (por ruta o nombre) para evitar el FFprobe interno. |
| Trabajos en segundo plano | `tareas.py` | `TareaBase` + `GestorTareas` (`QThread` por ejecución); señales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada`. |
| Escaneo asíncrono | `tareas_videos.TareaEscaneo` | Envuelve `escanear_videos` en segundo plano; errores por señal `error`. |
| FFprobe asíncrono | `tareas_videos.TareaFFprobe` | Metadatos de video en segundo plano; resultado y error por ruta. Desde B4.5 Etapa 3 acepta `nombres`/`stats`/`ruta_db` y reutiliza metadata de la BD para videos sin cambios (0 FFprobe), probeando solo los nuevos/cambiados. |
| Reutilización de metadata (B4.5 Etapa 3) | `escanear_videos._metadata_reutilizable` / `listar_registros_por_nombres` | Criterio barato `ruta normalizada + tamano_bytes + mtime_ns` (sin hash de contenido): 0 FFprobe solo si existe registro, `mtime_ns` no NULL, ruta/tamaño/`mtime_ns` coinciden y la metadata es válida. Consulta por lote por `nombre` (una SELECT); migración aditiva `videos.mtime_ns INTEGER NULL`; `obtener_tamanos_archivos` con un `os.stat` por archivo; `guardar_videos` persiste `mtime_ns`. |
| Carga diferida de previews (B4.6 Etapa 2) | `visor_videos` (`_crear_tarjetas`/`_encolar_previews`/`_aplicar_previews`/`Tarjeta.actualizar_previews`) | `_crear_tarjetas`/`_agregar_tarjetas`/`_reemplazar_tarjetas` no cargan previews cacheadas de golpe; las tarjetas parten con placeholders y las previews se incorporan progresivamente por la tubería existente. `Tarjeta._previews_completas` (interno, no persistido) decide la cola; `_aplicar_previews` ignora resultados tardíos de otra carpeta; `_reconstruir_previews_exploracion` cae a las previews de disco si las etiquetas aún no las tienen. |
| Lectura del catálogo | `escanear_videos.listar_videos` | Capa de lectura SQLite; abre y cierra su propia conexión en el hilo que la invoca. |
| Lectura asíncrona del catálogo | `tareas_videos.TareaLecturaCatalogo` | Lectura SQLite en segundo plano; errores por señal `error`; conexión por hilo (sin `check_same_thread=False`). |
| Lectura paginada del catálogo | `escanear_videos.listar_videos_paginado` + `tareas_videos.TareaLecturaCatalogoPaginada` | Página (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro en SQL; búsqueda parcial por `LIKE` parametrizada; sin leer toda la tabla; consumida por la interfaz para la carga inicial asíncrona de la primera página y para la **carga manual de una página adicional**. |
| Carga inicial asíncrona de la interfaz | `visor_videos.VisorVideos` + `tareas.GestorTareas` + `tareas_videos.TareaLecturaCatalogoPaginada` | La ventana se construye sin consultas SQL; `_iniciar_carga()` lee la primera página en segundo plano; estados de carga/error visibles y apagado ordenado en `closeEvent` (`gestor.cerrar()`). |
| Selección de carpeta desde la interfaz | `visor_videos.VisorVideos.seleccionar_carpeta` | `QFileDialog` + `os.path.abspath`/`os.path.isdir`; ruta en `carpeta_seleccionada`; no escanea, no toca SQLite/FFprobe/FFmpeg/miniaturas. |
| Escaneo asíncrono desde la interfaz | `visor_videos.VisorVideos.iniciar_escaneo` + `tareas_videos.TareaEscaneo` + `tareas.GestorTareas` | Botón "Escanear carpeta"; reutiliza el mismo `GestorTareas` de la ventana; estados internos `_escaneo_pendiente`/`tarea_escaneo`; resultado en `videos_detectados` con conteo visible; bloqueo de controles mientras el gestor está ocupado; sin SQLite/FFprobe/FFmpeg/miniaturas/tarjetas/recarga del catálogo. |
| Escritura individual | `escanear_videos.guardar_video` | Upsert transaccional de un único registro (datos preparados); `commit`/`rollback`/`close` propios; base inexistente → `FileNotFoundError` sin crear archivos. |
| Escritura individual asíncrona | `tareas_videos.TareaGuardarVideo` | Guarda un registro en segundo plano; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardado": True, "nombre": ...}`. |
| Escritura de colección | `escanear_videos.guardar_videos` | Upsert de una colección de registros en una **única transacción atómica** (un solo `connect` y un solo `commit`; `rollback` total ante cualquier fallo); validación completa y copias previas a SQL; resultado `{"guardados": n, "nombres": [...]}`; no elimina registros. |
| Escritura de colección asíncrona | `tareas_videos.TareaGuardarVideos` | Guarda una colección en segundo plano; instantánea de la lista y de cada registro; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardados": n, "nombres": [...]}`. |
| Preparación de registros básicos | `escanear_videos.preparar_registros_basicos` | Transforma los archivos detectados por el escaneo en registros con claves exactas `{nombre, ruta, extension, fecha_importacion}` (ruta absoluta en la carpeta escaneada); validación previa (no texto, iterable, carpeta no vacía); sin SQLite/FFprobe/FFmpeg/miniaturas. |
| Preparación del plan de sincronización | `escanear_videos.preparar_plan_sincronizacion` | Transforma el resultado de `detectar_diferencias` en el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`; `a_incorporar` son registros básicos de `preparar_registros_basicos` (su `fecha_importacion` se genera en la preparación); candidatos informativos; pura, sin SQLite/FFprobe/FFmpeg/miniaturas/pipeline/interfaz; la deduplicación de nombres repetidos sigue pendiente. |
| Aplicación de incorporaciones del plan | `escanear_videos.aplicar_incorporaciones` | Recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` y persiste únicamente `a_incorporar` reutilizando `guardar_videos` (misma transacción atómica); validación completa del plan antes de abrir SQLite; no elimina `candidatos_a_eliminar`, no modifica `ya_sincronizados`; resultado `{"incorporados", "nombres", "pendientes_eliminacion"}`; sin pipeline/interfaz/escaneo/FFprobe/FFmpeg; la eliminación controlada y la deduplicación siguen pendientes. |
| Eliminación controlada de candidatos del plan | `escanear_videos.eliminar_candidatos` | Recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` y elimina únicamente los registros de `candidatos_a_eliminar` (un `DELETE ... WHERE nombre = ?` por candidato con `rowcount`, un solo `commit`, `rollback` total, `close` en `finally`); validación completa compartida (`_validar_plan_sincronizacion`) antes de abrir SQLite; la colección de candidatos la ordena `_coleccion_nombres` (orden determinista de la validación actual); no elimina archivos físicos ni miniaturas, no toca `a_incorporar`/`ya_sincronizados`; resultado `{"eliminados", "nombres", "incorporados", "restantes"}` (`incorporados` informativo, puede ser `None`); sin pipeline/interfaz/escaneo/FFprobe/FFmpeg/`conectar_bd`/`guardar_videos`/`sincronizar_bd`; la integración asíncrona de la sincronización completa sigue pendiente. |
| Combinación de registros con metadatos FFprobe | `escanear_videos.combinar_registros_con_ffprobe` | Transforma los archivos detectados y el resultado de `TareaFFprobe` en registros con claves básicas `{nombre, ruta, extension, fecha_importacion}` + metadatos FFprobe (`duracion_segundos`, `ancho`, `alto`, `codec_video`; `NULL` si el video no tiene `datos`); pura, sin SQLite/FFprobe/FFmpeg/miniaturas; normalización interna de rutas. |
| Encadenamiento del pipeline desde la interfaz | `visor_videos.VisorVideos` + `tareas_videos.TareaEscaneo`/`TareaFFprobe`/`TareaMiniaturas`/`TareaGuardarVideos` + `escanear_videos.combinar_registros_con_ffprobe`/`combinar_registros_con_miniaturas` | Tareas sucesivas con el mismo `GestorTareas`: `TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas` → `combinar_registros_con_ffprobe` + `combinar_registros_con_miniaturas` → `TareaGuardarVideos`. El paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior (el gestor `Ocupado` rechaza una segunda tarea mientras otra corre); resultado/error del guardado limpian `_guardado_pendiente`; tras un error de guardado, de FFprobe o de miniaturas el gestor queda `inactivo` y un nuevo escaneo es posible. No es la sincronización completa del catálogo. |
| Miniaturas asíncronas | `tareas_videos.TareaMiniaturas` | Asegura/reutiliza/ cuenta miniaturas en segundo plano vía `asegurar_miniaturas`; FFmpeg y FFprobe solo dentro de la tarea; resultado `{"rutas", "resultados", "procesados", "con_miniatura", "sin_miniatura"}`. |
| Sincronización asíncrona del catálogo | `tareas_videos.TareaSincronizacionCatalogo` | Orquesta en segundo plano la secuencia exacta `detectar_diferencias` → `preparar_plan_sincronizacion` → `aplicar_incorporaciones` → `eliminar_candidatos`. Sin SQL, sin abrir SQLite directamente, sin conexiones almacenadas, sin `check_same_thread=False`, sin FFprobe/FFmpeg/miniaturas/subprocesos y sin acceso a la interfaz. Resultado `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`. Incorporación y eliminación como **transacciones independientes** (no una única transacción global). **Integrada con `visor_videos.py`**: se lanza tras el guardado exitoso del pipeline y al terminar dispara la **recarga asíncrona del catálogo** con reemplazo de tarjetas. |
| Recarga asíncrona del catálogo tras la sincronización | `visor_videos.VisorVideos._iniciar_recarga_catalogo` + `tareas_videos.TareaLecturaCatalogoPaginada` | **Solo tras una sincronización exitosa** (`_recarga_catalogo_pendiente` marcado por `_al_resultado_sincronizacion`), con el **mismo** `GestorTareas` y la misma tarea de lectura (`_crear_tarea_lectura`, primera página `TAMANIO_PAGINA_INICIAL`). `_al_resultado_recarga` reemplaza las tarjetas (`_reemplazar_tarjetas`: libera las viejas con `removeWidget`/`deleteLater`, vacía `self.tarjetas`, crea las nuevas y reaplica el filtro) conservando `resultado_sincronizacion`; `_al_error_recarga` conserva las tarjetas viejas, muestra `MENSAJE_ERROR_RECARGA` y deja la interfaz recuperable sin revertir la sincronización ya confirmada. Sin SQL en la GUI, sin FFprobe/FFmpeg/miniaturas y sin llamar a `listar_videos_paginado` directamente (solo vía la tarea). |
| Carga manual de una página adicional del catálogo | `visor_videos.VisorVideos.cargar_mas` + `tareas_videos.TareaLecturaCatalogoPaginada` + `tareas.GestorTareas` | Botón "Cargar más": lee la página siguiente con `OFFSET = len(self.tarjetas)` con el mismo gestor; `_al_resultado_pagina` **agrega** las tarjetas nuevas debajo de las existentes (`_agregar_tarjetas`) **sin reemplazarlas** y **sin duplicados**; `_al_error_pagina` conserva las tarjetas ya cargadas y muestra `MENSAJE_ERROR_PAGINA` ("No se pudo cargar la página"). El reemplazo de tarjetas sigue siendo exclusivo de la recarga tras la sincronización. |
| Apertura del video con la aplicación predeterminada | `apertura_videos.abrir_video_con_aplicacion_predeterminada` | **Único punto que ejecuta `os.startfile`** (verificado por AST en `prueba_doble_clic.py`). Recibe `nombre` + `carpeta`, valida ambos como texto no vacío (`ValueError`), resuelve la ruta **absoluta** (`os.path.abspath(os.path.join(...))`), comprueba que exista (`os.path.isfile`; `FileNotFoundError`) y abre con `os.startfile`. Un fallo del propio `os.startfile` propaga `OSError`. Sin SQLite, sin FFprobe/FFmpeg, sin subprocesos (`subprocess`/`Popen`) y sin acceso a la interfaz. |
| Detección del doble clic | `visor_videos.Tarjeta` | Señal de clase `doble_clic = Signal(str)` y sobrescritura de `mouseDoubleClickEvent` (llama a `super()` y emite `self.doble_clic.emit(self._nombre)`); **cualquier doble clic con el botón izquierdo sobre la tarjeta emite el nombre del video**. Solo UI: no valida rutas ni abre nada. |
| Apertura del video desde la interfaz | `visor_videos.VisorVideos._abrir_video` + `apertura_videos.abrir_video_con_aplicacion_predeterminada` | Conectado a `Tarjeta.doble_clic` en `_crear_tarjetas` y `_agregar_tarjetas`; invoca el servicio con `self.carpeta_seleccionada`; ante `ValueError`/`FileNotFoundError`/`OSError` muestra `MENSAJE_ERROR_ABRIR` ("No se pudo abrir el video") y nunca propaga excepciones. |
| Caché | — | **No existe** un módulo de caché; la BD cumple parcialmente ese rol para metadatos. |
| Configuración | `rutas.py` | Resolución de rutas del proyecto (raíz, BD, miniaturas, videos) centralizada e independiente del CWD. Aún no hay módulo de configuración completo. |
| Persistencia de marcadores | `escanear_videos.py` | Tabla `marcadores_video` (migración aditiva en `conectar_bd`); `listar_marcadores` / `guardar_marcador` / `eliminar_marcador` con validación previa y conexión propia por operación; coherencia con `videos.id` gestionada en la capa de servicio (sin cascade). |
| Marcadores asíncronos | `tareas_videos.TareaListarMarcadores` / `TareaGuardarMarcador` / `TareaEliminarMarcador` | Cargar, crear y eliminar marcadores en segundo plano; conexión abierta/cerrada en el hilo de trabajo; ejecutados por el gestor dedicado `gestor_marcadores` de la interfaz. |
| Reconciliación de marcadores en la interfaz | `visor_videos.VisorVideos` | La `Tarjeta` recibe `video_id` y no ejecuta SQLite; representación optimista en memoria, carga al expandir y cola serializada en `gestor_marcadores`; la carga se reconcilia como snapshot antiguo (conserva altas/bajas locales, IDs y deduplica por tolerancia temporal). |
| Persistencia de marcadores de varios videos | `escanear_videos.listar_marcadores_de` | Lee los marcadores persistidos de varios `video_id` (tuplas `(id, video_id, tiempo)`), agrupados en el orden recibido y ordenados cronológicamente dentro de cada video; validación previa y conexión propia por operación. La interfaz no consulta SQLite directamente. |
| Marcadores de varios videos asíncronos | `tareas_videos.TareaListarMarcadoresVarios` | Lectura en segundo plano de los marcadores de varios videos; ejecutada por el gestor dedicado `gestor_reproduccion` de la interfaz. |
| Reproducción de marcadores en VLC | `visor_videos.VisorVideos._reproducir_marcadores_en_vlc` + `playlist_vlc` | Acción de menú contextual (habilitada con selección); recolecta los videos seleccionados en **orden visible del catálogo**, lee sus marcadores, aplica el diálogo para videos sin marcadores (Omitir / Desde el inicio / Cancelar), omite archivos inexistentes con aviso y abre VLC una única vez con la playlist generada. |
| Ciclo de vida de playlists temporales | `playlist_vlc.limpiar_playlists_anteriores` | Antes de generar una nueva playlist elimina únicamente `visor_marcadores_*.m3u` del directorio temporal propio; bloqueos ignorados; sin borrar `.m3u` ajenos ni recorrer subdirectorios; no borra la playlist recién lanzada. |

## 5. Flujo de ejecución (apertura → tarjetas)

1. `python visor_videos.py` → `main()` crea `QApplication` y la `VisorVideos`.
2. `VisorVideos.__init__` crea la barra de búsqueda, el contador, el estado de carga ("Cargando catálogo…") y el `QScrollArea`. **No abre SQLite**: crea `GestorTareas(self)` y arranca `_iniciar_carga()`.
3. `_iniciar_carga()` construye `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)` y la ejecuta en un `QThread` mediante `gestor.iniciar()`.
4. En el hilo de trabajo, `TareaLecturaCatalogoPaginada._trabajo()` invoca `listar_videos_paginado`, que abre su propia conexión, ejecuta `SELECT ... ORDER BY nombre LIMIT ? OFFSET ?` y `SELECT COUNT(*) ...`, la cierra y devuelve `{"videos": [...], "total": n, "limite": n, "desplazamiento": n}`.
5. Al emitirse `tarea_resultado`, `_al_resultado` oculta el estado de carga, `_crear_tarjetas` crea una `Tarjeta` por video en la `QGridLayout` (una sola columna, una fila por video) y se aplica el filtro vigente.
6. Si la lectura falla, `_al_error` muestra "No se pudo cargar el catálogo" y la ventana permanece utilizable.
7. Cada tarjeta consulta `miniatura_principal(nombre)` sobre `miniaturas/`; si no encuentra imagen, muestra el recuadro "Sin miniatura".
8. El `QLineEdit` filtra en vivo (`filtrar`) **sobre las tarjetas ya cargadas** y el contador muestra "N videos".
9. Al cerrar la ventana, `closeEvent` llama `gestor.cerrar()` (timeout por defecto 5000 ms) para un apagado ordenado del hilo en curso.

La selección de carpeta es independiente de la carga del catálogo: el
botón "Seleccionar carpeta" abre `QFileDialog`, normaliza la ruta con
`os.path.abspath`, valida con `os.path.isdir` que exista y sea un
directorio, la muestra y la conserva en `carpeta_seleccionada`; al
cancelar se conserva la selección anterior y ante una ruta inválida se
rechaza con un mensaje visible sin cerrar la ventana. Seleccionar la
carpeta **no escanea su contenido**: no detecta archivos, no abre
SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas; la selección no
es persistente.

Escaneo manual y asíncrono de la carpeta elegida:

1. El usuario elige una carpeta válida y presiona el botón "Escanear
   carpeta" (`boton_escanear`), habilitado solo con carpeta válida y
   gestor inactivo.
2. `iniciar_escaneo()` revalida la carpeta con `os.path.isdir`, crea una
   `TareaEscaneo(carpeta)` y la inicia con el **mismo** `GestorTareas`
   de la ventana; marca `_escaneo_pendiente = True` y muestra
   "Escaneando carpeta…". Mientras el gestor está ocupado los botones de
   la fila quedan deshabilitados.
3. En el hilo de trabajo, `TareaEscaneo._trabajo()` devuelve la lista
   ordenada de archivos de video de la carpeta (misma función
   `escanear_videos`), sin tocar SQLite, FFprobe, FFmpeg ni miniaturas.
4. `_al_resultado` reenvía el resultado a `_al_resultado_escaneo`
   (enrutado por `_escaneo_pendiente`), que copia la lista en
   `videos_detectados`, limpia `_escaneo_pendiente`, **marca
   `_ffprobe_pendiente = True`** y muestra el conteo ("1 video
   detectado" / "N videos detectados"). No se crean tarjetas ni se
   recarga el catálogo.
5. Ante un error (carpeta inexistente, ruta-archivo), `_al_error_escaneo`
   limpia la cadena, muestra "No se pudo escanear la carpeta" y
   **conserva el último resultado exitoso** en `videos_detectados`; la
   cadena no se inicia.

Encadenamiento del pipeline escaneo → tamaños → FFprobe → miniaturas →
guardado (tareas sucesivas con el mismo gestor):

6. Al terminar el hilo del escaneo, `GestorTareas` vuelve a `inactivo` y
   emite `tarea_finalizada`. `_al_tarea_finalizada()` detecta
   `_tamanos_pendiente` activo y el gestor `inactivo`, y
   `_iniciar_tamanos()` crea `TareaTamanosArchivos(videos_detectados,
   tarea_escaneo.carpeta)` y la inicia con el mismo `GestorTareas`. En el
   hilo de trabajo, `TareaTamanosArchivos._trabajo()` invoca
   `obtener_tamanos_archivos`, que consulta `os.path.getsize` por archivo
   (un archivo inexistente o ilegible se registra como `None`) y devuelve
   el resumen `{"rutas", "resultados", "procesados", "con_tamano",
   "sin_tamano"}`. `_al_resultado_tamanos` (enrutado por
   `_tamanos_pendiente`) guarda el resultado en `resultado_tamanos`,
   limpia el flag y **marca `_ffprobe_pendiente = True`**. Ante un error,
   `_al_error_tamanos` limpia la cadena y muestra "No se pudo obtener el
   tamaño de los archivos".
7. Al terminar el hilo de los tamaños, `_al_tarea_finalizada()` detecta
   `_ffprobe_pendiente` activo y el gestor `inactivo`, y `_iniciar_ffprobe()`
   construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta,
   nombre)`) de los videos detectados e inicia `TareaFFprobe(rutas)` con
   el mismo `GestorTareas`. El paso siguiente no se lanza en el handler
   del resultado del escaneo: el gestor `Ocupado` rechazaría una segunda
   tarea.
8. En el hilo de trabajo, `TareaFFprobe._trabajo()` ejecuta
   `obtener_datos_ffprobe` por ruta (timeout 30 s) y devuelve el resumen
   con `resultados` (`ruta`, `datos`, `error` por archivo), `procesados`,
   `con_datos` y `con_error`. `_al_resultado_ffprobe` (enrutado por
   `_ffprobe_pendiente`) guarda el resultado en `resultado_ffprobe`,
   limpia el flag y **marca `_miniaturas_pendiente = True`**. Ante un
   error global de FFprobe, `_al_error_ffprobe` limpia la cadena y
    muestra "No se pudieron obtener los metadatos".
9. Al terminar FFprobe, `_al_tarea_finalizada()` detecta
   `_miniaturas_pendiente` activo y `_iniciar_miniaturas()` crea
   `TareaMiniaturas(videos_detectados, tarea_escaneo.carpeta)` y la
   inicia con el mismo `GestorTareas`. En el hilo de trabajo,
   `TareaMiniaturas._trabajo()` invoca `asegurar_miniaturas`, que por
   cada archivo existente asegura una miniatura (reutilizando una válida
   por `mtime` o generando una nueva con FFmpeg en la siguiente ranura
   libre, sin sobrescribir ni eliminar) y cuenta las existentes; devuelve
   el resumen `{"rutas", "resultados", "procesados", "con_miniatura",
   "sin_miniatura"}`. `_al_resultado_miniaturas` (enrutado por
   `_miniaturas_pendiente`) guarda el resultado en `resultado_miniaturas`,
   limpia el flag y **marca `_guardado_pendiente = True`**. Ante un error,
   `_al_error_miniaturas` limpia la cadena y muestra "No se pudieron
    generar las miniaturas".
10. Al terminar las miniaturas, `_al_tarea_finalizada()` detecta
    `_guardado_pendiente` activo y `_iniciar_guardado()` prepara los
    registros con `combinar_registros_con_ffprobe(videos_detectados,
    tarea_escaneo.carpeta, resultado_ffprobe)` (claves básicas
    `{nombre, ruta, extension, fecha_importacion}` con ruta absoluta +
    metadatos FFprobe `{duracion_segundos, ancho, alto, codec_video}`;
    `NULL` si el video no tiene `datos`), luego los combina con
    `combinar_registros_con_miniaturas(registros, resultado_miniaturas)`
    (clave `cantidad_miniaturas` por ruta normalizada; `None` si no hay
    coincidencia o el resultado es `None`) y con
    `combinar_registros_con_tamanos(registros, resultado_tamanos)`
    (clave `tamano_bytes` por ruta normalizada; `None` si no hay
    coincidencia o el tamaño es `None`), y persiste el resultado con
    `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo
    `GestorTareas`.
11. En el hilo de trabajo, `TareaGuardarVideos._trabajo()` invoca
    `guardar_videos`, que valida la colección, ejecuta el upsert
    transaccional (inserta o actualiza sin duplicar, **conservando los
    registros preexistentes** y sin eliminar ninguno) y hace un único
    `commit`; devuelve `{"guardados": n, "nombres": [...]}`.
12. `_al_resultado` reenvía el resultado a `_al_resultado_guardado`
    (enrutado por `_guardado_pendiente`), que limpia el flag, libera
    `resultado_tamanos`, `resultado_ffprobe` y `resultado_miniaturas`, guarda la cantidad en
    `registros_guardados`, habilita de nuevo el botón de escaneo y
    **marca `_sincronizacion_pendiente = True`**. No crea tarjetas ni
    recarga el catálogo en este punto.
13. Ante un error de escritura, `_al_error_guardado` limpia
    `_guardado_pendiente`, muestra "No se pudieron guardar los videos" y
    el gestor queda `inactivo`: la interfaz es recuperable y un nuevo
    escaneo es posible. Los registros preexistentes permanecen intactos.
14. El pipeline **no constituye la sincronización completa**: ejecuta
    FFprobe para completar duración, resolución y codec (con `NULL` ante
    vacíos, incompletos o fallos individuales), obtiene el tamaño de
    archivo (`tamano_bytes`; `NULL` si el archivo no existe o no es
    legible) y asegura una miniatura
    básica por video (reutilizando o generando; los vacíos no generan
    archivo), pero no elimina registros ausentes ni recorre subcarpetas.

Sincronización y recarga del catálogo (pasos 15-19, con el mismo gestor):

15. Al terminar el guardado, `_al_tarea_finalizada()` detecta
    `_sincronizacion_pendiente` activo y el gestor `inactivo`, y
    `_iniciar_sincronizacion()` revalida la carpeta (`os.path.isdir`) e
    inicia `TareaSincronizacionCatalogo(carpeta, ruta_db)` con el **mismo**
    `GestorTareas`, mostrando "Sincronizando catálogo…". La sincronización
    **solo se lanza tras un guardado exitoso**.
16. En el hilo de trabajo, `TareaSincronizacionCatalogo._trabajo()`
    encadena `detectar_diferencias` → `preparar_plan_sincronizacion` →
    `aplicar_incorporaciones` → `eliminar_candidatos` y devuelve
    `{"diferencias", "plan", "incorporaciones", "eliminaciones",
    "resumen"}`. `_al_resultado_sincronizacion` limpia el flag, libera la
    tarea, **conserva el resultado en `resultado_sincronizacion`**, muestra
    el resumen ("Sincronización completa: N incorporados, M eliminados, K
    candidatos restantes") y **marca `_recarga_catalogo_pendiente = True`**.
17. Al terminar la sincronización, `_al_tarea_finalizada()` detecta
    `_recarga_catalogo_pendiente` activo y `_iniciar_recarga_catalogo()`
    crea la **misma** tarea de lectura (`_crear_tarea_lectura()` →
    `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None,
    ruta_db)`) y la inicia con el mismo `GestorTareas`. La recarga **solo
    se lanza tras una sincronización exitosa**; es una fase de **solo
    lectura** de la primera página y **no ejecuta FFprobe, FFmpeg ni
    miniaturas**.
18. `_al_resultado` reenvía el resultado a `_al_resultado_recarga`
    (enrutado por `_recarga_catalogo_pendiente`): limpia el flag, libera
    la tarea y `_reemplazar_tarjetas(filas)` **quita las tarjetas viejas de
    la grilla** (`removeWidget` + `deleteLater` para liberar los widgets
    Qt), **vacía `self.tarjetas`**, crea las tarjetas nuevas con la primera
    página en la **misma `QGridLayout` y el mismo `QScrollArea` reutilizados**,
    reaplica el filtro vigente y actualiza el contador. No quedan tarjetas
    ocultas obsoletas; `resultado_sincronizacion` se **conserva intacto**.
19. Si la recarga falla, `_al_error_recarga` limpia la cadena, **conserva
    las tarjetas viejas**, muestra `MENSAJE_ERROR_RECARGA` ("No se pudo
    actualizar el catálogo"), el gestor queda `inactivo`, el botón de
    escaneo se rehabilita y un nuevo escaneo es posible. La recarga
    fallida **no revierte** la sincronización ya confirmada en SQLite.

La carga inicial **y la recarga tras la sincronización** cargan
automáticamente la **primera página** del catálogo (primeros
`TAMANIO_PAGINA_INICIAL` registros). Las **páginas posteriores pueden
cargarse manualmente** con el botón "Cargar más" (paso 20); **todavía no
existe** paginación automática ni scroll infinito, y la búsqueda en SQL
desde la interfaz queda para etapas futuras.

20. Si el usuario pulsa "Cargar más" (`cargar_mas()`): calcula el
    **desplazamiento con la cantidad de tarjetas ya cargadas**
    (`len(self.tarjetas)`), crea `_crear_tarea_lectura(len(self.tarjetas))`
    y ejecuta la **misma** `TareaLecturaCatalogoPaginada` con el **mismo**
    `GestorTareas`. `_al_resultado_pagina` **agrega** las filas nuevas con
    `_agregar_tarjetas` **sin reemplazar las existentes** y **descartando
    los nombres ya cargados** (deduplicación por `nombre`); el botón se
    **deshabilita** cuando ya se alcanzó `_total_catalogo`
    (`len(self.tarjetas) >= self._total_catalogo`).

Apertura del video por doble clic (interfaz → servicio):

1. El usuario hace **doble clic con el botón izquierdo** sobre una
   tarjeta. Qt entrega el evento a `Tarjeta.mouseDoubleClickEvent`, que
   llama a `super().mouseDoubleClickEvent(event)` y **emite la señal
   `doble_clic`** con `self._nombre` (el nombre del video).
2. `_abrir_video(nombre)` (conectado a `doble_clic` en `_crear_tarjetas`
   y `_agregar_tarjetas`) llama a
   `abrir_video_con_aplicacion_predeterminada(nombre,
   self.carpeta_seleccionada)` de `apertura_videos.py`.
3. El servicio valida `nombre`/`carpeta` (texto no vacío tras `strip()`;
   si no → `ValueError`), construye la **ruta absoluta**
   (`os.path.abspath(os.path.join(carpeta, nombre))`), comprueba con
   `os.path.isfile` que el archivo exista (si no → `FileNotFoundError`) y
   lo abre con `os.startfile(ruta)`, devolviendo la ruta. Un fallo del
   propio `os.startfile` propaga `OSError`.
4. Si el servicio **falla**, `_abrir_video` muestra `MENSAJE_ERROR_ABRIR`
   ("No se pudo abrir el video") en la etiqueta de estado; en éxito la
   deja en blanco. En ningún caso la excepción escapa al gestor de
   eventos. La apertura **no toca** SQLite, FFprobe, FFmpeg ni el
   catálogo: el video se abre con la aplicación predeterminada de
   Windows.

Flujo de datos (respaldo/escritura) — ejecución previa del CLI:

1. `python escanear_videos.py` → `main()`.
2. `conectar_bd()` crea/migra la tabla `videos`.
3. `sincronizar_bd(conn, "videos_prueba")`:
   - `escanear_videos("videos_prueba")` lista archivos válidos;
   - inserta los que no existen (`INSERT OR IGNORE`);
   - para cada uno: `asegurar_miniatura` (reutiliza o genera) + `obtener_datos_ffprobe` (si no está vacío) + `contar_miniaturas` → `UPDATE`;
   - elimina de la BD los que ya no están en disco.
4. `commit()` y cierre.

Flujo de ejecución asíncrona (infraestructura de tareas):

1. `gestor.iniciar(tarea)` valida la tarea (`TareaBase`, sin padre, no ejecutada), crea un `QThread` propio, la mueve a él y lo arranca.
2. El hilo ejecuta `TareaBase.ejecutar()`: emite `inicio`, corre `_trabajo()` y emite `resultado(valor)`; si `_trabajo()` lanza una excepción, emite `error(f"{Tipo}: {msg}")`. En ambos casos emite `finalizada`.
3. `GestorTareas` replica las señales al hilo principal (`tarea_iniciada`, `tarea_resultado`, `tarea_error`) y, al terminar el hilo (`hilo.finished`), vuelve a `inactivo` y libera el hilo. `cerrar(timeout_ms)` permite detener el hilo en curso.

## 6. Flujo de generación de miniaturas

**Estado actual: generación automática implementada.** Durante el escaneo, para cada video no vacío se asegura una miniatura. El flujo por video es:

1. `ffmpeg_disponible()` — verifica que FFmpeg esté disponible. Si no lo está, la generación se omite sin intentar ejecutar subprocesos.
2. `miniatura_reutilizable()` — busca la primera miniatura existente del video que sea válida según `miniatura_vigente()` (`mtime` de la miniatura ≥ `mtime` del video). Si existe, se **reutiliza** y no se genera nada.
3. Si ninguna es válida, `generar_miniatura()` extrae un fotograma (`-ss <tiempo> -frames:v 1 -q:v 3`) y lo escribe en la **siguiente ranura libre** (`siguiente_indice_libre()` → `miniaturas/<prefijo>_NN.jpg`). **Nunca se sobrescribe un archivo existente ni se elimina ninguno.**
4. `contar_miniaturas()` cuenta los archivos del video en `miniaturas/` y `actualizar_datos()` persiste `cantidad_miniaturas` en la BD.

**Integración en el pipeline:** el flujo del catálogo también se ejecuta
desde la interfaz como **paso asíncrono** del encadenamiento escaneo →
FFprobe → miniaturas → guardado: `TareaMiniaturas` invoca
`asegurar_miniaturas(videos, carpeta)`, que por cada archivo existente
aplica los pasos 1-3 y cuenta con `contar_miniaturas`; el resumen se
combina con los registros (`combinar_registros_con_miniaturas`) y la
cantidad se persiste junto con los metadatos FFprobe en el guardado. El
CLI (`sincronizar_bd`) conserva su propio flujo síncrono con
`asegurar_miniatura` + `actualizar_datos`.

Durante un escaneo se genera **como máximo una miniatura nueva por video**, y únicamente cuando no existe ninguna miniatura considerada vigente (criterio `mtime`). Pueden coexistir varias miniaturas del mismo video en distintas ranuras `_NN`. La convención `<prefijo>_NN.jpg` permite convivir con miniaturas preexistentes sin perderlas. Los videos vacíos (0 bytes) no generan miniatura.

## 7. Puntos de extensión previstos

1. **Generación de miniaturas con FFmpeg** — extracción de fotogramas mediante `asegurar_miniatura`/`generar_miniatura` con reutilización por `mtime` y preservación de archivos existentes.
2. **Ejecución asíncrona** — infraestructura de tareas en segundo plano (`TareaBase` + `GestorTareas` con `QThread` por ejecución) para escaneo, FFprobe, miniaturas, lectura y escritura del catálogo. Incluye pipeline encadenado con el mismo gestor y generación progresiva de previews con gestor independiente.
3. **Módulo de configuración** — centralizar rutas, extensiones, tamaños de tarjeta y número de columnas.
4. **Caché de miniaturas/metadatos** — formalizar la base de datos como caché de metadatos y evitar re-escaneos.
5. **Lectura/vistas del catálogo** — sobre `listar_videos()` y `listar_videos_paginado()`, agregar orden, agrupación y filtros adicionales. La lectura paginada con búsqueda en SQL y la carga manual de páginas adicionales están implementadas; la paginación automática y la búsqueda en SQL desde la interfaz quedan para etapas futuras.
6. **Resolución de rutas** — `rutas.py` centraliza la resolución de rutas del proyecto de forma independiente del directorio de trabajo, con soporte para modo PyInstaller (`sys.frozen`).

## 8. Problemas detectados

| # | Severidad | Problema |
| --- | --- | --- |
| 1 | Media | La interfaz (`visor_videos.py`) accedía a SQLite directamente y duplicaba el nombre de BD (`"biblioteca.db"`). **Corregido**. |
| 2 | Media | Rutas relativas (`miniaturas/`, `videos_prueba/`, `biblioteca.db`) dependían del directorio de trabajo; la app fallaba si se lanzaba desde otra ubicación. **Resuelto** (ver `rutas.py`). |
| 3 | Media | No existía generación de miniaturas; solo conteo. **Resuelto** (ver §6). |
| 4 | Media | FFprobe se ejecutaba en el hilo principal con timeout de 30 s por video; el escaneo bloquea. **Resuelto**: FFprobe se movió a segundo plano con `TareaFFprobe`, la carga inicial del catálogo se integró con las tareas asíncronas (`visor_videos.py` + `TareaLecturaCatalogoPaginada`) y la generación de miniaturas con FFmpeg se ejecuta dentro de `TareaMiniaturas` (segundo plano, nunca en el hilo principal). La sincronización completa del catálogo ya está integrada en la interfaz y, tras una sincronización exitosa, el catálogo se recarga en segundo plano y las tarjetas se reconstruyen. |
| 5 | Baja | `contar_miniaturas`/`miniatura_principal` usan coincidencia por prefijo (`startswith`); un video `video_real.mp4` podría matchear miniaturas de un hipotético `video_realista.mp4`. Pendiente. |
| 6 | Baja | Los videos vacíos (0 bytes) quedan sin metadatos; comportamiento correcto pero debe documentarse para el usuario. Pendiente. |
| 7 | Informativa | `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` son artefactos de prueba ajenos al visor. Se preservaron por política del proyecto. |
| 8 | Media | Crecimiento acumulativo de miniaturas: la regeneración escribe una ranura nueva (`_NN`) en lugar de sobrescribir; si el video cambia varias veces se acumulan archivos y `cantidad_miniaturas` crece. Pendiente. |
| 9 | Baja | La interfaz muestra la primera miniatura por orden alfabético (`_01`), incluso cuando una versión más nueva (`_02`) es la vigente. Pendiente. |
| 10 | Media | El criterio de reutilización usa únicamente `mtime` (sin hash ni validación de integridad); no detecta cambios de contenido que conserven la fecha. Pendiente (mejora diferida). |
| 11 | Media | Falta una limpieza controlada de versiones antiguas de miniaturas; por regla, los archivos nunca se eliminan automáticamente, por lo que requiere autorización expresa. Pendiente. |
| 12 | Media | FFmpeg escribe directamente en la ruta definitiva de la miniatura; si falla después de comenzar la escritura puede quedar un archivo parcial o corrupto. Actualmente ese archivo no se elimina ni se valida, y por existencia y `mtime` podría ser contado o considerado vigente. Pendiente. |
| 13 | Baja | **Restauración de rutas con nombres cortos 8.3 de Windows** (p. ej. `MARCOS~1`): el árbol carga los nombres largos (p. ej. `Marcos`), por lo que `revelar_ruta` no empareja un camino persistido con segmentos 8.3 y cae en el comportamiento tolerante (aplicación inicia sin carpeta seleccionada, sin inconsistencias). No afecta el uso normal ni el alcance de la Etapa 2.5; **deuda técnica** para una futura etapa de robustez del Centro de Navegación. |
| 14 | Baja | **Estado de "escaneada" por sesión** (Etapa 2.9): el indicador de carpetas escaneadas vive en memoria (`carpetas_escaneadas` del visor) y se pierde al reiniciar; no se persiste ni se deriva del catálogo (requeriría cambios de esquema o en módulos restringidos). La API (`EstadoNodo` + `_icono_para`) ya está preparada; documentada como **deuda técnica** para una etapa específica de persistencia del estado. |
| 15 | Informativa | **Marcadores huérfanos por diseño** (B4.2): si el registro del video desaparece (eliminación del catálogo, archivo fuera de disco, etc.) los marcadores de `marcadores_video` **no** se eliminan automáticamente (sin `ON DELETE CASCADE`); pueden quedar huérfanos, y no existe aún reasociación de movidos/renombrados ni por nombre/ruta. Deliberado para evitar pérdida automática de datos del usuario; la **reasociación futura** de marcadores huérfanos está prevista (ver `ROADMAP.md`, sección "Beta 4"). |
| 16 | Informativa | **Fingerprint sin hash de contenido** (B4.3.1): la versión de la caché densa de exploración se deriva de ruta + tamaño + `mtime_ns` + duración (SHA-256 reducido a 16 hex); dos archivos con exactamente esos mismos metadatos no son distinguibles y compartirían caché aunque el contenido difiera. **Limitación aceptada** para B4.3.1; no se intenta resolver (un hash de contenido encarecería el cálculo por video). |
| 17 | Informativa | **Densidad Auto provisional y superset de caché (B4.3.2/B4.3.3):** la generación es **individual y secuencial (un FFmpeg por objetivo, sin batch)**; los parámetros automáticos (`PASO_SEGUNDOS_DENSIDAD = 30`, `MINIMO = 15`, `MAXIMO = 200`) quedaron centralizados en `exploracion_cache.py` como **provisionales**, NO congelados y sin exponer en la interfaz. El control manual (B4.3.3) expone `Auto | 15 | 30 | 60 | 120 | 200` como total objetivo por tarjeta/sesión (**sin SQLite ni persistencia en `configuracion.json`**). La caché en disco puede contener un **superset** (p. ej. 120) respecto de la densidad actual (p. ej. 30): la tarea construye explícitamente `tiempos_objetivo(duración, cantidad_actual)` y solo emite/decodifica ese subconjunto; los extras permanecen en disco sin borrar ni regenerar. La notebook objetivo (i7-7500U / 16 GB / 940MX) validó la Etapa 1 y posteriormente **B4.3 en conjunto** con un video real de ~56 min. |

## 9. Dirección arquitectónica futura

La interfaz evoluciona hacia un sistema de paneles independientes basado en
**QSplitter** (ya implementado). Existe un único splitter entre el panel
izquierdo (árbol de navegación) y el panel derecho (catálogo). El árbol del
panel izquierdo se implementa por etapas (bloque de trabajo 2): la **Etapa
2.9** ya incorpora **indicadores visuales de carpetas escaneadas** (estado por
nodo con `EstadoNodo`, API preparada para estados futuros como PARCIAL o
CAMBIOS_PENDIENTES); las etapas siguientes podrán agregar el filtrado del
catálogo desde el árbol y la persistencia del estado de escaneado. La
arquitectura deberá permitir incorporar posteriormente nuevos paneles
(propiedades, favoritos, etiquetas, IA) sin rediseñar la interfaz. Esta
dirección está documentada en detalle en `VISION_PRODUCTO.md` y `ROADMAP.md`.

**Estado de la Beta 3:** la Beta 3 quedó **implementada, funcionalmente cerrada
y congelada sobre el código definitivo** (bloques A–E del Bloque de trabajo 3,
más el Bloque de trabajo 4 — catálogo por selección de carpetas — y las
correcciones finales incluidas). El desarrollo continuó en el **ciclo Beta 4**
(rama `beta4`): las etapas **B4.1 — Exploración temporal interactiva y
marcadores visuales**, **B4.2 — Persistencia de marcadores temporales por
video**, **B4.3.1 — Motor de caché temporal versionada y reanudable**,
**B4.3.2 — Cobertura rápida asíncrona integrada con la UI**, **B4.3.2 — Etapa
2: Densidad secundaria adaptativa**, **B4.3.3 — Ajustes de interacción y
densidad manual**, **B4.4 — Reproducción de marcadores en VLC** y **B4.5 —
Rendimiento de carga inicial** quedaron **completadas y aprobadas**, en bloques
pequeños y
acumulativos y **sin introducir cambios arquitectónicos** que todavía no
existieran; cada etapa extiende la arquitectura únicamente en la medida que su
propio alcance aprobado lo requiere (B4.2 incorporó la tabla `marcadores_video`
y un gestor dedicado `gestor_marcadores` en la interfaz, ambos aditivos; B4.3.1
incorporó `exploracion_cache.py` y `ruta_carpeta_exploracion()` en `rutas.py`,
también aditivos, **sin tocar SQLite** — `videos`, `marcadores_video` y
`biblioteca.db` intactos; B4.3.2 incorporó la tarea `TareaExploracionDensa` y el
consumo de la caché densa en la superficie temporal, aditivo, con decodificación
`QImage` en el worker, conversión `QPixmap` en la GUI y fallback a las previews
normales; la **Etapa 2** extendió `_trabajo()` con la **fase secundaria** de
densidad adaptativa, individual y secuencial, sin batch; y **B4.3.3** agregó la
**prioridad visual dinámica** (z-order de la preview sobre las miniaturas fijas
de marcadores) y la **densidad manual** (`Auto | 15 | 30 | 60 | 120 | 200` por
tarjeta/sesión con conjunto permitido explícito `tiempos_objetivo` y soporte de
caché superset), aditivos y sin tocar SQLite ni configuración).
**B4.4** agregó la integración mínima de **reproducción de marcadores en VLC**, aditiva y sin
cambios arquitectónicos: módulo de servicio `playlist_vlc.py` (localización de `vlc.exe`,
generación del `.m3u` UTF-8 con `#EXTVLCOPT:start-time` y limpieza propia de playlists
temporales anteriores), `listar_marcadores_de`/`TareaListarMarcadoresVarios` para leer
marcadores de varios videos, y la acción de menú contextual "Reproducir marcadores en VLC" con
diálogo Omitir/Desde el inicio/Cancelar y omisión de archivos inexistentes. Sin HTTP, sin
libVLC, sin loop automático y sin tocar SQLite salvo lecturas de marcadores.
**Reproducción de marcadores en VLC — completada** (Etapa 1: validación física de la
estrategia playlist con VLC 3.0.23; Etapa 2: integración mínima). **B4.4 queda completada; no
se declara la Beta 4 completa todavía.**
**B4.5 — Rendimiento de carga inicial.** **Etapa 1 (diagnóstico)**: con un dataset temporal de
121 videos se midió el pipeline normal de catálogo/miniaturas en la PC de desarrollo — FFprobe
de metadata ~4.5 s (121 procesos), miniaturas ~12.3 s, previews ~38.6 s (el cuello dominante,
~70 %), reescaneo caliente con FFprobe redundante (~4.6 s de ~4.9 s) — sin cambios de
producción. **Etapa 2 (eliminación de FFprobe redundante)**: `generar_miniatura`/`generar_preview`
aceptan `duracion_segundos=None` (válida → sin FFprobe interno, mismo cálculo temporal y FFmpeg;
inválida → fallback FFprobe anterior); `asegurar_miniaturas`/`generar_previews_faltantes` y
`TareaMiniaturas`/`TareaPreviewsProgresivas` propagan duraciones; la interfaz las toma de
`TareaFFprobe` (miniaturas) y de la tarjeta (previews). En frío: **484 FFprobe internos → 0**,
mismos 484 FFmpeg; total backend ~55.6 s → ~37.1 s (medición de PC de desarrollo). Sin cambios
de cantidad, posiciones, calidad, progresividad, lotes, caché, paralelismo ni FFmpeg. Pendiente
técnico sin corregir: las previews existentes se consideran reutilizables por existencia del
archivo. **Etapa 3 (reutilización de metadata en reescaneos sin cambios)**: criterio barato
`ruta normalizada + tamano_bytes + mtime_ns` (sin hash de contenido) mediante `_metadata_reutilizable`;
migración aditiva `videos.mtime_ns INTEGER NULL`; `obtener_tamanos_archivos` con un `os.stat` por
archivo; `listar_registros_por_nombres` (consulta por lote por `nombre`, una SELECT); `TareaFFprobe`
clasifica y solo probea los videos nuevos/cambiados/sin `mtime_ns`/con metadata inválida;
`guardar_videos` persiste `mtime_ns`. Reescaneo caliente de 121 videos: **121 FFprobe → 0**,
backend ~4.9 s → ~0.1–0.5 s (referencia de PC de desarrollo); verificación empírica con 10
archivos físicos independientes: **10 → 0 → 1 → 0**. `video_id`/marcadores intactos; un cambio de
ruta fuerza FFprobe conservando la identidad por nombre/upsert. Riesgo residual aceptado
(mismo ruta+tamaño+`mtime_ns` con contenido distinto); sin hash. **B4.5 queda completada en sus
Etapas 1-3; no se declara la Beta 4 completa todavía.**
**B4.6 — Rendimiento de carga visual.** **Etapa 1 (diagnóstico)**: con 100 tarjetas/300 previews
cacheadas se descompuso el costo de la carga visual — construcción de widgets ~0.42 s,
`miniatura_principal` ~0.05 s, **`_crear_tarjetas` cargaba y escalaba las 300 previews de golpe
(0.74 s caliente / ~3.5 s frío)**, bloqueo síncrono total 1.4–4.4 s, RAM ~+690 MB — sin cambios de
producción. **Etapa 2 (carga diferida de previews cacheadas)**: `_crear_tarjetas`/`_agregar_tarjetas`/
`_reemplazar_tarjetas` ya no cargan previews cacheadas; las tarjetas parten con textos + miniatura
principal + placeholders y las previews se incorporan **progresivamente** por la tubería existente
(`_encolar_previews` → `TareaPreviewsProgresivas` → `generar_previews_faltantes` → `_aplicar_previews`).
`Tarjeta._previews_completas` (interno, no persistido) decide la cola; `_aplicar_previews` ignora
resultados tardíos de otra carpeta (A→B); `_reconstruir_previews_exploracion` cae a las previews de
disco si las etiquetas aún no las tienen (ajuste de integración del diferido; no modifica B4.3).
Con caché completa **0 FFmpeg**; con faltantes la generación normal. Medición: `_crear_tarjetas(100)`
**0.69–0.85 s** (antes 1.4–4.4 s), tarjetas visibles ~0.72 s, primera preview ~1.0 s, **300 previews
~2.1 s**, máximo bloqueo continuo **~0.7 s**, lotes ~20–30 ms. **La interfaz queda utilizable antes
de terminar las previews.** Pendientes separados: RAM/retención de pixmaps, `_construir_exploracion`
en colapsadas, reconciliación de reemplazo y `os.listdir` de `miniatura_principal`. **B4.6 quedó
completada en sus Etapas 1-2; no se declara la Beta 4 completa todavía.**

**Cierre de Beta 4 (2026-08-10):** la **Beta 4 quedó CERRADA y aprobada**, build final
`Beta 4 — B4.12` (commit técnico `198cdf533986b88c6e25dc0087722cf2b86e5f99`, instalador
`VisorVideos_Beta4_Setup.exe`, SHA-256 `730B4DAB1CD2F1F5CFDD184D2DC6FE80CF0481B8754080F0FF10CF991F89431F`),
validada en la notebook (B4.11: validación manual amplia; B4.12: validación final corta) y con la
suite integral posterior a las correcciones en **87 suites / 1570/1570 OK / 0 FAIL funcional**.
**Beta 5 CERRADA internamente (2026-08-15, rama `beta5`):** commit técnico principal
`969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
`VisorVideos_Beta5_ValidacionFinal_Setup.exe`; identidad **`Beta 5 — B5.0`**. Los cuatro bloques
iniciales (A: entrada temporal a VLC; B: segmentos A–B; C: reproducción simple y en bucle; D:
secuencia automática) y el plan B5.1–B5.9 quedaron **implementados**, junto con los pulidos
finales de interacción (creación por drag, edición de extremos A/B, scroll horizontal local de
previews, mejoras de visibilidad de segmentos y feedback visual de edición). Sin distribución
pública, sin merge a `main`, sin GitHub Release. Ver la sección "Modelo de segmentos" más abajo.

**Decisión arquitectónica registrada en B5.0 — MARCADOR ≠ SEGMENTO (dirección, NO implementada):**
el marcador ("instante interesante") y el segmento ("intervalo interesante", `video_id` + inicio
`A` + fin `B`, con `A < B`) son **entidades independientes**; no se convierten marcadores en
puntos de inicio/fin. Modelo previsto para B5.1 (sin CASCADE, misma política de orfandad que los
marcadores, sin hashes, sin detección de renombrados, migración aditiva e idempotente):
tabla independiente `segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT
NULL, inicio REAL NOT NULL, fin REAL NOT NULL)` e índice `idx_segmentos_video_video_id_inicio
(video_id, inicio)`, con validaciones `video_id > 0`, `inicio >= 0`, `fin > inicio`. Se describe
como **dirección aprobada conceptualmente**, no como esquema existente (no existe ninguna
implementación todavía).

**Evidencia técnica VLC de B5.0 (probada en VLC 3.0.23, video real de 12 s):** `start-time` y
`stop-time` funcionan por CLI y dentro de M3U (`#EXTVLCOPT:start-time`/`#EXTVLCOPT:stop-time`), con
valores decimales; el **bucle** se logra con una playlist de una entrada (`start-time` + `stop-time`)
más `--loop` (no usa el A–B interactivo nativo); la **secuencia automática** se logra con una
playlist de varias entradas del mismo archivo con `start-time` y `stop-time` (VLC salta solo al
llegar a cada `stop-time`). Pendiente de validación en la notebook objetivo y de la precisión
frame-exacta de los límites.

**Criterio de higiene de procesos VLC para pruebas (B5.0):** cada VLC lanzado por una prueba debe
conservar su **PID/handle** y la prueba debe cerrar **exclusivamente procesos propios** (prohibido
matar globalmente `vlc.exe`); cleanup en `finally`, cierre normal primero y `terminate`/`kill` solo
como fallback; no cerrar instancias VLC preexistentes del usuario. La investigación B5.0 detectó y
corrigió un **residual** producido por una prueba `--loop` (proceso huérfano); los scripts
temporales de `%TEMP%` no se incorporan al repositorio.

**Observación arquitectónica (Etapa B3.1):** el instante que se muestra sobre
cada preview se deriva de `(duración, índice)` con `calcular_tiempo_preview`,
como se acordó para la Beta 3. Para la futura mejora "Apertura del video desde
una preview" (Bloque E), el instante deberá provenir del **instante real
utilizado al generar el fotograma**, no de un recálculo; no se implementa en
esta etapa, únicamente queda registrado para esa futura implementación.
| 13 | Baja | El pipeline limitado escribía registros **básicos** (nombre, ruta absoluta, extensión, fecha de importación) sin ejecutar FFprobe; los videos quedaban sin duración, resolución ni codec. **Resuelto**: FFprobe se integró en el pipeline (`TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaGuardarVideos`) y los registros se guardan con los metadatos disponibles (`NULL` ante vacíos, incompletos o fallos individuales). |
