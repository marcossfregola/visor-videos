# Documento t├®cnico ÔÇö Visor de Videos

> **Identidad vigente:** `Beta 7 - B7.13` ÔÇö Beta 7 "Organizaci├│n y operaciones de archivos" **cerrada y publicada** en B7.13 (B7.0ÔÇôB7.13 completas y auditadas; **commit oficial de cierre funcional** `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` `B7 Cerrar Beta 7 B7.13`; **tag anotado `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3`**; **rama `beta7` publicada en `origin/beta7` y puede contener reconciliaciones documentales posteriores al tag**; **repositorio GitHub actualmente PUBLIC**; **GitHub Release `v7.0-beta` prerelease publicada** sin instalador p├║blico Beta 7; **validaci├│n espec├¡fica del instalador Beta 7 permanece PENDIENTE**). Capacidades incorporadas en B7: **organizaci├│n de archivos** (renombrado individual `TareaRenombrarVideo`, masivo `TareaRenombrarMasivo` con motor `nombres.py`, mover/copiar/eliminar por lote `TareaLoteOperaciones`/`TareaMoverVideo`/`TareaCopiarVideo`/`TareaEliminarVideo`, crear carpetas `TareaCrearCarpeta`) y **modo Organizaci├│n/Explorer** (panel Destino con `PanelOrganizacion`, navegaci├│n destino `rutas.listar_subcarpetas`/`TareaListarSubcarpetasDestino`, doble panel `QSplitter` vertical, objetivo estable ra├¡z/subcarpeta `resolver_destino_drop`, drag & drop interno `QDrag` `Qt.MoveAction` + MIME `application/x-visor-videos-ids-b713a` con prevalidaci├│n at├│mica fuera de UI, actualizaci├│n cat├ílogo v├¡a recarga paginada B7.8 sin rescan global, preservaci├│n de filtros/orden/selecci├│n/viewport).

---

## 1. ├ürbol de directorios

```
prueba/
Ôö£ÔöÇÔöÇ biblioteca.db          Base de datos SQLite del cat├ílogo
Ôö£ÔöÇÔöÇ configuracion.json     Configuraci├│n local del usuario (├║ltima carpeta seleccionada; generada por la app, gitignored)
Ôö£ÔöÇÔöÇ datos.txt              Salida del script de prueba main.py (ajeno al visor)
Ôö£ÔöÇÔöÇ main.py                Script de prueba de operaciones (ajeno al visor)
Ôö£ÔöÇÔöÇ operaciones.py         L├│gica pura de operaciones sobre archivos (copiar B3.14, pegar B3.15, eliminar B3.16)
Ôö£ÔöÇÔöÇ seleccion_carpetas.py  Conjunto de carpetas seleccionadas por ruta (Selecci├│n personalizada, Bloque 4)
Ôö£ÔöÇÔöÇ instalador.iss         Script oficial Inno Setup 6.7.3 del instalador (instalaci├│n por usuario; ver `EMPACADO.md`)
Ôö£ÔöÇÔöÇ EMPACADO.md            Procedimiento oficial de empaquetado (PyInstaller + Inno Setup, reproducible)
Ôö£ÔöÇÔöÇ prueba_agente.py       Artifacto de prueba (ajeno al visor)
Ôö£ÔöÇÔöÇ escanear_videos.py     CLI / backend: escaneo + SQLite + FFprobe
Ôö£ÔöÇÔöÇ rutas.py               Resoluci├│n centralizada de rutas del proyecto (independiente del CWD); incluye `ruta_carpeta_exploracion()` (`miniaturas/exploracion`, B4.3.1) y `ruta_video_existente()` (resoluci├│n/validaci├│n de existencia de la ruta de video delegada por la UI, B4.12)
Ôö£ÔöÇÔöÇ tareas.py              Infraestructura reutilizable de trabajos en segundo plano (QThread)
Ôö£ÔöÇÔöÇ tareas_videos.py       Tareas de video as├¡ncronas (TareaFFprobe, TareaEscaneo, TareaTamanosArchivos, TareaLecturaCatalogo, TareaLecturaCatalogoPaginada, TareaGuardarVideo, TareaGuardarVideos, TareaMiniaturas, TareaPreviewsProgresivas, TareaSincronizacionCatalogo, y desde B4.2 TareaListarMarcadores, TareaGuardarMarcador, TareaEliminarMarcador; desde B4.3.2 TareaExploracionDensa ÔÇö cobertura densa en dos fases: 15 prioritarios + densidad secundaria adaptativa; desde B4.3.3 con `objetivo_manual` y conjunto permitido expl├¡cito; desde B4.4 TareaListarMarcadoresVarios ÔÇö lectura as├¡ncrona de marcadores de varios videos; desde B4.5 TareaMiniaturas/TareaPreviewsProgresivas aceptan `duraciones` (evitan FFprobe interno cuando la duraci├│n ya es conocida) y `TareaFFprobe` acepta `nombres`/`stats`/`ruta_db` para reutilizar metadata de videos sin cambios (B4.5 Etapa 3))
Ôö£ÔöÇÔöÇ prueba_tareas.py       Pruebas automatizadas de la infraestructura de trabajos
Ôö£ÔöÇÔöÇ prueba_ffprobe.py      Pruebas automatizadas de TareaFFprobe
Ôö£ÔöÇÔöÇ prueba_escaneo.py      Pruebas automatizadas de TareaEscaneo
Ôö£ÔöÇÔöÇ prueba_lectura.py      Pruebas automatizadas de TareaLecturaCatalogo
Ôö£ÔöÇÔöÇ prueba_lectura_paginada.py  Pruebas automatizadas de TareaLecturaCatalogoPaginada
Ôö£ÔöÇÔöÇ prueba_interfaz_asincrona.py  Pruebas automatizadas de la integraci├│n as├¡ncrona de la interfaz (29)
Ôö£ÔöÇÔöÇ prueba_seleccion_carpeta.py  Pruebas automatizadas de la selecci├│n de carpeta en la interfaz (26)
Ôö£ÔöÇÔöÇ prueba_guardar.py      Pruebas automatizadas de TareaGuardarVideo
Ôö£ÔöÇÔöÇ prueba_guardar_videos.py  Pruebas automatizadas de TareaGuardarVideos
Ôö£ÔöÇÔöÇ prueba_escaneo_interfaz.py  Pruebas automatizadas del escaneo as├¡ncrono desde la interfaz (36)
Ôö£ÔöÇÔöÇ prueba_escaneo_guardado.py  Pruebas automatizadas del encadenamiento escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ guardado (24)
Ôö£ÔöÇÔöÇ prueba_detectar.py      Pruebas automatizadas de la detecci├│n de diferencias disco Ôåö BD (15)
Ôö£ÔöÇÔöÇ prueba_plan_sincronizacion.py  Pruebas automatizadas de la preparaci├│n del plan de sincronizaci├│n (12)
Ôö£ÔöÇÔöÇ prueba_aplicar_incorporaciones.py  Pruebas automatizadas de la aplicaci├│n de incorporaciones del plan de sincronizaci├│n (15)
Ôö£ÔöÇÔöÇ prueba_eliminar_candidatos.py  Pruebas automatizadas de la eliminaci├│n controlada de candidatos del plan de sincronizaci├│n (16)
Ôö£ÔöÇÔöÇ prueba_sincronizacion_asincrona.py  Pruebas automatizadas de la sincronizaci├│n as├¡ncrona del cat├ílogo (27)
Ôö£ÔöÇÔöÇ prueba_sincronizacion_interfaz.py  Pruebas automatizadas de la sincronizaci├│n completa integrada en la interfaz (18)
Ôö£ÔöÇÔöÇ prueba_recarga_catalogo.py  Pruebas automatizadas de la recarga as├¡ncrona del cat├ílogo tras la sincronizaci├│n (20)
Ôö£ÔöÇÔöÇ prueba_pagina_siguiente.py  Pruebas automatizadas de la carga manual de una p├ígina adicional del cat├ílogo en la interfaz (20)
Ôö£ÔöÇÔöÇ prueba_tamano_archivo.py  Pruebas automatizadas del tama├▒o de archivo (15)
Ôö£ÔöÇÔöÇ prueba_previews_progresivas.py  Pruebas automatizadas de los previews progresivos (16)
Ôö£ÔöÇÔöÇ apertura_videos.py     Servicio de apertura de videos con la aplicaci├│n predeterminada del sistema (├║nico m├│dulo que ejecuta `os.startfile`)
Ôö£ÔöÇÔöÇ playlist_vlc.py       Integraci├│n de playlists VLC (B4.4): localiza `vlc.exe`, genera el `.m3u` temporal con `#EXTVLCOPT:start-time` por entrada (encoding UTF-8), limpia playlists propias anteriores y lanza VLC una ├║nica vez; sin HTTP ni libVLC
Ôö£ÔöÇÔöÇ prueba_doble_clic.py   Pruebas automatizadas de la apertura del video por doble clic (14)
Ôö£ÔöÇÔöÇ prueba_menu_contextual.py  Pruebas automatizadas del men├║ contextual con clic derecho (14)
Ôö£ÔöÇÔöÇ prueba_restauracion_seleccion.py  Pruebas automatizadas de la restauraci├│n de selecci├│n tras reemplazo de tarjetas (15)
Ôö£ÔöÇÔöÇ prueba_shift_clic.py  Pruebas automatizadas de la selecci├│n por rango con Shift+clic (28)
Ôö£ÔöÇÔöÇ prueba_copiar_rutas_seleccionados.py  Pruebas automatizadas de la copia de rutas de seleccionados al portapapeles (8)
Ôö£ÔöÇÔöÇ prueba_abrir_carpetas_seleccionados.py  Pruebas automatizadas de la apertura de carpetas de seleccionados (10)
Ôö£ÔöÇÔöÇ prueba_escaneo_subcarpetas.py  Pruebas automatizadas del escaneo recursivo con subcarpetas (12)
Ôö£ÔöÇÔöÇ prueba_persistencia_subcarpetas.py  Pruebas automatizadas de la persistencia de "Incluir subcarpetas" (10)
Ôö£ÔöÇÔöÇ prueba_cantidad_previews.py  Pruebas automatizadas de la cantidad configurable de previews (11)
Ôö£ÔöÇÔöÇ prueba_version_build.py  Pruebas automatizadas de la identificaci├│n visible de versi├│n/build (Beta 7, 3): constantes, texto exacto `Beta 7 ÔÇö B7.13` y etiqueta visible en la status bar
Ôö£ÔöÇÔöÇ configuracion.py       Servicio de persistencia de configuraci├│n (├║ltima carpeta seleccionada en `configuracion.json`) + constantes centrales de versi├│n/build (`VERSION_PRODUCTO`, `BUILD_IDENTIFICADOR`, `TEXTO_VERSION_BUILD` ÔåÆ `Beta 7 ÔÇö B7.13`)
Ôö£ÔöÇÔöÇ prueba_persistencia_carpeta.py  Pruebas automatizadas de la persistencia de la ├║ltima carpeta seleccionada (20)
Ôö£ÔöÇÔöÇ arbol_navegacion.py  ├ürbol de navegaci├│n del panel izquierdo (nodo ra├¡z "Este equipo", discos y carpetas con carga diferida, selecci├│n funcional, sincronizaci├│n y persistencia/restauraci├│n de la carpeta activa); Etapa 2.5 del bloque de trabajo 2, desacoplado del cat├ílogo. Bloque 4: modo de selecci├│n de carpetas con checkboxes + herramientas de selecci├│n r├ípida (Etapas 2-3)
Ôö£ÔöÇÔöÇ prueba_arbol_navegacion.py  Pruebas automatizadas del ├írbol de navegaci├│n del panel izquierdo (Etapa 2.1)
Ôö£ÔöÇÔöÇ prueba_expansion_carpetas.py  Pruebas automatizadas de la expansi├│n de discos y carpetas con carga diferida (Etapa 2.2)
Ôö£ÔöÇÔöÇ prueba_seleccion_arbol.py  Pruebas automatizadas de la selecci├│n funcional del ├írbol de navegaci├│n (Etapa 2.3)
Ôö£ÔöÇÔöÇ prueba_carpeta_actual.py  Pruebas automatizadas de la integraci├│n de la selecci├│n del ├írbol con la carpeta activa de la aplicaci├│n (Etapa 2.4)
Ôö£ÔöÇÔöÇ prueba_persistencia_arbol.py  Pruebas automatizadas de la persistencia y restauraci├│n del ├írbol (Etapa 2.5)
Ôö£ÔöÇÔöÇ prueba_escaneo_arbol.py  Pruebas automatizadas del disparo autom├ítico del escaneo desde el ├írbol y el di├ílogo (Etapa 2.6)
Ôö£ÔöÇÔöÇ prueba_subcarpetas_arbol.py  Pruebas de verificaci├│n de la paridad ├írbol/bot├│n/di├ílogo respecto de "Incluir subcarpetas" (Etapa 2.7)
Ôö£ÔöÇÔöÇ prueba_escaneo_automatico.py  Pruebas automatizadas de la preferencia independiente de "Escaneo autom├ítico" y sus cuatro combinaciones con "Incluir subcarpetas" (Etapa 2.8)
Ôö£ÔöÇÔöÇ prueba_indicador_escaneado.py  Pruebas automatizadas de los indicadores visuales de carpetas escaneadas (Etapa 2.9)
Ôö£ÔöÇÔöÇ nombres.py             Motor general y reutilizable de nombres (B6.8): componente puro/testeable separado de UI/SQLite/FFmpeg/PySide6; tokens cerrados, sanitizacion Windows, extension controlada, colisiones deterministas
Ôö£ÔöÇÔöÇ exploracion_cache.py    Motor de cach├® temporal versionada y reanudable en disco (B4.3.1): estructura `miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` + `f{ms:010d}.jpg`), fingerprint sin hash, reanudaci├│n y escritura at├│mica; densidad secundaria provisional centralizada (`objetivo_total_densidad`, 1/30 s, m├¡n 15, m├íx 200) para B4.3.2 Etapa 2; sin UI ni SQLite
Ôö£ÔöÇÔöÇ visor_videos.py        Interfaz gr├ífica (PySide6): panel izquierdo con ├írbol de navegaci├│n (`ArbolNavegacion`) + carga as├¡ncrona de la primera p├ígina + carga manual de una p├ígina adicional ("Cargar m├ís") + selecci├│n de carpeta + persistencia de la ├║ltima carpeta seleccionada (servicio `configuracion`) + escaneo as├¡ncrono de la carpeta elegida + encadenamiento escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ registros con tama├▒o/metadatos ÔåÆ guardado ÔåÆ sincronizaci├│n completa del cat├ílogo ÔåÆ recarga as├¡ncrona del cat├ílogo (reemplazo de tarjetas) + generaci├│n progresiva de previews con gestor propio + apertura del video por doble clic (se├▒al `Tarjeta.doble_clic` ÔåÆ `_abrir_video` ÔåÆ servicio `apertura_videos`) + **persistencia de marcadores temporales con gestor dedicado `gestor_marcadores` (B4.2)** (la `Tarjeta` recibe `video_id`, carga marcadores al expandir y persiste altas/bajas sin SQLite directo, con reconciliaci├│n de la carga como snapshot antiguo) + **cobertura densa de exploraci├│n temporal integrada con la tarjeta (B4.3.2)**: `TareaExploracionDensa` con `resultado_parcial` progresivo, decodificaci├│n `QImage` en el worker y conversi├│n `QPixmap` en la GUI, fallback a previews normales, selecci├│n en RAM durante `mouseMove`, cancelaci├│n cooperativa, aislamiento AÔåÆB, colapso que libera RAM y reexpansi├│n que reutiliza la cach├®; **densidad secundaria adaptativa en segundo plano (Etapa 2)** y **prioridad visual din├ímica + densidad manual (B4.3.3)** y **reproducci├│n de marcadores en VLC (B4.4)**: acci├│n de men├║ contextual "Reproducir marcadores en VLC" que recolecta los videos seleccionados en orden visible, lee sus marcadores (gestor dedicado `gestor_reproduccion`), dialoga sobre videos sin marcadores, omite archivos inexistentes y abre VLC una ├║nica vez con una playlist temporal; y **carga diferida de previews cacheadas (B4.6)**: las tarjetas parten con placeholders y las previews se incorporan progresivamente; **identificaci├│n visible de versi├│n/build en la status bar inferior (`Beta 4 ÔÇö B4.12`)**; `main()` es el **punto de entrada de producci├│n** (solo UI, sin pruebas)
Ôö£ÔöÇÔöÇ prueba_smoke.py        Arn├®s de smoke tests (ejecuci├│n expl├¡cita con `python prueba_smoke.py`): verifica el pipeline completo (paginaci├│n, escaneo + carpeta + sincronizaci├│n, previews, doble clic y persistencia) con una base SQLite temporal; no se ejecuta al iniciar la aplicaci├│n
Ôö£ÔöÇÔöÇ prueba_exploracion_cache_b431.py  Pruebas automatizadas del motor de cach├® temporal (B4.3.1, 29)
Ôö£ÔöÇÔöÇ prueba_exploracion_b432.py  Pruebas de la cobertura r├ípida integrada con la UI (B4.3.2 Etapa 1, 20)
Ôö£ÔöÇÔöÇ prueba_exploracion_densidad_b432.py  Pruebas de la densidad secundaria adaptativa (B4.3.2 Etapa 2, 12)
Ôö£ÔöÇÔöÇ prueba_exploracion_b433.py  Pruebas de prioridad visual din├ímica y densidad manual (B4.3.3, 22)
Ôö£ÔöÇÔöÇ prueba_reproduccion_marcadores_b44.py  Pruebas de la reproducci├│n de marcadores en VLC (B4.4, 24)
Ôö£ÔöÇÔöÇ DOCUMENTO_TECNICO.md   Este documento
Ôö£ÔöÇÔöÇ miniaturas/            Im├ígenes de miniatura (JPG, generadas autom├íticamente)
Ôöé   ÔööÔöÇÔöÇ <prefijo>_<NN>.jpg  Convenci├│n de nombres; cach├® ignorada, contenido variable
Ôö£ÔöÇÔöÇ videos_prueba/         Videos de prueba (datos de ejemplo)
Ôöé   Ôö£ÔöÇÔöÇ video_01.mp4       (0 bytes)
Ôöé   Ôö£ÔöÇÔöÇ video_03.avi       (0 bytes)
Ôöé   Ôö£ÔöÇÔöÇ video_04.mp4       (0 bytes)
Ôöé   ÔööÔöÇÔöÇ video_real.mp4     (5756 bytes, 640x360 h264 5s)
ÔööÔöÇÔöÇ __pycache__/           Compilados de Python (generados, no versionados)
```

> Nota: `miniaturas/` es una cach├® ignorada por Git; su contenido cambia con cada escaneo. Actualmente existen dos archivos locales de prueba (`video_real_01.jpg` y `video_real_02.jpg`), pero no forman parte estable de la arquitectura. La convenci├│n general de nombres es `miniaturas/<prefijo>_<NN>.jpg`.

## 2. Prop├│sito de cada carpeta

| Carpeta | Prop├│sito |
| --- | --- |
| `miniaturas/` | Almacena las miniaturas generadas de cada video. El visor lee de aqu├¡ para mostrar la tarjeta. El backend **genera** las miniaturas durante el escaneo y las **preserva**: nunca las sobrescribe ni las elimina autom├íticamente. |
| `miniaturas/exploracion/` | Cach├® densa de exploraci├│n temporal (B4.3.1): por video y por versi├│n de fingerprint (`<video_id>/<version_fingerprint>/`), con `meta.json` + `f*.jpg`. Ignorada por Git, regenerable y **nunca borrada autom├íticamente** (las versiones antiguas quedan en disco hasta una limpieza futura, fuera de alcance). |
| `videos_prueba/` | Dataset de prueba con el que `escanear_videos.py` sincroniza el cat├ílogo. Contiene archivos vac├¡os (sin metadatos) y un video real. |
| `__pycache__/` | Cach├® de bytecode de Python. Generado autom├íticamente, debe ignorarse en VCS. |

## 3. Prop├│sito de cada m├│dulo

### `escanear_videos.py` ÔÇö backend / l├│gica del cat├ílogo
├Ünico m├│dulo con responsabilidad sobre el **dominio** y los **datos**:

- `escanear_videos(carpeta)` ÔÇö escaneo de archivos: lista archivos del directorio filtrando por extensi├│n (`.mp4`, `.mkv`, `.avi`), ordenados. Soporta un modo recursivo controlado por el flag `_ESCANEO_RECURSIVO` (configurable mediante `configurar_escaneo_recursivo(activado)`): cuando est├í activado, recorre todas las subcarpetas con `os.walk` y devuelve rutas relativas (respecto a `carpeta`); cuando est├í desactivado, solo lista la carpeta ra├¡z con `os.listdir`. El modo se controla desde la interfaz mediante la casilla `Incluir subcarpetas`. La funci├│n `_nombre_seguro(nombre)` reemplaza los separadores de ruta por `_` para que los nombres de archivo de miniaturas y previews sigan siendo planos incluso cuando el nombre del video incluye subcarpetas.
- `preparar_registros_basicos(videos, carpeta)` ÔÇö **preparaci├│n de registros b├ísicos del cat├ílogo** a partir de los archivos detectados por el escaneo. Recibe la lista de nombres de archivos y la carpeta escaneada; devuelve una lista de registros con las claves exactas `{nombre, ruta, extension, fecha_importacion}`. `ruta` es la ruta **absoluta** del archivo dentro de la carpeta escaneada (`os.path.join(carpeta, nombre)`), `extension` es la extensi├│n en min├║sculas y `fecha_importacion` es una marca de tiempo ISO (`datetime.now().isoformat()`) com├║n a los registros de la preparaci├│n. **Validaci├│n previa**: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vac├¡a (`ValueError` en caso contrario).   No detecta archivos, no abre SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas: es la capa de transformaci├│n entre el escaneo y la escritura (`guardar_videos`).
- `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)` ÔÇö **combinaci├│n de registros con metadatos FFprobe**: capa de cat├ílogo **pura** que transforma los archivos detectados por el escaneo y el resultado de `TareaFFprobe` en registros con metadatos. Parte de `preparar_registros_basicos` (claves b├ísicas `{nombre, ruta, extension, fecha_importacion}`) y luego integra los metadatos de FFprobe por ruta: para cada registro busca el `datos` asociado a su `ruta` dentro de `resultado_ffprobe["resultados"]` (los ├¡tems que no son `dict` o no tienen `ruta` se ignoran; un `datos` no-dict se trata como `None`) y aplica las claves de `CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")`; si el video no tiene `datos` (resultado vac├¡o, incompleto o fallo individual), las claves se escriben como `NULL` (`None`). Las rutas se comparan con la normalizaci├│n interna `_normalizar_ruta` (`os.path.normcase(os.path.normpath(ruta))`; `None` si la entrada es `None`). No abre SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas ni toca la interfaz: es la capa de transformaci├│n entre el escaneo y la escritura (`guardar_videos`).
- `conectar_bd(ruta_db=None)` ÔÇö acceso a SQLite: crea la tabla `videos` si no existe y aplica **migraci├│n idempotente** de columnas extras (`COLUMNAS_EXTRA`): `duracion_segundos REAL`, `ancho INTEGER`, `alto INTEGER`, `codec_video TEXT`, `cantidad_miniaturas INTEGER` y **`tamano_bytes INTEGER`**. Por cada columna, `PRAGMA table_info(videos)` decide si ya existe y solo entonces ejecuta `ALTER TABLE ... ADD COLUMN`; repetir la conexi├│n no duplica columnas ni toca los datos existentes. **Etapa B4.2**: adem├ís ejecuta la **migraci├│n aditiva** de la tabla `marcadores_video` (`_asegurar_tabla_marcadores`): crea la tabla y su ├¡ndice si no existen, idempotente y **sin** activar `PRAGMA foreign_keys` ni usar `ON DELETE CASCADE` (los marcadores son datos del usuario y su coherencia con `videos.id` se gestiona en la capa de servicio, no por borrado autom├ítico). Acepta una ruta de base opcional (por defecto `ruta_biblioteca()`); el arn├®s de smoke tests (`prueba_smoke.py`) reutiliza este esquema para crear una base SQLite temporal v├ílida sin depender de `biblioteca.db`.
- `obtener_datos_ffprobe(ruta)` ÔÇö integraci├│n con **FFprobe**: extrae duraci├│n, ancho, alto y codec del primer stream de video. Timeout 30 s; devuelve `None` ante cualquier fallo. En Windows, todos los `subprocess.run` (FFprobe, FFmpeg en `generar_miniatura` y `generar_preview`) usan `creationflags=subprocess.CREATE_NO_WINDOW` mediante `_ARGS_SIN_CONSOLA` para evitar ventanas de consola emergentes.
- `ffmpeg_disponible()` ÔÇö integraci├│n con **FFmpeg**: verifica disponibilidad del ejecutable (`shutil.which`).
- `ruta_miniatura(video, indice=1)` ÔÇö ruta can├│nica `miniaturas/<prefijo>_<NN>.jpg`.
- `calcular_tiempo_miniatura(duracion)` ÔÇö tiempo representativo para extraer el fotograma (10 % de la duraci├│n, acotado entre 0.1 y 10 s; 1 s si se desconoce).
- `miniatura_vigente(ruta_video, ruta_miniatura)` ÔÇö criterio de reutilizaci├│n por `mtime`: la miniatura es v├ílida si existe y su `mtime` es ÔëÑ al del video.
- `generar_miniatura(ruta_video, ruta_miniatura, duracion_segundos=None)` ÔÇö extrae un fotograma con FFmpeg (`-ss`, `-frames:v 1`). Timeout 30 s; devuelve `False` ante cualquier fallo. **Etapa B4.5**: si `duracion_segundos` es una duraci├│n utilizable (`_duracion_utilizable`: n├║mero real finito > 0) la usa directamente para calcular el tiempo objetivo **sin ejecutar FFprobe interno**; si es inv├ílida/ausente, ejecuta `obtener_datos_ffprobe` como fallback (comportamiento anterior). El FFmpeg y el archivo resultante son id├®nticos.
- `siguiente_indice_libre(video)` ÔÇö primer ├¡ndice `_NN` sin archivo existente.
- `miniatura_reutilizable(video, ruta_video)` ÔÇö primera miniatura existente del video que sea v├ílida (orden alfab├®tico) o `None`. **Excluye los archivos `_preview_`** (`_es_archivo_preview`): los previews progresivos no cuentan como miniaturas reutilizables.
- `asegurar_miniatura(video, ruta_video, duracion_segundos=None)` ÔÇö reutiliza una miniatura v├ílida si existe; si no, genera una nueva en la **siguiente ranura libre** (pasando la duraci├│n conocida a `generar_miniatura`, B4.5). Nunca sobrescribe ni elimina archivos.
- `asegurar_miniaturas(videos, carpeta, on_progreso=None, duraciones=None)` ÔÇö **aseguramiento de miniaturas por colecci├│n** para el pipeline: capa de cat├ílogo que orquesta `asegurar_miniatura` + `contar_miniaturas` por archivo. **Validaci├│n previa**: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vac├¡a (`ValueError`). Para cada nombre construye la ruta absoluta (`os.path.join(carpeta, nombre)`); si el archivo no existe registra `asegurada=0` y `cantidad_miniaturas=0`; si existe, invoca `asegurar_miniatura` y luego `contar_miniaturas`. **Etapa B4.5**: `duraciones` (mapa por ruta o por nombre) se propaga a `asegurar_miniatura`/`generar_miniatura`, que evitan el FFprobe interno cuando la duraci├│n es utilizable. Devuelve el resumen `{"rutas": [...], "resultados": [{"ruta", "asegurada", "cantidad_miniaturas"}...], "procesados": n, "con_miniatura": n, "sin_miniatura": n}`. **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` tras procesar cada nombre (incluidos los inexistentes); si es `None` el comportamiento es id├®ntico. Sin Qt; no abre SQLite ni toca la interfaz.
- `combinar_registros_con_miniaturas(registros, resultado_miniaturas)` ÔÇö **combinaci├│n de registros con cantidad de miniaturas**: capa de cat├ílogo **pura** que transforma los registros ya preparados (b├ísicos + FFprobe) y el resultado de `TareaMiniaturas` en registros con `cantidad_miniaturas`. Para cada registro busca el ├¡tem de `resultado_miniaturas["resultados"]` por ruta normalizada (`_normalizar_ruta`; los ├¡tems que no son `dict` o no tienen `ruta` se ignoran); si el valor de `cantidad_miniaturas` no es un entero se escribe como `None`; si no hay coincidencia o el resultado es `None`, tambi├®n `None`. Devuelve **copias** de los registros con la clave agregada. No abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `contar_miniaturas(video)` ÔÇö cuenta miniaturas existentes en `miniaturas/` cuyo nombre empieza con el prefijo del video. **Excluye los archivos `_preview_`** (`_es_archivo_preview`): los previews progresivos no alteran `cantidad_miniaturas`.
- `CANTIDAD_PREVIEWS_POR_DEFECTO = 3`, `CANTIDAD_PREVIEWS` (mutable, configurable con `configurar_cantidad_previews(n)`) ÔÇö cantidad de previews por video. A diferencia de la versi├│n original (constante), ahora la cantidad puede modificarse en tiempo de ejecuci├│n desde la interfaz mediante un `QComboBox` con opciones 3, 5, 7 y 9. La preferencia se persiste en `configuracion.json` (clave `cantidad_previews`) y se restaura al iniciar. La interfaz crea esa cantidad de etiquetas por `Tarjeta`; si existen m├ís previews que etiquetas, solo se muestran las que caben; si existen menos, se muestran las disponibles. La generaci├│n de nuevos previews respeta la cantidad configurada (sin forzar regeneraci├│n de los ya existentes).
- `ruta_preview(video, indice)` ÔÇö ruta can├│nica `miniaturas/<prefijo>_preview_NN.jpg` del preview `indice`.
- `_es_archivo_preview(nombre, video)` ÔÇö `True` si el nombre de archivo empieza con el prefijo del video seguido de `_preview_` (permite excluir los previews de la l├│gica de miniaturas).
- `previews_existentes(video)` ÔÇö lista de rutas de los ├¡ndices 1..3 que ya existen en `miniaturas/` (en orden); `[]` si no hay previews.
- `previews_faltantes(video)` ÔÇö lista de ├¡ndices 1..3 sin archivo en `miniaturas/` (generaci├│n incremental: solo los ├¡ndices que faltan).
- `calcular_tiempo_preview(duracion, indice=None)` ÔÇö tiempo representativo para extraer el fotograma del preview: proporcional `indice / (CANTIDAD_PREVIEWS + 1)` de la duraci├│n (25/50/75 % con `indice` en 1..3), acotado entre 0.1 s y `0.95 ├ù duraci├│n`; 1 s si se desconoce la duraci├│n o el ├¡ndice no es 1..3 (entero, no bool).
- `generar_preview(ruta_video, destino, indice=None, duracion_segundos=None)` ÔÇö extrae un fotograma con FFmpeg (`-ss <tiempo>`, `-frames:v 1`, `-q:v 3`) en el `tiempo` calculado. Timeout 30 s; devuelve `False` ante cualquier fallo. **Etapa B4.5**: con `duracion_segundos` utilizable usa esa duraci├│n **sin FFprobe interno** (mismo tiempo objetivo y FFmpeg); si es inv├ílida/ausente, fallback a `obtener_datos_ffprobe`.
- `generar_previews_faltantes(videos, carpeta, duraciones=None)` ÔÇö **generaci├│n de previews progresivos por colecci├│n**: capa de cat├ílogo que orquesta `previews_faltantes` + `generar_preview` por archivo. **Validaci├│n previa**: `videos` no texto (`str`/`bytes`/`bytearray`) ni no iterable (`TypeError`); `carpeta` texto no vac├¡o (`ValueError`). Para cada nombre construye la ruta absoluta (`os.path.join(carpeta, nombre)`), calcula los ├¡ndices **faltantes** y genera **solo esos**: si el archivo existe y no est├í vac├¡o intenta `generar_preview` (con la duraci├│n de `duraciones` si est├í disponible, B4.5); si FFmpeg falla y existe una miniatura principal v├ílida (`miniatura_reutilizable`) la copia como base (`shutil.copyfile`); si el archivo no existe o no hay base cuenta un error. **Nunca sobrescribe ni elimina archivos** (un ├¡ndice existente no se regenera). Devuelve el resumen `{"rutas": [...], "resultados": [{"nombre", "ruta", "previews", "generados", "reutilizados", "errores", "completos"}...], "procesados": n, "con_previews": n, "sin_previews": n}`, donde `completos` indica si ya existen los 3 previews. No abre SQLite ni toca la interfaz.
- `obtener_tamanos_archivos(videos, carpeta, on_progreso=None)` ÔÇö **estad├¡stica de archivo por colecci├│n** para el pipeline: capa de cat├ílogo que, para cada nombre de video, construye la ruta absoluta (`os.path.join(carpeta, nombre)`) y consulta con **un ├║nico `os.stat` por archivo** su tama├▒o y `mtime_ns` (`st_size` y `st_mtime_ns`; **B4.5 Etapa 3**, evita `getsize`+`stat` por separado). Un archivo legible se registra con `tamano_bytes` y `mtime_ns`; un archivo inexistente o ilegible (`OSError`) registra ambos como `None`. Devuelve el resumen `{"rutas": [...], "resultados": [{"ruta", "tamano_bytes", "mtime_ns"}...], "procesados": n, "con_tamano": n, "sin_tamano": n}`. **Validaci├│n previa**: `carpeta` texto no vac├¡o (`ValueError`); carpeta inexistente ÔåÆ `FileNotFoundError`; `videos` no texto ni no iterable (`TypeError`). **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` se invoca tras procesar cada archivo; si es `None` el comportamiento es id├®ntico. Sin Qt; no abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `combinar_registros_con_tamanos(registros, resultado_tamanos)` ÔÇö **combinaci├│n de registros con tama├▒o de archivo**: capa de cat├ílogo **pura** que transforma los registros ya preparados (b├ísicos + FFprobe + miniaturas) y el resultado de `TareaTamanosArchivos` en registros con `tamano_bytes`. Para cada registro busca el ├¡tem de `resultado_tamanos["resultados"]` por ruta normalizada (`_normalizar_ruta`; los ├¡tems que no son `dict` o no tienen `ruta` se ignoran); si el valor de `tamano_bytes` no es un entero se escribe como `None`; si no hay coincidencia o el resultado es `None`, tambi├®n `None`. Devuelve **copias** de los registros con la clave agregada. No abre SQLite, no ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `insertar_video`, `actualizar_datos`, `sincronizar_bd` ÔÇö l├│gica de sincronizaci├│n disco Ôåö BD: inserta nuevos, actualiza metadatos (incluida `cantidad_miniaturas` tras `asegurar_miniatura`), elimina de la BD los que ya no est├ín en disco. Operan sobre una conexi├│n administrada por el llamador (el `commit` lo hace `main()`).
- `guardar_video(datos, ruta_db=None)` ÔÇö **escritura individual transaccional** de un ├║nico registro. Recibe el registro ya preparado como `dict` con las claves de las columnas reales. Obligatorias: `nombre`, `ruta`, `extension`, `fecha_importacion`; opcionales (se guardan como `NULL` si faltan o son `None`): `duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`, `tamano_bytes`. Reutiliza la validaci├│n y el upsert internos compartidos (`_validar_registro_video`, `_upsert_video`) con `guardar_videos`; no duplica SQL ni validaci├│n. **Validaci├│n previa a SQL**: si `datos` no es un `dict` lanza `TypeError`; si falta una clave obligatoria lanza `ValueError` con el nombre de la clave; ambas se verifican **antes de conectar** (no se abre ni modifica la base). Inserta si `nombre` no existe o actualiza el mismo registro (`ON CONFLICT(nombre) DO UPDATE`), sin duplicar. Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos (mismo contrato que `listar_videos`). Ciclo: abre la conexi├│n, ejecuta el upsert, hace `commit` solo si la operaci├│n termin├│ correctamente, hace `rollback` ante cualquier error y cierra siempre en `finally`. Devuelve `{"guardado": True, "nombre": ...}`. No ejecuta escaneo, FFprobe ni FFmpeg; no modifica miniaturas.
- `guardar_videos(datos_videos, ruta_db=None, on_progreso=None)` ÔÇö **escritura de colecci├│n transaccional** en una **├║nica transacci├│n at├│mica**. Recibe una colecci├│n materializable de registros con el mismo contrato de `guardar_video` (una lista/tupla/iterable de `dict`; se rechaza el texto). **Validaci├│n completa previa**: la entrada debe ser iterable y no texto (`TypeError` en caso contrario), se materializa en una lista, se validan **todos** los registros (`_validar_registro_video`: no-dict ÔåÆ `TypeError`; clave obligatoria ausente ÔåÆ `ValueError`) y se toman **copias superficiales** de cada uno; si un registro es inv├ílido se rechaza la colecci├│n completa **sin abrir SQLite**. Inserta o actualiza cada registro (mismo upsert `ON CONFLICT(nombre) DO UPDATE` que `guardar_video`, sin duplicar SQL). **Ciclo at├│mico**: abre **una sola** conexi├│n, ejecuta **todos** los upserts, realiza **un solo** `commit` al terminar, ejecuta `rollback` ante cualquier excepci├│n (ning├║n registro anterior persiste; los preexistentes conservan sus valores originales; no queda transacci├│n abierta) y cierra siempre en `finally`. **Colecci├│n vac├¡a**: devuelve ├®xito con cero registros y no modifica la base. **Base inexistente**: `FileNotFoundError` sin crear archivos. Devuelve el resumen simple `{"guardados": <cantidad>, "nombres": [nombres en el orden de la colecci├│n]}`. **Callback de progreso opcional** (Etapa B3.21): `on_progreso(indice + 1, total)` tras cada upsert del bucle de escritura; si es `None` el comportamiento es id├®ntico. Sin Qt. No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg, no genera miniaturas, **no elimina registros** y no compara disco Ôåö base: la sincronizaci├│n del cat├ílogo sigue pendiente.
- `listar_videos(ruta_db=None)` ÔÇö **capa de lectura** que consume la interfaz: devuelve las filas del cat├ílogo (nombre, duraci├│n, ancho, alto, codec, cantidad de miniaturas, tama├▒o en bytes, ruta e `id`) ordenadas por nombre, como tuplas de **nueve campos** `(nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id)` (la columna `ruta` se incorpor├│ en la correcci├│n de cierre de la Beta 3 para que el cat├ílogo transporte la carpeta real de cada video y el subsistema de previews no dependa de la navegaci├│n; la columna `id` ÔÇö`videos.id`ÔÇö se incorpor├│ en la **B4.2** como ├║ltima columna para relacionar los marcadores persistentes con el video). Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. Abre y cierra su propia conexi├│n en el hilo que la invoca (sin `check_same_thread=False`). **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar; si la base no existe (falta el archivo o el directorio padre), lanza `FileNotFoundError` sin crear archivos. La lectura nunca crea la base; la creaci├│n es responsabilidad de `conectar_bd()`/`main()`.
- `detectar_diferencias(carpeta, ruta_db=None, carpetas_protegidas=None)` ÔÇö **detecci├│n no destructiva de diferencias** entre la carpeta de videos y el cat├ílogo SQLite: primera parte de la sincronizaci├│n completa. Compara los archivos de video de la carpeta (`escanear_videos(carpeta)`, solo `.mp4`/`.mkv`/`.avi` con extensi├│n en min├║sculas) con los registros de la base (un ├║nico `SELECT nombre, ruta FROM videos` sobre una conexi├│n propia abierta y cerrada en `finally`; sin `check_same_thread=False`) y devuelve el dict `{"carpeta", "presentes_en_ambos", "nuevos", "ausentes_del_disco"}` con listas ordenadas (determinista). **Validaci├│n previa**: `carpeta` debe ser una ruta de texto no vac├¡a (`ValueError`); carpeta inexistente ÔåÆ `FileNotFoundError` "Carpeta no encontrada: ..."; base inexistente ÔåÆ `FileNotFoundError` "Base de datos no encontrada: ...", en ambos casos **sin crear archivos**; `carpetas_protegidas` (si se pasa) debe ser una colecci├│n no texto (`TypeError`). **Modo tradicional** (sin `carpetas_protegidas`): id├®ntico al anterior ÔÇö los ausentes son los registros **por nombre** no presentes en disco. **Modo multicarpeta** (Etapa 5, con `carpetas_protegidas`): un registro solo es ausente si su **ruta pertenece a la carpeta** (`_es_subcarpeta`/`os.path.commonpath`) y no est├í en disco ÔÇö as├¡ los registros de otras ra├¡ces del alcance nunca se eliminan por error, y en carpetas solapadas los borrados dentro de cada carpeta s├¡ se reconcilian. **Solo lectura**: no inserta, no actualiza ni elimina registros, no modifica miniaturas, no ejecuta FFprobe/FFmpeg y no llama a `sincronizar_bd`. **Ausencia deliberada**: no detecta movimientos ni renombrados (compara por nombre, sin hash ni identidad estable) y no recorre subcarpetas por s├¡ misma.
- `preparar_plan_sincronizacion(diferencias)` ÔÇö **preparaci├│n del plan de sincronizaci├│n**: operaci├│n pura de la capa de cat├ílogo que recibe el resultado de `detectar_diferencias()` y devuelve el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`. `a_incorporar` contiene los **registros b├ísicos** de los videos nuevos preparados con `preparar_registros_basicos(nuevos, carpeta)` (claves `{nombre, ruta, extension, fecha_importacion}`, ruta absoluta); **`fecha_importacion` se genera al preparar esos registros** (marca ISO ├║nica del momento de la preparaci├│n), no durante `detectar_diferencias`. `ya_sincronizados` y `candidatos_a_eliminar` son listas ordenadas de nombres (los candidatos a eliminaci├│n son **├║nicamente informativos**). **Validaci├│n previa**: `diferencias` debe ser un dict (`TypeError`); faltar `carpeta`, `presentes_en_ambos`, `nuevos` o `ausentes_del_disco` ÔåÆ `ValueError` ("falta la clave obligatoria: ..."); `carpeta` texto no vac├¡o (`ValueError`); las colecciones no pueden ser texto ni no iterables (`TypeError`, helper interno `_coleccion_nombres`). Las claves extra se ignoran. **Sin efectos**: el plan no inserta, actualiza ni elimina registros, **no accede a SQLite**, no ejecuta FFprobe ni FFmpeg y no est├í integrado al pipeline ni a la interfaz. **Ausencia deliberada**: la aplicaci├│n real del plan contin├║a pendiente y **no existe todav├¡a deduplicaci├│n de nombres repetidos**.
- `aplicar_incorporaciones(plan, ruta_db=None)` ÔÇö **aplicaci├│n no destructiva de las incorporaciones del plan de sincronizaci├│n**: recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` producido por `preparar_plan_sincronizacion` y persiste **├║nicamente** `a_incorporar`, delegando en la escritura de colecci├│n `guardar_videos` (misma transacci├│n at├│mica: un solo `connect`, todos los upserts, un solo `commit`, `rollback` total ante cualquier fallo, `close` en `finally`). **Validaci├│n completa previa** (antes de delegar y de abrir SQLite): `plan` no-dict ÔåÆ `TypeError`; falta de `carpeta`, `a_incorporar`, `ya_sincronizados` o `candidatos_a_eliminar` ÔåÆ `ValueError`; `carpeta` texto no vac├¡o (`ValueError`); `a_incorporar` no texto e iterable (validaci├│n sin consumirla; `TypeError` en caso contrario); `ya_sincronizados` y `candidatos_a_eliminar` se validan como colecciones de nombres (helper interno `_coleccion_nombres`). Cada registro de `a_incorporar` se valida tambi├®n dentro de `guardar_videos` (`_validar_registro_video`) antes de abrir SQLite. **No destructivo**: no elimina registros, **no modifica `ya_sincronizados`** ni reescribe los registros preexistentes que est├®n sincronizados y **no aplica `candidatos_a_eliminar`** (solo informa su cantidad). No altera las colecciones recibidas ni expone referencias internas mutables. Devuelve el resultado simple y estable `{"incorporados": <cantidad>, "nombres": [nombres en el orden de la colecci├│n], "pendientes_eliminacion": <cantidad de candidatos>}`. No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg/miniaturas/subprocesos y **no est├í integrada todav├¡a al pipeline ni a la interfaz**: la eliminaci├│n controlada de `candidatos_a_eliminar` y la deduplicaci├│n de nombres repetidos contin├║an pendientes.
- `eliminar_candidatos(plan, ruta_db=None)` ÔÇö **eliminaci├│n controlada de los candidatos ausentes del plan de sincronizaci├│n**: recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` producido por `preparar_plan_sincronizacion` y elimina **├║nicamente** los registros nombrados en `candidatos_a_eliminar`, con el mismo patr├│n at├│mico de escritura: **una sola conexi├│n**, un `DELETE FROM videos WHERE nombre = ?` por candidato (con `cursor.rowcount` para contar solo las eliminaciones reales), **un solo `commit`**, `rollback` total ante cualquier fallo y `close` en `finally`. La **validaci├│n completa previa** (compartida con `aplicar_incorporaciones` mediante el helper `_validar_plan_sincronizacion`) se ejecuta antes de abrir SQLite: `plan` no-dict ÔåÆ `TypeError`; falta de `carpeta`, `a_incorporar`, `ya_sincronizados` o `candidatos_a_eliminar` ÔåÆ `ValueError`; `carpeta` texto no vac├¡o (`ValueError`); `a_incorporar` no texto e iterable (`TypeError`); `ya_sincronizados` y `candidatos_a_eliminar` como colecciones de nombres (helper `_coleccion_nombres`, que las devuelve **ordenadas**; por eso el orden procesado y devuelto es el **orden determinista de la validaci├│n actual**, no necesariamente el orden original de la colecci├│n del plan). El recorrido de eliminaci├│n usa esa colecci├│n ordenada. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos. **Solo registros**: no elimina archivos f├¡sicos ni miniaturas, no modifica `ya_sincronizados` ni los preexistentes sincronizados y no incorpora `a_incorporar`. Un candidato que no existe en la base no cuenta como eliminado y queda en `restantes`. **Colecci├│n vac├¡a de candidatos**: v├ílida, devuelve cero eliminaciones y **no modifica la base** (bytes y contenido id├®nticos). Devuelve el resultado `{"eliminados": <cantidad real>, "nombres": [eliminados en el orden determinista de la validaci├│n], "incorporados": <cantidad de `a_incorporar` o `None`>, "restantes": <candidatos no encontrados/no eliminados>}`; `incorporados` es **informativo y derivado del plan** (`len(plan["a_incorporar"])`, o `None` si no se puede medir, p. ej. una colecci├│n no materializable) y **no representa incorporaciones ejecutadas por esta funci├│n**. No ejecuta escaneo/FFprobe/FFmpeg/miniaturas/subprocesos, no reutiliza `conectar_bd`/`guardar_videos`/`sincronizar_bd` y **no est├í integrada todav├¡a al pipeline ni a la interfaz**: la integraci├│n as├¡ncrona de la sincronizaci├│n completa sigue pendiente.
- `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` ÔÇö **lectura paginada del cat├ílogo**, claramente diferenciada de `listar_videos()` y preparada para que la interfaz consuma cat├ílogos de decenas de miles de videos sin cargar todos los registros en memoria. Ejecuta en SQLite dos consultas con el **mismo filtro**: una consulta paginada (`SELECT ... FROM videos ORDER BY nombre LIMIT ? OFFSET ?`) y un `COUNT(*)`. Sin texto de b├║squeda, cuenta y lista todo el cat├ílogo; con texto, aplica a ambas consultas una coincidencia **parcial de nombre** (`LIKE` con patr├│n `%texto%`). Todos los valores (l├¡mite, desplazamiento, patr├│n) se pasan mediante **par├ímetros SQL**; nunca se interpola el texto buscado en el SQL. No lee primero toda la tabla, no cambia el esquema, no crea ├¡ndices y no implementa ordenamiento configurable. **Validaci├│n previa a SQL**: `limite` debe ser entero positivo (bool ÔåÆ `TypeError`; Ôëñ 0 ÔåÆ `ValueError`); `desplazamiento` debe ser entero ÔëÑ 0 (bool ÔåÆ `TypeError`; < 0 ÔåÆ `ValueError`); `texto` debe ser `None` o texto (`TypeError` en caso contrario). Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos. Devuelve la estructura estable `{"videos": [...], "total": <int>, "limite": <int>, "desplazamiento": <int>}`, donde cada elemento de `videos` conserva exactamente los mismos campos y el mismo formato que `listar_videos()` (tuplas de **nueve campos** `(nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id)`; `tamano_bytes` es `NULL`/`None` si el tama├▒o no se obtuvo; el `id` es la ├║ltima columna, incorporada en la **B4.2**). Abre y cierra su propia conexi├│n en el hilo que la invoca (sin `check_same_thread=False`). **Limitaci├│n conocida**: `%` y `_` del texto act├║an como comodines SQL `LIKE` (no como caracteres literales); la comilla simple s├¡ se trata literalmente. Pendiente de decisi├│n si se acepta como contrato.
- `_asegurar_tabla_marcadores(conn)` ÔÇö **migraci├│n aditiva e idempotente** de la tabla de
  marcadores (B4.2): `CREATE TABLE IF NOT EXISTS marcadores_video (id INTEGER PRIMARY KEY
  AUTOINCREMENT, video_id INTEGER NOT NULL, tiempo REAL NOT NULL)` e
  `idx_marcadores_video_video_id_tiempo`. **B6.3**: adem├ís a├▒ade la columna `color` mediante
  `_asegurar_columna_color`. Se invoca desde `conectar_bd` y desde la conexi├│n
  del repositorio de marcadores. No activa `PRAGMA foreign_keys` ni usa `ON DELETE CASCADE`.
- `listar_marcadores(video_id, ruta_db=None)` ÔÇö marcadores persistidos de un video, ordenados
  por tiempo; devuelve tuplas `(id, video_id, tiempo, color)` de la tabla `marcadores_video`
  (`WHERE video_id = ?`); `color` (B6.3) es una clave estable de `COLORES_CLASIFICACION` o
  `None` (color hist├│rico rojo). **Validaci├│n previa**: `video_id` entero positivo (bool ÔåÆ
  `TypeError`; Ôëñ 0 ÔåÆ `ValueError`). Abre y cierra su propia conexi├│n (mismo patr├│n que
  `listar_videos`); base inexistente ÔåÆ `FileNotFoundError` sin crear archivos. No ejecuta
  FFprobe/FFmpeg ni toca la interfaz.
- `guardar_marcador(video_id, tiempo, ruta_db=None, color=None)` ÔÇö persiste un marcador y
  devuelve su **`id` de la base** (`cursor.lastrowid`). **B6.3**: `color` es opcional (clave
  estable o `None`) y se inserta en el mismo `INSERT`, nunca en una segunda escritura; los
  callers hist├│ricos sin color quedan en `NULL`. **Validaci├│n previa**: `video_id` entero
  positivo; `tiempo` num├®rico no negativo (bool ÔåÆ `TypeError`; < 0 ÔåÆ `ValueError`); `color`
  validado con `_validar_color_clasificacion`. Ciclo transaccional:
  conexi├│n propia, `INSERT`, `commit` solo si termin├│ correctamente, `rollback` ante error y
  `close` en `finally`. No ejecuta FFprobe/FFmpeg ni toca la interfaz.
- `eliminar_marcador(marcador_id, ruta_db=None)` ÔÇö elimina un marcador por su `id`; devuelve
  `True` si se elimin├│ una fila (`rowcount > 0`) y `False` si no exist├¡a. **Validaci├│n previa**:
  `marcador_id` entero positivo. Ciclo transaccional propio (patr├│n de `guardar_marcador`).
- **Paleta cerrada de clasificaci├│n por color (B6.3).** `COLORES_CLASIFICACION` ÔÇö paleta de 6
  colores `(clave, r, g, b)` (rojo, naranja, amarillo, verde, azul, violeta), **├║nica fuente de
  verdad** del subsistema de clasificaci├│n (la UI y la configuraci├│n solo expresan colores
  mediante estas claves). La misma paleta sirve para **marcadores y segmentos**; `NULL`
  conserva los colores hist├│ricos (marcador rojo, segmento azul). API: `CLAVES_COLOR_CLASIFICACION`
  (frozenset de claves), `color_rgb(clave)` (RGB o `None`) y `_validar_color_clasificacion(clave)`
  (`None` aceptado = quitar color; no-texto ÔåÆ `TypeError`; clave ajena a la paleta ÔåÆ `ValueError`).
- `_asegurar_columna_color(conn, tabla)` ÔÇö **migraci├│n aditiva e idempotente** de la columna
  `color TEXT NULL` (B6.3), invocada desde `_asegurar_tabla_marcadores`,
  `_asegurar_tabla_segmentos` y los conectores de los repositorios. Consulta
  `PRAGMA table_info(tabla)` y ejecuta `ALTER TABLE ... ADD COLUMN` solo si falta; no toca los
  datos existentes (los registros hist├│ricos quedan en `NULL`).
- `asignar_color_marcador(marcador_id, clave, ruta_db=None)` ÔÇö asigna o quita (`clave=None`)
  el color de clasificaci├│n de un marcador persistido (B6.3): `UPDATE marcadores_video SET
  color = ? WHERE id = ?` en ciclo transaccional propio (`commit`/`rollback`/`close`); devuelve
  la fila persistida `(id, video_id, tiempo, color)` si el marcador exist├¡a (`rowcount > 0`) o
  `None` si no. **Validaci├│n previa**: `marcador_id` entero positivo y clave con
  `_validar_color_clasificacion`.
- **Segmentos con color (B6.3).** Las funciones del repositorio de segmentos
   (`listar_segmentos`, `listar_segmentos_de`, `guardar_segmento`) siguen el mismo esquema que
   sus equivalentes de marcadores: `color` como ├║ltimo campo de la tupla (B6.3) y par├ímetro
   opcional de creaci├│n en el mismo `INSERT`, con `None` que conserva el color hist├│rico azul.
   `asignar_color_segmento(segmento_id, clave, ruta_db=None)` es el an├ílogo de
   `asignar_color_marcador` (devuelve la fila `(id, inicio, fin, color)` o `None`).
- **Videos derivados y trazabilidad (B6.11).** Migraci├│n aditiva idempotente `_asegurar_tablas_derivados(conn)` ÔÇö `CREATE TABLE IF NOT EXISTS videos_derivados (id PK, derivado_video_id UNIQUE, original_video_id, tipo TEXT CHECK individual/lote/secuencia, fecha_creacion, derivado_nombre/ruta, original_nombre/ruta ÔÇö snapshot hist├│rico sin `FOREIGN KEY CASCADE`) e ├¡ndices `idx_videos_derivados_original/derivado`; `CREATE TABLE videos_derivados_segmentos (id PK, derivacion_id, segmento_id, orden, inicio, fin)` e ├¡ndices `idx_videos_derivados_segmentos_derivacion/orden`; invocada desde `conectar_bd`. Alta incremental `incorporar_video_derivado_al_catalogo(derivado_ruta, original_video_id, segmentos_orden=[{segmento_id,inicio,fin}], tipo, ruta_db)` ÔÇö valida archivo existente/no vac├¡o, extensi├│n `.mp4/.mkv`, `tipo` en `individual/lote/secuencia`, `segmentos` no vac├¡a con `segmento_id>0` y `fin>ini`, `original_video_id` existe en `videos`, bloqueo derivado-de-derivado (`original_video_id` no est├í en `videos_derivados.derivado_video_id`), duplicado `UNIQUE(nombre)` con `normcase/normpath` sin reutilizaci├│n silenciosa, `segmento_id` existe y pertenece a `original_video_id`, `ruta` fuera de ra├¡z permitida, FFprobe+`stat` fuera de transacci├│n, transacci├│n at├│mica `BEGIN`ÔåÆ`_upsert_video`ÔåÆ`INSERT videos_derivados`ÔåÆN `INSERT videos_derivados_segmentos`ÔåÆ`COMMIT` (rollback ante `IntegrityError`/`Exception`); devuelve `{ok, derivado_video_id, derivacion_id, error, catalog_error}` y conserva archivo si `catalog_error`. Lectura: `es_video_derivado(video_id)`, `obtener_derivacion_por_derivado(derivado_video_id)ÔåÆ{derivacion, segmentos ORDER BY orden}` (persiste tras borrar original/derivado de `videos`), `listar_derivaciones_por_original(original_video_id)ÔåÆ[... ORDER BY id ASC]`. Validaci├│n estricta de secuencia en `TareaExportarSecuencia`: longitud y correspondencia exacta `segmentos` vs `segmentos_info_orden` (mismatch ÔåÆ archivo conservado, `alta_catalogo ok False`, sin trazabilidad falsa).
- `main()` ÔÇö CLI: sincroniza el cat├ílogo contra `videos_prueba/` (ruta resuelta por `rutas.py`).

### `rutas.py` ÔÇö capa centralizada de resoluci├│n de rutas
├Ünico m├│dulo responsable de derivar las rutas del proyecto a partir de su ubicaci├│n real, sin depender del directorio de trabajo. La ra├¡z se resuelve con `_directorio_base()`: en **modo PyInstaller** (`getattr(sys, "frozen", False)` verdadero) usa `os.path.dirname(sys.executable)` ÔÇöla carpeta del ejecutable empaquetadoÔÇö; ejecut├índose desde el c├│digo fuente usa `os.path.dirname(os.path.abspath(__file__))`. As├¡ los datos (`biblioteca.db`, `miniaturas/`, `configuracion.json`) se crean junto al ejecutable portable o junto al proyecto de desarrollo seg├║n el modo:

- `ruta_raiz()` ÔÇö directorio ra├¡z del proyecto.
- `ruta_biblioteca()` ÔÇö ruta de `biblioteca.db`.
- `ruta_carpeta_miniaturas()` ÔÇö ruta de `miniaturas/`.
- `ruta_carpeta_videos()` ÔÇö ruta de `videos_prueba/`.
- `ruta_configuracion()` ÔÇö ruta de `configuracion.json` (configuraci├│n local del usuario).

Dise├▒ado como punto ├║nico de extensi├│n para futuras rutas de configuraci├│n; no constituye todav├¡a un m├│dulo de configuraci├│n completo.

### `apertura_videos.py` ÔÇö servicio de apertura de videos
M├│dulo **de servicio** que separa de la interfaz la apertura de un video con la aplicaci├│n predeterminada de Windows. Es el **├║nico m├│dulo que ejecuta `os.startfile`** (verificado por AST de `visor_videos.py` en `prueba_doble_clic.py`):

- `abrir_video_con_aplicacion_predeterminada(nombre, carpeta)` ÔÇö recibe el **nombre** del video y la **carpeta** en la que se encuentra; **valida ambos** como texto no vac├¡o (tras `strip()`; `None`, `""`, solo espacios o un no-texto ÔåÆ `ValueError`), construye la **ruta absoluta** (`os.path.abspath(os.path.join(carpeta, nombre))`) **fuera de la interfaz**, valida con `os.path.isfile` que el archivo exista (si no ÔåÆ `FileNotFoundError` con la ruta) y abre el video con `os.startfile(ruta)`. Devuelve la ruta absoluta. Un fallo del propio `os.startfile` (p. ej. falta la aplicaci├│n asociada) propaga `OSError`. No abre SQLite, no ejecuta FFprobe/FFmpeg, no usa subprocesos (`Popen`/`subprocess`) y no toca la interfaz.

### `playlist_vlc.py` ÔÇö integraci├│n de playlists VLC (B4.4)
M├│dulo **de servicio** que a├¡sla de la interfaz la integraci├│n con **VLC** mediante **playlists puras** (una entrada por marcador). Sin HTTP, sin libVLC, sin automatizaci├│n de teclas ni de botones:

- `localizar_vlc()` ÔÇö resuelve `vlc.exe` en orden: `%ProgramFiles%\VideoLAN\VLC\vlc.exe`, `%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe` y `shutil.which("vlc")`. Sin registro ni b├║squedas recursivas de discos; devuelve `None` si no se encuentra.
- `formatear_tiempo_vlc(segundos)` ÔÇö texto de `start-time` conservando **precisi├│n decimal** razonable (p. ej. `12.437`), recortando el ruido de punto flotante (`0.30000000000000004` ÔåÆ `0.3`). No modifica los datos persistidos.
- `formatear_titulo_marcador(nombre, segundos)` ÔÇö t├¡tulo descriptivo tipo `video.mp4 ÔÇö 00:01:12.437` (`H:MM:SS.mmm`), limpiando saltos de l├¡nea.
- `limpiar_playlists_anteriores(directorio)` ÔÇö elimina **solo** las playlists propias previas `visor_marcadores_*.m3u` del directorio indicado (un solo nivel, sin subdirectorios). Un archivo bloqueado se ignora (`except OSError: pass`) y la limpieza contin├║a. Nunca toca `.m3u` ajenos ni recorre el ├írbol.
- `generar_m3u(entradas, ruta_destino)` ÔÇö escribe el `.m3u` en **UTF-8 expl├¡cito** (soporta espacios, acentos y Unicode). **Primero** limpia las playlists propias anteriores de `os.path.dirname(ruta_destino)` y **despu├®s** escribe la nueva (no borra la playlist reci├®n lanzada). Cada entrada `{ruta, nombre, tiempo}` se serializa como `#EXTINF:-1,<t├¡tulo>` + `#EXTVLCOPT:start-time=<segundos>` + `<ruta absoluta>`.
- `abrir_playlist_en_vlc(ruta_m3u, ruta_vlc)` ÔÇö lanza **VLC una ├║nica vez** con la playlist completa (`subprocess.Popen([ruta_vlc, ruta_m3u])`), sin loop autom├ítico.

### `configuracion.py` ÔÇö servicio de persistencia de configuraci├│n
M├│dulo **de servicio** que separa de la interfaz la persistencia de la configuraci├│n local del usuario en un archivo JSON (`configuracion.json` en la ra├¡z del proyecto, gitignored). Persiste la **├║ltima carpeta seleccionada**. No abre SQLite, no ejecuta FFprobe/FFmpeg y no toca la interfaz:

- `CLAVE_CARPETA = "ultima_carpeta"` ÔÇö clave del JSON con la carpeta persistida.
- `VARIABLE_ENTORNO = "VISOR_CONFIG"` ÔÇö variable de entorno que redirige la ruta del archivo de configuraci├│n; la usan **solo las suites de prueba** para aislarse del archivo real del usuario. No es una bandera de depuraci├│n: es una redirecci├│n de ubicaci├│n y el arn├®s de pruebas la emplea para no tocar `configuracion.json`.
- `_resolver_ruta_config(ruta_config)` ÔÇö orden de resoluci├│n de la ruta: si se recibe una `ruta_config` expl├¡cita se usa esa; si no, la variable de entorno `VISOR_CONFIG` (absolutizada); si tampoco hay entorno, `ruta_configuracion()`.
- `guardar_ultima_carpeta(carpeta, ruta_config=None)` ÔÇö persiste la carpeta. **Validaci├│n previa**: `carpeta` texto no vac├¡o tras `strip()` (si no ÔåÆ `ValueError`); la ruta se **absolutiza** (`os.path.abspath`) y se comprueba con `os.path.isdir` que exista y sea un directorio (si no ÔåÆ devuelve `None` sin escribir). Escritura **at├│mica**: lee el JSON existente (o `{}`), a├▒ade `CLAVE_CARPETA` y escribe en un archivo temporal `<ruta>.tmp` que luego se **reemplaza** con `os.replace` (no quedan archivos parciales). Crea el directorio padre con `os.makedirs(..., exist_ok=True)`. Devuelve la ruta absoluta guardada.
- `obtener_ultima_carpeta(ruta_config=None)` ÔÇö restaura la carpeta persistida. **Tolerante**: si el archivo no existe, el JSON es corrupto (`OSError`/`ValueError`), no es un diccionario, la clave no es texto no vac├¡o o la carpeta dej├│ de existir, devuelve `None` sin lanzar y sin crear el archivo. Devuelve la ruta **absoluta**.
- Internos: `_leer(ruta_config)` (JSON a `dict` o `None` ante ausencia/corrupci├│n) y `_escribir(datos, ruta_config)` (escritura at├│mica con `.tmp` + `os.replace`). Persiste adem├ís la preferencia `incluir_subcarpetas` (booleano) mediante `guardar_preferencia_subcarpetas(activado, ruta_config)` y `obtener_preferencia_subcarpetas(ruta_config)` (devuelve `False` por defecto), y la preferencia **`escaneo_automatico`** (booleano) mediante `CLAVE_ESCANEO_AUTOMATICO = "escaneo_automatico"`, `guardar_preferencia_escaneo_automatico(activado, ruta_config)` y `obtener_preferencia_escaneo_automatico(ruta_config)` (**devuelve `True` por defecto**, preservando el comportamiento previo y la compatibilidad con archivos de configuraci├│n antiguos sin la clave). **Etapa B3.3**: adem├ís persiste el **tama├▒o de las miniaturas** mediante `CLAVE_TAMANIO_MINIATURAS = "tamano_miniaturas"`, `guardar_tamano_miniaturas(nombre, ruta_config)` (valida `pequeno`/`mediano`/`grande`; valor inv├ílido ÔåÆ `None` sin escribir) y `obtener_tamano_miniaturas(ruta_config)` (**devuelve `"mediano"` por defecto**; si el valor almacenado no es texto o no es uno de los tres tama├▒os v├ílidos vuelve autom├íticamente a `"mediano"`), con el mismo patr├│n at├│mico. **Etapa B3.5**: adem├ís persiste el **retardo de la vista ampliada** mediante `CLAVE_RETARDO_VISTA_AMPLIADA = "retardo_vista_ampliada_ms"`, `guardar_retardo_vista_ampliada(ms, ruta_config)` (valida los valores discretos `-1/0/250/400/600`; `-1` = "Desactivado" desde la Etapa B3.14a; valor inv├ílido ÔåÆ `None` sin escribir) y `obtener_retardo_vista_ampliada(ruta_config)` (**devuelve `400` por defecto**; valor almacenado inv├ílido ÔåÆ `400`), aditivo y sin migraci├│n para configuraciones antiguas. **Etapa B3.7**: adem├ís persiste el **factor de la vista ampliada** mediante `CLAVE_TAMANO_VISTA_AMPLIADA = "tamano_vista_ampliada"`, `guardar_tamano_vista_ampliada(factor, ruta_config)` (valida `1.2/1.6/2.0/2.5/3.0/3.5`, con 3.0 y 3.5 incorporados en la Etapa B3.14b; valor inv├ílido ÔåÆ `None` sin escribir) y `obtener_tamano_vista_ampliada(ruta_config)` (**devuelve `1.6` por defecto**; valor almacenado inv├ílido ÔåÆ `1.6`), tambi├®n aditivo.

- **Nombres globales de colores de la clasificaci├│n (B6.3).** Persiste en el mismo
  `configuracion.json` los nombres visibles opcionales por clave de paleta, **sin cambiar las
  claves estables**: `CLAVE_NOMBRES_COLORES = "nombres_colores"` (clave ra├¡z del JSON),
  `LIMITE_LONGITUD_NOMBRE_COLOR = 40` y `NOMBRES_COLORES_POR_DEFECTO` (de f├íbrica). API:
  `guardar_nombre_color(clave, nombre, ruta_config=None)` (permite solo claves de la paleta y
  texto Ôëñ 40 tras `strip()`; un nombre vac├¡o elimina la entrada y restaura el de f├íbrica;
  devuelve el texto efectivo o `None`), `obtener_nombres_colores(ruta_config=None)` (solo
  claves v├ílidas, recortadas y dentro del l├¡mite) y `texto_color(clave, ruta_config=None)`
  (nombre configurado o el de f├íbrica; `None` para claves ajenas). Mismo patr├│n at├│mico
  `.tmp` + `os.replace`; aditivo, sin migraci├│n (configuraciones antiguas sin la clave usan
  los nombres de f├íbrica).

### `arbol_navegacion.py` ÔÇö ├írbol de navegaci├│n del panel izquierdo
M├│dulo **de interfaz** que encapsula el ├írbol del panel izquierdo, base del futuro Centro de Navegaci├│n. Separado en un m├│dulo propio para no mezclar la l├│gica de archivos con el resto de la interfaz:

- `TEXTO_RAIZ = "Este equipo"` ÔÇö texto del nodo ra├¡z del ├írbol.
- `discos_disponibles()` ÔÇö devuelve las unidades disponibles del sistema (solo Windows). Recorre `string.ascii_uppercase` y conserva las letras cuya ra├¡z `X:\` existe (`os.path.exists`). L├│gica pura: sin Qt, sin SQLite, sin subprocesos y sin dependencias externas.
- `carpetas_de(ruta)` ÔÇö **funci├│n pura** que devuelve los subdirectorios inmediatos de `ruta` (solo directorios, sin archivos), ordenados alfab├®ticamente de forma insensible a may├║sculas (`sorted(..., key=str.lower)`). Tolerante: cualquier error de acceso al sistema de archivos (`OSError` en general: permiso denegado, ruta inexistente, archivo) devuelve `[]` sin interrumpir la exploraci├│n.
- `ROL_RUTA = Qt.UserRole + 1` / `ROL_CARGADO = Qt.UserRole + 2` / `ROL_PLACEHOLDER = Qt.UserRole + 3` / `ROL_ESTADO = Qt.UserRole + 4` ÔÇö roles de datos de cada nodo: ruta absoluta, estado de carga, marcador de hijo placeholder y estado visual (valor de `EstadoNodo`).
- `EstadoNodo(IntEnum)` ÔÇö estados visuales del nodo, preparados para crecer sin cambiar la API p├║blica: `SIN_ESCANEAR = 0`, `ESCANEADA = 1`, `PARCIAL = 2`, `CAMBIOS_PENDIENTES = 3`, `ERROR = 4` (en esta etapa solo se usan `SIN_ESCANEAR` y `ESCANEADA`).
- `ArbolNavegacion(QTreeWidget)` ÔÇö widget del ├írbol (Etapa 2.9): `setHeaderHidden(True)` (sin encabezado), `setSelectionMode(QAbstractItemView.SingleSelection)` (selecci├│n funcional de discos y carpetas), nodo ra├¡z `TEXTO_RAIZ` expandido y un hijo por disco (`discos_disponibles()`). **Carga diferida por placeholder**: cada disco y cada carpeta lleva un hijo ficticio marcado con `ROL_PLACEHOLDER` (y `Qt.NoItemFlags`) para mostrar el indicador de expansi├│n; `itemExpanded` conectado **internamente** a `_al_expandir` ÔåÆ `_cargar`, que al expandir un nodo **quita el placeholder y consulta ├║nicamente sus hijos inmediatos** (un solo nivel, sin recorrer el ├írbol completo ni precalcular niveles posteriores). El estado de carga se guarda **en el propio nodo** (`ROL_CARGADO`), por lo que re-expandir no recarga ni duplica; la ruta absoluta de cada nodo queda en `ROL_RUTA`. Una carpeta sin subdirectorios queda sin hijos y sin flecha. **Selecci├│n funcional**: el m├®todo p├║blico **`carpeta_actual()`** es la interfaz oficial para consultar la carpeta seleccionada (ruta absoluta almacenada en `_ruta_actual`, o `None`); la se├▒al de clase **`ruta_seleccionada = Signal(str)`** solo **notifica** cambios de selecci├│n. El handler `_al_cambiar_actual` (conectado a `currentItemChanged`) valida el nodo con `_ruta_valida()`: el nodo ra├¡z "Este equipo" (sin `ROL_RUTA`) y los placeholders (`ROL_PLACEHOLDER`) **nunca son selecci├│n v├ílida** ÔÇö no modifican `carpeta_actual()` ni emiten rutas. Al contraer un ancestro, si el ├¡tem previamente seleccionado queda oculto (`anterior.isHidden()`), se **conserva `_ruta_actual`** sin reemitir; no hay restauraci├│n visual autom├ítica de la selecci├│n (decisi├│n de dise├▒o). **Sincronizaci├│n app ÔåÆ ├írbol**: el m├®todo p├║blico **`seleccionar_ruta(ruta)`** busca **solo entre los nodos ya cargados** (recursi├│n en memoria, sin recorrer el sistema de archivos ni cargar carpetas nuevas), expande los ancestros ya cargados y hace `setCurrentItem`; si la ruta no est├í presente, no modifica la selecci├│n ni lanza. **Restauraci├│n de la carpeta persistida**: el m├®todo p├║blico **`revelar_ruta(ruta)`** reconstruye **estrictamente de forma incremental** la rama necesaria para volver a mostrar una carpeta: ubica el disco que contiene la ruta (`_buscar_disco` por prefijo com├║n), expande cada nivel (disparando la carga diferida existente) y busca ├║nicamente el siguiente componente (`_buscar_hijo_por_ruta`, comparaci├│n insensible a may├║sculas con `os.path.normcase`), sin recorrer el ├írbol ni el disco completos ni cargar ramas ajenas al camino; selecciona la carpeta destino o devuelve `False` sin lanzar si no puede reconstruirla (disco ausente, carpeta eliminada, camino cambiado). **Fuente ├║nica de verdad**: el ├írbol puede cambiar la carpeta activa de la aplicaci├│n y reflejarla (el visor conecta `ruta_seleccionada` a `_al_carpeta_actual_arbol`), pero `carpeta_actual()` representa ├║nicamente el estado interno del widget; el ├írbol no escanea, no toca el cat├ílogo, SQLite ni el panel derecho. **Indicadores visuales (Etapa 2.9)**: el m├®todo p├║blico **`marcar_carpeta_escaneada(ruta)`** marca una carpeta como escaneada (agrega la ruta a `_carpetas_escaneadas` y actualiza su indicador; si el nodo a├║n no est├í cargado, el indicador se aplica al crearse por carga diferida). El estado de cada nodo se deriva por pertenencia en `_estado_de(item)` y se almacena **solo como valor** en `ROL_ESTADO` (`int`); la representaci├│n visual se calcula **exclusivamente** en `_icono_para(estado)` (checkmark est├índar `QStyle.SP_DialogApplyButton` para `ESCANEADA`; sin ├¡cono para `SIN_ESCANEAR`) ÔÇö no se almacenan objetos `QIcon` en los datos del nodo. Marcar una carpeta **no altera** la selecci├│n, la expansi├│n ni la navegaci├│n. El ├írbol **no conoce SQLite ni el cat├ílogo**: recibe ├║nicamente un conjunto de rutas. Se instancia en el constructor de `VisorVideos` como `self.arbol_navegacion` (contenido del panel izquierdo del `QSplitter`).

- **Modo de selecci├│n de carpetas y herramientas r├ípidas** (Bloque de trabajo 4, **Etapas 2-3, entrega conjunta**): `ArbolNavegacion(parent=None, seleccion=None)` recibe una referencia a **`SeleccionCarpetas`** (├║nica fuente de verdad). `set_modo_seleccion(activo)` activa el modo: cada carpeta cargada muestra un **checkbox** cuyo estado refleja el conjunto (`_aplicar_check`, con guard `_sincronizando_checks` para ignorar emisiones espurias de `itemChanged` ÔÇö los `QTreeWidgetItem` de PySide6 nacen checkables por defecto y `_crear_nodo_disco`/`_crear_nodo_carpeta` quedan envueltos en el guard); marcar/desmarcar modifica **solo** `SeleccionCarpetas` (`_al_item_cambiado` compara el estado con el conjunto y solo sincroniza si difiere), **sin** cambiar la carpeta activa, **sin** iniciar escaneos y **sin** alterar la navegaci├│n. Con el modo desactivado el ├írbol se comporta **exactamente igual que antes** (sin checkboxes; la ra├¡z se limpia al construirse). **Herramientas de selecci├│n r├ípida**: `seleccionar_todas_nivel()` (hijos cargados del nivel actual), `deseleccionar_todas()` (vac├¡a el conjunto), `invertir_nivel()` (invierte solo el nivel conservando lo externo, v├¡a `_reemplazar_seleccion` = `limpiar` + `seleccionar_todas`), y por men├║ contextual (solo en modo selecci├│n) `seleccionar_hasta`/`deseleccionar_hasta`/`seleccionar_desde`/`deseleccionar_desde` sobre la **lista ordenada de hermanos** (`_hijos_ordenados`, orden visual = orden de `carpetas_de` = alfab├®tico case-insensitive; `_rango_hasta`/`_rango_desde`). **Todas** las acciones solo materializan **rutas** en `SeleccionCarpetas` (sin intervalos ni estructuras paralelas) y refrescan los checks con `_refrescar_checks`.

### `visor_videos.py` ÔÇö interfaz gr├ífica

**Infraestructura de paneles (QSplitter):** La ventana principal se divide en dos paneles permanentes mediante un `QSplitter` horizontal (`Qt.Horizontal`). El panel izquierdo (`QWidget`, minWidth=80, maxWidth=400) contiene el ├írbol de navegaci├│n (`ArbolNavegacion`, de `arbol_navegacion.py`) **m├ís el toggle "Modo selecci├│n" y una fila de acciones r├ípidas** ("Seleccionar todas", "Deseleccionar todas", "Invertir", oculta salvo en modo selecci├│n) del Bloque 4 (Etapas 2-3): al activar el modo, el ├írbol muestra checkboxes sincronizados con `SeleccionCarpetas` y las acciones masivas operan sobre el nivel actual; en modo normal el ├írbol se comporta igual que antes. El ├írbol, en la Etapa 2.9, muestra el nodo ra├¡z "Este equipo", los discos y sus carpetas (carga diferida por nivel), permite seleccionar discos y carpetas, **persiste y restaura** la carpeta activa, al seleccionar una carpeta v├ílida **inicia autom├íticamente el escaneo solo si la preferencia "Escaneo autom├ítico" est├í activa** (el mismo `iniciar_escaneo()` del bot├│n) y muestra un **indicador visual de carpetas escaneadas** (Etapa 2.9); la selecci├│n del ├írbol actualiza la **carpeta activa de la aplicaci├│n** (`carpeta_seleccionada` y `etiqueta_carpeta`) y el cat├ílogo se actualiza mediante el pipeline existente, sin afectar el panel derecho. **Preferencia independiente (Etapa 2.8)**: "Escaneo autom├ítico al seleccionar carpeta" es independiente de "Incluir subcarpetas", soportando las cuatro combinaciones (escaneo autom├ítico ├ù subcarpetas). **Verificaci├│n (Etapa 2.7)**: ├írbol, bot├│n y di├ílogo comparten `iniciar_escaneo()` y respetan de forma **id├®ntica** el estado de "Incluir subcarpetas" (`configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())`); verificado por `prueba_subcarpetas_arbol.py`. El panel derecho contiene toda la interfaz existente sin cambios, encapsulada en la clase `PanelPrincipal` (ver abajo). El splitter utiliza `handleWidth=8` para garantizar que la barra divisoria pueda tomarse c├│modamente con el mouse, y el cursor `Qt.SplitHCursor` se asigna exclusivamente al `QSplitterHandle` (no al splitter completo) mediante `splitter.handle(1).setCursor(Qt.SplitHCursor)`. El `setStretchFactor(0, 0)` y `setStretchFactor(1, 1)` hacen que solo el panel derecho se expanda al redimensionar la ventana.

**`PanelPrincipal(QWidget)`:** Subclase expl├¡cita del panel derecho (`visor_videos.py:285-302`). Redefine `minimumSizeHint()` para devolver `QSize(0, 0)`. Esta decisi├│n arquitect├│nica fue necesaria porque el `minimumSizeHint` por defecto (~720 px) est├í dominado por la barra de herramientas `fila_carpeta` (9 widgets: botones, checkboxes, combo, labels) cuyo `minimumSizeHint` combinado fuerza un m├¡nimo de ~703 px + m├írgenes. Sin la anulaci├│n, el QSplitter usa ese valor como tama├▒o m├¡nimo efectivo del panel derecho, bloqueando el arrastre del divisor hacia la derecha porque el panel ya est├í en su m├¡nimo. Al devolver `(0, 0)`, el splitter solo respeta el `minimumWidth` expl├¡cito del panel izquierdo (80 px), permitiendo que el divisor se arrastre libremente en ambas direcciones.

- `VisorVideos(QMainWindow)` ÔÇö constructor `__init__(self, ruta_db=None, parent=None, ruta_config=None)`; ventana principal: `QSplitter` horizontal con panel izquierdo (├írbol de navegaci├│n `ArbolNavegacion` con el nodo "Este equipo" y los discos) y panel derecho (`PanelPrincipal`) con fila de selecci├│n de carpeta (bot├│n + etiqueta de ruta), barra de b├║squeda, contador, bot├│n "Cargar m├ís", tarjetas horizontales (una por video, una fila por video en una ├║nica columna) dentro de un `QScrollArea`. Se construye **sin consultas SQLite**; la primera p├ígina del cat├ílogo se carga en segundo plano mediante `GestorTareas` + `TareaLecturaCatalogoPaginada` (constantes `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO = "Cargando cat├ílogoÔÇª"`, `MENSAJE_ERROR = "No se pudo cargar el cat├ílogo"`, `MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"`, `MENSAJE_RUTA_INVALIDA = "La ruta no es v├ílida o no es una carpeta"`, `MENSAJE_ERROR_TAMANOS = "No se pudieron obtener los tama├▒os de los archivos"`, `MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"`, `MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"`, `MENSAJE_ERROR_MINIATURAS = "No se pudieron generar las miniaturas"`, `MENSAJE_SINCRONIZANDO = "Sincronizando cat├ílogoÔÇª"`, `MENSAJE_ERROR_SINCRONIZACION = "No se pudo sincronizar el cat├ílogo"`, `MENSAJE_ERROR_RECARGA = "No se pudo actualizar el cat├ílogo"`, `MENSAJE_ERROR_PAGINA = "No se pudo cargar la p├ígina"`, `MENSAJE_ERROR_ABRIR = "No se pudo abrir el video"`). Se construye **sin consultas SQLite**; la primera p├ígina del cat├ílogo se carga en segundo plano y, tras una sincronizaci├│n exitosa, se **recarga en segundo plano y se reconstruyen las tarjetas**; adem├ís el usuario puede **cargar manualmente una p├ígina adicional** con el bot├│n "Cargar m├ís", que agrega las tarjetas nuevas debajo de las ya cargadas **sin reemplazarlas** y **sin duplicados**. El pipeline de escaneo es `TareaEscaneo` ÔåÆ `TareaTamanosArchivos` ÔåÆ `TareaFFprobe` ÔåÆ `TareaMiniaturas` ÔåÆ `TareaGuardarVideos`, y tras el guardado exitoso se encadena la **sincronizaci├│n completa** (`TareaSincronizacionCatalogo`) y la **recarga as├¡ncrona del cat├ílogo`. Tras cada carga inicial, recarga o p├ígina adicional, un **segundo `GestorTareas`** (`gestor_previews`) genera en segundo plano, en lotes de a 3 videos y mediante `TareaPreviewsProgresivas`, los **tres previews progresivos** de cada tarjeta (con un `QTimer` de 300 ms que evita competir con la carga del cat├ílogo); cada tarjeta muestra sus previews de forma incremental a medida que se generan.
- `carpeta_seleccionada` ÔÇö atributo con la carpeta elegida; comienza como `None` y, en el arranque, `obtener_ultima_carpeta(self._ruta_config)` **restaura la ├║ltima carpeta persistida** si existe (si la carpeta persistida ya no existe o el JSON est├í ausente/corrupto devuelve `None` sin lanzar). **Es la ├║nica fuente de verdad de la carpeta activa de la aplicaci├│n**: el ├írbol puede cambiarla y reflejarla, y el di├ílogo tambi├®n la cambia y persiste.
- `self.arbol_navegacion` / `_al_carpeta_actual_arbol(ruta)` ÔÇö el ├írbol se guarda como atributo y su se├▒al `ruta_seleccionada` se conecta a `_al_carpeta_actual_arbol`: valida `os.path.isdir`, ignora selecciones repetidas (`if self.carpeta_seleccionada == ruta: return`), asigna `carpeta_seleccionada = ruta`, actualiza `etiqueta_carpeta`, limpia `mensaje_carpeta`, **persiste** la carpeta con `guardar_ultima_carpeta(ruta, self._ruta_config)` (misma clave y escritura at├│mica que el di├ílogo), rearma botones (`_actualizar_botones_carpeta`) y **dispara el escaneo solo si la preferencia de escaneo autom├ítico est├í activa** (`_disparar_escaneo_si_automatico()` ÔåÆ `iniciar_escaneo()` si `self.escaneo_automatico.isChecked()`). El guard de repetici├│n impide el disparo durante la restauraci├│n de arranque y la sincronizaci├│n con el di├ílogo. **Sin** cat├ílogo ni panel derecho. En el arranque, la carpeta restaurada se reconstruye con `self.arbol_navegacion.revelar_ruta(carpeta_guardada)`; si la ruta no puede reconstruirse, la aplicaci├│n queda **sin carpeta seleccionada** (`carpeta_seleccionada = None` y etiqueta `MENSAJE_SIN_CARPETA`) de forma consistente.
- `seleccionar_carpeta()` ÔÇö el di├ílogo conserva su comportamiento intacto (validaci├│n, normalizaci├│n, persistencia) y, tras seleccionar, llama `self.arbol_navegacion.seleccionar_ruta(ruta_absoluta)` para que el ├írbol refleje la carpeta elegida (solo si el nodo ya est├í cargado; si no, la aplicaci├│n sigue funcionando sin construir el ├írbol). Al finalizar dispara **un ├║nico escaneo solo si la preferencia de escaneo autom├ítico est├í activa** (`_disparar_escaneo_si_automatico()`); la sincronizaci├│n posterior con el ├írbol no produce un segundo escaneo (guard de repetici├│n).
- `boton_seleccionar_carpeta` / `etiqueta_carpeta` / `mensaje_carpeta` ÔÇö bot├│n "Seleccionar carpeta" (`QPushButton`), etiqueta de solo lectura con la ruta elegida (`QLabel` con `Qt.TextSelectableByMouse`) y etiqueta de mensajes de error, integrados en una fila superior sin redise├▒ar la ventana.
- `seleccionar_carpeta()` ÔÇö abre `QFileDialog.getExistingDirectory`; si el usuario cancela, conserva la selecci├│n anterior; si la ruta es v├ílida, la **normaliza con `os.path.abspath`** (ruta absoluta), la **valida con `os.path.isdir`** (existe y es directorio), la muestra en la etiqueta, la guarda en `carpeta_seleccionada` y la **persiste** llamando a `guardar_ultima_carpeta(ruta_absoluta, self._ruta_config)` (escritura at├│mica en `configuracion.json`); si la ruta no existe o no es un directorio, rechaza la selecci├│n, conserva la anterior y muestra `MENSAJE_RUTA_INVALIDA` sin cerrar la ventana. **Etapa 2.8**: seleccionar una carpeta v├ílida (por el di├ílogo o por el ├írbol) **inicia autom├íticamente el escaneo solo si la preferencia "Escaneo autom├ítico" est├í activa** (mediante `_disparar_escaneo_si_automatico()` ÔåÆ el mismo punto de entrada `iniciar_escaneo()` del bot├│n "Escanear carpeta"); con la preferencia desactivada, la carpeta queda seleccionada sin escanear (exactamente un disparo por acci├│n del usuario; el guard de repetici├│n evita dobles disparos). No accede a SQLite/FFprobe/FFmpeg directamente: todo ocurre en el pipeline existente. La selecci├│n **persiste** entre ejecuciones (restaurada al iniciar) **sin** escaneo autom├ítico en la restauraci├│n.
- `boton_escanear` / `incluir_subcarpetas` / `escaneo_automatico` / `estado_escaneo` ÔÇö bot├│n "Escanear carpeta" (`QPushButton`), casillas "Incluir subcarpetas" y "Escaneo autom├ítico" (`QCheckBox`) y etiqueta de estado del escaneo (`QLabel`), integrados en la fila de selecci├│n de carpeta. El bot├│n queda habilitado solo si existe una carpeta v├ílida y el gestor est├í `inactivo`. Al iniciar el escaneo, el estado de la casilla de subcarpetas se comunica al m├│dulo `escanear_videos` mediante `configurar_escaneo_recursivo()`. Ambas casillas persisten al cambiar (`stateChanged` ÔåÆ `guardar_preferencia_subcarpetas` / `guardar_preferencia_escaneo_automatico`) y se restauran al iniciar (`obtener_preferencia_subcarpetas` / `obtener_preferencia_escaneo_automatico`). El bot├│n "Escanear carpeta" **ignora** la preferencia de escaneo autom├ítico (siempre escanea).
- `barra_progreso` ÔÇö `QProgressBar` visible bajo la barra de b├║squeda durante el pipeline. **Modo indeterminado (rango 0-0)** para las etapas sin avance real (escaneo, sincronizaci├│n, recarga): muestra solo el texto de la etapa. **Modo determinado** durante tama├▒os, FFprobe, miniaturas y guardado (Etapa B3.21) y durante Copiar/Pegar/Eliminar (Etapa B3.22): `_mostrar_progreso()` restablece siempre el rango `(0,0)` al iniciar cada paso (no arrastra el rango de la etapa anterior), guarda el texto en `self._texto_progreso` y reinicia `self._progreso_detallado`; el handler `_al_progreso_pipeline(procesado, total)` (conectado tanto a `gestor.tarea_progreso` como a `gestor_operaciones.tarea_progreso`) fija `setRange(0, total)` + `setValue(procesado)` y, **solo la primera vez de cada etapa** (Etapa B3.23), aplica el formato detallado `"{texto} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar` (nombre de la etapa + "N de M" + porcentaje). Muestra la etapa actual mediante `setFormat()` con los textos "EscaneandoÔÇª", "Obteniendo tama├▒osÔÇª", "Leyendo metadatosÔÇª", "Generando miniaturasÔÇª", "GuardandoÔÇª", "SincronizandoÔÇª", "Actualizando cat├ílogoÔÇª", "CopiandoÔÇª", "PegandoÔÇª" y "EliminandoÔÇª". Se oculta al finalizar (`_al_resultado_recarga`, `_al_resultado_*` de operaciones) o ante cualquier error (`_limpiar_cadena`). **Exclusi├│n mutua** (Etapa B3.22): las operaciones no pueden iniciarse mientras el pipeline principal est├® activo (`self.gestor.activo`) ÔÇö guard en `_iniciar_copia/pegar/eliminar` y reflejado en `_actualizar_boton_copiar/pegar/eliminar`. Controlada por la bandera `_pipeline_activo` y los m├®todos privados `_mostrar_progreso(texto)` y `_ocultar_progreso()`.
- `Tarjeta.seleccionada` / `Tarjeta.seleccion_por_rango` / `Tarjeta.menu_contextual` / `_nombres_seleccionados` ÔÇö selecci├│n visual de filas con `mousePressEvent` en la clase `Tarjeta`. Un clic izquierdo sin modificadores emite `seleccionada(nombre, ctrl)` hacia `_al_seleccionar_tarjeta`. Sin Ctrl: selecciona una ├║nica fila y deselecciona las dem├ís. Con Ctrl: agrega o quita la fila de la selecci├│n m├║ltiple. Con Shift (`Qt.ShiftModifier`): emite `seleccion_por_rango(nombre)` hacia `_al_seleccion_por_rango`, que selecciona todas las filas del rango comprendido entre el ancla (`_ancla_seleccion`) y la fila clickeada, seg├║n el orden visible (`self.visibles`). Si no existe un ancla o el ancla ya no est├í visible, Shift+clic equivale a un clic normal (selecciona una y establece nuevo ancla). El ancla se actualiza en cada selecci├│n simple, Ctrl+clic y Shift+clic sin ancla previa; no se modifica durante un rango Shift+clic. `_reemplazar_tarjetas` limpia el ancla. El clic derecho (`Qt.RightButton`) emite la se├▒al `menu_contextual(nombre)`; si la tarjeta no estaba seleccionada, primero la selecciona (deseleccionando las dem├ís); si ya pertenec├¡a a una selecci├│n m├║ltiple, la conserva intacta. El m├®todo `_mostrar_menu_contextual` construye un `QMenu` con cinco acciones ÔÇö"Abrir" (reutiliza `_abrir_video`, id├®ntico al doble clic), "Abrir carpeta" (abre la carpeta seleccionada con `os.startfile`), "Copiar ruta" (copia la ruta completa del video sobre el que se abri├│ el men├║), "Copiar rutas de los seleccionados" (copia todas las rutas, una por l├¡nea, en orden visible) y "Abrir carpetas de los seleccionados" (abre las carpetas de todos los videos seleccionados, deduplicando para no abrir la misma carpeta m├ís de una vez)ÔÇö y lo muestra con `menu.exec(QCursor.pos())`. El conjunto `_nombres_seleccionados` (expuesto como `@property nombres_seleccionados`) rastrea los nombres seleccionados. `Tarjeta.marcar_seleccionada(True/False)` aplica o remueve un borde azul de 3px (`ESTILO_SELECCIONADA`). La selecci├│n persiste al filtrar y se restaura autom├íticamente al reconstruir tarjetas (`_reemplazar_tarjetas`): los nombres que siguen existiendo en el nuevo conjunto se vuelven a marcar (estado interno y estilo visual sincronizados); los nombres que ya no aparecen se descartan. El doble clic (`mouseDoubleClickEvent`) no interfiere con la selecci├│n.
- `videos_detectados` ÔÇö atributo de la operaci├│n de escaneo: lista de archivos de video detectados en la ├║ltima ejecuci├│n exitosa; comienza como `None` (a├║n no se escane├│) y no persiste entre ejecuciones.
- `iniciar_escaneo(carpetas=None)` ÔÇö **punto de entrada ├║nico del escaneo**, usado por el bot├│n "Escanear carpeta" (`boton_escanear.clicked`, **incondicional**, conectado con lambda para no pasar el `bool` de `clicked`) y, mediante `_disparar_escaneo_si_automatico()` (solo si la preferencia "Escaneo autom├ítico" est├í activa), por la selecci├│n de una carpeta en el ├írbol (`_al_carpeta_actual_arbol`) y por el di├ílogo (`seleccionar_carpeta`). **Alcance (Etapas 4-6, Bloque 4):** la fuente de verdad del alcance es el **selector de modo** (`_modo_alcance`, Etapa 6): "Solo carpeta actual" ÔåÆ `[carpeta_seleccionada]` sin recursi├│n; "Carpeta actual y todas las subcarpetas" ÔåÆ `[carpeta_seleccionada]` con recursi├│n; "Selecci├│n personalizada" ÔåÆ `seleccion_carpetas.obtener_seleccion()` con recursi├│n. Adem├ís acepta `carpetas=None` (ÔåÆ seg├║n el modo), una cadena (una carpeta) o una **lista de carpetas** (escaneo multicarpeta); filtra carpetas inexistentes y **deduplica** (`dict.fromkeys`). Luego **normaliza el alcance efectivo** (`_alcance_efectivo`, Etapa 5): si la recursi├│n est├í **desactivada**, conserva la lista tal cual; si est├í **activada**, elimina las **ra├¡ces descendientes redundantes** (cualquier carpeta contenida en otra del alcance, detectada con `_ruta_contiene`/`os.path.commonpath` sobre rutas normalizadas ÔÇö comparaci├│n robusta que no confunde prefijos como `C:\Videos` y `C:\Videos2`), de modo que el mismo archivo f├¡sico nunca se escanea dos veces. Para cada carpeta del alcance efectivo ejecuta la cadena completa existente (`_iniciar_escaneo_carpeta`: escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ guardado ÔåÆ **sincronizaci├│n** ÔåÆ recarga) **secuencialmente** mediante la cola `_cola_carpetas_escaneo`; `_al_tarea_finalizada` avanza a la siguiente carpeta al terminar cada cadena, y la **uni├│n** queda materializada en el cat├ílogo global. Con una sola carpeta el comportamiento es **id├®ntico** al anterior. El checkbox "Incluir subcarpetas" queda ├║nicamente como **adaptador de compatibilidad oculto** (`incluir_subcarpetas`, no visible): su estado se sincroniza bidireccionalmente con el modo (una llamada `setChecked(True)` equivale a elegir "Carpeta actual + subcarpetas") para no romper llamadas existentes; `_sincronizar_alcance_desde_modo`, `_al_cambiar_modo_alcance` y `_al_cambiar_subcarpetas` mantienen la sincronizaci├│n con guard de reentrada.
- `_al_resultado_escaneo(videos)` ÔÇö al recibir la lista, la copia en `videos_detectados`, limpia `_escaneo_pendiente`, **marca `_ffprobe_pendiente = True`** (para que el resultado/error siguiente pertenezca a FFprobe) y muestra el conteo en `estado_escaneo` ("1 video detectado" / "N videos detectados"). No crea tarjetas ni recarga el cat├ílogo.
- `_al_error_escaneo(mensaje)` ÔÇö ante un fallo (carpeta inexistente, ruta que no es carpeta, etc.): limpia `_escaneo_pendiente` y `_guardado_pendiente` y muestra `MENSAJE_ERROR_ESCANEO` ("No se pudo escanear la carpeta"). **El ├║ltimo resultado exitoso se conserva**: `videos_detectados` no se borra si ya ten├¡a un valor previo.
- `_tamanos_pendiente` / `tarea_tamanos` / `resultado_tamanos` ÔÇö atributos del **paso de tama├▒o de archivo** del encadenamiento: estado interno que enruta el resultado/error de `TareaTamanosArchivos`, la tarea en curso y el ├║ltimo resumen de `obtener_tamanos_archivos` (`None` hasta que termina).
- `_iniciar_tamanos()` ÔÇö se lanza al recibir `tarea_finalizada` del escaneo (gestor `inactivo` y `_tamanos_pendiente` activo): valida que existan `tarea_escaneo` y `videos_detectados`, crea `TareaTamanosArchivos(videos_detectados, tarea_escaneo.carpeta)` y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena. Solo consulta el sistema de archivos (`os.path.getsize`); no abre SQLite ni ejecuta FFprobe/FFmpeg.
- `_al_resultado_tamanos(resultado)` ÔÇö al recibir el resumen de `TareaTamanosArchivos`: limpia `_tamanos_pendiente`, **marca `_ffprobe_pendiente = True`** (para que el resultado/error siguiente pertenezca a FFprobe), guarda el resultado en `resultado_tamanos` y libera `tarea_tamanos`. No crea tarjetas ni recarga el cat├ílogo.
- `_al_error_tamanos(mensaje)` ÔÇö ante un fallo de la obtenci├│n de tama├▒os (carpeta inexistente, contrato inv├ílido, etc.): limpia la cadena y muestra `MENSAJE_ERROR_TAMANOS` ("No se pudieron obtener los tama├▒os de los archivos"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el ├║ltimo resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_ffprobe_pendiente` / `tarea_ffprobe` / `resultado_ffprobe` ÔÇö atributos del **paso de metadatos FFprobe** del encadenamiento: estado interno que enruta el resultado/error de FFprobe, la tarea `TareaFFprobe` en curso y el ├║ltimo resultado de FFprobe (`None` hasta que termina).
- `_iniciar_ffprobe()` ÔÇö se lanza al recibir `tarea_finalizada` del escaneo (gestor `inactivo` y `_ffprobe_pendiente` activo): construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta, nombre)`) de los videos detectados y crea `TareaFFprobe(rutas, nombres=self.videos_detectados, stats=self.resultado_tamanos, ruta_db=self._ruta_db)` (**B4.5 Etapa 3**: la clasificaci├│n ocurre en el worker, la UI no consulta SQLite) y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena.
- `_al_resultado_ffprobe(resultado)` ÔÇö al recibir el resumen de `TareaFFprobe`: limpia `_ffprobe_pendiente`, **marca `_miniaturas_pendiente = True`** (para que el resultado/error siguiente pertenezca a las miniaturas), guarda el resultado en `resultado_ffprobe` y libera `tarea_ffprobe`. No crea tarjetas ni recarga el cat├ílogo.
- `_al_error_ffprobe(mensaje)` ÔÇö ante un fallo global de FFprobe (subproceso ausente, error del ejecutable, etc.): limpia la cadena y muestra `MENSAJE_ERROR_FFPROBE` ("No se pudieron obtener los metadatos"). **El ├║ltimo resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_miniaturas_pendiente` / `tarea_miniaturas` / `resultado_miniaturas` ÔÇö atributos del **paso de miniaturas** del encadenamiento: estado interno que enruta el resultado/error de `TareaMiniaturas`, la tarea en curso y el ├║ltimo resumen de `asegurar_miniaturas` (`None` hasta que termina).
- `_iniciar_miniaturas()` ÔÇö se lanza al recibir `tarea_finalizada` de FFprobe (gestor `inactivo` y `_miniaturas_pendiente` activo): valida que existan `tarea_escaneo` y `videos_detectados`, construye el mapa de duraciones desde `self.resultado_ffprobe` (`_duraciones_desde_ffprobe`, **B4.5**), crea `TareaMiniaturas(videos_detectados, tarea_escaneo.carpeta, duraciones=duraciones)` y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena. FFmpeg se ejecuta ├║nicamente dentro de la tarea (nunca en el hilo principal ni directamente desde la interfaz).
- `_al_resultado_miniaturas(resultado)` ÔÇö al recibir el resumen de `TareaMiniaturas`: limpia `_miniaturas_pendiente`, **marca `_guardado_pendiente = True`** (para que el resultado/error siguiente pertenezca al guardado), guarda el resultado en `resultado_miniaturas` y libera `tarea_miniaturas`. No crea tarjetas ni recarga el cat├ílogo.
- `_al_error_miniaturas(mensaje)` ÔÇö ante un fallo de la generaci├│n de miniaturas (FFmpeg ausente, error del ejecutable, etc.): limpia la cadena y muestra `MENSAJE_ERROR_MINIATURAS` ("No se pudieron generar las miniaturas"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el ├║ltimo resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_guardado_pendiente` / `tarea_guardado` / `registros_guardados` ÔÇö atributos del **encadenamiento de guardado**: estado interno que enruta el resultado/error del guardado, la tarea `TareaGuardarVideos` en curso y la cantidad de registros persistidos (`None` hasta que termina el guardado).
- `_al_tarea_finalizada()` ÔÇö **dispara el paso siguiente de la cadena al terminar cada tarea**: cuando el gestor vuelve a `inactivo` (el gestor solo admite una tarea a la vez), enruta seg├║n el flag activo: si `_escaneo_pendiente` est├í activo no hace nada (el resultado del escaneo ya marc├│ el siguiente flag); si `_tamanos_pendiente` est├í activo inicia `TareaTamanosArchivos` (ver `_iniciar_tamanos`); si `_ffprobe_pendiente` est├í activo inicia `TareaFFprobe` (ver `_iniciar_ffprobe`); si `_miniaturas_pendiente` est├í activo inicia `TareaMiniaturas` (ver `_iniciar_miniaturas`); si `_guardado_pendiente` est├í activo inicia `TareaGuardarVideos` (ver `_iniciar_guardado`); si no hay flag activo y el gestor vuelve a `inactivo`, limpia la cadena.
- `_iniciar_guardado()` ÔÇö se lanza al recibir `tarea_finalizada` de las miniaturas (gestor `inactivo` y `_guardado_pendiente` activo): valida que existan `tarea_escaneo`, `videos_detectados`, `resultado_tamanos`, `resultado_ffprobe` y `resultado_miniaturas`, prepara los registros con `combinar_registros_con_ffprobe(videos_detectados, tarea_escaneo.carpeta, resultado_ffprobe)` (claves b├ísicas + metadatos FFprobe; `NULL` si faltan), luego los combina con `combinar_registros_con_miniaturas(registros, resultado_miniaturas)` (clave `cantidad_miniaturas` por ruta; `None` si no hay coincidencia o el resultado es `None`) y finalmente con `combinar_registros_con_tamanos(registros, resultado_tamanos)` (clave `tamano_bytes` por ruta; `None` si no hay coincidencia o el archivo no es legible), y persiste el resultado con `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo `GestorTareas`; si el inicio falla, limpia la cadena. No se ejecuta FFmpeg ni FFprobe en este paso.
- `_al_resultado_guardado(resultado)` ÔÇö al recibir `{"guardados": n, "nombres": [...]}`: limpia `_guardado_pendiente`, libera `resultado_ffprobe` y `resultado_miniaturas`, guarda la cantidad en `registros_guardados` y habilita de nuevo el bot├│n de escaneo (gestor `inactivo`). No crea tarjetas ni recarga el cat├ílogo.
- `_al_error_guardado(mensaje)` ÔÇö ante un fallo de escritura (base inexistente, base corrupta, contrato inv├ílido): limpia `_guardado_pendiente` y muestra `MENSAJE_ERROR_GUARDADO` ("No se pudieron guardar los videos"). El gestor queda `inactivo` y la interfaz es recuperable: se puede iniciar un nuevo escaneo. No se eliminan registros preexistentes ni se recarga el cat├ílogo.
- `_sincronizacion_pendiente` / `tarea_sincronizacion` / `resultado_sincronizacion` ÔÇö atributos del **paso de sincronizaci├│n** del encadenamiento: estado interno que enruta el resultado/error de `TareaSincronizacionCatalogo`, la tarea en curso y el **resultado completo** `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}` de la ├║ltima sincronizaci├│n exitosa (`None` hasta que termina o si no se sincroniz├│).
- `_iniciar_sincronizacion(carpeta=None)` ÔÇö se lanza al recibir `tarea_finalizada` del guardado (gestor `inactivo` y `_sincronizacion_pendiente` activo). **Criterio de resoluci├│n de carpeta** (Etapa B3.18): usa, en orden, el par├ímetro opcional `carpeta` ÔåÆ el override temporal `_carpeta_sincronizacion` (si est├í fijado) ÔåÆ `self.carpeta_seleccionada`. Consume y limpia el override en el arranque para evitar reutilizaciones accidentales. Revalida la carpeta con `os.path.isdir` y crea `TareaSincronizacionCatalogo(carpeta, self._ruta_db, carpetas_protegidas=...)`; en **modo multicarpeta** (`_alcance_sincronizacion`, Etapa 5) las carpetas protegidas son las dem├ís ra├¡ces del alcance efectivo, de modo que cada carpeta sincroniza sus propios registros **por ruta** sin eliminar los de otras ra├¡ces. La inicia con el **mismo** `GestorTareas` de la ventana; si el gestor rechaza la tarea o la carpeta dej├│ de ser v├ílida, limpia la cadena. Muestra `MENSAJE_SINCRONIZANDO` ("Sincronizando cat├ílogoÔÇª") y bloquea los controles mientras corre.
- `_al_resultado_sincronizacion(resultado)` ÔÇö al recibir el resultado completo: limpia `_sincronizacion_pendiente`, libera `tarea_sincronizacion`, **conserva el resultado en `resultado_sincronizacion`** y muestra el resumen final en `estado_escaneo` mediante `texto_resumen_sincronizacion(resultado["resumen"])` ("Sincronizaci├│n completa: N incorporados, M eliminados, K candidatos restantes"). **Etapa 2.9**: toma la carpeta escaneada de `resultado["diferencias"]["carpeta"]`, la agrega a `self.carpetas_escaneadas` y llama `self.arbol_navegacion.marcar_carpeta_escaneada(carpeta)` (actualiza el indicador visual del ├írbol). El gestor queda `inactivo`, los botones se rearman y **marca `_recarga_catalogo_pendiente = True`** para que `_al_tarea_finalizada` inicie la recarga del cat├ílogo (`_iniciar_recarga_catalogo`). No crea tarjetas en este punto.
- `_al_error_sincronizacion(mensaje)` ÔÇö ante un fallo de la sincronizaci├│n: limpia la cadena y muestra `MENSAJE_ERROR_SINCRONIZACION` ("No se pudo sincronizar el cat├ílogo"). El gestor queda `inactivo`, la interfaz es recuperable con un nuevo escaneo posible y **el ├║ltimo resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_recarga_catalogo_pendiente` / `tarea_recarga_catalogo` ÔÇö atributos del **paso de recarga del cat├ílogo** del encadenamiento: estado interno que enruta el resultado/error de la recarga y la tarea `TareaLecturaCatalogoPaginada` de la recarga en curso (`None` cuando no hay recarga activa).
- `_crear_tarea_lectura(desplazamiento=0)` ÔÇö factor├¡a de la tarea de lectura `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, desplazamiento, None, ruta_db)`; la **misma** tarea se usa para la carga inicial (`_iniciar_carga`, desplazamiento 0), para la recarga tras la sincronizaci├│n (`_iniciar_recarga_catalogo`, desplazamiento 0) y para la **carga manual de una p├ígina adicional** (`cargar_mas`, desplazamiento = cantidad de tarjetas ya cargadas).
- `_iniciar_recarga_catalogo()` ÔÇö se lanza al recibir `tarea_finalizada` de la sincronizaci├│n (gestor `inactivo` y `_recarga_catalogo_pendiente` activo): crea `_crear_tarea_lectura()` y la inicia con el **mismo** `GestorTareas` de la ventana, guard├índola en `tarea_recarga_catalogo`; si el gestor rechaza la tarea, limpia la cadena y muestra `MENSAJE_ERROR_RECARGA`. La recarga **solo se lanza tras una sincronizaci├│n exitosa** y **no ejecuta FFprobe, FFmpeg ni miniaturas**: solo relee la primera p├ígina del cat├ílogo.
- `_al_resultado_recarga(resultado)` ÔÇö al recibir el resultado de la recarga: limpia `_recarga_catalogo_pendiente`, libera `tarea_recarga_catalogo`, **actualiza `_total_catalogo`** con el `total` del resultado y llama `_reemplazar_tarjetas(resultado.get("videos", []))`. `resultado_sincronizacion` se **conserva intacto** (el resumen mostrado no se pierde con la recarga).
- `_al_error_recarga(mensaje)` ÔÇö ante un fallo de la recarga: limpia la cadena, muestra `MENSAJE_ERROR_RECARGA` ("No se pudo actualizar el cat├ílogo"), el gestor queda `inactivo`, el bot├│n de escaneo se rehabilita y un nuevo escaneo es posible. **Conserva las tarjetas viejas** y **no revierte** la sincronizaci├│n ya confirmada en SQLite.
- `_reemplazar_tarjetas(filas)` ÔÇö al llegar un resultado v├ílido de la recarga: **quita las tarjetas antiguas de la grilla** (`cuadricula.removeWidget` + `tarjeta.deleteLater()` para liberar los widgets Qt), **vac├¡a `self.tarjetas` y `self.visibles`**, crea las tarjetas nuevas con `_crear_tarjetas(filas)` (primera p├ígina) en la **misma `QGridLayout` y el mismo `QScrollArea` reutilizados** y reaplica el filtro vigente. No quedan tarjetas ocultas obsoletas.
- `_total_catalogo` ÔÇö total de registros del cat├ílogo (`COUNT`) conocido hasta ahora; `None` hasta que llega el primer resultado de lectura. Lo actualizan la carga inicial, la recarga tras la sincronizaci├│n y cada p├ígina adicional; habilita/deshabilita el bot├│n "Cargar m├ís".
- `_pagina_pendiente` / `tarea_pagina` ÔÇö atributos de la **carga manual de una p├ígina adicional**: estado interno que enruta el resultado/error de la p├ígina y la tarea `TareaLecturaCatalogoPaginada` de la p├ígina en curso (`None` cuando no hay carga de p├ígina activa).
- `boton_cargar_mas` ÔÇö bot├│n "Cargar m├ís" (`QPushButton`) en la barra de b├║squeda, **deshabilitado al inicio**; habilitado solo cuando la carga inicial termin├│ (`_carga_completada`), se conoce `_total_catalogo`, quedan tarjetas por cargar (`len(self.tarjetas) < self._total_catalogo`), el gestor est├í `inactivo` y no hay cadena activa (`_actualizar_botones_carpeta`).
- `cargar_mas()` ÔÇö acci├│n manual del bot├│n "Cargar m├ís": si el gestor est├í ocupado o la carga inicial no termin├│, retorna; calcula el **`OFFSET` como la cantidad de tarjetas ya cargadas** (`len(self.tarjetas)`), crea `_crear_tarea_lectura(len(self.tarjetas))` y la inicia con el **mismo** `GestorTareas`; marca `_pagina_pendiente = True` y guarda la tarea en `tarea_pagina`. Si `gestor.iniciar()` rechaza la tarea, limpia los flags y rearma los botones. **No reemplaza tarjetas**: el reemplazo sigue siendo exclusivo de la recarga posterior a la sincronizaci├│n (`_reemplazar_tarjetas`).
- `_al_resultado_pagina(resultado)` ÔÇö al recibir `{"videos", "total", "limite", "desplazamiento"}`: limpia `_pagina_pendiente`, libera `tarea_pagina`, actualiza `_total_catalogo` y **agrega las tarjetas nuevas debajo de las ya cargadas** con `_agregar_tarjetas`, **descartando las filas cuyo `nombre` ya est├í cargado** (deduplicaci├│n por nombre; `nombre` es `UNIQUE` en SQLite, por lo que en la carga real no se producen filas repetidas; la deduplicaci├│n cubre p├íginas falsas/duplicadas de las pruebas). Reaplica el filtro vigente y rearma los botones.
- `_al_error_pagina(mensaje)` ÔÇö ante un fallo de la p├ígina: limpia la cadena (`_limpiar_cadena`), muestra `MENSAJE_ERROR_PAGINA` ("No se pudo cargar la p├ígina"), el gestor queda `INACTIVO`, las tarjetas ya cargadas se **conservan** y el bot├│n "Cargar m├ís" se rearma (un nuevo intento es posible).
- `_agregar_tarjetas(filas)` ÔÇö agrega una `Tarjeta` por fila **en la misma `QGridLayout`** en las posiciones siguientes a las ya ocupadas (fila `len(self.tarjetas) + indice`, columna 0; una fila por video), **conecta la se├▒al `doble_clic` de cada tarjeta a `_abrir_video`**, las agrega a `self.tarjetas`/`self.visibles` y reaplica el filtro vigente. A diferencia de `_reemplazar_tarjetas`, **no libera ninguna tarjeta existente**.
- `texto_resumen_sincronizacion(resumen)` ÔÇö formatea el resumen final de la sincronizaci├│n: `"Sincronizaci├│n completa: {incorporados} incorporados, {eliminados} eliminados, {candidatos_restantes} candidatos restantes"`; si `resumen` es `None` o faltan claves, usa `0` para cada cantidad.
- `_mostrar_estado_escaneo()` ÔÇö pluraliza el conteo: `videos_detectados is None` ÔåÆ `MENSAJE_SIN_ESCANEO` ("Sin escanear"); 1 ÔåÆ "1 video detectado"; n ÔåÆ "n videos detectados".
- `_actualizar_botones_carpeta()` ÔÇö mantiene habilitado el bot├│n "Escanear carpeta" solo con carpeta v├ílida y gestor `inactivo`; habilita el bot├│n "Cargar m├ís" solo con carga inicial terminada, `_total_catalogo` conocido, tarjetas por cargar (`len(self.tarjetas) < self._total_catalogo`), gestor `inactivo` y sin cadena activa; mientras el escaneo (o la carga inicial o una p├ígina adicional) est├í en curso, los botones de la fila quedan deshabilitados.
- Enrutado por estado: `_al_resultado` / `_al_error` reenv├¡an el resultado/error a los handlers de escaneo (`_al_resultado_escaneo` / `_al_error_escaneo`) **cuando `_escaneo_pendiente` est├í activo**, a los de tama├▒os (`_al_resultado_tamanos` / `_al_error_tamanos`) **cuando `_tamanos_pendiente` est├í activo**, a los de FFprobe (`_al_resultado_ffprobe` / `_al_error_ffprobe`) **cuando `_ffprobe_pendiente` est├í activo**, a los de miniaturas (`_al_resultado_miniaturas` / `_al_error_miniaturas`) **cuando `_miniaturas_pendiente` est├í activo**, a los de guardado (`_al_resultado_guardado` / `_al_error_guardado`) **cuando `_guardado_pendiente` est├í activo** y a los de sincronizaci├│n (`_al_resultado_sincronizacion` / `_al_error_sincronizacion`) **cuando `_sincronizacion_pendiente` est├í activo** y a los de recarga (`_al_resultado_recarga` / `_al_error_recarga`) **cuando `_recarga_catalogo_pendiente` est├í activo** y a los de una p├ígina adicional (`_al_resultado_pagina` / `_al_error_pagina`) **cuando `_pagina_pendiente` est├í activo**; la cadena se produce porque el escaneo, los tama├▒os, FFprobe, las miniaturas, el guardado, la sincronizaci├│n, la recarga y la carga de una p├ígina adicional son tareas sucesivas con el mismo gestor (el paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior, no en el handler del resultado); **antes de abortar** por `_carga_completada`, los handlers reenv├¡an primero a la p├ígina si `_pagina_pendiente` est├í activo (la carga inicial termina una sola vez; una p├ígina adicional puede llegar despu├®s). Es suficiente para una ├║nica tarea activa a la vez y debe revisarse si la interfaz incorpora m├ís tipos de tarea. **Los previews progresivos no se enrutan por este mecanismo**: usan un **segundo `GestorTareas`** (`gestor_previews`) con se├▒ales y handlers propios (`_al_resultado_previews` / `_al_error_previews` / `_al_previews_finalizada`), de modo que el enrutado del gestor principal queda sin cambios. **Ausencia deliberada**: el pipeline escribe registros con metadatos FFprobe (duraci├│n, resoluci├│n, codec; `NULL` si FFprobe no puede obtenerlos), `cantidad_miniaturas` (por ruta; `None` si no hay coincidencia) y `tamano_bytes` (por ruta; `None` si el archivo no existe o no es legible) mediante el upsert transaccional existente, conservando los registros preexistentes; tras el guardado exitoso se lanza la sincronizaci├│n completa (`TareaSincronizacionCatalogo`) que elimina de SQLite ├║nicamente los registros ausentes del disco, conserva intactos los metadatos y la cantidad de miniaturas de los presentes y **no elimina archivos f├¡sicos ni miniaturas**; **tras una sincronizaci├│n exitosa se recarga el cat├ílogo en segundo plano** (`TareaLecturaCatalogoPaginada` con el mismo gestor) y se **reemplazan las tarjetas** (se liberan las viejas y se crean las nuevas con la primera p├ígina en la misma grilla), conservando `resultado_sincronizacion`; no recorre subcarpetas y no ejecuta FFmpeg directamente desde la interfaz (la generaci├│n ocurre dentro de `TareaMiniaturas`).
- `TAMANIOS_MINIATURAS` / `TAMANIO_MINIATURAS_ACTUAL` / `configurar_tamano_miniaturas(nombre)` / `dimensiones_miniatura()` / `texto_tamano_miniaturas(nombre)` / `clave_tamano_miniaturas(texto)` ÔÇö **tama├▒o configurable de las im├ígenes de la tarjeta** (Etapa B3.3). Cuatro presets de caja de escalado: `pequeno` (260├ù146), `mediano` (320├ù180, **valor actual y predeterminado**), `grande` (400├ù225) y `muy_grande` (**512├ù288**, incorporado en la **Etapa B3.6** como ampliaci├│n de A3; se integr├│ solo ampliando los datos, sin l├│gica nueva). `dimensiones_miniatura()` devuelve la caja vigente; las claves inv├ílidas se ignoran. El escalado es **solo en memoria** reutilizando los pixmaps ya cargados (sin FFmpeg, sin relectura de disco, sin regeneraci├│n ni reescaneo). La preferencia se persiste en `configuracion.json` (clave `tamano_miniaturas`, default `"mediano"`) y se restaura al iniciar; la restauraci├│n usa `blockSignals` para no escribir la configuraci├│n en el arranque.
- `VistaAmpliada(QFrame)` / `RETARDO_VISTA_AMPLIADA_MS` / `RETARDO_OCULTAR_VISTA_MS` / `FACTOR_VISTA_AMPLIADA` / `FACTOR_VISTA_AMPLIADA_ACTUAL` / `configurar_factor_vista_ampliada(factor)` ÔÇö **vista ampliada al posar el mouse** (Etapa B3.4). Un **├║nico popup por `VisorVideos`** (ventana de nivel superior con flags `Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`, un `QLabel` interno), reutilizado continuamente (nunca se crea ni destruye por hover). `preparar(pixmap)` escala el pixmap original ya cargado en memoria a **`FACTOR_VISTA_AMPLIADA_ACTUAL` ├ù `dimensiones_miniatura()`** (proporcional al tama├▒o de la miniatura) y, si ya est├í visible mostrando el mismo pixmap, solo reutiliza (evita parpadeos). El factor es configurable desde la **Etapa B3.7** (valores `1.2/1.6/2.0/2.5`, default `1.6` = comportamiento previo; la **Etapa B3.14b** agrega `3.0/3.5`, quedando el m├íximo en `3.5` ÔÇö la vista ampliada puede ocupar pr├ícticamente toda la pantalla, siempre acotada por `_posicion_vista`; sin tratamiento especial para los nuevos factores). `ocultar()` limpia y oculta. **Etapa B3.9**: `_al_vista_solicitada` oculta de inmediato el popup si ya est├í visible y la nueva miniatura es distinta (transici├│n limpia; la misma imagen no oculta). `Tarjeta` instala `installEventFilter(self)` sobre `_imagen_miniatura` y cada preview; en `QEvent.Enter` emite `vista_solicitada(pixmap_original)` y en `QEvent.Leave` emite `vista_abandonada()`. La ventana maneja: retardo `QTimer` single-shot (configurable desde B3.5, default 400 ms, verifica el objetivo; **Etapa B3.14a**: se agrega el valor discreto "Desactivado" (`-1`) que impide que se active el mecanismo ÔÇö `_al_vista_solicitada` retorna de inmediato, no se inicia el timer ni aparece el popup; `_aplicar_retardo_vista_ampliada(-1)` adem├ís detiene el timer y oculta un popup visible; `self._retardo_vista_ampliada` conserva el valor vigente y, al restaurar, solo se fija el intervalo si no es `-1`; volver a cualquier retardo reactiva la funcionalidad), ocultado programado (150 ms al salir), ocultado por scroll (`valueChanged` del scrollbar), por reconstrucci├│n (`_reemplazar_tarjetas`) y en `closeEvent`. Posicionamiento con `_posicion_vista()`: offset respecto del cursor (evita ciclos enter/leave) y acotado a la geometr├¡a disponible de la pantalla. Comportamiento id├®ntico para miniatura principal y previews. Sin lecturas de disco, sin procesos externos, sin SQLite ni pipeline.
- `PreferenciasDialog(QDialog)` / `RETARDOS_VISTA_AMPLIADA` / `TEXTOS_RETARDO_VISTA_AMPLIADA` / `FACTORES_VISTA_AMPLIADA` / `TEXTOS_FACTOR_VISTA_AMPLIADA` ÔÇö **preferencias de miniaturas** (Etapa B3.5, ampliada en B3.7). Di├ílogo modal abierto por el bot├│n "PreferenciasÔÇª" (`_abrir_preferencias`), con dos preferencias: **retardo** de la vista ampliada (valores discretos `Desactivado (-1)`, incorporado en la **Etapa B3.14a**; `Inmediato (0)`, `250 ms`, `400 ms` predeterminado, `600 ms`) y **tama├▒o** de la vista ampliada (factores `1.2x/1.6x/2.0x/2.5x/3.0x/3.5x`, default `1.6`, incorporado en la **Etapa B3.7** y ampliado en la **B3.14b**). `retardo_seleccionado()` y `factor_vista_seleccionado()` devuelven los valores de los combos; al **Aceptar** se llaman `_aplicar_retardo_vista_ampliada(ms)` y `_aplicar_tamano_vista_ampliada(factor)`, que persisten con la infraestructura de `configuracion.py` y aplican de inmediato (`_timer_vista_mostrar.setInterval(ms)` y `configurar_factor_vista_ampliada(factor)`), sin reiniciar, sin reconstruir el cat├ílogo y sin alterar selecci├│n/scroll. Con `-1` (`Desactivado`) `_aplicar_retardo_vista_ampliada` detiene el timer y oculta un popup visible. Los controles **Previews** y **Tama├▒o** permanecen con acceso directo en la barra principal (decisi├│n de la auditor├¡a: priorizar la velocidad de uso). Las claves `retardo_vista_ampliada_ms` y `tamano_vista_ampliada` son aditivas: configuraciones antiguas sin la clave o con valor inv├ílido usan los defaults (`400 ms` y `1.6`) sin migraci├│n.
- `PreviewConTiempo(QLabel)` ÔÇö etiqueta de preview con **tiempo superpuesto** (Etapa B3.1) y **tama├▒o redimensionable** (Etapa B3.3): mismo widget por slot y mismo layout que el placeholder original (sin alterar tama├▒os de tarjeta, de miniaturas ni el scroll). `poner_preview(pixmap, tiempo)` almacena el pixmap original (`_pixmap_original`), escala a `dimensiones_miniatura()` con `KeepAspectRatio` y guarda el texto del instante; `paintEvent` conserva el fondo y el borde del placeholder, dibuja el fotograma centrado y, **solo si hay tiempo**, superpone en la esquina inferior derecha un rect├íngulo redondeado semitransparente oscuro (`rgba(0,0,0,150)`) con texto claro (`rgba(255,255,255,235)`). `reajustar()` reescala el original en memoria al tama├▒o vigente (tambi├®n actualiza la altura de los placeholders sin imagen). Si `tiempo` es `None` (duraci├│n desconocida o inv├ílida) dibuja ├║nicamente el fotograma, **sin valores por defecto**.
- `formatear_tiempo(segundos)` ÔÇö formatea un instante en segundos como `"m:ss"` o `"h:mm:ss"` (redondeado al segundo). Devuelve `None` si el valor no es num├®rico (incluido `bool`) o es negativo. Usos: **B3.1** en `_colocar_preview` (si devuelve `None` la interfaz **no dibuja overlay**); **B3.2** en el campo "Duraci├│n" de la tarjeta, donde `None` se respalda con el texto "No disponible".
- `_duracion_valida(duracion)` ÔÇö helper reutilizable (Etapa B3.9) que centraliza el criterio de "duraci├│n v├ílida" (num├®rico no `bool` y `> 0`; la duraci├│n **0 es inv├ílida**); se usa en el texto de duraci├│n de la tarjeta y en el overlay, eliminando la duplicaci├│n sin cambiar comportamiento. En la refinaci├│n de la Etapa 5 se cambi├│ accidentalmente a `>= 0` (duraci├│n 0 tratada como v├ílida ÔåÆ tarjetas "0:00" y overlays en duraci├│n 0); la **auditor├¡a de la Etapa 7** lo detect├│ y se restaur├│ el criterio `> 0` (regresi├│n corregida).
- `LIMITE_ORIGINAL_MINIATURA` / `_pixmap_acotado(pixmap)` ÔÇö **acotado de los pixmaps originales retenidos en memoria** (Etapa B3.9). Al cargar una preview o la miniatura principal se almacena el original con el lado mayor acotado a `LIMITE_ORIGINAL_MINIATURA = 1280` (cubre la mayor salida: Muy grande 512 ├ù factor 2.5 = 1280). Im├ígenes Ôëñ 1280 se conservan tal cual (mismo objeto). Se mantiene el reescalado en memoria sin releer disco ni regenerar, y la calidad de todos los tama├▒os y de la vista ampliada queda preservada.
- `Tarjeta(QFrame)` ÔÇö tarjeta horizontal por video (layout `QHBoxLayout`): **columna de datos a la izquierda** (`maxWidth=240`, seis campos con word wrap: nombre, duraci├│n, resoluci├│n, codec, miniaturas y tama├▒o) + **contenedor horizontal de im├ígenes** (`QHBoxLayout` con spacing 6, stretch=1) que agrupa consecutivamente cuatro im├ígenes del mismo nivel ÔÇöminiatura principal y tres previewsÔÇö con `setFixedHeight(ALTO_TARJETA)` y ancho ajustado autom├íticamente al pixmap real escalado (manteniendo relaci├│n de aspecto), m├ís un `addStretch()` final que concentra el espacio sobrante a la derecha. La fila se desempaqueta como tupla `nombre, duracion, ancho, alto, codec, miniaturas, tamano, *_resto = fila` (**siete campos b├ísicos**; `*_resto` captura las columnas opcionales del cat├ílogo si est├ín presentes ÔÇö`_resto[0]` = columna `ruta` (├║ltima en la correcci├│n de cierre de la Beta 3) y `_resto[1]` = columna `id` (`videos.id`, incorporada como ├║ltima en la **B4.2**), con las filas de `listar_videos`/`listar_videos_paginado` de **nueve columnas**, y compatibilidad con filas de 7 columnas en pruebas); la carpeta real del video (`self._carpeta_video`) se deriva de esa `ruta` rest├índole el nombre relativo (base de escaneo) y es la fuente de la carpeta para la generaci├│n de previews (correcci├│n de cierre de la Beta 3); **`self._video_id`** se toma de `_resto[1]` (B4.2) y es la identidad del video para cargar/crear/eliminar marcadores persistentes (una tarjeta sin `id` no persiste marcadores); el tama├▒o se presenta con `formatear_tamano(tamano)` y la duraci├│n con `formatear_tiempo(duracion)` (**B3.2 ÔÇö duraci├│n simplificada**: `m:ss` si es menor a una hora, `h:mm:ss` si es una hora o m├ís, y `"No disponible"` si la duraci├│n no existe o no es v├ílida; cambio solo de presentaci├│n, el valor `duracion_segundos` permanece num├®rico). Cada preview se actualiza de forma **incremental** con `actualizar_previews(rutas)` / `_colocar_preview(indice, ruta)`, reemplazando el placeholder "Generando previewÔÇª" por el pixmap escalado cuando el archivo ya existe y es cargable. **B4.6 Etapa 2 ÔÇö carga diferida**: la tarjeta conserva `_previews_completas` (estado interno no persistido) que marca si los primeros `CANTIDAD_PREVIEWS` slots tienen pixmap; `actualizar_previews` lo actualiza y, si la tarjeta est├í expandida, llama `_renderizar_marcadores()` (los marcadores obtienen su miniatura cuando llegan previews). por el pixmap escalado cuando el archivo ya existe y es cargable. **Etapa B3.1 (tiempo sobre las previews)**: cada slot de preview es un `PreviewConTiempo`; la tarjeta conserva `self._duracion = duracion` (duraci├│n del cat├ílogo) y `_colocar_preview` deriva el instante con `calcular_tiempo_preview(duracion, indice + 1)` y `formatear_tiempo` ÔÇö **sin FFprobe adicional, sin pipeline, sin cambios de esquema ni persistencia de tiempos**. Si la duraci├│n es `None` o inv├ílida, no se dibuja overlay. **Etapa B3.3 (tama├▒o configurable)**: el escalado de la miniatura principal y de las previews usa `dimensiones_miniatura()` (presets Peque├▒o/Mediano/Grande); la tarjeta conserva el pixmap original (`_miniatura_original`, `_imagen_miniatura`) y el recuadro "Sin miniatura" (`_recuadro_sin_miniatura`), y `aplicar_tamano()` reescala **en memoria** las im├ígenes y actualiza alturas cuando cambia el tama├▒o (cambio inmediato, sin reescaneo, sin regeneraci├│n, sin reconstrucci├│n; se conservan selecci├│n, scroll y overlays). Las previews existentes en disco se cargan inmediatamente al construir cada tarjeta (`_crear_tarjetas` y `_agregar_tarjetas`), antes de cualquier generaci├│n as├¡ncrona, para conservarlas tras el reescaneo de una carpeta ya procesada. **Apertura por doble clic**: la clase declara la se├▒al de clase `doble_clic = Signal(str)` y sobrescribe `mouseDoubleClickEvent(event)` (llama a `super().mouseDoubleClickEvent(event)` y emite `self.doble_clic.emit(self._nombre)`), de modo que **cualquier doble clic con el bot├│n izquierdo sobre la tarjeta emite el nombre del video**; la interfaz conecta esa se├▒al a `_abrir_video` tanto en la carga inicial (`_crear_tarjetas`) como en las p├íginas adicionales (`_agregar_tarjetas`).
- `formatear_tamano(valor)` ÔÇö presentaci├│n legible del tama├▒o en bytes: enteros ÔëÑ 0 ÔåÆ `B` (menos de 1024), `KB` (un decimal), `MB` (un decimal) o `GB` (un decimal) seg├║n el umbral; un valor no-entero (`None`, texto, float, `bool`) o negativo ÔåÆ `"Desconocido"`.
- `_iniciar_carga()` ÔÇö crea la tarea de lectura con `_crear_tarea_lectura(desplazamiento=0)` (`TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)`) y la inicia con `gestor.iniciar(tarea)`.
- `gestor_previews` ÔÇö **segundo `GestorTareas`** propio, independiente del gestor principal, dedicado a la generaci├│n **progresiva** de previews. Sus se├▒ales se conectan a `_al_resultado_previews` / `_al_error_previews` / `_al_previews_finalizada`; se cierra en `closeEvent` junto con el gestor principal.
- `_cola_previews` ÔÇö cola de **pares `(nombre, carpeta)`** de video pendientes de generar previews; la carpeta es la **carpeta real del propio video** (de su registro del cat├ílogo), no la carpeta de navegaci├│n. Evita re-encolar los que ya tienen previews o ya est├ín en cola.
- `_timer_previews` ÔÇö `QTimer` single-shot de 300 ms que arranca la cola de previews al terminar cada carga/recarga/p├ígina (`_programar_previews`), para no competir con la carga del cat├ílogo.
- `previews_de(nombre)` ÔÇö funci├│n del m├│dulo: devuelve `previews_existentes(nombre)` (rutas de los previews ya generados, en orden 1..3).
- `_programar_previews()` / `_iniciar_previews()` ÔÇö tras cada carga inicial, recarga o p├ígina adicional: si la carga termin├│, arranca el temporizador; al dispararse, encola los nombres de las tarjetas (`_encolar_previews`) y lanza el primer lote (`_al_previews_finalizada`). **No dependen de `carpeta_seleccionada`** (correcci├│n de cierre de la Beta 3): cada video aporta su propia carpeta.
- `_encolar_previews(nombres)` ÔÇö agrega a `_cola_previews` los nombres de las tarjetas **no completas** (flag `Tarjeta._previews_completas`, B4.6 Etapa 2) que no est├®n pendientes, encolando cada uno con la carpeta de su tarjeta (`tarjeta._carpeta_video`, derivada de la columna `ruta` del cat├ílogo); descarta los videos sin carpeta resoluble. De este modo **tambi├®n las previews cacheadas** entran a la cola y se aplican progresivamente (0 FFmpeg). **Etapa B3.8**: al aumentar la cantidad configurada, `_al_cambiar_cantidad_previews` llama `_programar_previews()` al final, de modo que la cola existente encola autom├íticamente solo los videos incompletos y genera **├║nicamente los ├¡ndices faltantes** (`generar_previews_faltantes`), sin escanear ni releer el cat├ílogo; al disminuir no se genera nada (solo se ocultan previews).
- `_siguiente_lote_previews()` ÔÇö si el gestor de previews est├í libre, agrupa la cola por carpeta y toma hasta `TAMANIO_LOTE_PREVIEWS = 3` nombres de una **├║nica carpeta**, construye el mapa de duraciones de las tarjetas del lote (`Tarjeta._duracion`, **B4.5**), crea `TareaPreviewsProgresivas(lote, carpeta, duraciones=duraciones)` y la inicia con `gestor_previews`, re-encolando el resto; al terminar cada lote (`_al_previews_finalizada`) se procesa el siguiente, encadenando lotes hasta vaciar la cola. As├¡ cada lote genera siempre contra la carpeta correcta de sus videos y con la duraci├│n ya conocida (evita FFprobe interno).
- `Tarjeta._carpeta_video` ÔÇö carpeta real del video derivada de su registro del cat├ílogo (la columna `ruta`, que `listar_videos`/`listar_videos_paginado` ahora incluyen como ├║ltima columna, menos el nombre relativo del video). Es la fuente de la carpeta para la generaci├│n de previews, de modo que la navegaci├│n (`carpeta_seleccionada`) ya no interviene.
- `Tarjeta._asegurar_slots_previews(cantidad)` / `ajustar_previews(cantidad)` ÔÇö **crecimiento din├ímico de slots** (Etapa B3.8): si la tarjeta fue creada con menos etiquetas que la cantidad solicitada, se crean `PreviewConTiempo` adicionales (con `dimensiones_miniatura()`, `eventFilter` y colocados antes del `addStretch()`), sin reconstruir la tarjeta; conservan selecci├│n, overlays, tama├▒o configurado y vista ampliada. `ajustar_previews` crece los slots, luego muestra/oculta y actualiza las previews existentes; disminuir la cantidad solo oculta (sin trabajo en segundo plano).
- `_aplicar_previews(resultado)` / `_al_resultado_previews(resultado)` ÔÇö al llegar el resultado de un lote, recorre `resultados` y llama `actualizar_previews(nombre, previews)` sobre la tarjeta correspondiente, **mostrando cada preview a medida que se genera**. **B4.6 Etapa 2 ÔÇö protecci├│n de resultados tard├¡os**: antes de aplicar valida que la carpeta del video del resultado (`item["ruta"]`) corresponda a la `_carpeta_video` de la tarjeta actual; un resultado tard├¡o de otra carpeta (cambio AÔåÆB) se ignora sin im├ígenes cruzadas.
- `TAMANIO_LOTE_PREVIEWS` ÔÇö constante de la interfaz: tama├▒o de lote (3 videos) de la generaci├│n de previews.
- `_al_resultado(resultado)` ÔÇö al recibir el resultado: oculta el estado de carga, **actualiza `_total_catalogo`** con el `total`, crea las tarjetas (`_crear_tarjetas`) y marca `_carga_completada`.
- `_al_error(mensaje)` ÔÇö al fallar la lectura: muestra `MENSAJE_ERROR` sin cerrar la ventana.
- `_crear_tarjetas(filas)` ÔÇö construye una `Tarjeta` por fila en la `QGridLayout` (una sola columna, una fila por video), **conecta la se├▒al `doble_clic` de cada tarjeta a `_abrir_video`** y reaplica el filtro vigente. **B4.6 Etapa 2 ÔÇö carga diferida de previews**: ya **no** carga las previews cacheadas al construir (las tarjetas parten con textos + miniatura principal + placeholders); las previews se incorporan despu├®s progresivamente por la tuber├¡a existente.
- `_abrir_video(nombre)` ÔÇö **apertura por doble clic**: toma `nombre` de la se├▒al y `self.carpeta_seleccionada` como carpeta, e invoca `abrir_video_con_aplicacion_predeterminada(nombre, self.carpeta_seleccionada)` (de `apertura_videos.py`, que resuelve y valida la ruta y ejecuta `os.startfile`). Si el servicio **falla** (`ValueError`, `FileNotFoundError` u `OSError`) muestra `MENSAJE_ERROR_ABRIR` en la etiqueta de estado; en ├®xito deja la etiqueta en blanco. Nunca propaga excepciones al gestor de eventos.
- `filtrar(texto)` ÔÇö filtrado por coincidencia de nombre **sobre todas las tarjetas actualmente cargadas en la interfaz**, sean de la primera p├ígina o de p├íginas agregadas manualmente con el bot├│n "Cargar m├ís"; mantiene `visibles` y actualiza el contador.
- `actualizar_contador()` ÔÇö muestra "N videos" / "1 video" seg├║n las tarjetas visibles.
- `_actualizar_resumen_seleccion()` / `resumen_seleccion` ÔÇö **resumen permanente de selecci├│n** (Etapa B3.11): una etiqueta en la barra de b├║squeda muestra "X de Y seleccionados", donde **Y = tarjetas visibles** (`self.visibles`) y **X = visibles seleccionadas** (intersecci├│n con `_nombres_seleccionados`). M├®todo ├║nico y centralizado; se invoca desde dos puntos de enganche que cubren todos los cambios: `_marcar_tarjeta` (selecci├│n simple/Ctrl/Shift, deselecci├│n, restauraci├│n) y `filtrar` (b├║squeda, carga inicial, "Cargar m├ís", reconstrucci├│n del cat├ílogo), m├ís el cierre de `_limpiar_seleccion`. Refleja ├║nicamente las tarjetas visibles (nunca el cat├ílogo completo); no altera layout, no produce parpadeos ni modifica el comportamiento de selecci├│n.
- **Modo Selecci├│n + Checks por fila** (Etapa B3.12) ÔÇö `boton_modo_seleccion` (toggle checkable en la barra) y `_modo_seleccion`; cada `Tarjeta` incorpora un `QCheckBox` (`_check`) en el ├¡ndice 0 del layout ra├¡z, **oculto por defecto**, visible solo cuando el modo est├í activo (`mostrar_check`). La sincronizaci├│n es **bidireccional y centralizada en `_marcar_tarjeta`**: toda mutaci├│n de selecci├│n actualiza el check (`set_check`, con `blockSignals` para evitar reentradas) y el check emite `seleccion_check(nombre, marcado)` ÔåÆ `_al_check_tarjeta` (muta `_nombres_seleccionados` y llama `_marcar_tarjeta`). `_nombres_seleccionados` permanece como **├║nica fuente de verdad**; activar/desactivar el modo solo alterna la visibilidad de los checks, conservando la selecci├│n y el resumen (B3.11) intactos. En   `_crear_tarjetas`/`_agregar_tarjetas` se conecta la se├▒al y se aplica el modo. Nota de implementaci├│n: `_al_check_cambiar` usa `self._check.isChecked()` (no `estado == Qt.Checked`) por la sem├íntica enum/int de PySide6.
- **Atajos b├ísicos de selecci├│n** (Etapa B3.13) ÔÇö dos `QShortcut` sobre la ventana principal: **Ctrl+A** (`_atajo_ctrl_a`) y **Esc** (`_atajo_esc`). `_atajo_seleccionar_todo`: si el foco est├í en el `QLineEdit` de b├║squeda, replica su comportamiento nativo (`selectAll()`) sin tocar las tarjetas; en caso contrario, `_seleccionar_todo_visible()` itera **`self.visibles`** (respeta el filtro activo), agrega a `_nombres_seleccionados` y llama `_marcar_tarjeta(nombre, True)`, cerrando con `_actualizar_resumen_seleccion()` (idempotente). `_atajo_salir_modo_seleccion`: si el modo est├í activo, `boton_modo_seleccion.setChecked(False)` (oculta solo los checks y conserva la selecci├│n y el resumen); si est├í inactivo, no hace nada. Se preserva el comportamiento del buscador y `_nombres_seleccionados` sigue siendo la ├║nica fuente de verdad.
- **Atajos de operaciones** (Etapa B3.17) ÔÇö tres `QShortcut` con el mismo patr├│n de B3.13: **Ctrl+C** (`_atajo_copiar`), **Ctrl+V** (`_atajo_pegar`) y **Supr** (`_atajo_eliminar`, `QKeySequence("Del")`). Cada handler (`_atajo_operacion_copiar`/`_atajo_operacion_pegar`/`_atajo_operacion_eliminar`) **reutiliza directamente** los handlers de los botones (`_iniciar_copia()`, `_iniciar_pegar()`, `_iniciar_eliminar()`), sin l├│gica paralela ni validaciones duplicadas (sin selecci├│n, sin portapapeles, gestor ocupado y carpeta inv├ílida ya est├ín cubiertos por esos m├®todos). Criterio de foco id├®ntico a Ctrl+A: si la b├║squeda tiene foco se **preserva el comportamiento nativo del `QLineEdit`** replic├índolo (`copy()`, `paste()` y `del_()`, este ├║ltimo el nombre de PySide6 para el slot `del`) y no se inicia ninguna operaci├│n.
- **Operaci├│n Copiar** (Etapa B3.14) ÔÇö `TareaCopiarArchivos(TareaBase)` ejecuta en segundo plano la l├│gica pura `operaciones.copiar_archivos(origen, archivos, destino, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22), usando un tercer gestor dedicado **`gestor_operaciones`** (independiente del pipeline y de las previews; se cierra en `closeEvent`). El bot├│n **"CopiarÔÇª"** en la barra (`_actualizar_boton_copiar` lo habilita con selecci├│n + carpeta v├ílida + gestores inactivos, incluida la **exclusi├│n mutua** con el pipeline) abre `QFileDialog.getExistingDirectory`; si el usuario cancela no hace nada. La tarea emite por `tarea_resultado` el resumen `{"copiados", "omitidos", "errores"}`; el slot `_al_resultado_copia` oculta la barra de progreso y muestra en `estado_escaneo` "Copiado: X ÔÇö Omitidos: Y ÔÇö Errores: Z" (sin atributos de estado permanentes). `copiar_archivos` copia con `shutil.copy2`, crea subdirectorios para nombres anidados, **omite** destinos ya existentes (nunca sobrescribe), registra errores por archivo y contin├║a. El cat├ílogo no se resincroniza (la copia exporta a otra carpeta sin alterar la escaneada).
- **Operaci├│n Pegar** (Etapa B3.15) ÔÇö usa un **portapapeles interno** (`self._portapapeles`, lista de rutas absolutas de los archivos copiados con ├®xito, alimentada en `_al_resultado_copia` desde `resumen["copiados"]`) y un bot├│n **"PegarÔÇª"** en la barra (`_actualizar_boton_pegar` lo habilita con portapapeles no vac├¡o + carpeta v├ílida + `gestor_operaciones` inactivo). `_iniciar_pegar` detecta colisiones (destino ya existente por `basename`) y, si las hay, muestra **un ├║nico di├ílogo modal** con botones "Omitir"/"Cancelar" (nunca sobrescribe); si el usuario cancela no inicia ninguna tarea. `TareaPegarArchivos(TareaBase)` ejecuta en segundo plano `operaciones.pegar_archivos(archivos, destino, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22) reutilizando el **mismo `gestor_operaciones`** de Copiar; un despachador (`_operacion_archivos` + `_al_resultado_operaciones`/`_al_error_operaciones`) enruta el resultado a `_al_resultado_pegar`/`_al_error_pegar`. `_al_resultado_pegar` oculta la barra de progreso, muestra el resumen "Pegado: X ÔÇö Omitidos: Y ÔÇö Errores: Z" en `estado_escaneo` y, si hubo copias, dispara la **resincronizaci├│n incremental** `_procesar_archivos_pegados(nombres)`: reutiliza la cadena existente (tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ guardado ÔåÆ sincronizaci├│n ÔåÆ recarga) fijando `videos_detectados` a los archivos pegados y usando un `TareaEscaneo(carpeta)` como portador de `.carpeta` (no iniciado); solo los archivos pegados pasan por FFprobe/miniaturas, sin reescaneo completo. **Correcci├│n de carrera (Etapa B3.18):** la carpeta se **captura al inicio** de `_procesar_archivos_pegados` y se fija en el override temporal `_carpeta_sincronizacion`, que `_iniciar_sincronizacion` consume en el paso de sincronizaci├│n; as├¡ la sincronizaci├│n usa **exactamente la carpeta capturada** aunque el usuario cambie de carpeta durante la cadena, evitando que se eliminen del cat├ílogo los registros reci├®n pegados. `_carpeta_sincronizacion` se limpia autom├íticamente (en `_iniciar_sincronizacion`, `_limpiar_cadena` e `iniciar_escaneo`).
- **Operaci├│n Eliminar** (Etapa B3.16) ÔÇö bot├│n **"EliminarÔÇª"** en la barra (`_actualizar_boton_eliminar` lo habilita con selecci├│n + carpeta v├ílida + `gestor_operaciones` inactivo). `_iniciar_eliminar` muestra **un ├║nico di├ílogo modal** de confirmaci├│n que indica la cantidad de archivos seleccionados, que ser├ín enviados a la Papelera de reciclaje y que podr├ín restaurarse desde all├¡; botones "Eliminar"/"Cancelar" (default Cancelar; si cancela no inicia ninguna tarea). `TareaEliminarArchivos(TareaBase)` ejecuta en segundo plano `operaciones.eliminar_archivos(archivos, self.reportar_progreso)` (progreso real por archivo, Etapa B3.22) reutilizando el **mismo `gestor_operaciones`** de Copiar/Pegar; el despachador (`_operacion_archivos` + `_al_resultado_operaciones`/`_al_error_operaciones`) enruta a `_al_resultado_eliminar`/`_al_error_eliminar`. `_al_resultado_eliminar` muestra el resumen "Eliminado: X ÔÇö Omitidos: Y ÔÇö Errores: Z" y, si hubo eliminaciones, dispara (diferido con `QTimer.singleShot(0)`, para que el resumen sea visible) la **actualizaci├│n incremental del cat├ílogo** `_procesar_archivos_eliminados`: reutiliza el **paso de sincronizaci├│n existente** (`TareaSincronizacionCatalogo`, que detecta los archivos ausentes y los elimina) seguido de la recarga, **sin reescaneo completo** (no pasa por FFprobe ni miniaturas). **Correcci├│n de carrera (Etapa B3.18):** igual que en Pegar, `_procesar_archivos_eliminados` **captura la carpeta al inicio** y la fija en `_carpeta_sincronizacion`, de modo que la sincronizaci├│n opera sobre la carpeta de la operaci├│n y no sobre `carpeta_seleccionada` si ├®sta cambi├│.
- `seleccion_carpetas.py` ÔÇö **conjunto de carpetas seleccionadas por ruta** (Bloque de trabajo 4, "Selecci├│n personalizada", primera etapa). Clase pura `SeleccionCarpetas(ruta_config=None)`: mantiene el conjunto como **├║nica fuente de verdad** (`set` de rutas absolutas), sin dependencia del ├írbol ni de Qt. API: `seleccionar(ruta)` (agrega solo carpetas existentes; ignora inexistentes/valores inv├ílidos), `deseleccionar(ruta)`, `alternar(ruta)` (devuelve el estado resultante), `limpiar()`, `seleccionar_todas(lista)` (agrega las existentes sin duplicar; devuelve la cantidad), `obtener_seleccion()` (devuelve una **copia**). Persiste en configuraci├│n (clave `carpetas_seleccionadas`, patr├│n at├│mico `.tmp`+`os.replace`) tras cada cambio real y **restaura en el constructor descartando rutas inexistentes**. `visor_videos.py` lo instancia al iniciar (`self.seleccion_carpetas`). Sin intervalos internos, sin UI, sin cambios en escaneo/SQLite/pipeline. `configuracion.py` expone `guardar_seleccion_carpetas(rutas, ruta_config=None)` (normaliza y deduplica, conserva las dem├ís claves) y `obtener_seleccion_carpetas(ruta_config=None)` (descarta rutas inexistentes; configs anteriores/inv├ílidas ÔåÆ lista vac├¡a).
- `configuracion.py` ÔÇö **modo de alcance del escaneo** (Etapa 6): constantes `MODO_ALCANCE_SOLO`/`MODO_ALCANCE_SUBCARPETAS`/`MODO_ALCANCE_SELECCION` (`MODOS_ALCANCE_VALIDOS`), `CLAVE_MODO_ALCANCE`, `guardar_modo_alcance(modo, ruta_config=None)` (persiste el modo y mantiene sincronizada la clave booleana `incluir_subcarpetas` para compatibilidad) y `obtener_modo_alcance(ruta_config=None)` con **migraci├│n retrocompatible**: si no hay modo v├ílido, migra desde el booleano `incluir_subcarpetas` (True ÔåÆ "con_subcarpetas", False ÔåÆ "solo_carpeta"); default "solo_carpeta". `visor_videos.py` lo restaura al iniciar (`self._modo_alcance`) y lo expone en `combo_modo_alcance` (├║nica fuente de verdad visible); el checkbox "Incluir subcarpetas" queda como adaptador de compatibilidad oculto.
- `operaciones.py` ÔÇö m├│dulo de **l├│gica pura de operaciones sobre archivos** (incorporado a la arquitectura en B3.14; conserva `sumar`): `copiar_archivos(origen, archivos, destino, on_progreso=None)` valida los argumentos (`origen`/`destino` texto no vac├¡o; `archivos` colecci├│n no texto), copia con `shutil.copy2` preservando metadatos, crea directorios padre, omite archivos existentes, captura `OSError` por archivo y devuelve el resumen `{"copiados": [rutas], "omitidos": [rutas], "errores": [(ruta, mensaje)]}`. `pegar_archivos(archivos, destino, on_progreso=None)` (B3.15) copia cada ruta de origen con `shutil.copy2` a `os.path.join(destino, os.path.basename(ruta))`, **omite** destinos ya existentes (nunca sobrescribe), registra errores por archivo (`OSError` o origen inexistente) y contin├║a, devolviendo el mismo resumen. `eliminar_archivos(archivos, on_progreso=None)` (B3.16) env├¡a cada ruta a la **Papelera de reciclaje de Windows mediante la API nativa `SHFileOperationW` a trav├®s de `ctypes`** (`_SHFILEOPSTRUCTW` con `FO_DELETE` + `FOF_ALLOWUNDO`, `FOF_NOCONFIRMATION`, `FOF_NOERRORUI` y `FOF_SILENT`; `pFrom` con lista de doble NUL), una invocaci├│n por archivo para aislar errores y continuar; **nunca borra permanentemente**; origen inexistente o archivo bloqueado se registran como errores; devuelve `{"eliminados": [rutas], "omitidos": [], "errores": [(ruta, mensaje)]}`. **Callback de progreso opcional** (Etapa B3.22): las tres funciones emiten `on_progreso(indice + 1, total)` **una vez por archivo** (incluyendo omitidos y errores); sin callback, el comportamiento es id├®ntico. **Sin dependencias externas** y sin Qt, SQLite ni pipeline.
- `closeEvent(event)` ÔÇö apagado ordenado: detiene `_timer_previews`, llama `gestor.cerrar()`, `gestor_previews.cerrar()` y `gestor_marcadores.cerrar()` (timeout por defecto 5000 ms) y acepta el evento.
- **Clasificaci├│n visual por color (B6.3) en la interfaz.** La `Tarjeta` incorpora un selector
  `_selector_color` (QComboBox "Sin clasificar" + los 6 colores de la paleta, textos con
  `texto_color`); el color activo se adjunta a los marcadores y segmentos nuevos que se crean
  en esa tarjeta. Los **men├║s contextuales** de marcador y de segmento incluyen el submen├║
  **"Asignar color"** (6 colores + "Sin clasificar", deshabilitado si el ├¡tem ya no tiene
  color); en el marcador el clic derecho ya **no elimina** directamente (ofrece "Eliminar
  marcador" dentro del men├║). Las operaciones se enrutan como tipo `"color"` en la cola de
  los gestores dedicados y, ante error, se **revierte el color previo**; la marca/banda local
  se recolorea de inmediato (`set_marcadores`/`set_segmentos`). **Correcci├│n del defecto
  PySide/QMenu**: los submen├║s se crean con el men├║ como padre `QObject`
  (`QMenu("Asignar color", menu)`) y se conservan las referencias
  (`_submenu_marcador_color_actual` / `_submenu_segmento_color_actual`), evitando que PySide
  libere el submen├║ antes de mostrarlo. `PreferenciasDialog` gana la secci├│n **"Nombres de
  colores de la clasificaci├│n"** (muestra del color + `QLineEdit` por clave, l├¡mite de 40, y
  al aceptar persiste con `guardar_nombre_color`); `_refrescar_textos_colores` actualiza los
  textos del selector y los men├║s se construyen por demanda con `texto_color`.
- `miniatura_principal(nombre)` ÔÇö ubica la primera miniatura cuyo prefijo coincide con el video, **excluyendo los archivos `_preview_`** (`_es_archivo_preview`), de modo que la miniatura principal nunca es un preview.
- `main()` ÔÇö **punto de entrada de producci├│n**: solo inicia la interfaz gr├ífica ÔÇö`QApplication(sys.argv)`, `VisorVideos()`, `resize(900, 600)`, `show()` y `sys.exit(app.exec())`ÔÇö. **No ejecuta pruebas autom├íticamente**: el arranque normal ya no lanza el smoke test, que se independiz├│ en el arn├®s `prueba_smoke.py` (ver la secci├│n siguiente).

### `prueba_smoke.py` ÔÇö arn├®s de smoke tests (ejecuci├│n expl├¡cita)
Arn├®s independiente del arranque normal: contiene el **smoke test del pipeline completo** que viv├¡a dentro de `visor_videos.main()`, movido sin cambios de comportamiento (el ├║nico ajuste es el parcheo de la fase de doble clic, que ahora apunta a `visor_videos.abrir_video_con_aplicacion_predeterminada`). Se ejecuta **expl├¡citamente** con `python prueba_smoke.py`; la aplicaci├│n normal no lo ejecuta al iniciar. Crea una **base SQLite temporal** reutilizando el esquema existente (`conectar_bd(ruta_db)` + `commit()` + `close()`, sin depender de `biblioteca.db`) y verifica el pipeline completo por fases:
- **Fase de paginaci├│n** ÔÇö inserta 150 registros (`guardar_videos`) y verifica la carga inicial (`primera_pagina=100`, `contador_primera_pagina=100 videos`, `cargar_mas_habilitado=True`), dispara "Cargar m├ís" (`boton_cargar_mas.click()`), espera el fin de la p├ígina y comprueba `total_tras_cargar_mas=150`, **cero duplicados** (`duplicados_tras_cargar_mas=0`), `primeras_conservadas=True` y `contador_tras_cargar_mas=150 videos`.
- **Fase de escaneo + carpeta + sincronizaci├│n** ÔÇö verifica el estado inicial sin carpeta ("Sin escanear" y bot├│n de escanear deshabilitado), simula la selecci├│n y la cancelaci├│n de una carpeta temporal (di├ílogo inyectado y siempre restaurado) con archivos de video y no-video, espera la carga as├¡ncrona, dispara el escaneo real con `boton_escanear.click()`, espera la cadena completa escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ guardado ÔåÆ sincronizaci├│n y comprueba `videos_detectados` (3 videos), `guardado_total=3`, `resumen_sincronizacion=Sincronizaci├│n completa: 0 incorporados, 0 eliminados, 0 candidatos restantes`, el estado final y el filtro con "real".
- **Fase de previews progresivos** ÔÇö con la **carpeta real `videos_prueba/`** ejecuta la cadena completa del pipeline y espera a que el gestor de previews quede `inactivo` (cola vac├¡a y temporizador parado); imprime `previews_archivos` (archivos `_preview_` presentes en `miniaturas/`), `previews_pixmaps` (etiquetas con pixmap) y `previews_tarjetas`.
- **Fase de doble clic** ÔÇö `QTest.mouseDClick` real sobre la tarjeta del video real de `videos_prueba/` con `abrir_video_con_aplicacion_predeterminada` **parcheado** (se captura la invocaci├│n y se restaura despu├®s); imprime `abrir_nombre`, `abrir_ruta`, `abrir_mensaje` y `abrir_con_aplicacion`.
- **Fase de persistencia** ÔÇö con una configuraci├│n temporal (`VISOR_CONFIG`) verifica la restauraci├│n de la ├║ltima carpeta; imprime `config_ruta`, `persistencia_restaurada` y `persistencia_sin_carpeta`.
- `main()` termina con `exit 0` solo si todas las fases pasan, **sin avisos `QThread: Destroyed`**. Las suites de interfaz `prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py` y `prueba_recarga_catalogo.py` invocan este arn├®s v├¡a `subprocess` (`["prueba_smoke.py"]`).

### `tareas.py` ÔÇö infraestructura gen├®rica de trabajos en segundo plano
- `Estado` ÔÇö estados del ciclo de vida: `inactivo`, `ocupado`, `finalizando`, `cerrado`.
- `TareaBase(QObject)` ÔÇö clase base de tareas as├¡ncronas; se├▒ales `inicio`, `finalizada`, `error(str)`, `resultado(object)` y **`progreso(int, int)`** (infraestructura de progreso, Etapa B3.20). `ejecutar()` emite `inicio`, invoca `_trabajo()` y emite `resultado(valor)`; ante una excepci├│n emite `error(f"{Tipo}: {msg}")`; siempre emite `finalizada`. Las subclases implementan `_trabajo()`. La emisi├│n de `progreso` es **opcional y aditiva** (`ejecutar()` no se modifica y ninguna tarea existente emite progreso todav├¡a); `reportar_progreso(procesado, total)` es un helper que convierte a `int` (ignora inv├ílidos), ignora `total <= 0` (indeterminado), acota `procesado` a `[0, total]` y emite `self.progreso` ÔÇö las subclases pueden tambi├®n emitir `self.progreso.emit(...)` directamente.
- `GestorTareas(QObject)` ÔÇö orquesta cada tarea en un `QThread` propio. Se├▒ales `tarea_iniciada`, `tarea_resultado(object)`, `tarea_error(str)`, `tarea_finalizada`, **`tarea_progreso(int, int)`** y `actividad_cambiada(bool)`. `iniciar(tarea)` valida la tarea, crea el `QThread`, la mueve a ├®l y lo arranca; conecta `tarea.progreso ÔåÆ relay.al_progreso` (reenv├¡o con el mismo criterio del token `_vigente`, descartando emisiones tard├¡as tras cerrar o reemplazar la tarea); el hilo termina cuando la tarea emite `finalizada`. `cerrar(timeout_ms)` permite el apagado ordenado.

### `tareas_videos.py` ÔÇö tareas as├¡ncronas espec├¡ficas de video
Capa de **tareas as├¡ncronas**: no define l├│gica de cat├ílogo ni de datos. Re-exporta desde `escanear_videos.py` las funciones que la interfaz necesita importar (entre ellas `preparar_registros_basicos`, `combinar_registros_con_ffprobe`, `combinar_registros_con_tamanos`, `obtener_tamanos_archivos`, `previews_existentes`, `calcular_tiempo_preview`, `generar_previews_faltantes` y `conectar_bd`), lo que evita que `visor_videos.py` dependa directamente del backend de cat├ílogo.
- `rutas_videos()` ÔÇö rutas absolutas de los videos de `videos_prueba/` detectados por `escanear_videos`.
- `TareaFFprobe(TareaBase)` ÔÇö ejecuta `obtener_datos_ffprobe` sobre una lista de rutas en segundo plano; devuelve un diccionario con `rutas`, `resultados`, `procesados`, `con_datos` y `con_error`. Cada resultado contiene `ruta`, `datos` y `error` por archivo. **Progreso real** (Etapa B3.21): recorre las rutas con un bucle expl├¡cito y emite `reportar_progreso(indice + 1, total)` tras cada ruta. **B4.5 Etapa 3 ÔÇö reutilizaci├│n de metadata**: acepta adem├ís `nombres`, `stats` (resultado de `obtener_tamanos_archivos` con `tamano_bytes`/`mtime_ns` por ruta) y `ruta_db`; si est├ín presentes, consulta los registros previos por lote (`listar_registros_por_nombres`), clasifica con `_metadata_reutilizable` (criterio ruta normalizada + tama├▒o + `mtime_ns` + metadata v├ílida) y ejecuta FFprobe **solo** para los videos nuevos/cambiados/sin `mtime_ns`/con metadata inv├ílida; los reutilizables emiten `datos` con la metadata de la BD. El resultado final tiene el mismo formato para todos (indistinguible por origen). Sin esos par├ímetros conserva el comportamiento anterior (FFprobe para todas las rutas).
- `TareaEscaneo(TareaBase)` ÔÇö recibe una carpeta y devuelve la misma lista ordenada de archivos de video que `escanear_videos(carpeta)`. Una carpeta inexistente (`FileNotFoundError`) o una ruta que no es carpeta (`NotADirectoryError`) se propaga mediante la se├▒al `error` de la infraestructura.
- `TareaTamanosArchivos(TareaBase)` ÔÇö recibe la lista de nombres de video y la carpeta escaneada, conserva una instant├ínea (`list(...)`; `None` ÔåÆ lista vac├¡a, texto ÔåÆ lista de un elemento) y expone las propiedades de solo lectura `videos` (copia) y `carpeta`. `_trabajo()` invoca `obtener_tamanos_archivos(videos, carpeta, self.reportar_progreso)` (progreso real por video, Etapa B3.21) y devuelve su resumen `{"rutas", "resultados", "procesados", "con_tamano", "sin_tamano"}` (un `dict` con `tamano_bytes` y `mtime_ns` por ruta, obtenidos con un ├║nico `os.stat` ÔÇö B4.5 Etapa 3; `None` si el archivo no existe o es ilegible). Los errores de contrato (`TypeError`/`ValueError`) y `FileNotFoundError` se convierten en la se├▒al `error` gestionada por `TareaBase`. No abre SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas ni toca la interfaz.
- `TareaMiniaturas(TareaBase)` ÔÇö recibe la lista de nombres de video, la carpeta escaneada y, desde **B4.5**, un mapa opcional `duraciones` (por ruta o por nombre); conserva una instant├ínea (`list(...)`), y `_trabajo()` invoca `asegurar_miniaturas(videos, carpeta, self.reportar_progreso, self._duraciones)` (progreso real por video, Etapa B3.21) y devuelve su resumen `{"rutas", "resultados", "procesados", "con_miniatura", "sin_miniatura"}`. Con duraciones disponibles evita el FFprobe interno de `generar_miniatura` (B4.5). Los errores de contrato (`TypeError`/`ValueError`) se convierten en la se├▒al `error` gestionada por `TareaBase`. Ejecuta FFmpeg y FFprobe ├║nicamente dentro de la tarea (nunca en el hilo principal); no abre SQLite ni toca la interfaz. Re-exporta `asegurar_miniaturas` y `combinar_registros_con_miniaturas` desde `escanear_videos`.
- `TareaPreviewsProgresivas(TareaBase)` ÔÇö genera los **previews progresivos** de una lista de videos en segundo plano: conserva una instant├ínea de los nombres (`list(...)`) y la carpeta, expone las propiedades de solo lectura `videos` (copia) y `carpeta`, y `_trabajo()` invoca `generar_previews_faltantes(videos, carpeta, self._duraciones)` (con el mapa opcional `duraciones` desde **B4.5**) devolviendo su resumen `{"rutas", "resultados", "procesados", "con_previews", "sin_previews"}` (cada resultado incluye `nombre`, `previews` ÔÇörutas de los 1..3 existentesÔÇö, `generados`, `reutilizados`, `errores` y `completos`). Con duraciones disponibles evita el FFprobe interno de `generar_preview` (B4.5). Los errores de contrato (`TypeError`/`ValueError`) se convierten en la se├▒al `error` gestionada por `TareaBase`. FFmpeg se ejecuta ├║nicamente dentro de la tarea (nunca en el hilo principal); no abre SQLite, no consulta la BD ni toca la interfaz. La interfaz la ejecuta con un **segundo `GestorTareas`** (`gestor_previews`) en lotes de a 3 videos.
- `TareaLecturaCatalogo(TareaBase)` ÔÇö lee el cat├ílogo en segundo plano invocando `listar_videos(ruta_db)`; devuelve la misma estructura que la lectura s├¡ncrona. Acepta una ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Regla de conexi├│n SQLite por hilo**: la conexi├│n se abre y se cierra dentro del hilo de trabajo, se usa ├║nicamente en ese hilo, no se almacena como atributo persistente de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores de lectura (`FileNotFoundError` si la base no existe, `sqlite3.OperationalError`, `sqlite3.DatabaseError`, etc.) se convierten en la se├▒al `error` gestionada por `TareaBase`. La lectura no crea archivos: si la base no existe, se comunica `FileNotFoundError` sin crear la base.
- `TareaLecturaCatalogoPaginada(TareaBase)` ÔÇö lectura **paginada** del cat├ílogo en segundo plano. Recibe los mismos par├ímetros que `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` (ruta de base opcional; por defecto `ruta_biblioteca()`). El constructor conserva una instant├ínea de los par├ímetros (escalares inmutables) y expone las propiedades `limite`, `desplazamiento`, `texto` y `ruta_db`. `_trabajo()` invoca `listar_videos_paginado` y devuelve exactamente su resultado `{"videos", "total", "limite", "desplazamiento"}`. **Regla de conexi├│n SQLite por hilo**: la conexi├│n se abre y se cierra dentro del hilo de trabajo (mediante la funci├│n s├¡ncrona), se usa ├║nicamente en ese hilo, no se almacena como atributo y no se usa `check_same_thread=False`. Los errores de contrato (`TypeError`/`ValueError`), `FileNotFoundError` si la base no existe y `sqlite3.DatabaseError` si la base est├í corrupta se convierten en la se├▒al `error` gestionada por `TareaBase`. No accede a la interfaz, no escanea archivos, no ejecuta FFprobe ni FFmpeg y no escribe en SQLite. `TareaLecturaCatalogo` conserva su contrato sin cambios.
- `TareaGuardarVideo(TareaBase)` ÔÇö guarda un ├║nico registro de video en segundo plano invocando `guardar_video(datos, ruta_db)`; devuelve el resultado simple `{"guardado": True, "nombre": ...}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instant├ínea del registro**: el constructor toma una copia superficial (`self._datos = dict(datos)`), de modo que mutaciones posteriores del diccionario original del llamador no afectan la ejecuci├│n; la propiedad `datos` devuelve una copia y nunca expone el diccionario interno. Un valor que `dict()` no pueda copiar se conserva como `datos` inv├ílido y `_trabajo()` lo comunica mediante `error` (`TypeError`) sin tocar la base. **Regla de conexi├│n SQLite por hilo**: la conexi├│n se abre dentro de `_trabajo()` (mediante la funci├│n s├¡ncrona), se usa ├║nicamente en ese hilo, el `commit` se ejecuta en el hilo de trabajo solo si toda la operaci├│n termin├│ correctamente, se ejecuta `rollback` ante cualquier error posterior al inicio de la transacci├│n, se cierra siempre en `finally`, no se almacena como atributo de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores (`FileNotFoundError` si la base no existe, `sqlite3.DatabaseError` si la base est├í corrupta, `ValueError`/`TypeError` por contrato inv├ílido, etc.) se convierten en la se├▒al `error`. No sincroniza el cat├ílogo, no elimina registros, no encadena tareas y no se conecta a la interfaz.
- `TareaGuardarVideos(TareaBase)` ÔÇö guarda una **colecci├│n de registros** en segundo plano invocando `guardar_videos(datos_videos, ruta_db, self.reportar_progreso)` (progreso real por registro, Etapa B3.21); devuelve el resumen `{"guardados": <cantidad>, "nombres": [...]}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instant├ínea de la colecci├│n y de cada registro**: el constructor materializa la colecci├│n (`list(...)`) y toma una **copia superficial por registro** (`dict(d)`) al construirse; no conserva la colecci├│n mutable original, de modo que mutaciones posteriores de la lista o de los diccionarios del llamador no afectan la ejecuci├│n; la propiedad `datos` devuelve copias frescas y nunca expone el estado interno. **El constructor nunca lanza ante entradas inv├ílidas**: si la colecci├│n no es iterable, es texto, contiene un elemento no copiable, o incluso si su materializaci├│n falla a mitad de la iteraci├│n (p. ej. un generador que lanza una excepci├│n), la tarea se construye igualmente, se conserva la causa como colecci├│n inv├ílida y `_trabajo()` la comunica mediante `error` (un `TypeError` que envuelve la causa) sin tocar la base; los errores de contrato que solo `guardar_videos` detecta al validar (p. ej. una clave obligatoria ausente en un registro ya copiado) tambi├®n se comunican por `error` durante la ejecuci├│n. **Regla de conexi├│n SQLite por hilo**: la conexi├│n se abre dentro de `_trabajo()` (mediante la funci├│n s├¡ncrona) y realiza un ├║nico `commit` por colecci├│n en el hilo de trabajo; `rollback` ante cualquier error; se cierra siempre en `finally`; no se almacena como atributo de la tarea; sin `check_same_thread=False`. Los errores (`FileNotFoundError`, `sqlite3.DatabaseError`, `ValueError`/`TypeError` por contrato inv├ílido, fallo durante el registro intermedio con rollback total) se convierten en la se├▒al `error`. No sincroniza el cat├ílogo, no elimina registros, no encadena tareas, no implementa escritura por lotes concurrentes y no se conecta a la interfaz.
- `TareaSincronizacionCatalogo(TareaBase)` ÔÇö **sincronizaci├│n as├¡ncrona del cat├ílogo**: orquesta en segundo plano la sincronizaci├│n disco Ôåö BD encadenando las cuatro operaciones de la capa de cat├ílogo en la secuencia exacta `detectar_diferencias` ÔåÆ `preparar_plan_sincronizacion` ÔåÆ `aplicar_incorporaciones` ÔåÆ `eliminar_candidatos`. El constructor recibe `carpeta` (ruta de texto de la carpeta de videos) y `ruta_db` **opcional** (ruta SQLite; por defecto se delega el default a las funciones de `escanear_videos`, es decir `ruta_biblioteca()`), m├ís `parent` como **padre Qt compatible con `QObject`** (no espec├¡ficamente un `QWidget`) y `carpetas_protegidas` **opcional** (Etapa 5: ra├¡ces del alcance multicarpeta a proteger); conserva ambos valores y los expone mediante las propiedades de solo lectura `carpeta` y `ruta_db`, que **devuelven directamente los valores actualmente inmutables (`str` o `None`) recibidos en el constructor** ÔÇö no realizan copias generales ni devuelven nuevas copias. `_trabajo()` invoca las cuatro funciones mediante el m├│dulo `escanear_videos` en el orden exacto indicado (pasando `carpetas_protegidas` a `detectar_diferencias`) y devuelve el resultado `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`; `resumen` contiene `nuevos`, `ya_sincronizados`, `incorporados`, `eliminados` y `candidatos_restantes` (no se afirma que el resultado completo sea inmutable). **La tarea no contiene SQL, no abre SQLite directamente, no almacena conexiones y no usa `check_same_thread=False`**: todo el acceso a la base ocurre dentro de las funciones s├¡ncronas de `escanear_videos`, cada una con su propia conexi├│n abierta y cerrada en el hilo de trabajo. **No ejecuta FFprobe, FFmpeg, miniaturas ni subprocesos y no accede a la interfaz.** **Atomicidad**: la incorporaci├│n y la eliminaci├│n son **transacciones independientes**, no una ├║nica transacci├│n global; si falla la incorporaci├│n **no se ejecuta la eliminaci├│n** (la excepci├│n propaga y `TareaBase` emite `error`); si falla la eliminaci├│n, las **incorporaciones ya confirmadas permanecen** y la eliminaci├│n fallida revierte **├║nicamente su propia transacci├│n** (rollback interno de `eliminar_candidatos`), sin revertir las incorporaciones previas. Se ejecuta en segundo plano por la infraestructura `tareas.py` (`TareaBase` + `GestorTareas` en un `QThread` por ejecuci├│n) con las se├▒ales `inicio`, `resultado`, `error` y `finalizada`; el hilo de trabajo es distinto del principal. **No est├í integrada todav├¡a con `visor_videos.py`**: la tarea existe como pieza orquestadora y la **pr├│xima etapa pendiente es integrar esta tarea con el flujo de la interfaz**.

- `TareaListarMarcadores(TareaBase)` ÔÇö **lectura as├¡ncrona de marcadores** (B4.2): recibe
  `video_id` (y `ruta_db` opcional) y `_trabajo()` invoca `listar_marcadores(video_id, ruta_db)`,
  devolviendo su resultado (lista de tuplas `(id, video_id, tiempo, color)` desde **B6.3**).
  Expone las propiedades
  de solo lectura `video_id` y `ruta_db`. Los errores de contrato y de lectura se convierten
  en la se├▒al `error` gestionada por `TareaBase`. Conexi├│n abierta y cerrada en el hilo de
  trabajo (patr├│n de `TareaLecturaCatalogo`).
- `TareaGuardarMarcador(TareaBase)` ÔÇö **persistencia as├¡ncrona de un marcador** (B4.2): recibe
  `video_id`, `tiempo` y `ruta_db` opcional; **B6.3** acepta adem├ís `color` (clave estable o
  `None`, persistido en el mismo `INSERT`). `_trabajo()` invoca
  `guardar_marcador(video_id, tiempo, ruta_db, color)` y devuelve el **`id` de la base**. El
  `commit` y el `rollback` ocurren dentro del hilo de trabajo. Expone las propiedades
  `video_id`, `tiempo`, `color` y `ruta_db`.
- `TareaEliminarMarcador(TareaBase)` ÔÇö **eliminaci├│n as├¡ncrona de un marcador** (B4.2): recibe
  `marcador_id` (y `ruta_db` opcional); `_trabajo()` invoca
  `eliminar_marcador(marcador_id, ruta_db)` y devuelve `True`/`False`. Expone las propiedades
  `marcador_id` y `ruta_db`. La interfaz la ejecuta con un **gestor dedicado**
  (`gestor_marcadores`, cuarto gestor), no con el gestor principal ni el de previews.
- `TareaAsignarColorMarcador(TareaBase)` ÔÇö **asignaci├│n as├¡ncrona de color a un marcador**
  (B6.3): recibe `marcador_id`, `color` (clave estable o `None` = quitar) y `ruta_db`
  opcional; `_trabajo()` invoca `asignar_color_marcador(marcador_id, color, ruta_db)` y
  devuelve la fila persistida `(id, video_id, tiempo, color)` o `None`. Expone las propiedades
  `marcador_id`, `color` y `ruta_db`. Mismo gestor dedicado que las dem├ís operaciones de
  marcadores.
- `TareaAsignarColorSegmento(TareaBase)` ÔÇö **asignaci├│n as├¡ncrona de color a un segmento**
  (B6.3): recibe `segmento_id`, `color` (clave estable o `None` = quitar) y `ruta_db`
  opcional; `_trabajo()` invoca `asignar_color_segmento(segmento_id, color, ruta_db)` y
  devuelve la fila persistida `(id, inicio, fin, color)` o `None`. Expone las propiedades
  `segmento_id`, `color` y `ruta_db`. Mismo patr├│n que la instrucci├│n de segmentos del gestor
  dedicado de la interfaz.
- `TareaExploracionDensa(TareaBase)` ÔÇö **cobertura densa de exploraci├│n temporal de un video**
  (B4.3.2 / B4.3.3): recibe `video_id`, `ruta_video`, `duracion`, `parent` y, desde B4.3.3,
  `objetivo_manual` (None = Auto); captura **instant├íneas inmutables** y expone las propiedades
  de solo lectura `video_id`, `ruta_video`, `duracion` y `objetivo_manual`. `_trabajo()` calcula
  el objetivo total como `objetivo_manual` si es positivo o `objetivo_total_densidad(duraci├│n)`
  en Auto, y genera en **dos fases secuenciales**: la **fase r├ípida** produce los
  **`FOTOGRAMAS_INICIALES = 15`** prioritarios y, solo despu├®s de terminar y sin cancelarse, la
  **fase secundaria** completa hasta el objetivo reutilizando lo existente (un FFmpeg por
  objetivo, serial, sin batch). En cada fase se construye expl├¡citamente el **conjunto
  permitido** `tiempos_objetivo(duraci├│n, cantidad_actual)` y la emisi├│n (`resultado_parcial`)
  y la cola final **solo decodifican/emiten ese subconjunto**: la cach├® en disco puede contener
  un **superset** (densidades manuales previas) y la tarea decide qu├® subconjunto utiliza. En
  ambas fases emite **resultados parciales progresivos** a trav├®s de la se├▒al
  **`resultado_parcial = Signal(object)`** (un diccionario con `video_id`, `version` y una lista
  `(ms, QImage)` ya decodificada en el worker) y termina con la cola final
  `{"imagenes": [(ms, QImage), ...]}` de los fotogramas a├║n no emitidos. La decodificaci├│n de
  los JPEG (`QImage`) ocurre **en el hilo de trabajo**; la conversi├│n a `QPixmap` y su
  aplicaci├│n se delega a la GUI. Usa la **cancelaci├│n cooperativa** de la cach├® para abortar la
  generaci├│n al cambiar de video/tarjeta (la fase secundaria no arranca si la tarea fue
  cancelada). No abre SQLite y no toca la interfaz.

### `exploracion_temporal.py` ÔÇö l├│gica pura de exploraci├│n temporal (B4.1 y B4.3.1)
M├│dulo **puro** (sin Qt, sin FFmpeg, sin SQLite, sin archivos ni cach├® persistente) que
concentra el mapeo espacial/temporal, la selecci├│n de la preview existente m├ís cercana y la
**densidad/orden de la cach├® densa de exploraci├│n** (B4.3.1):

- `ancho_valido(ancho)` / `duracion_valida(duracion)` ÔÇö validaci├│n de ancho (px) y duraci├│n (s)
  como n├║meros positivos no `bool`.
- `normalizar_posicion(posicion, ancho)` ÔÇö acota la posici├│n horizontal al intervalo `[0, ancho]`
  (devuelve `None` si el ancho o la posici├│n no son v├ílidos).
- `posicion_a_tiempo(posicion, ancho, duracion)` ÔÇö **mapeo posici├│n ÔåÆ instante**: `x=0 ÔåÆ 0`,
  `x=ancho ÔåÆ duracion`, proporcional en el medio; fuera de rango se acota. Es la base de la
  conversi├│n del cursor en la superficie temporal.
- `tiempo_a_posicion(instante, ancho, duracion)` ÔÇö inversa (instante ÔåÆ px), usada para dibujar el
  marcador m├│vil, las marcas persistentes y posicionar la preview m├│vil.
- `preview_mas_cercana(instantes, instante)` ÔÇö ├¡ndice de la preview (dentro de la lista original)
  cuyo **tiempo real** es el m├ís cercano al instante solicitado por distancia temporal absoluta;
  descarta `None` y en empate elige el menor ├¡ndice. No es "posici├│n dentro de la lista": usa el
  tiempo asociado a cada preview.
- `agregar_marcador_ordenado(instante, marcadores, tolerancia)` ÔÇö inserta el instante real
  conservando el orden temporal y evitando duplicados absurdamente cercanos.
- `cantidad_fotogramas(duracion)` ÔÇö **densidad de la cach├® densa** (B4.3.1):
  `clamp(round(duraci├│n / PASO_SEGUNDOS), MINIMO_FOTOGRAMAS, MAXIMO_FOTOGRAMAS)` con
  `PASO_SEGUNDOS = 2.0`, piso 40 y techo 200 (aprobados provisionalmente en el dise├▒o de B4.3);
  duraci├│n inv├ílida ÔåÆ 0 (sin cach├® posible).
- `tiempos_objetivo(duracion, cantidad)` ÔÇö instantes objetivo en **milisegundos enteros** en
  **orden progresivo de cobertura** (B4.3.1): la cobertura crece por **bisecci├│n de huecos**
  (primero el punto medio 50 %, luego los cuartos 25/75 %, luego los octavos 12.5/37.5/62.5/
  87.5 %, y as├¡), de izquierda a derecha en cada nivel. Es el orden de generaci├│n recomendado:
  pocos fotogramas bien repartidos al inicio y densidad creciente despu├®s (base de la estrategia
  h├¡brida de B4.3.2). Descarta duplicados por redondeo.
- `fotograma_mas_cercano(ms_existentes, instante)` ÔÇö milisegundo del fotograma existente m├ís
  cercano al instante pedido (segundos ÔåÆ ms) por **`bisect`**; en empate de distancia elige el
  fotograma anterior (menor instante).

### `scrubber.py` ÔÇö superficie temporal y miniatura de marcador (B4.1)
M├│dulo **de interfaz** con dos clases:

- `FranjaExploracion(QWidget)` ÔÇö la **superficie temporal**: toda la segunda fila expandida
  representa la duraci├│n completa del video (izquierda = 0 %, derecha = 100 %). Convierte el
  movimiento del mouse (usa **solo la coordenada X**; la altura es irrelevante) en la se├▒al
  `instante_seleccionado(float)`, el clic izquierdo en `marcador_solicitado(float)` y el clic
  derecho sobre una marca en `marcador_contextual_solicitado(float)` (**B6.3**; antes
  `marcador_eliminar_solicitado`, por el men├║ contextual). Dibuja la pista, el marcador
  m├│vil azul del cursor, las marcas persistentes (color de clasificaci├│n o rojo hist├│rico,
  B6.3) y el texto del tiempo. No conoce videos,
  previews, FFmpeg, SQLite ni cach├®.
- `MiniaturaMarcador(QLabel)` ÔÇö miniatura fijada de un marcador: recibe el **clic derecho** y
  emite `contextual_solicitado(tiempo)` (**B6.3**; antes `eliminar_solicitado`, porque el clic
  derecho ya no elimina directamente sino que abre el men├║ contextual del marcador); el clic
  izquierdo queda reservado (no crea ni elimina);
  reenv├¡a el movimiento del mouse a la superficie en coordenadas de la superficie para que el
  scrubbing contin├║e aunque el cursor pase por encima de la miniatura.
- **Render del color de clasificaci├│n (B6.3).** `FranjaExploracion` recibe adem├ís los colores
  de los marcadores (`set_marcadores(marcadores, colores=None)`, mapa `tiempo ÔåÆ clave`) y
  pinta cada marca con `_color_marca_para(tiempo)` (QColor de la paleta v├¡a `color_rgb`, o el
  rojo hist├│rico `_COLOR_MARCA` si la clave falta o es `NULL`). Las bandas de segmento se
  dibujan con `_color_fondo_segmento(seg)` / `_color_borde_segmento(seg)`: si el segmento es
  un `dict` con `color` de la paleta, usan ese color (fondo con la alpha hist├│rica); cualquier
  otro caso conserva el azul hist├│rico (`_COLOR_SEGMENTO` / `_COLOR_SEGMENTO_BORDE`).

**Integraci├│n con `Tarjeta` (`visor_videos.py`):** la tarjeta conserva el **estado de los
marcadores** (`_marcadores` = lista de `{"tiempo": float, "pixmap": QPixmap, "etiqueta": QLabel}`,
con el **tiempo real como fuente de verdad**), decide **qu├® pixmap mostrar**
(`preview_mas_cercana` sobre los tiempos reales de las previews cargadas) y **d├│nde mostrarlo**
(`tiempo_a_posicion` del instante solicitado, con clamp para mantener la imagen dentro de la
superficie). La separaci├│n **"qu├® imagen / d├│nde"** es expl├¡cita: la posici├│n de la preview m├│vil
depende **solo del instante solicitado**, nunca del tiempo propio de la preview elegida; el label
de la preview se ajusta al tama├▒o real del pixmap (compatible con previews horizontales y
verticales, sin huecos internos). La superficie se acota al ancho visible del `QScrollArea`
(`_limitar_ancho_superficie`) para que el extremo derecho (100 %) siempre sea alcanzable.
**`mouseMove` = cero FFmpeg + cero acceso a disco + cero creaci├│n innecesaria de pixmaps** (se
reutilizan pixmaps ya cargados en memoria). Los marcadores son **solo en memoria** (persisten
mientras vive la tarjeta durante la sesi├│n); la **persistencia queda deliberadamente fuera de
B4.1** y ser├í responsabilidad de B4.2.

### Persistencia de marcadores (B4.2)

**Persistencia.** Los marcadores temporales creados por el usuario se almacenan
**permanentemente en SQLite**: se relacionan mediante **`videos.id`**, reaparecen entre
sesiones, pueden eliminarse permanentemente y recuperan su representaci├│n visual usando las
previews disponibles.

**Tabla `marcadores_video`:**

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `video_id INTEGER NOT NULL`
- `tiempo REAL NOT NULL`

├ìndice: `idx_marcadores_video_video_id_tiempo`.

**Sin:** cascade autom├ítico (`PRAGMA foreign_keys` desactivado y sin `ON DELETE CASCADE`),
nombre/ruta como identidad, imagen persistida, nota/color/tipo ni JSON. La coherencia con
`videos.id` se gestiona en la capa de servicio.

**Pol├¡tica de conservaci├│n (deliberada):**

- Reescaneo del mismo registro ÔåÆ **conserva** los marcadores.
- Cambios de metadatos ÔåÆ **conserva**.
- Reemplazo silencioso manteniendo el mismo registro ÔåÆ actualmente **conserva**.
- Si el registro de video desaparece ÔåÆ los marcadores **NO** se eliminan autom├íticamente;
  pueden quedar **marcadores hu├®rfanos**.
- No existe a├║n **reasociaci├│n** de movidos/renombrados, ni se intenta reasociar por nombre o
  ruta.

Esto es deliberado para **evitar la p├®rdida autom├ítica de datos creados por el usuario**.

**Arquitectura en la interfaz (`visor_videos.py`, B4.2):**

- `Tarjeta` recibe `video_id` (de la columna `id` del registro del cat├ílogo) y **no ejecuta
  SQLite directamente**.
- Mantiene la **representaci├│n optimista en memoria** (`_marcadores` con
  `{"id", "tiempo", "pixmap", "etiqueta", "eliminada"}`; `marcador_id` = identidad t├®cnica
  persistente; `id=None` mientras no se confirma el INSERT).
- **Carga** los marcadores al expandir (`marcadores_solicitados` emitido por `Tarjeta` ÔåÆ
  `_solicitar_carga_marcadores`, una sola vez por tarjeta).
- **Persiste** altas/bajas mediante el **gestor dedicado `gestor_marcadores`** (cuarto
  `GestorTareas`, independiente del pipeline, de previews y de operaciones; cola serializada
  `_cola_marcadores` + `_procesar_siguiente_marcador`, se cierra en `closeEvent`). Los
  handlers `_al_marcador_creado` / `_al_marcador_eliminado` encolan operaciones de tipo
  `"crear"` / `"eliminar"` / `"cargar"`; `_al_resultado_marcadores` aplica el `id` de la base
  al registro local (y encola un DELETE compensatorio si el marcador ya fue eliminado) y
  `_al_error_marcadores` deshace la marca local de eliminaci├│n pendiente y vuelve a cargar
  tras un DELETE fallido.
- **Reconciliaci├│n as├¡ncrona.** La carga desde SQLite se trata como un **snapshot
  potencialmente antiguo**: **NO reemplaza ciegamente** el estado local. `_aplicar_marcadores_cargados`
  conserva las **altas locales** ocurridas mientras la carga estaba pendiente, respeta las
  **bajas locales** (`_marcadores_eliminados_carga`, con DELETE compensatorio de la fila
  persistida), conserva los **IDs persistentes existentes** y **deduplica por la misma
  tolerancia temporal** usada por la interacci├│n (`_tolerancia_marcadores` = duraci├│n / ancho
  ├ù 0.5), cancelando el INSERT redundante cuando una fila de la carga coincide con un marcador
  local sin `id`.
- **Carreras cubiertas:**
  - **Crear y borrar antes de terminar el INSERT**: si el `CREATE` sigue en la cola se
    cancela (`_cancelar_crear_pendiente`); si ya se ejecut├│, el DELETE compensatorio lo
    elimina.
  - **Cargar + crear**: la carga tard├¡a no elimina la nueva marca.
  - **Carga + marcador equivalente**: se conserva un solo marcador, se adopta el ID
    persistente y se cancela el INSERT redundante.
  - **Carga + baja local**: el snapshot viejo no resucita el marcador; puede ejecutarse un
    DELETE compensatorio.
  - **Recuperaci├│n tras DELETE fallido**: se vuelve a consultar (`"cargar"`) y no se destruyen
    altas locales pendientes.

### `exploracion_cache.py` ÔÇö motor de cach├® temporal versionada y reanudable (B4.3.1)
M├│dulo **puro** (sin Qt, sin SQLite y sin acoplamiento con `escanear_videos`) que materializa
en disco la cach├® densa de exploraci├│n temporal:

- **Estructura:** `miniaturas/exploracion/<video_id>/<version_fingerprint>/` con `meta.json` +
  `f{ms:010d}.jpg` (altura 120 px, JPEG). El `video_id` identifica la carpeta contenedora y no
  se repite en el nombre del JPG. `video_id_desde_ruta` deriva un id del nombre base saneado
  (limitaci├│n documentada: dos rutas con el mismo nombre base colisionan; la integraci├│n real
  B4.3.2 deber├í pasar el `video_id` de la base de datos).
- **Fingerprint de metadatos baratos:** ruta normalizada (`normcase` + `normpath` + `abspath`) +
  tama├▒o + `mtime_ns` + duraci├│n ÔåÆ `version_id_de_fingerprint` = **SHA-256 reducido a 16 hex**.
  **NO** es un hash del contenido del video; **limitaci├│n aceptada**: dos archivos con la misma
  ruta, tama├▒o, mtime y duraci├│n no son distinguibles sin hash de contenido (no se intenta
  resolver en B4.3.1). Costo de `version_actual` Ôëê **13 ┬Ás** (un `os.stat` + SHA-256); impacto
  CPU/RAM despreciable.
- **Identidad y completitud separadas:** la carpeta de versi├│n identifica a qu├® fingerprint
  pertenecen sus JPEGs; la completitud se deriva de `objetivos - existentes`. Una versi├│n
  parcial sigue siendo reconocible y **reanudable** sin repetir FFmpeg para los JPEGs ya
  terminados (cada JPEG se escribe **at├│micamente**: temporal ÔåÆ `os.replace`; un `f*.jpg`
  presente est├í completo). `meta.json` solo se escribe cuando la generaci├│n termina sin
  cancelarse y **completa** (`faltantes == 0`).
- **Invalidaci├│n no destructiva:** cualquier cambio en el fingerprint produce una **versi├│n
  distinta**; las versiones antiguas quedan en disco (no se borra nada autom├íticamente; la
  limpieza queda para una etapa futura, fuera de alcance). Una versi├│n nunca utiliza ni lista
  JPEGs de otra. `.tmp` y archivos de preparaci├│n/fallidos quedan fuera del ├¡ndice y de la
  lista (`listar_fotogramas_version` filtra por el conjunto objetivo de la duraci├│n).
- **Generaci├│n:** `generar_fotogramas(video_id, ruta_video, duracion=None, cantidad=None, ...)`
  consulta la duraci├│n con ffprobe si no se pasa (timeout 30 s), usa la densidad
  `cantidad_fotogramas` y la cobertura `tiempos_objetivo`, reutiliza los JPEGs ya presentes y
  emite una **invocaci├│n de FFmpeg por fotograma** (`-ss` + `-frames:v 1` + reducci├│n de
  resoluci├│n durante la extracci├│n, timeout 30 s, sin ventana de consola) ÔÇö **serial, un FFmpeg
  a la vez**. Callbacks opcionales `on_progreso(indice, total)` y cancelaci├│n cooperativa
  `cancelar()`. Devuelve un resumen con `generados`, `reutilizados`, `errores`, `cancelado`,
  `faltantes`, `version` y `fotogramas`.
- **Densidad secundaria (B4.3.2 Etapa 2, provisional):** constantes centralizadas
  `FOTOGRAMAS_INICIALES = 15`, `PASO_SEGUNDOS_DENSIDAD = 30.0`,
  `MINIMO_FOTOGRAMAS_DENSIDAD = 15` y `MAXIMO_FOTOGRAMAS_DENSIDAD = 200`, y la funci├│n
  `objetivo_total_densidad(duraci├│n)` = `clamp(max(15, ceil(d/30)), 15, 200)` (duraci├│n
  inv├ílida/cero/negativa/bool ÔåÆ 0). Son **provisionales** (30 s / m├¡n 15 / m├íx 200) y NO se
  exponen en la interfaz; la arquitectura permite configurarlos despu├®s (p. ej. 60 / 30 / 15 s)
  en una etapa separada.
- **API para consumidores** (sin gestionar versiones): `listar_fotogramas`, `faltantes`,
  `cache_vigente`, `fotograma_mas_cercano_en_cache`, `ruta_carpeta_actual`, `version_actual`.
  `fotograma_mas_cercano_en_cache` consulta **solo la versi├│n vigente**, nunca fotogramas de
  otras versiones ni sobrantes ajenos al conjunto objetivo.

**Benchmarks (B4.3.1, PC de desarrollo ÔÇö no garantizan rendimiento en el hardware objetivo):**
fuente sint├®tica `testsrc2` 640├ù360 @ 24 fps, 300 s (~28 MB). FFmpeg por fotograma:
20 ÔåÆ **1.20 s**, 40 ÔåÆ **2.38 s**, 100 ÔåÆ **6.02 s**, 200 ÔåÆ **12.04 s**; primera imagen
individual Ôëê **0.06 s**; cobertura de 15 puntos Ôëê **0.88 s**. Modo lote (solo **medici├│n de
referencia**, no implementado en B4.3.1): 40 ÔåÆ **0.70 s**, 100 ÔåÆ **0.72 s**; primera imagen
del lote Ôëê **0.054 s**. El **hardware objetivo** (notebook 16 GB RAM, Intel Core i7-7500U @
2.70 GHz, NVIDIA GeForce 940MX 2 GB, Intel HD Graphics 620) debe priorizar **agilidad y
fluidez**; antes de congelar MAX / cantidad inicial / lote / concurrencia se requiere una
**prueba real en esa notebook**.

### Cobertura densa integrada con la UI (`visor_videos.py`, B4.3.2)

**Consumo de la cach├® densa en la tarjeta.** La superficie temporal de B4.1 consume la cach├® de
B4.3.1 mediante la tarea as├¡ncrona `TareaExploracionDensa`, ejecutada con el **gestor principal
de tareas** (un solo lanzamiento por tarjeta): mientras no existe cach├® la superficie conserva el
**fallback a las previews normales** y, en cuanto la tarea emite parciales, la cobertura mejora
**progresivamente** sin bloquear la interfaz. El flujo en `visor_videos.py`:
`_procesar_siguiente_exploracion` conecta la se├▒al `resultado_parcial` y
`_al_resultado_parcial_exploracion` la consume; `_aplicar_exploracion_densa` (compatible con
`(ms, QImage)` y con deduplicaci├│n de repeticiones) convierte la `QImage` del worker en
`QPixmap` **en el hilo de la GUI** y la aplica al fotograma temporal.

**Reglas de integraci├│n:**
- **Selecci├│n exclusivamente en RAM durante `mouseMove`**: el cursor nunca lanza FFmpeg ni
  accede al disco; elige la imagen **m├ís cercana** entre las previews normales y los fotogramas
  densos cargados (la preview normal gana el empate; los fotogramas densos solo entran cuando
  mejoran la distancia temporal).
- **Prioridad visual din├ímica (B4.3.3)**: durante el hover la preview din├ímica queda **por
  encima** de las miniaturas fijas de marcadores (`raise_()` en `_al_instante_exploracion`); al
  salir de la superficie (`QEvent.Leave` en el `eventFilter` del franja) se aplica `lower()` y
  las fijas vuelven a su orden visual normal. Los marcadores conservan tiempo/id; un marcador
  nunca tapa el instante que se explora activamente. Solo z-order de widgets, sin trabajo pesado
  en `mouseMove`.
- **Dos fases secuenciales (Etapa 2):** `_trabajo()` primero genera la **fase r├ípida** con los
  **`FOTOGRAMAS_INICIALES = 15`** prioritarios (Etapa 1) y, solo despu├®s de terminar y sin
  cancelarse, la **fase secundaria** completa hasta el objetivo de densidad reutilizando lo
  existente y generando ├║nicamente los faltantes. **Sin solapamiento**: una imagen secundaria no
  aparece antes de finalizar la fase r├ípida. Generaci├│n **individual y secuencial, un FFmpeg por
  objetivo, sin batch y sin paralelismo**.
- **Densidad manual (B4.3.3):** `QComboBox` "Densidad:" (`Auto | 15 | 30 | 60 | 120 | 200`,
  constante `DENSIDADES_DISPONIBLES`) en la tarjeta expandida. `Auto` usa
  `objetivo_total_densidad(duraci├│n)`; los valores manuales son el **total objetivo
  independiente de la duraci├│n** (video de 30 s: Auto ÔåÆ 15, manual 60 ÔåÆ 60, manual 120 ÔåÆ 120),
  con los **15 prioritarios siempre primero**. La tarea recibe `objetivo_manual` (None = Auto) y
  en cada fase construye el **conjunto permitido** `tiempos_objetivo(duraci├│n, cantidad_actual)`:
  la cach├® en disco puede contener un **superset** y la tarea/UI decide el subconjunto ÔÇö la
  RAM/UI se limita al conjunto objetivo actual; **aumentar** reutiliza lo existente (15ÔåÆ60,
  60ÔåÆ120); **disminuir** no borra disco ni regenera; **volver a Auto** recalcula y conserva los
  extras de disco. El valor es **por tarjeta/sesi├│n** (se conserva en colapso/reexpansi├│n de la
  misma tarjeta; vuelve a Auto si se reconstruye por recarga); **sin SQLite ni persistencia en
  `configuracion.json`** (la persistencia futura queda separada).
- **`FOTOGRAMAS_INICIALES = 15` y par├ímetros Auto provisionales**: la cobertura inicial y el
  objetivo autom├ítico (`PASO_SEGUNDOS_DENSIDAD`, m├¡nimo y m├íximo) NO est├ín congelados ni se
  exponen en la interfaz; est├ín centralizados en `exploracion_cache.py` para configurarlos
  despu├®s (p. ej. 60 / 30 / 15 s) en una etapa separada. El control manual (B4.3.3) s├¡ expone
  cantidades fijas.
- **Decodificaci├│n en el worker**: los JPEG se leen y decodifican a `QImage` dentro del hilo de
  trabajo y viajan por se├▒al; la conversi├│n a `QPixmap` (objeto ligado a la GUI) y su pintado
  ocurren en el hilo principal. Aplica a ambas fases.
- **Cancelaci├│n cooperativa**: al cambiar de video/tarjeta o de densidad, la tarea anterior se
  cancela de forma cooperativa (la cach├® aborta la generaci├│n entre fotogramas; la fase
  secundaria no arranca si la tarea fue cancelada); el estado de la tarjeta sigue el video
  correcto. Cambiar o colapsar detiene la continuaci├│n del trabajo y lo ya generado queda
  reutilizable.
- **Aislamiento AÔåÆB**: cada tarjeta usa su propia cach├® (`video_id` + versi├│n vigente); la
  cobertura de una tarjeta nunca se aplica a la vecina.
- **Colapso que libera RAM**: al colapsar la tarjeta se sueltan las referencias a los `QPixmap`
  densos (queda el `QPixmap` de la miniatura/previews y el estado de marcadores); la cach├® en
  disco no se borra.
- **Reexpansi├│n que reutiliza**: al reexpandir, si la versi├│n sigue vigente, no se regenera
  nada (la fase r├ípida recupera primero los 15 y la secundaria completa hasta el objetivo actual
  sin FFmpeg si ya est├ín en disco); si el video cambi├│ (nuevo fingerprint) se genera una
  versi├│n nueva sin tocar la anterior.
- **Marcadores**: conservan su tiempo e `id` y pueden **mejorar visualmente** su miniatura al
  llegar fotogramas densos m├ís cercanos a su instante (incluidos los secundarios y manuales).

**Medidas de referencia (B4.3.2/B4.3.3, PC de desarrollo ÔÇö no garantizan rendimiento en el
hardware objetivo):** video sint├®tico de ~56 min (1280├ù720, 30 fps), objetivo Auto 112.
Primer fotograma prioritario Ôëê **0.10 s**; **15 prioritarios Ôëê 1.13 s**; **primer secundario
(16.┬║) Ôëê 1.21 s** (despu├®s de la fase r├ípida, sin solapamiento); **total 112 Ôëê 8.39 s**;
reexpansi├│n con cach├® completa Ôëê **0.08 s** (sin regenerar); scrub desde RAM sin lectura de
disco. Con un video de 30 s y densidad manual 60/120 la generaci├│n es r├ípida (fotogramas ya en
disco se reutilizan; FFmpeg = 0 al bajar densidad). La **notebook objetivo** (i7-7500U / 16 GB /
940MX) valid├│ la **Etapa 1** y posteriormente **B4.3 en conjunto** con un video real de ~56 min.
**NO se requiere una campa├▒a adicional de benchmarks exhaustivos**; el **batch NO est├í
implementado** (decisi├│n de producto: generaci├│n individual y secuencial).

### M├│dulos ajenos al visor (preservados, no forman parte de la arquitectura)
- `main.py` ÔÇö prueba que escribe el resultado en `datos.txt`.
- `prueba_agente.py` ÔÇö artifacto de validaci├│n del agente.

## 4. Separaci├│n de responsabilidades

| Responsabilidad | M├│dulo | Observaci├│n |
| --- | --- | --- |
| Interfaz | `visor_videos.py` | Debe ser agn├│stica a SQLite (corregido). |
| L├│gica del cat├ílogo | `escanear_videos.py` | `sincronizar_bd`, `actualizar_datos`. |
| Acceso a SQLite | `escanear_videos.py` | ├Ünico punto de acceso a la BD (corregido). |
| Escaneo de archivos | `escanear_videos.escanear_videos` | Filtro por extensi├│n. |
| FFprobe | `escanear_videos.obtener_datos_ffprobe` | Metadatos de video. |
| FFmpeg | `escanear_videos.generar_miniatura` | Extrae un fotograma del video; genera la miniatura autom├íticamente (se ejecuta dentro de `TareaMiniaturas`). Desde B4.5 acepta `duracion_segundos` (v├ílida ÔåÆ sin FFprobe interno). |
| Generaci├│n de miniaturas | `escanear_videos.asegurar_miniatura` / `asegurar_miniaturas` | Genera o reutiliza; escribe solo en la siguiente ranura libre y preserva los archivos existentes; `asegurar_miniaturas` orquesta la colecci├│n del pipeline. Desde B4.5 propaga `duraciones` (por ruta o nombre) para evitar el FFprobe interno. |
| Trabajos en segundo plano | `tareas.py` | `TareaBase` + `GestorTareas` (`QThread` por ejecuci├│n); se├▒ales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada`. |
| Escaneo as├¡ncrono | `tareas_videos.TareaEscaneo` | Envuelve `escanear_videos` en segundo plano; errores por se├▒al `error`. |
| FFprobe as├¡ncrono | `tareas_videos.TareaFFprobe` | Metadatos de video en segundo plano; resultado y error por ruta. Desde B4.5 Etapa 3 acepta `nombres`/`stats`/`ruta_db` y reutiliza metadata de la BD para videos sin cambios (0 FFprobe), probeando solo los nuevos/cambiados. |
| Reutilizaci├│n de metadata (B4.5 Etapa 3) | `escanear_videos._metadata_reutilizable` / `listar_registros_por_nombres` | Criterio barato `ruta normalizada + tamano_bytes + mtime_ns` (sin hash de contenido): 0 FFprobe solo si existe registro, `mtime_ns` no NULL, ruta/tama├▒o/`mtime_ns` coinciden y la metadata es v├ílida. Consulta por lote por `nombre` (una SELECT); migraci├│n aditiva `videos.mtime_ns INTEGER NULL`; `obtener_tamanos_archivos` con un `os.stat` por archivo; `guardar_videos` persiste `mtime_ns`. |
| Carga diferida de previews (B4.6 Etapa 2) | `visor_videos` (`_crear_tarjetas`/`_encolar_previews`/`_aplicar_previews`/`Tarjeta.actualizar_previews`) | `_crear_tarjetas`/`_agregar_tarjetas`/`_reemplazar_tarjetas` no cargan previews cacheadas de golpe; las tarjetas parten con placeholders y las previews se incorporan progresivamente por la tuber├¡a existente. `Tarjeta._previews_completas` (interno, no persistido) decide la cola; `_aplicar_previews` ignora resultados tard├¡os de otra carpeta; `_reconstruir_previews_exploracion` cae a las previews de disco si las etiquetas a├║n no las tienen. |
| Lectura del cat├ílogo | `escanear_videos.listar_videos` | Capa de lectura SQLite; abre y cierra su propia conexi├│n en el hilo que la invoca. |
| Lectura as├¡ncrona del cat├ílogo | `tareas_videos.TareaLecturaCatalogo` | Lectura SQLite en segundo plano; errores por se├▒al `error`; conexi├│n por hilo (sin `check_same_thread=False`). |
| Lectura paginada del cat├ílogo | `escanear_videos.listar_videos_paginado` + `tareas_videos.TareaLecturaCatalogoPaginada` | P├ígina (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro en SQL; b├║squeda parcial por `LIKE` parametrizada; sin leer toda la tabla; consumida por la interfaz para la carga inicial as├¡ncrona de la primera p├ígina y para la **carga manual de una p├ígina adicional**. |
| Carga inicial as├¡ncrona de la interfaz | `visor_videos.VisorVideos` + `tareas.GestorTareas` + `tareas_videos.TareaLecturaCatalogoPaginada` | La ventana se construye sin consultas SQL; `_iniciar_carga()` lee la primera p├ígina en segundo plano; estados de carga/error visibles y apagado ordenado en `closeEvent` (`gestor.cerrar()`). |
| Selecci├│n de carpeta desde la interfaz | `visor_videos.VisorVideos.seleccionar_carpeta` | `QFileDialog` + `os.path.abspath`/`os.path.isdir`; ruta en `carpeta_seleccionada`; no escanea, no toca SQLite/FFprobe/FFmpeg/miniaturas. |
| Escaneo as├¡ncrono desde la interfaz | `visor_videos.VisorVideos.iniciar_escaneo` + `tareas_videos.TareaEscaneo` + `tareas.GestorTareas` | Bot├│n "Escanear carpeta"; reutiliza el mismo `GestorTareas` de la ventana; estados internos `_escaneo_pendiente`/`tarea_escaneo`; resultado en `videos_detectados` con conteo visible; bloqueo de controles mientras el gestor est├í ocupado; sin SQLite/FFprobe/FFmpeg/miniaturas/tarjetas/recarga del cat├ílogo. |
| Escritura individual | `escanear_videos.guardar_video` | Upsert transaccional de un ├║nico registro (datos preparados); `commit`/`rollback`/`close` propios; base inexistente ÔåÆ `FileNotFoundError` sin crear archivos. |
| Escritura individual as├¡ncrona | `tareas_videos.TareaGuardarVideo` | Guarda un registro en segundo plano; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardado": True, "nombre": ...}`. |
| Escritura de colecci├│n | `escanear_videos.guardar_videos` | Upsert de una colecci├│n de registros en una **├║nica transacci├│n at├│mica** (un solo `connect` y un solo `commit`; `rollback` total ante cualquier fallo); validaci├│n completa y copias previas a SQL; resultado `{"guardados": n, "nombres": [...]}`; no elimina registros. |
| Escritura de colecci├│n as├¡ncrona | `tareas_videos.TareaGuardarVideos` | Guarda una colecci├│n en segundo plano; instant├ínea de la lista y de cada registro; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardados": n, "nombres": [...]}`. |
| Preparaci├│n de registros b├ísicos | `escanear_videos.preparar_registros_basicos` | Transforma los archivos detectados por el escaneo en registros con claves exactas `{nombre, ruta, extension, fecha_importacion}` (ruta absoluta en la carpeta escaneada); validaci├│n previa (no texto, iterable, carpeta no vac├¡a); sin SQLite/FFprobe/FFmpeg/miniaturas. |
| Preparaci├│n del plan de sincronizaci├│n | `escanear_videos.preparar_plan_sincronizacion` | Transforma el resultado de `detectar_diferencias` en el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`; `a_incorporar` son registros b├ísicos de `preparar_registros_basicos` (su `fecha_importacion` se genera en la preparaci├│n); candidatos informativos; pura, sin SQLite/FFprobe/FFmpeg/miniaturas/pipeline/interfaz; la deduplicaci├│n de nombres repetidos sigue pendiente. |
| Aplicaci├│n de incorporaciones del plan | `escanear_videos.aplicar_incorporaciones` | Recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` y persiste ├║nicamente `a_incorporar` reutilizando `guardar_videos` (misma transacci├│n at├│mica); validaci├│n completa del plan antes de abrir SQLite; no elimina `candidatos_a_eliminar`, no modifica `ya_sincronizados`; resultado `{"incorporados", "nombres", "pendientes_eliminacion"}`; sin pipeline/interfaz/escaneo/FFprobe/FFmpeg; la eliminaci├│n controlada y la deduplicaci├│n siguen pendientes. |
| Eliminaci├│n controlada de candidatos del plan | `escanear_videos.eliminar_candidatos` | Recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` y elimina ├║nicamente los registros de `candidatos_a_eliminar` (un `DELETE ... WHERE nombre = ?` por candidato con `rowcount`, un solo `commit`, `rollback` total, `close` en `finally`); validaci├│n completa compartida (`_validar_plan_sincronizacion`) antes de abrir SQLite; la colecci├│n de candidatos la ordena `_coleccion_nombres` (orden determinista de la validaci├│n actual); no elimina archivos f├¡sicos ni miniaturas, no toca `a_incorporar`/`ya_sincronizados`; resultado `{"eliminados", "nombres", "incorporados", "restantes"}` (`incorporados` informativo, puede ser `None`); sin pipeline/interfaz/escaneo/FFprobe/FFmpeg/`conectar_bd`/`guardar_videos`/`sincronizar_bd`; la integraci├│n as├¡ncrona de la sincronizaci├│n completa sigue pendiente. |
| Combinaci├│n de registros con metadatos FFprobe | `escanear_videos.combinar_registros_con_ffprobe` | Transforma los archivos detectados y el resultado de `TareaFFprobe` en registros con claves b├ísicas `{nombre, ruta, extension, fecha_importacion}` + metadatos FFprobe (`duracion_segundos`, `ancho`, `alto`, `codec_video`; `NULL` si el video no tiene `datos`); pura, sin SQLite/FFprobe/FFmpeg/miniaturas; normalizaci├│n interna de rutas. |
| Encadenamiento del pipeline desde la interfaz | `visor_videos.VisorVideos` + `tareas_videos.TareaEscaneo`/`TareaFFprobe`/`TareaMiniaturas`/`TareaGuardarVideos` + `escanear_videos.combinar_registros_con_ffprobe`/`combinar_registros_con_miniaturas` | Tareas sucesivas con el mismo `GestorTareas`: `TareaEscaneo` ÔåÆ `TareaFFprobe` ÔåÆ `TareaMiniaturas` ÔåÆ `combinar_registros_con_ffprobe` + `combinar_registros_con_miniaturas` ÔåÆ `TareaGuardarVideos`. El paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior (el gestor `Ocupado` rechaza una segunda tarea mientras otra corre); resultado/error del guardado limpian `_guardado_pendiente`; tras un error de guardado, de FFprobe o de miniaturas el gestor queda `inactivo` y un nuevo escaneo es posible. No es la sincronizaci├│n completa del cat├ílogo. |
| Miniaturas as├¡ncronas | `tareas_videos.TareaMiniaturas` | Asegura/reutiliza/ cuenta miniaturas en segundo plano v├¡a `asegurar_miniaturas`; FFmpeg y FFprobe solo dentro de la tarea; resultado `{"rutas", "resultados", "procesados", "con_miniatura", "sin_miniatura"}`. |
| Sincronizaci├│n as├¡ncrona del cat├ílogo | `tareas_videos.TareaSincronizacionCatalogo` | Orquesta en segundo plano la secuencia exacta `detectar_diferencias` ÔåÆ `preparar_plan_sincronizacion` ÔåÆ `aplicar_incorporaciones` ÔåÆ `eliminar_candidatos`. Sin SQL, sin abrir SQLite directamente, sin conexiones almacenadas, sin `check_same_thread=False`, sin FFprobe/FFmpeg/miniaturas/subprocesos y sin acceso a la interfaz. Resultado `{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`. Incorporaci├│n y eliminaci├│n como **transacciones independientes** (no una ├║nica transacci├│n global). **Integrada con `visor_videos.py`**: se lanza tras el guardado exitoso del pipeline y al terminar dispara la **recarga as├¡ncrona del cat├ílogo** con reemplazo de tarjetas. |
| Recarga as├¡ncrona del cat├ílogo tras la sincronizaci├│n | `visor_videos.VisorVideos._iniciar_recarga_catalogo` + `tareas_videos.TareaLecturaCatalogoPaginada` | **Solo tras una sincronizaci├│n exitosa** (`_recarga_catalogo_pendiente` marcado por `_al_resultado_sincronizacion`), con el **mismo** `GestorTareas` y la misma tarea de lectura (`_crear_tarea_lectura`, primera p├ígina `TAMANIO_PAGINA_INICIAL`). `_al_resultado_recarga` reemplaza las tarjetas (`_reemplazar_tarjetas`: libera las viejas con `removeWidget`/`deleteLater`, vac├¡a `self.tarjetas`, crea las nuevas y reaplica el filtro) conservando `resultado_sincronizacion`; `_al_error_recarga` conserva las tarjetas viejas, muestra `MENSAJE_ERROR_RECARGA` y deja la interfaz recuperable sin revertir la sincronizaci├│n ya confirmada. Sin SQL en la GUI, sin FFprobe/FFmpeg/miniaturas y sin llamar a `listar_videos_paginado` directamente (solo v├¡a la tarea). |
| Carga manual de una p├ígina adicional del cat├ílogo | `visor_videos.VisorVideos.cargar_mas` + `tareas_videos.TareaLecturaCatalogoPaginada` + `tareas.GestorTareas` | Bot├│n "Cargar m├ís": lee la p├ígina siguiente con `OFFSET = len(self.tarjetas)` con el mismo gestor; `_al_resultado_pagina` **agrega** las tarjetas nuevas debajo de las existentes (`_agregar_tarjetas`) **sin reemplazarlas** y **sin duplicados**; `_al_error_pagina` conserva las tarjetas ya cargadas y muestra `MENSAJE_ERROR_PAGINA` ("No se pudo cargar la p├ígina"). El reemplazo de tarjetas sigue siendo exclusivo de la recarga tras la sincronizaci├│n. |
| Apertura del video con la aplicaci├│n predeterminada | `apertura_videos.abrir_video_con_aplicacion_predeterminada` | **├Ünico punto que ejecuta `os.startfile`** (verificado por AST en `prueba_doble_clic.py`). Recibe `nombre` + `carpeta`, valida ambos como texto no vac├¡o (`ValueError`), resuelve la ruta **absoluta** (`os.path.abspath(os.path.join(...))`), comprueba que exista (`os.path.isfile`; `FileNotFoundError`) y abre con `os.startfile`. Un fallo del propio `os.startfile` propaga `OSError`. Sin SQLite, sin FFprobe/FFmpeg, sin subprocesos (`subprocess`/`Popen`) y sin acceso a la interfaz. |
| Detecci├│n del doble clic | `visor_videos.Tarjeta` | Se├▒al de clase `doble_clic = Signal(str)` y sobrescritura de `mouseDoubleClickEvent` (llama a `super()` y emite `self.doble_clic.emit(self._nombre)`); **cualquier doble clic con el bot├│n izquierdo sobre la tarjeta emite el nombre del video**. Solo UI: no valida rutas ni abre nada. |
| Apertura del video desde la interfaz | `visor_videos.VisorVideos._abrir_video` + `apertura_videos.abrir_video_con_aplicacion_predeterminada` | Conectado a `Tarjeta.doble_clic` en `_crear_tarjetas` y `_agregar_tarjetas`; invoca el servicio con `self.carpeta_seleccionada`; ante `ValueError`/`FileNotFoundError`/`OSError` muestra `MENSAJE_ERROR_ABRIR` ("No se pudo abrir el video") y nunca propaga excepciones. |
| Cach├® | ÔÇö | **No existe** un m├│dulo de cach├®; la BD cumple parcialmente ese rol para metadatos. |
| Configuraci├│n | `rutas.py` | Resoluci├│n de rutas del proyecto (ra├¡z, BD, miniaturas, videos) centralizada e independiente del CWD. A├║n no hay m├│dulo de configuraci├│n completo. |
| Persistencia de marcadores | `escanear_videos.py` | Tabla `marcadores_video` (migraci├│n aditiva en `conectar_bd`); `listar_marcadores` / `guardar_marcador` / `eliminar_marcador` con validaci├│n previa y conexi├│n propia por operaci├│n; coherencia con `videos.id` gestionada en la capa de servicio (sin cascade). |
| Marcadores as├¡ncronos | `tareas_videos.TareaListarMarcadores` / `TareaGuardarMarcador` / `TareaEliminarMarcador` | Cargar, crear y eliminar marcadores en segundo plano; conexi├│n abierta/cerrada en el hilo de trabajo; ejecutados por el gestor dedicado `gestor_marcadores` de la interfaz. |
| Reconciliaci├│n de marcadores en la interfaz | `visor_videos.VisorVideos` | La `Tarjeta` recibe `video_id` y no ejecuta SQLite; representaci├│n optimista en memoria, carga al expandir y cola serializada en `gestor_marcadores`; la carga se reconcilia como snapshot antiguo (conserva altas/bajas locales, IDs y deduplica por tolerancia temporal). |
| Persistencia de marcadores de varios videos | `escanear_videos.listar_marcadores_de` | Lee los marcadores persistidos de varios `video_id` (tuplas `(id, video_id, tiempo)`), agrupados en el orden recibido y ordenados cronol├│gicamente dentro de cada video; validaci├│n previa y conexi├│n propia por operaci├│n. La interfaz no consulta SQLite directamente. |
| Marcadores de varios videos as├¡ncronos | `tareas_videos.TareaListarMarcadoresVarios` | Lectura en segundo plano de los marcadores de varios videos; ejecutada por el gestor dedicado `gestor_reproduccion` de la interfaz. |
| Reproducci├│n de marcadores en VLC | `visor_videos.VisorVideos._reproducir_marcadores_en_vlc` + `playlist_vlc` | Acci├│n de men├║ contextual (habilitada con selecci├│n); recolecta los videos seleccionados en **orden visible del cat├ílogo**, lee sus marcadores, aplica el di├ílogo para videos sin marcadores (Omitir / Desde el inicio / Cancelar), omite archivos inexistentes con aviso y abre VLC una ├║nica vez con la playlist generada. |
| Ciclo de vida de playlists temporales | `playlist_vlc.limpiar_playlists_anteriores` | Antes de generar una nueva playlist elimina ├║nicamente `visor_marcadores_*.m3u` del directorio temporal propio; bloqueos ignorados; sin borrar `.m3u` ajenos ni recorrer subdirectorios; no borra la playlist reci├®n lanzada. |

## 5. Flujo de ejecuci├│n (apertura ÔåÆ tarjetas)

1. `python visor_videos.py` ÔåÆ `main()` crea `QApplication` y la `VisorVideos`.
2. `VisorVideos.__init__` crea la barra de b├║squeda, el contador, el estado de carga ("Cargando cat├ílogoÔÇª") y el `QScrollArea`. **No abre SQLite**: crea `GestorTareas(self)` y arranca `_iniciar_carga()`.
3. `_iniciar_carga()` construye `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)` y la ejecuta en un `QThread` mediante `gestor.iniciar()`.
4. En el hilo de trabajo, `TareaLecturaCatalogoPaginada._trabajo()` invoca `listar_videos_paginado`, que abre su propia conexi├│n, ejecuta `SELECT ... ORDER BY nombre LIMIT ? OFFSET ?` y `SELECT COUNT(*) ...`, la cierra y devuelve `{"videos": [...], "total": n, "limite": n, "desplazamiento": n}`.
5. Al emitirse `tarea_resultado`, `_al_resultado` oculta el estado de carga, `_crear_tarjetas` crea una `Tarjeta` por video en la `QGridLayout` (una sola columna, una fila por video) y se aplica el filtro vigente.
6. Si la lectura falla, `_al_error` muestra "No se pudo cargar el cat├ílogo" y la ventana permanece utilizable.
7. Cada tarjeta consulta `miniatura_principal(nombre)` sobre `miniaturas/`; si no encuentra imagen, muestra el recuadro "Sin miniatura".
8. El `QLineEdit` filtra en vivo (`filtrar`) **sobre las tarjetas ya cargadas** y el contador muestra "N videos".
9. Al cerrar la ventana, `closeEvent` llama `gestor.cerrar()` (timeout por defecto 5000 ms) para un apagado ordenado del hilo en curso.

La selecci├│n de carpeta es independiente de la carga del cat├ílogo: el
bot├│n "Seleccionar carpeta" abre `QFileDialog`, normaliza la ruta con
`os.path.abspath`, valida con `os.path.isdir` que exista y sea un
directorio, la muestra y la conserva en `carpeta_seleccionada`; al
cancelar se conserva la selecci├│n anterior y ante una ruta inv├ílida se
rechaza con un mensaje visible sin cerrar la ventana. Seleccionar la
carpeta **no escanea su contenido**: no detecta archivos, no abre
SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas; la selecci├│n no
es persistente.

Escaneo manual y as├¡ncrono de la carpeta elegida:

1. El usuario elige una carpeta v├ílida y presiona el bot├│n "Escanear
   carpeta" (`boton_escanear`), habilitado solo con carpeta v├ílida y
   gestor inactivo.
2. `iniciar_escaneo()` revalida la carpeta con `os.path.isdir`, crea una
   `TareaEscaneo(carpeta)` y la inicia con el **mismo** `GestorTareas`
   de la ventana; marca `_escaneo_pendiente = True` y muestra
   "Escaneando carpetaÔÇª". Mientras el gestor est├í ocupado los botones de
   la fila quedan deshabilitados.
3. En el hilo de trabajo, `TareaEscaneo._trabajo()` devuelve la lista
   ordenada de archivos de video de la carpeta (misma funci├│n
   `escanear_videos`), sin tocar SQLite, FFprobe, FFmpeg ni miniaturas.
4. `_al_resultado` reenv├¡a el resultado a `_al_resultado_escaneo`
   (enrutado por `_escaneo_pendiente`), que copia la lista en
   `videos_detectados`, limpia `_escaneo_pendiente`, **marca
   `_ffprobe_pendiente = True`** y muestra el conteo ("1 video
   detectado" / "N videos detectados"). No se crean tarjetas ni se
   recarga el cat├ílogo.
5. Ante un error (carpeta inexistente, ruta-archivo), `_al_error_escaneo`
   limpia la cadena, muestra "No se pudo escanear la carpeta" y
   **conserva el ├║ltimo resultado exitoso** en `videos_detectados`; la
   cadena no se inicia.

Encadenamiento del pipeline escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ
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
   tama├▒o de los archivos".
7. Al terminar el hilo de los tama├▒os, `_al_tarea_finalizada()` detecta
   `_ffprobe_pendiente` activo y el gestor `inactivo`, y `_iniciar_ffprobe()`
   construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta,
   nombre)`) de los videos detectados e inicia `TareaFFprobe(rutas)` con
   el mismo `GestorTareas`. El paso siguiente no se lanza en el handler
   del resultado del escaneo: el gestor `Ocupado` rechazar├¡a una segunda
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
   cada archivo existente asegura una miniatura (reutilizando una v├ílida
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
    tarea_escaneo.carpeta, resultado_ffprobe)` (claves b├ísicas
    `{nombre, ruta, extension, fecha_importacion}` con ruta absoluta +
    metadatos FFprobe `{duracion_segundos, ancho, alto, codec_video}`;
    `NULL` si el video no tiene `datos`), luego los combina con
    `combinar_registros_con_miniaturas(registros, resultado_miniaturas)`
    (clave `cantidad_miniaturas` por ruta normalizada; `None` si no hay
    coincidencia o el resultado es `None`) y con
    `combinar_registros_con_tamanos(registros, resultado_tamanos)`
    (clave `tamano_bytes` por ruta normalizada; `None` si no hay
    coincidencia o el tama├▒o es `None`), y persiste el resultado con
    `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo
    `GestorTareas`.
11. En el hilo de trabajo, `TareaGuardarVideos._trabajo()` invoca
    `guardar_videos`, que valida la colecci├│n, ejecuta el upsert
    transaccional (inserta o actualiza sin duplicar, **conservando los
    registros preexistentes** y sin eliminar ninguno) y hace un ├║nico
    `commit`; devuelve `{"guardados": n, "nombres": [...]}`.
12. `_al_resultado` reenv├¡a el resultado a `_al_resultado_guardado`
    (enrutado por `_guardado_pendiente`), que limpia el flag, libera
    `resultado_tamanos`, `resultado_ffprobe` y `resultado_miniaturas`, guarda la cantidad en
    `registros_guardados`, habilita de nuevo el bot├│n de escaneo y
    **marca `_sincronizacion_pendiente = True`**. No crea tarjetas ni
    recarga el cat├ílogo en este punto.
13. Ante un error de escritura, `_al_error_guardado` limpia
    `_guardado_pendiente`, muestra "No se pudieron guardar los videos" y
    el gestor queda `inactivo`: la interfaz es recuperable y un nuevo
    escaneo es posible. Los registros preexistentes permanecen intactos.
14. El pipeline **no constituye la sincronizaci├│n completa**: ejecuta
    FFprobe para completar duraci├│n, resoluci├│n y codec (con `NULL` ante
    vac├¡os, incompletos o fallos individuales), obtiene el tama├▒o de
    archivo (`tamano_bytes`; `NULL` si el archivo no existe o no es
    legible) y asegura una miniatura
    b├ísica por video (reutilizando o generando; los vac├¡os no generan
    archivo), pero no elimina registros ausentes ni recorre subcarpetas.

Sincronizaci├│n y recarga del cat├ílogo (pasos 15-19, con el mismo gestor):

15. Al terminar el guardado, `_al_tarea_finalizada()` detecta
    `_sincronizacion_pendiente` activo y el gestor `inactivo`, y
    `_iniciar_sincronizacion()` revalida la carpeta (`os.path.isdir`) e
    inicia `TareaSincronizacionCatalogo(carpeta, ruta_db)` con el **mismo**
    `GestorTareas`, mostrando "Sincronizando cat├ílogoÔÇª". La sincronizaci├│n
    **solo se lanza tras un guardado exitoso**.
16. En el hilo de trabajo, `TareaSincronizacionCatalogo._trabajo()`
    encadena `detectar_diferencias` ÔåÆ `preparar_plan_sincronizacion` ÔåÆ
    `aplicar_incorporaciones` ÔåÆ `eliminar_candidatos` y devuelve
    `{"diferencias", "plan", "incorporaciones", "eliminaciones",
    "resumen"}`. `_al_resultado_sincronizacion` limpia el flag, libera la
    tarea, **conserva el resultado en `resultado_sincronizacion`**, muestra
    el resumen ("Sincronizaci├│n completa: N incorporados, M eliminados, K
    candidatos restantes") y **marca `_recarga_catalogo_pendiente = True`**.
17. Al terminar la sincronizaci├│n, `_al_tarea_finalizada()` detecta
    `_recarga_catalogo_pendiente` activo y `_iniciar_recarga_catalogo()`
    crea la **misma** tarea de lectura (`_crear_tarea_lectura()` ÔåÆ
    `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None,
    ruta_db)`) y la inicia con el mismo `GestorTareas`. La recarga **solo
    se lanza tras una sincronizaci├│n exitosa**; es una fase de **solo
    lectura** de la primera p├ígina y **no ejecuta FFprobe, FFmpeg ni
    miniaturas**.
18. `_al_resultado` reenv├¡a el resultado a `_al_resultado_recarga`
    (enrutado por `_recarga_catalogo_pendiente`): limpia el flag, libera
    la tarea y `_reemplazar_tarjetas(filas)` **quita las tarjetas viejas de
    la grilla** (`removeWidget` + `deleteLater` para liberar los widgets
    Qt), **vac├¡a `self.tarjetas`**, crea las tarjetas nuevas con la primera
    p├ígina en la **misma `QGridLayout` y el mismo `QScrollArea` reutilizados**,
    reaplica el filtro vigente y actualiza el contador. No quedan tarjetas
    ocultas obsoletas; `resultado_sincronizacion` se **conserva intacto**.
19. Si la recarga falla, `_al_error_recarga` limpia la cadena, **conserva
    las tarjetas viejas**, muestra `MENSAJE_ERROR_RECARGA` ("No se pudo
    actualizar el cat├ílogo"), el gestor queda `inactivo`, el bot├│n de
    escaneo se rehabilita y un nuevo escaneo es posible. La recarga
    fallida **no revierte** la sincronizaci├│n ya confirmada en SQLite.

La carga inicial **y la recarga tras la sincronizaci├│n** cargan
autom├íticamente la **primera p├ígina** del cat├ílogo (primeros
`TAMANIO_PAGINA_INICIAL` registros). Las **p├íginas posteriores pueden
cargarse manualmente** con el bot├│n "Cargar m├ís" (paso 20); **todav├¡a no
existe** paginaci├│n autom├ítica ni scroll infinito, y la b├║squeda en SQL
desde la interfaz queda para etapas futuras.

20. Si el usuario pulsa "Cargar m├ís" (`cargar_mas()`): calcula el
    **desplazamiento con la cantidad de tarjetas ya cargadas**
    (`len(self.tarjetas)`), crea `_crear_tarea_lectura(len(self.tarjetas))`
    y ejecuta la **misma** `TareaLecturaCatalogoPaginada` con el **mismo**
    `GestorTareas`. `_al_resultado_pagina` **agrega** las filas nuevas con
    `_agregar_tarjetas` **sin reemplazar las existentes** y **descartando
    los nombres ya cargados** (deduplicaci├│n por `nombre`); el bot├│n se
    **deshabilita** cuando ya se alcanz├│ `_total_catalogo`
    (`len(self.tarjetas) >= self._total_catalogo`).

Apertura del video por doble clic (interfaz ÔåÆ servicio):

1. El usuario hace **doble clic con el bot├│n izquierdo** sobre una
   tarjeta. Qt entrega el evento a `Tarjeta.mouseDoubleClickEvent`, que
   llama a `super().mouseDoubleClickEvent(event)` y **emite la se├▒al
   `doble_clic`** con `self._nombre` (el nombre del video).
2. `_abrir_video(nombre)` (conectado a `doble_clic` en `_crear_tarjetas`
   y `_agregar_tarjetas`) llama a
   `abrir_video_con_aplicacion_predeterminada(nombre,
   self.carpeta_seleccionada)` de `apertura_videos.py`.
3. El servicio valida `nombre`/`carpeta` (texto no vac├¡o tras `strip()`;
   si no ÔåÆ `ValueError`), construye la **ruta absoluta**
   (`os.path.abspath(os.path.join(carpeta, nombre))`), comprueba con
   `os.path.isfile` que el archivo exista (si no ÔåÆ `FileNotFoundError`) y
   lo abre con `os.startfile(ruta)`, devolviendo la ruta. Un fallo del
   propio `os.startfile` propaga `OSError`.
4. Si el servicio **falla**, `_abrir_video` muestra `MENSAJE_ERROR_ABRIR`
   ("No se pudo abrir el video") en la etiqueta de estado; en ├®xito la
   deja en blanco. En ning├║n caso la excepci├│n escapa al gestor de
   eventos. La apertura **no toca** SQLite, FFprobe, FFmpeg ni el
   cat├ílogo: el video se abre con la aplicaci├│n predeterminada de
   Windows.

Flujo de datos (respaldo/escritura) ÔÇö ejecuci├│n previa del CLI:

1. `python escanear_videos.py` ÔåÆ `main()`.
2. `conectar_bd()` crea/migra la tabla `videos`.
3. `sincronizar_bd(conn, "videos_prueba")`:
   - `escanear_videos("videos_prueba")` lista archivos v├ílidos;
   - inserta los que no existen (`INSERT OR IGNORE`);
   - para cada uno: `asegurar_miniatura` (reutiliza o genera) + `obtener_datos_ffprobe` (si no est├í vac├¡o) + `contar_miniaturas` ÔåÆ `UPDATE`;
   - elimina de la BD los que ya no est├ín en disco.
4. `commit()` y cierre.

Flujo de ejecuci├│n as├¡ncrona (infraestructura de tareas):

1. `gestor.iniciar(tarea)` valida la tarea (`TareaBase`, sin padre, no ejecutada), crea un `QThread` propio, la mueve a ├®l y lo arranca.
2. El hilo ejecuta `TareaBase.ejecutar()`: emite `inicio`, corre `_trabajo()` y emite `resultado(valor)`; si `_trabajo()` lanza una excepci├│n, emite `error(f"{Tipo}: {msg}")`. En ambos casos emite `finalizada`.
3. `GestorTareas` replica las se├▒ales al hilo principal (`tarea_iniciada`, `tarea_resultado`, `tarea_error`) y, al terminar el hilo (`hilo.finished`), vuelve a `inactivo` y libera el hilo. `cerrar(timeout_ms)` permite detener el hilo en curso.

## 6. Flujo de generaci├│n de miniaturas

**Estado actual: generaci├│n autom├ítica implementada.** Durante el escaneo, para cada video no vac├¡o se asegura una miniatura. El flujo por video es:

1. `ffmpeg_disponible()` ÔÇö verifica que FFmpeg est├® disponible. Si no lo est├í, la generaci├│n se omite sin intentar ejecutar subprocesos.
2. `miniatura_reutilizable()` ÔÇö busca la primera miniatura existente del video que sea v├ílida seg├║n `miniatura_vigente()` (`mtime` de la miniatura ÔëÑ `mtime` del video). Si existe, se **reutiliza** y no se genera nada.
3. Si ninguna es v├ílida, `generar_miniatura()` extrae un fotograma (`-ss <tiempo> -frames:v 1 -q:v 3`) y lo escribe en la **siguiente ranura libre** (`siguiente_indice_libre()` ÔåÆ `miniaturas/<prefijo>_NN.jpg`). **Nunca se sobrescribe un archivo existente ni se elimina ninguno.**
4. `contar_miniaturas()` cuenta los archivos del video en `miniaturas/` y `actualizar_datos()` persiste `cantidad_miniaturas` en la BD.

**Integraci├│n en el pipeline:** el flujo del cat├ílogo tambi├®n se ejecuta
desde la interfaz como **paso as├¡ncrono** del encadenamiento escaneo ÔåÆ
FFprobe ÔåÆ miniaturas ÔåÆ guardado: `TareaMiniaturas` invoca
`asegurar_miniaturas(videos, carpeta)`, que por cada archivo existente
aplica los pasos 1-3 y cuenta con `contar_miniaturas`; el resumen se
combina con los registros (`combinar_registros_con_miniaturas`) y la
cantidad se persiste junto con los metadatos FFprobe en el guardado. El
CLI (`sincronizar_bd`) conserva su propio flujo s├¡ncrono con
`asegurar_miniatura` + `actualizar_datos`.

Durante un escaneo se genera **como m├íximo una miniatura nueva por video**, y ├║nicamente cuando no existe ninguna miniatura considerada vigente (criterio `mtime`). Pueden coexistir varias miniaturas del mismo video en distintas ranuras `_NN`. La convenci├│n `<prefijo>_NN.jpg` permite convivir con miniaturas preexistentes sin perderlas. Los videos vac├¡os (0 bytes) no generan miniatura.

## 7. Puntos de extensi├│n previstos

1. **Generaci├│n de miniaturas con FFmpeg** ÔÇö extracci├│n de fotogramas mediante `asegurar_miniatura`/`generar_miniatura` con reutilizaci├│n por `mtime` y preservaci├│n de archivos existentes.
2. **Ejecuci├│n as├¡ncrona** ÔÇö infraestructura de tareas en segundo plano (`TareaBase` + `GestorTareas` con `QThread` por ejecuci├│n) para escaneo, FFprobe, miniaturas, lectura y escritura del cat├ílogo. Incluye pipeline encadenado con el mismo gestor y generaci├│n progresiva de previews con gestor independiente.
3. **M├│dulo de configuraci├│n** ÔÇö centralizar rutas, extensiones, tama├▒os de tarjeta y n├║mero de columnas.
4. **Cach├® de miniaturas/metadatos** ÔÇö formalizar la base de datos como cach├® de metadatos y evitar re-escaneos.
5. **Lectura/vistas del cat├ílogo** ÔÇö sobre `listar_videos()` y `listar_videos_paginado()`, agregar orden, agrupaci├│n y filtros adicionales. La lectura paginada con b├║squeda en SQL y la carga manual de p├íginas adicionales est├ín implementadas; la paginaci├│n autom├ítica y la b├║squeda en SQL desde la interfaz quedan para etapas futuras.
6. **Resoluci├│n de rutas** ÔÇö `rutas.py` centraliza la resoluci├│n de rutas del proyecto de forma independiente del directorio de trabajo, con soporte para modo PyInstaller (`sys.frozen`).

## 8. Problemas detectados

| # | Severidad | Problema |
| --- | --- | --- |
| 1 | Media | La interfaz (`visor_videos.py`) acced├¡a a SQLite directamente y duplicaba el nombre de BD (`"biblioteca.db"`). **Corregido**. |
| 2 | Media | Rutas relativas (`miniaturas/`, `videos_prueba/`, `biblioteca.db`) depend├¡an del directorio de trabajo; la app fallaba si se lanzaba desde otra ubicaci├│n. **Resuelto** (ver `rutas.py`). |
| 3 | Media | No exist├¡a generaci├│n de miniaturas; solo conteo. **Resuelto** (ver ┬º6). |
| 4 | Media | FFprobe se ejecutaba en el hilo principal con timeout de 30 s por video; el escaneo bloquea. **Resuelto**: FFprobe se movi├│ a segundo plano con `TareaFFprobe`, la carga inicial del cat├ílogo se integr├│ con las tareas as├¡ncronas (`visor_videos.py` + `TareaLecturaCatalogoPaginada`) y la generaci├│n de miniaturas con FFmpeg se ejecuta dentro de `TareaMiniaturas` (segundo plano, nunca en el hilo principal). La sincronizaci├│n completa del cat├ílogo ya est├í integrada en la interfaz y, tras una sincronizaci├│n exitosa, el cat├ílogo se recarga en segundo plano y las tarjetas se reconstruyen. |
| 5 | Baja | `contar_miniaturas`/`miniatura_principal` usan coincidencia por prefijo (`startswith`); un video `video_real.mp4` podr├¡a matchear miniaturas de un hipot├®tico `video_realista.mp4`. Pendiente. |
| 6 | Baja | Los videos vac├¡os (0 bytes) quedan sin metadatos; comportamiento correcto pero debe documentarse para el usuario. Pendiente. |
| 7 | Informativa | `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` son artefactos de prueba ajenos al visor. Se preservaron por pol├¡tica del proyecto. |
| 8 | Media | Crecimiento acumulativo de miniaturas: la regeneraci├│n escribe una ranura nueva (`_NN`) en lugar de sobrescribir; si el video cambia varias veces se acumulan archivos y `cantidad_miniaturas` crece. Pendiente. |
| 9 | Baja | La interfaz muestra la primera miniatura por orden alfab├®tico (`_01`), incluso cuando una versi├│n m├ís nueva (`_02`) es la vigente. Pendiente. |
| 10 | Media | El criterio de reutilizaci├│n usa ├║nicamente `mtime` (sin hash ni validaci├│n de integridad); no detecta cambios de contenido que conserven la fecha. Pendiente (mejora diferida). |
| 11 | Media | Falta una limpieza controlada de versiones antiguas de miniaturas; por regla, los archivos nunca se eliminan autom├íticamente, por lo que requiere autorizaci├│n expresa. Pendiente. |
| 12 | Media | FFmpeg escribe directamente en la ruta definitiva de la miniatura; si falla despu├®s de comenzar la escritura puede quedar un archivo parcial o corrupto. Actualmente ese archivo no se elimina ni se valida, y por existencia y `mtime` podr├¡a ser contado o considerado vigente. Pendiente. |
| 13 | Baja | **Restauraci├│n de rutas con nombres cortos 8.3 de Windows** (p. ej. `MARCOS~1`): el ├írbol carga los nombres largos (p. ej. `Marcos`), por lo que `revelar_ruta` no empareja un camino persistido con segmentos 8.3 y cae en el comportamiento tolerante (aplicaci├│n inicia sin carpeta seleccionada, sin inconsistencias). No afecta el uso normal ni el alcance de la Etapa 2.5; **deuda t├®cnica** para una futura etapa de robustez del Centro de Navegaci├│n. |
| 14 | Baja | **Estado de "escaneada" por sesi├│n** (Etapa 2.9): el indicador de carpetas escaneadas vive en memoria (`carpetas_escaneadas` del visor) y se pierde al reiniciar; no se persiste ni se deriva del cat├ílogo (requerir├¡a cambios de esquema o en m├│dulos restringidos). La API (`EstadoNodo` + `_icono_para`) ya est├í preparada; documentada como **deuda t├®cnica** para una etapa espec├¡fica de persistencia del estado. |
| 15 | Informativa | **Marcadores hu├®rfanos por dise├▒o** (B4.2): si el registro del video desaparece (eliminaci├│n del cat├ílogo, archivo fuera de disco, etc.) los marcadores de `marcadores_video` **no** se eliminan autom├íticamente (sin `ON DELETE CASCADE`); pueden quedar hu├®rfanos, y no existe a├║n reasociaci├│n de movidos/renombrados ni por nombre/ruta. Deliberado para evitar p├®rdida autom├ítica de datos del usuario; la **reasociaci├│n futura** de marcadores hu├®rfanos est├í prevista (ver `ROADMAP.md`, secci├│n "Beta 4"). |
| 16 | Informativa | **Fingerprint sin hash de contenido** (B4.3.1): la versi├│n de la cach├® densa de exploraci├│n se deriva de ruta + tama├▒o + `mtime_ns` + duraci├│n (SHA-256 reducido a 16 hex); dos archivos con exactamente esos mismos metadatos no son distinguibles y compartir├¡an cach├® aunque el contenido difiera. **Limitaci├│n aceptada** para B4.3.1; no se intenta resolver (un hash de contenido encarecer├¡a el c├ílculo por video). |
| 17 | Informativa | **Densidad Auto provisional y superset de cach├® (B4.3.2/B4.3.3):** la generaci├│n es **individual y secuencial (un FFmpeg por objetivo, sin batch)**; los par├ímetros autom├íticos (`PASO_SEGUNDOS_DENSIDAD = 30`, `MINIMO = 15`, `MAXIMO = 200`) quedaron centralizados en `exploracion_cache.py` como **provisionales**, NO congelados y sin exponer en la interfaz. El control manual (B4.3.3) expone `Auto | 15 | 30 | 60 | 120 | 200` como total objetivo por tarjeta/sesi├│n (**sin SQLite ni persistencia en `configuracion.json`**). La cach├® en disco puede contener un **superset** (p. ej. 120) respecto de la densidad actual (p. ej. 30): la tarea construye expl├¡citamente `tiempos_objetivo(duraci├│n, cantidad_actual)` y solo emite/decodifica ese subconjunto; los extras permanecen en disco sin borrar ni regenerar. La notebook objetivo (i7-7500U / 16 GB / 940MX) valid├│ la Etapa 1 y posteriormente **B4.3 en conjunto** con un video real de ~56 min. |

## 9. Direcci├│n arquitect├│nica futura

La interfaz evoluciona hacia un sistema de paneles independientes basado en
**QSplitter** (ya implementado). Existe un ├║nico splitter entre el panel
izquierdo (├írbol de navegaci├│n) y el panel derecho (cat├ílogo). El ├írbol del
panel izquierdo se implementa por etapas (bloque de trabajo 2): la **Etapa
2.9** ya incorpora **indicadores visuales de carpetas escaneadas** (estado por
nodo con `EstadoNodo`, API preparada para estados futuros como PARCIAL o
CAMBIOS_PENDIENTES); las etapas siguientes podr├ín agregar el filtrado del
cat├ílogo desde el ├írbol y la persistencia del estado de escaneado. La
arquitectura deber├í permitir incorporar posteriormente nuevos paneles
(propiedades, favoritos, etiquetas, IA) sin redise├▒ar la interfaz. Esta
direcci├│n est├í documentada en detalle en `VISION_PRODUCTO.md` y `ROADMAP.md`.

**Estado de la Beta 3:** la Beta 3 qued├│ **implementada, funcionalmente cerrada
y congelada sobre el c├│digo definitivo** (bloques AÔÇôE del Bloque de trabajo 3,
m├ís el Bloque de trabajo 4 ÔÇö cat├ílogo por selecci├│n de carpetas ÔÇö y las
correcciones finales incluidas). El desarrollo continu├│ en el **ciclo Beta 4**
(rama `beta4`): las etapas **B4.1 ÔÇö Exploraci├│n temporal interactiva y
marcadores visuales**, **B4.2 ÔÇö Persistencia de marcadores temporales por
video**, **B4.3.1 ÔÇö Motor de cach├® temporal versionada y reanudable**,
**B4.3.2 ÔÇö Cobertura r├ípida as├¡ncrona integrada con la UI**, **B4.3.2 ÔÇö Etapa
2: Densidad secundaria adaptativa**, **B4.3.3 ÔÇö Ajustes de interacci├│n y
densidad manual**, **B4.4 ÔÇö Reproducci├│n de marcadores en VLC** y **B4.5 ÔÇö
Rendimiento de carga inicial** quedaron **completadas y aprobadas**, en bloques
peque├▒os y
acumulativos y **sin introducir cambios arquitect├│nicos** que todav├¡a no
existieran; cada etapa extiende la arquitectura ├║nicamente en la medida que su
propio alcance aprobado lo requiere (B4.2 incorpor├│ la tabla `marcadores_video`
y un gestor dedicado `gestor_marcadores` en la interfaz, ambos aditivos; B4.3.1
incorpor├│ `exploracion_cache.py` y `ruta_carpeta_exploracion()` en `rutas.py`,
tambi├®n aditivos, **sin tocar SQLite** ÔÇö `videos`, `marcadores_video` y
`biblioteca.db` intactos; B4.3.2 incorpor├│ la tarea `TareaExploracionDensa` y el
consumo de la cach├® densa en la superficie temporal, aditivo, con decodificaci├│n
`QImage` en el worker, conversi├│n `QPixmap` en la GUI y fallback a las previews
normales; la **Etapa 2** extendi├│ `_trabajo()` con la **fase secundaria** de
densidad adaptativa, individual y secuencial, sin batch; y **B4.3.3** agreg├│ la
**prioridad visual din├ímica** (z-order de la preview sobre las miniaturas fijas
de marcadores) y la **densidad manual** (`Auto | 15 | 30 | 60 | 120 | 200` por
tarjeta/sesi├│n con conjunto permitido expl├¡cito `tiempos_objetivo` y soporte de
cach├® superset), aditivos y sin tocar SQLite ni configuraci├│n).
**B4.4** agreg├│ la integraci├│n m├¡nima de **reproducci├│n de marcadores en VLC**, aditiva y sin
cambios arquitect├│nicos: m├│dulo de servicio `playlist_vlc.py` (localizaci├│n de `vlc.exe`,
generaci├│n del `.m3u` UTF-8 con `#EXTVLCOPT:start-time` y limpieza propia de playlists
temporales anteriores), `listar_marcadores_de`/`TareaListarMarcadoresVarios` para leer
marcadores de varios videos, y la acci├│n de men├║ contextual "Reproducir marcadores en VLC" con
di├ílogo Omitir/Desde el inicio/Cancelar y omisi├│n de archivos inexistentes. Sin HTTP, sin
libVLC, sin loop autom├ítico y sin tocar SQLite salvo lecturas de marcadores.
**Reproducci├│n de marcadores en VLC ÔÇö completada** (Etapa 1: validaci├│n f├¡sica de la
estrategia playlist con VLC 3.0.23; Etapa 2: integraci├│n m├¡nima). **B4.4 queda completada; no
se declara la Beta 4 completa todav├¡a.**
**B4.5 ÔÇö Rendimiento de carga inicial.** **Etapa 1 (diagn├│stico)**: con un dataset temporal de
121 videos se midi├│ el pipeline normal de cat├ílogo/miniaturas en la PC de desarrollo ÔÇö FFprobe
de metadata ~4.5 s (121 procesos), miniaturas ~12.3 s, previews ~38.6 s (el cuello dominante,
~70 %), reescaneo caliente con FFprobe redundante (~4.6 s de ~4.9 s) ÔÇö sin cambios de
producci├│n. **Etapa 2 (eliminaci├│n de FFprobe redundante)**: `generar_miniatura`/`generar_preview`
aceptan `duracion_segundos=None` (v├ílida ÔåÆ sin FFprobe interno, mismo c├ílculo temporal y FFmpeg;
inv├ílida ÔåÆ fallback FFprobe anterior); `asegurar_miniaturas`/`generar_previews_faltantes` y
`TareaMiniaturas`/`TareaPreviewsProgresivas` propagan duraciones; la interfaz las toma de
`TareaFFprobe` (miniaturas) y de la tarjeta (previews). En fr├¡o: **484 FFprobe internos ÔåÆ 0**,
mismos 484 FFmpeg; total backend ~55.6 s ÔåÆ ~37.1 s (medici├│n de PC de desarrollo). Sin cambios
de cantidad, posiciones, calidad, progresividad, lotes, cach├®, paralelismo ni FFmpeg. Pendiente
t├®cnico sin corregir: las previews existentes se consideran reutilizables por existencia del
archivo. **Etapa 3 (reutilizaci├│n de metadata en reescaneos sin cambios)**: criterio barato
`ruta normalizada + tamano_bytes + mtime_ns` (sin hash de contenido) mediante `_metadata_reutilizable`;
migraci├│n aditiva `videos.mtime_ns INTEGER NULL`; `obtener_tamanos_archivos` con un `os.stat` por
archivo; `listar_registros_por_nombres` (consulta por lote por `nombre`, una SELECT); `TareaFFprobe`
clasifica y solo probea los videos nuevos/cambiados/sin `mtime_ns`/con metadata inv├ílida;
`guardar_videos` persiste `mtime_ns`. Reescaneo caliente de 121 videos: **121 FFprobe ÔåÆ 0**,
backend ~4.9 s ÔåÆ ~0.1ÔÇô0.5 s (referencia de PC de desarrollo); verificaci├│n emp├¡rica con 10
archivos f├¡sicos independientes: **10 ÔåÆ 0 ÔåÆ 1 ÔåÆ 0**. `video_id`/marcadores intactos; un cambio de
ruta fuerza FFprobe conservando la identidad por nombre/upsert. Riesgo residual aceptado
(mismo ruta+tama├▒o+`mtime_ns` con contenido distinto); sin hash. **B4.5 queda completada en sus
Etapas 1-3; no se declara la Beta 4 completa todav├¡a.**
**B4.6 ÔÇö Rendimiento de carga visual.** **Etapa 1 (diagn├│stico)**: con 100 tarjetas/300 previews
cacheadas se descompuso el costo de la carga visual ÔÇö construcci├│n de widgets ~0.42 s,
`miniatura_principal` ~0.05 s, **`_crear_tarjetas` cargaba y escalaba las 300 previews de golpe
(0.74 s caliente / ~3.5 s fr├¡o)**, bloqueo s├¡ncrono total 1.4ÔÇô4.4 s, RAM ~+690 MB ÔÇö sin cambios de
producci├│n. **Etapa 2 (carga diferida de previews cacheadas)**: `_crear_tarjetas`/`_agregar_tarjetas`/
`_reemplazar_tarjetas` ya no cargan previews cacheadas; las tarjetas parten con textos + miniatura
principal + placeholders y las previews se incorporan **progresivamente** por la tuber├¡a existente
(`_encolar_previews` ÔåÆ `TareaPreviewsProgresivas` ÔåÆ `generar_previews_faltantes` ÔåÆ `_aplicar_previews`).
`Tarjeta._previews_completas` (interno, no persistido) decide la cola; `_aplicar_previews` ignora
resultados tard├¡os de otra carpeta (AÔåÆB); `_reconstruir_previews_exploracion` cae a las previews de
disco si las etiquetas a├║n no las tienen (ajuste de integraci├│n del diferido; no modifica B4.3).
Con cach├® completa **0 FFmpeg**; con faltantes la generaci├│n normal. Medici├│n: `_crear_tarjetas(100)`
**0.69ÔÇô0.85 s** (antes 1.4ÔÇô4.4 s), tarjetas visibles ~0.72 s, primera preview ~1.0 s, **300 previews
~2.1 s**, m├íximo bloqueo continuo **~0.7 s**, lotes ~20ÔÇô30 ms. **La interfaz queda utilizable antes
de terminar las previews.** Pendientes separados: RAM/retenci├│n de pixmaps, `_construir_exploracion`
en colapsadas, reconciliaci├│n de reemplazo y `os.listdir` de `miniatura_principal`. **B4.6 qued├│
completada en sus Etapas 1-2; no se declara la Beta 4 completa todav├¡a.**

**Cierre de Beta 4 (2026-08-10):** la **Beta 4 qued├│ CERRADA y aprobada**, build final
`Beta 4 ÔÇö B4.12` (commit t├®cnico `198cdf533986b88c6e25dc0087722cf2b86e5f99`, instalador
`VisorVideos_Beta4_Setup.exe`, SHA-256 `730B4DAB1CD2F1F5CFDD184D2DC6FE80CF0481B8754080F0FF10CF991F89431F`),
validada en la notebook (B4.11: validaci├│n manual amplia; B4.12: validaci├│n final corta) y con la
suite integral posterior a las correcciones en **87 suites / 1570/1570 OK / 0 FAIL funcional**.
**Beta 5 CERRADA internamente (2026-08-15, rama `beta5`):** commit t├®cnico principal
`969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
`VisorVideos_Beta5_ValidacionFinal_Setup.exe`; identidad **`Beta 5 ÔÇö B5.0`**. Los cuatro bloques
iniciales (A: entrada temporal a VLC; B: segmentos AÔÇôB; C: reproducci├│n simple y en bucle; D:
secuencia autom├ítica) y el plan B5.1ÔÇôB5.9 quedaron **implementados**, junto con los pulidos
finales de interacci├│n (creaci├│n por drag, edici├│n de extremos A/B, scroll horizontal local de
previews, mejoras de visibilidad de segmentos y feedback visual de edici├│n). Sin distribuci├│n
p├║blica, sin merge a `main`, sin GitHub Release. Ver la secci├│n "Modelo de segmentos" m├ís abajo.

**Decisi├│n arquitect├│nica registrada en B5.0 ÔÇö MARCADOR Ôëá SEGMENTO (direcci├│n, NO implementada):**
el marcador ("instante interesante") y el segmento ("intervalo interesante", `video_id` + inicio
`A` + fin `B`, con `A < B`) son **entidades independientes**; no se convierten marcadores en
puntos de inicio/fin. Modelo previsto para B5.1 (sin CASCADE, misma pol├¡tica de orfandad que los
marcadores, sin hashes, sin detecci├│n de renombrados, migraci├│n aditiva e idempotente):
tabla independiente `segmentos_video (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT
NULL, inicio REAL NOT NULL, fin REAL NOT NULL)` e ├¡ndice `idx_segmentos_video_video_id_inicio
(video_id, inicio)`, con validaciones `video_id > 0`, `inicio >= 0`, `fin > inicio`. Se describe
como **direcci├│n aprobada conceptualmente**, no como esquema existente (no existe ninguna
implementaci├│n todav├¡a).

**Evidencia t├®cnica VLC de B5.0 (probada en VLC 3.0.23, video real de 12 s):** `start-time` y
`stop-time` funcionan por CLI y dentro de M3U (`#EXTVLCOPT:start-time`/`#EXTVLCOPT:stop-time`), con
valores decimales; el **bucle** se logra con una playlist de una entrada (`start-time` + `stop-time`)
m├ís `--loop` (no usa el AÔÇôB interactivo nativo); la **secuencia autom├ítica** se logra con una
playlist de varias entradas del mismo archivo con `start-time` y `stop-time` (VLC salta solo al
llegar a cada `stop-time`). Pendiente de validaci├│n en la notebook objetivo y de la precisi├│n
frame-exacta de los l├¡mites.

**Criterio de higiene de procesos VLC para pruebas (B5.0):** cada VLC lanzado por una prueba debe
conservar su **PID/handle** y la prueba debe cerrar **exclusivamente procesos propios** (prohibido
matar globalmente `vlc.exe`); cleanup en `finally`, cierre normal primero y `terminate`/`kill` solo
como fallback; no cerrar instancias VLC preexistentes del usuario. La investigaci├│n B5.0 detect├│ y
corrigi├│ un **residual** producido por una prueba `--loop` (proceso hu├®rfano); los scripts
temporales de `%TEMP%` no se incorporan al repositorio.

**Observaci├│n arquitect├│nica (Etapa B3.1):** el instante que se muestra sobre
cada preview se deriva de `(duraci├│n, ├¡ndice)` con `calcular_tiempo_preview`,
como se acord├│ para la Beta 3. Para la futura mejora "Apertura del video desde
una preview" (Bloque E), el instante deber├í provenir del **instante real
utilizado al generar el fotograma**, no de un rec├ílculo; no se implementa en
esta etapa, ├║nicamente queda registrado para esa futura implementaci├│n.
| 13 | Baja | El pipeline limitado escrib├¡a registros **b├ísicos** (nombre, ruta absoluta, extensi├│n, fecha de importaci├│n) sin ejecutar FFprobe; los videos quedaban sin duraci├│n, resoluci├│n ni codec. **Resuelto**: FFprobe se integr├│ en el pipeline (`TareaEscaneo` ÔåÆ `TareaFFprobe` ÔåÆ `combinar_registros_con_ffprobe` ÔåÆ `TareaGuardarVideos`) y los registros se guardan con los metadatos disponibles (`NULL` ante vac├¡os, incompletos o fallos individuales). |
