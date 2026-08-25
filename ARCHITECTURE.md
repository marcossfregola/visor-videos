# ARCHITECTURE — Visor de Videos

Arquitectura vigente del proyecto (condensada del documento tecnico heredado y de las decisiones tecnicas verificadas). No es un changelog ni un manual linea por linea; el detalle de implementacion que ya refleja el codigo fuente no se duplica aqui.

## 1. Estructura general

Workspace: `C:\prueba` (repo Git, rama `beta9` abierta B9.0 desde `v8.0-beta`/`e851c7c2be1c3d12aac8ccb633e1aaecea2b7d3d`; baseline publicado `origin/beta8` + `v8.0-beta` alineados en `e851c7c`; cierre técnico B8.4 `97cb2f7f30853ed3a80ac310b7112cac80440158` / cierre documental `38fbc88e30c892b75b3bf66d752c49ba4c057c33`, parent B8.3 `e4104ae53cf205811e57e582350733552aaa8740`; `main@d04a7124dcb7741d16c015d88909d12851c58289` divergida, NO base de `beta9`).

```text
visor_videos.py          Interfaz grafica PySide6 (ventana, tarjetas, previews, navegacion, organización)
escanear_videos.py       Backend / logica del catalogo: escaneo, SQLite, FFprobe, FFmpeg, sincronizacion, marcadores/segmentos/derivados
arbol_navegacion.py      Arbol de navegacion del panel izquierdo (Este equipo -> discos -> carpetas)
configuracion.py         Servicio de persistencia de preferencias (configuracion.json) + colores de clasificación
tareas.py                Infraestructura generica de trabajos en segundo plano (QThread / GestorTareas)
tareas_videos.py         Tareas asincronas especificas de video (FFprobe, escaneo, miniaturas, lectura, guardado, sincronizacion, marcadores, exploración densa, exportación, lote, organización)
operaciones.py           Logica pura de operaciones sobre archivos (copiar, pegar, eliminar) — base para lote
seleccion_carpetas.py    Conjunto de carpetas seleccionadas por ruta (Selección personalizada)
rutas.py                 Resolucion centralizada de rutas, independiente del CWD (soporta PyInstaller) + destino drop y miniaturas + `normalizar_ruta_clave` (B8.1)
apertura_videos.py       Servicio de apertura con la aplicacion predeterminada (unico modulo que ejecuta os.startfile)
playlist_vlc.py          Integración VLC via playlists .m3u (B4.4)
exploracion_cache.py     Motor de caché densa versionada y reanudable (B4.3.1) con fingerprint (separado de cache normal)
exploracion_temporal.py  Utilidades de tiempos objetivo para exploración densa
scrubber.py              Superficie temporal y render de marcadores/segmentos (B4.1/B6.3/B6.4)
nombres.py               Motor puro de nombres con sanitización Windows (B6.8)
copiar_video.py / mover_video.py / eliminar_video.py / crear_carpeta.py / lote_operaciones.py / renombrar_video.py / renombrar_masivo.py
                         Operaciones individuales y por lote de organización (B7.1–B7.6)
panel_organizacion.py    Panel Organización/Explorer con drag & drop (B7.9–B7.13)
exportar_segmento.py / exportar_secuencia.py
                         Exportación de segmentos con verificación FFprobe (B6.7/B6.10)
instalador.iss           Script Inno Setup oficial del instalador (ver EMPACADO.md)
biblioteca.db            Catalogo SQLite (ignorado; regenerable)
configuracion.json       Preferencias locales del usuario (ignorado)
miniaturas/              Miniatura/previews JPG + caché exploración (ignorado)
videos_prueba/           Videos de prueba (tracked)
Distribucion/            Instaladores (ignorado)
prueba_*.py              amplia suite de pruebas automatizadas versionadas (B3–B7, B8.1/B8.2)
infra/bridge/            Infraestructura reconstruible Bridge/MCP
```

Mantenidos como ajenos al visor: `main.py` (script de prueba de operaciones), `operaciones.py` (logica pura usada por el visor), `prueba_agente.py`, `datos.txt`.

## 2. Responsabilidades por modulo

- `escanear_videos.py`: unico modulo con responsabilidad sobre el dominio y los datos. Escaneo, preparación de registros, acceso SQLite con migración idempotente (videos, marcadores, segmentos, derivados, colores, `ruta_normalizada` B8.1), integración FFprobe/FFmpeg, reutilización/generación de miniaturas y previews, detección de diferencias, plan de sincronización, lectura paginada, paleta de colores, trazabilidad de derivados, y cache normal por `video_id` + migración legacy (B8.2).
- `visor_videos.py`: interfaz grafica. Carga inicial asíncrona, "Cargar mas", filtro y ordenamiento, tarjetas con miniaturas/previews y exploración temporal, marcadores/segmentos con edición, selección, menú contextual, operaciones de organización por lote, panel Organización/Explorer con doble panel y drag & drop, escaneo asíncrono y recarga con preservación de filtros/orden/selección/viewport, y pipeline B8.1/B8.2 (guardar antes de miniaturas, `cantidad_miniaturas` por `video_id`, `v<id>`).
- `arbol_navegacion.py`: panel izquierdo con nodo raiz "Este equipo", discos y carpetas con carga diferida, selección funcional, indicadores de escaneo, modo selección multicarpeta.
- `rutas.py`: resolucion centralizada de rutas (raiz, BD, miniaturas, videos) independiente del CWD, con soporte PyInstaller, `ruta_video_existente`, `resolver_destino_drop`/`validar_destino_drop_completo`, `listar_subcarpetas` y `normalizar_ruta_clave` (B8.1: `strip+abspath+normpath+normcase`).
- `configuracion.py`: persistencia de preferencias en `configuracion.json` (carpeta, subcarpetas, cantidad de previews, escaneo automático, tamaños, vista ampliada, modo alcance, orden, nombres de colores, versión/build).
- `tareas.py`: infraestructura generica (`TareaBase` + `GestorTareas`).
- `tareas_videos.py`: tareas específicas (escaneo, FFprobe, tamaños, miniaturas, lectura paginada, guardado, previews progresivas, sincronización, marcadores/segmentos/colores, exploración densa, exportación segmento/lote/secuencia, organización, prevalidación drop) y **B8.2** `TareaMiniaturasPorId`, `TareaPreviewsPorId`, `TareaMigrarCacheLegacy`, `TareaActualizarCantidadMiniaturas` (existen y verificadas por búsqueda en código).
- `operaciones.py` + `copiar/mover/eliminar/crear_carpeta/lote/renombrar_*`: lógica pura de operaciones de archivos (copiar/pegar/eliminar a Papelera, mover, renombrar) — base para `TareaLoteOperaciones`.
- `nombres.py`: motor puro de nombres (tokens, sanitización Windows, extensión controlada, colisiones).
- `panel_organizacion.py`: panel destino con validación de drop y prevalidación atómica.
- `playlist_vlc.py` / `scrubber.py` / `exploracion_*`: exploración temporal y reproducción VLC.
- `instalador.iss` + `EMPACADO.md` + `preparar_empaquetado.py`: empaquetado oficial.

## 3. Separacion de responsabilidades

- UI separada de logica: la interfaz no accede directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada; todo se encola como tarea en segundo plano.
- El catalogo (`escanear_videos.py`) contiene capas puras de transformacion separadas del acceso a SQLite y de los subprocesos.
- La apertura de archivos esta aislada en un unico servicio.
- La resolucion de rutas esta centralizada y es independiente del CWD (incluye normalización de identidad B8.1).

## 4. Catalogos y sincronizacion (SQLite)

- Tabla `videos` con columnas base y extras (`duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`, `tamano_bytes`, `ruta`, `mtime_ns`) + `ruta_normalizada` (`TEXT NOT NULL`, `UNIQUE(ruta_normalizada)` `idx_videos_ruta_normalizada`). Desde B8.3 `nombre TEXT NOT NULL` **sin** `UNIQUE` (`B8.3 cutover`), homónimos `AAAA.mp4` en `A/B` coexisten con `video_id` distinto y `ruta_normalizada` distinta (`video_id` lógica, `ruta_normalizada` física, `nombre` no único). `AUTOINCREMENT` preservado.
- Helper oficial `rutas.normalizar_ruta_clave(ruta)` — única función para clave técnica `ruta_normalizada` (`strip` → `abspath` → `normpath` → `normcase`); `videos.ruta` conserva ruta original.
- `guardar_video`/`guardar_videos` dual-write: escriben conjuntamente `ruta` + `ruta_normalizada` (`INSERT ... ON CONFLICT(nombre) DO UPDATE` y actualización de `ruta_normalizada`); `video_id` se resuelve por `ruta_normalizada` (`SELECT id WHERE ruta_normalizada = ?`) — libros de migración B8.1.
- Migracion idempotente por `PRAGMA table_info` + `ALTER TABLE` + creación de índice único sin destruir datos ni eliminar `UNIQUE(nombre)`.
- Escritura transaccional atomica; `FileNotFoundError` sin crear archivos si base inexistente.
- Lectura paginada con `LIMIT/OFFSET` y `COUNT` parametrizados; ordenamiento configurable y filtros por color/segmento.
- Sincronizacion: `detectar_diferencias` -> `preparar_plan_sincronizacion` -> `aplicar_incorporaciones` -> `eliminar_candidatos`, en segundo plano; recarga con reemplazo de tarjetas preservando filtros/orden/selección (B7.8).
- Cada video transporta su `ruta` real y su `ruta_normalizada` estable; alcance multicarpeta vs carpeta activa.

## 5. Escaneo, FFprobe y FFmpeg

- Escaneo por extension, modo recursivo configurable y nombres planos seguros.
- FFprobe con timeout 30s; reutilización por `ruta+tamano+mtime_ns` (B4.5) para evitar FFprobe redundante.
- FFmpeg: pipeline B8.1/B8.2 **guarda antes de miniaturas normales** (antes B7: miniaturas → guardado; ahora B8: tamaños → FFprobe → **guardado** → miniaturas por `video_id` → `actualizar_cantidad_miniaturas` por `video_id`); `cantidad_miniaturas` se actualiza puntualmente por `video_id` (`actualizar_cantidad_miniaturas`/`batch`), no por nombre.
- Cache normal por `video_id`: `v<video_id>_<NN>.jpg` (`ruta_miniatura_id`) y `v<video_id>_preview_<NN>.jpg` (`ruta_preview_id`); helpers `contar_miniaturas_por_id`, `miniatura_reutilizable_por_id`, `previews_faltantes_por_id`.
- Migración legacy no destructiva (`migrar_cache_legacy_a_id`): copia `video_*.jpg`/`video_preview_*.jpg` → `v<id>_*.jpg` por copia (temp + `os.replace`), no borra legacy, idempotente, sin fallback ambiguo por nombre; fallo por archivo no afecta otros; ya existe si destino existe.
- Caché densa versionada por fingerprint (B4.3) y exploración con 15 prioritarios + densidad secundaria; permanece separada de cache normal (no migrada por B8.2).
- Subprocesos con `CREATE_NO_WINDOW`.

## 6. Tareas en segundo plano

- `TareaBase` + `GestorTareas`: un `QThread` por ejecucion, una tarea activa por gestor, senales `inicio/resultado/error/finalizada`, apagado ordenado.
- Pipeline encadenado B8.2: escaneo -> tamanos -> FFprobe -> guardado (`TareaGuardarVideos`, genera `video_id`/`rutas_por_id`) -> miniaturas por id (`TareaMiniaturasPorId`, incluye migración legacy por copia) -> actualizar `cantidad_miniaturas` por id -> sincronizacion -> recarga. Corrige pipeline antiguo B7 (miniaturas→guardado) a realidad B8.2 (guardado antes de miniaturas).
- Previews progresivas y cache normal por id: `TareaPreviewsPorId` (por `video_id`, con `rutas_por_id`/`nombres_por_id`/`duraciones`, también con migración legacy) y migración dedicada `TareaMigrarCacheLegacy` (por `video_id`, copia no destructiva, verificada en `tareas_videos.py`).
- UI consume cache y rutas resueltas (por `video_id`) sin hacer FS/SQLite/FFmpeg directo; pesado fuera de UI. Incluye secuenciación diferida y protección contra carrera migración/previews (vuelo diferido).
- Exploración densa y exportación con gestores independientes; cache densa B4.x separada.

## 7. Pruebas

- Amplia suite de pruebas automatizadas versionadas `prueba_*.py` (desde `prueba_tareas.py` hasta `prueba_drag_*`, `prueba_version_build.py`, `prueba_integracion_b612.py`, `prueba_b81_identidad.py`, `prueba_b82_cache_id.py`, etc.).
- Arnés smoke (`prueba_smoke.py`) y suites de organización/exportación/derivados integradas.
- Fallos históricos y transitorios ver `STATUS.md`; tests no deben modificar estado real del usuario (`RULES.md` 7).

## 8. Puntos de extension previstos

- Paneles adicionales y organización ya implementada (Beta 7) sobre QSplitter.
- Vistas del catalogo con filtros y ordenamiento ya implementadas (B6.2/B6.5).
- Resolución de rutas con soporte PyInstaller y normalización de identidad.

## 9. Direccion arquitectonica futura

- Centro de navegacion permanente extensible (ya con Organización/Explorer).
- Herramientas de manipulación basadas en el modelo visual de escenas/previews sin timeline.
- Cambios por etapas pequeñas; cada etapa extiende la arquitectura solo en su alcance aprobado. **Beta 8 — B8.1–B8.4 completadas y publicadas** (`v8.0-beta`/`e851c7c`; sin arquitectura futura de Beta 9 aún).

## 10. Decisiones arquitectonicas duraderas

Formato: Decision / Razon / Alternativas descartadas.

### 10.1 PySide6 sobre PyQt6
- **Decision:** el stack es PySide6 (Qt 6).
- **Razon:** decision conversacional vigente.
- **Alternativas descartadas:** PyQt6, Tkinter, wxPython.

### 10.2 Separacion estricta UI / logica
- **Decision:** la interfaz nunca accede directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada.
- **Razon:** evita bloqueos y acoplamiento.
- **Alternativas descartadas:** UI con acceso directo a la BD.

### 10.3 Trabajo pesado fuera del hilo principal
- **Decision:** toda tarea costosa usa `QThread`/`GestorTareas`.
- **Razon:** fluidez de la interfaz.
- **Alternativas descartadas:** ejecucion síncrona.

### 10.4 Pipeline por carpeta, no paralelismo agresivo
- **Decision:** soporte multicarpeta reutiliza pipeline secuencialmente.
- **Razon:** menor riesgo.
- **Alternativas descartadas:** pipelines paralelos simultaneos.

### 10.5 Carpeta activa != alcance del catalogo; cada video transporta su ruta
- **Decision:** cada registro lleva su `ruta` real y su `ruta_normalizada` estable (B8.1).
- **Razon:** bug critico Beta 3 por usar estado de navegacion; identidad estable requerida por T09.
- **Alternativas descartadas:** resolver por `carpeta_seleccionada`.

### 10.6 Seleccion personalizada materializada como rutas
- **Decision:** conjunto explicito de rutas.
- **Razon:** evita ambigüedad.
- **Alternativas descartadas:** intervalos.

### 10.7 Operaciones de archivos seguras
- **Decision:** copiar = copia fisica; pegar = portapapeles interno; renombrar con motor `nombres.py` y ciclos con temporales; mover/copiar/eliminar por lote y drag & drop con prevalidación atómica; nunca sobrescribir silenciosamente; eliminar = Papelera nativa Windows; nunca borrado permanente; operaciones en segundo plano.
- **Razon:** seguridad y previsibilidad.
- **Alternativas descartadas:** `os.remove`/sobrescritura directa.

### 10.8 Incrementalidad despues de operaciones
- **Decision:** copiar/pegar/mover/renombrar/eliminar no provocan reescaneos completos; actualización vía recarga paginada preservando filtros/orden/selección/viewport (B7.8).
- **Razon:** coherente con actualización parcial.
- **Alternativas descartadas:** reescaneo completo tras cada operación.

### 10.9 Reutilizacion de miniaturas por mtime y ranuras sin sobrescribir
- **Decision:** se reutiliza miniatura válida (mtime >= video); generación en siguiente ranura libre; nunca sobrescribir ni eliminar. Para cache normal B8.2 por `video_id` (v<id>), regeneración determinista de canónica `_01`.
- **Razon:** preservacion de cache.
- **Alternativas descartadas:** sobrescritura total.

### 10.10 Resolucion centralizada de rutas
- **Decision:** `rutas.py` centraliza rutas independientemente del CWD, con soporte PyInstaller, incluyendo `resolver_destino_drop` y `validar_destino_drop_completo` y `normalizar_ruta_clave` (B8.1).
- **Razon:** fallaba al lanzarse desde otra ubicación; empaquetado exige rutas relativas al ejecutable; identidad requiere normalización estable.
- **Alternativas descartadas:** rutas relativas al CWD, normalización ad-hoc por nombre.

### 10.11 Instalador por usuario con preservación de datos
- **Decision:** instalacion por usuario (`%LOCALAPPDATA%\Programs\VisorVideos`, `PrivilegesRequired=lowest`), AppId independiente, `biblioteca.db` vacía con `onlyifdoesntexist uninsneveruninstall`, **sin** `[UninstallDelete]` destructivo que borre `biblioteca.db`/`configuracion.json`/`miniaturas`; desinstalación conserva datos del usuario (B6.1) y **no** elimina datos persistentes; FFmpeg/FFprobe por PATH, no se empaquetan; DB seed via `preparar_empaquetado.py` con `escanear_videos.conectar_bd`.
- **Razon:** sin permisos de administrador; preserva catalogo en reinstalaciones; evita pérdida irreversible de marcadores/segmentos.
- **Alternativas descartadas:** instalacion por maquina, empaquetado de FFmpeg, desinstalación completa con `[UninstallDelete]` (Beta 3, obsoleta desde B6.1).
