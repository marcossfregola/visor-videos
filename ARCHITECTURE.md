# ARCHITECTURE — Visor de Videos

Arquitectura vigente del proyecto (condensada del documento tecnico heredado y de las decisiones tecnicas verificadas). No es un changelog ni un manual linea por linea; el detalle de implementacion que ya refleja el codigo fuente no se duplica aqui.

## 1. Estructura general

Workspace: `C:\prueba` (repo Git, rama `main` reconciliada con `beta7`, remote `origin` = `https://github.com/marcossfregola/visor-videos.git`).

```text
visor_videos.py          Interfaz grafica PySide6 (ventana, tarjetas, previews, navegacion, organización)
escanear_videos.py       Backend / logica del catalogo: escaneo, SQLite, FFprobe, FFmpeg, sincronizacion, marcadores/segmentos/derivados
arbol_navegacion.py      Arbol de navegacion del panel izquierdo (Este equipo -> discos -> carpetas)
configuracion.py         Servicio de persistencia de preferencias (configuracion.json) + colores de clasificación
tareas.py                Infraestructura generica de trabajos en segundo plano (QThread / GestorTareas)
tareas_videos.py         Tareas asincronas especificas de video (FFprobe, escaneo, miniaturas, lectura, guardado, sincronizacion, marcadores, exploración densa, exportación, lote, organización)
operaciones.py           Logica pura de operaciones sobre archivos (copiar, pegar, eliminar) — base para lote
seleccion_carpetas.py    Conjunto de carpetas seleccionadas por ruta (Selección personalizada)
rutas.py                 Resolucion centralizada de rutas, independiente del CWD (soporta PyInstaller) + destino drop y miniaturas
apertura_videos.py       Servicio de apertura con la aplicacion predeterminada (unico modulo que ejecuta os.startfile)
playlist_vlc.py          Integración VLC via playlists .m3u (B4.4)
exploracion_cache.py     Motor de caché densa versionada y reanudable (B4.3.1) con fingerprint
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
prueba_*.py              amplia suite de pruebas automatizadas versionadas (B3–B7)
infra/bridge/            Infraestructura reconstruible Bridge/MCP
```

Mantenidos como ajenos al visor: `main.py` (script de prueba de operaciones), `operaciones.py` (logica pura usada por el visor), `prueba_agente.py`, `datos.txt`.

## 2. Responsabilidades por modulo

- `escanear_videos.py`: unico modulo con responsabilidad sobre el dominio y los datos. Escaneo, preparación de registros, acceso SQLite con migración idempotente (videos, marcadores, segmentos, derivados, colores), integración FFprobe/FFmpeg, reutilización/generación de miniaturas y previews, detección de diferencias, plan de sincronización, lectura paginada, paleta de colores, trazabilidad de derivados.
- `visor_videos.py`: interfaz grafica. Carga inicial asíncrona, "Cargar mas", filtro y ordenamiento, tarjetas con miniaturas/previews y exploración temporal, marcadores/segmentos con edición, selección, menú contextual, operaciones de organización por lote, panel Organización/Explorer con doble panel y drag & drop, escaneo asíncrono y recarga con preservación de filtros/orden/selección/viewport.
- `arbol_navegacion.py`: panel izquierdo con nodo raiz "Este equipo", discos y carpetas con carga diferida, selección funcional, indicadores de escaneo, modo selección multicarpeta.
- `rutas.py`: resolucion centralizada de rutas (raiz, BD, miniaturas, videos) independiente del CWD, con soporte PyInstaller, `ruta_video_existente`, `resolver_destino_drop`/`validar_destino_drop_completo`, `listar_subcarpetas`.
- `configuracion.py`: persistencia de preferencias en `configuracion.json` (carpeta, subcarpetas, cantidad de previews, escaneo automático, tamaños, vista ampliada, modo alcance, orden, nombres de colores, versión/build).
- `tareas.py`: infraestructura generica (`TareaBase` + `GestorTareas`).
- `tareas_videos.py`: tareas específicas (escaneo, FFprobe, tamaños, miniaturas, lectura paginada, guardado, previews progresivas, sincronización, marcadores/segmentos/colores, exploración densa, exportación segmento/lote/secuencia, organización, prevalidación drop).
- `operaciones.py` + `copiar/mover/eliminar/crear_carpeta/lote/renombrar_*`: lógica pura de operaciones de archivos (copiar/pegar/eliminar a Papelera, mover, renombrar) — base para `TareaLoteOperaciones`.
- `nombres.py`: motor puro de nombres (tokens, sanitización Windows, extensión controlada, colisiones).
- `panel_organizacion.py`: panel destino con validación de drop y prevalidación atómica.
- `playlist_vlc.py` / `scrubber.py` / `exploracion_*`: exploración temporal y reproducción VLC.
- `instalador.iss` + `EMPACADO.md` + `preparar_empaquetado.py`: empaquetado oficial.

## 3. Separacion de responsabilidades

- UI separada de logica: la interfaz no accede directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada; todo se encola como tarea en segundo plano.
- El catalogo (`escanear_videos.py`) contiene capas puras de transformacion separadas del acceso a SQLite y de los subprocesos.
- La apertura de archivos esta aislada en un unico servicio.
- La resolucion de rutas esta centralizada y es independiente del CWD.

## 4. Catalogos y sincronizacion (SQLite)

- Tabla `videos` con columnas base y extras (`duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`, `tamano_bytes`, `ruta`, `mtime_ns`) + `marcadores_video`, `segmentos_video` (con `color`), `videos_derivados` y `videos_derivados_segmentos`.
- Migracion idempotente por `PRAGMA table_info` + `ALTER TABLE`.
- Escritura transaccional atomica; `FileNotFoundError` sin crear archivos si base inexistente.
- Lectura paginada con `LIMIT/OFFSET` y `COUNT` parametrizados; ordenamiento configurable y filtros por color/segmento.
- Sincronizacion: `detectar_diferencias` -> `preparar_plan_sincronizacion` -> `aplicar_incorporaciones` -> `eliminar_candidatos`, en segundo plano; recarga con reemplazo de tarjetas preservando filtros/orden/selección (B7.8).
- Cada video transporta su `ruta` real; alcance multicarpeta vs carpeta activa.

## 5. Escaneo, FFprobe y FFmpeg

- Escaneo por extension, modo recursivo configurable y nombres planos seguros.
- FFprobe con timeout 30s; reutilización por `ruta+tamano+mtime_ns` (B4.5) para evitar FFprobe redundante.
- FFmpeg: miniaturas y previews con reutilizacion por `mtime` y ranuras sin sobrescribir; previews faltantes generadas de forma progresiva y diferida (B4.6). Caché densa versionada por fingerprint (B4.3) y exploración con 15 prioritarios + densidad secundaria.
- Subprocesos con `CREATE_NO_WINDOW`.

## 6. Tareas en segundo plano

- `TareaBase` + `GestorTareas`: un `QThread` por ejecucion, una tarea activa por gestor, senales `inicio/resultado/error/finalizada`, apagado ordenado.
- Pipeline encadenado: escaneo -> tamanos -> FFprobe -> miniaturas -> guardado -> sincronizacion -> recarga.
- Previews progresivas, exploración densa y exportación con gestores independientes.

## 7. Pruebas

- Amplia suite de pruebas automatizadas versionadas `prueba_*.py` (desde `prueba_tareas.py` hasta `prueba_drag_*`, `prueba_version_build.py`, `prueba_integracion_b612.py` etc.).
- Arnés smoke (`prueba_smoke.py`) y suites de organización/exportación/derivados integradas.
- Fallos históricos y transitorios ver `STATUS.md`; tests no deben modificar estado real del usuario (`RULES.md` 7).

## 8. Puntos de extension previstos

- Paneles adicionales y organización ya implementada (Beta 7) sobre QSplitter.
- Vistas del catalogo con filtros y ordenamiento ya implementadas (B6.2/B6.5).
- Resolución de rutas con soporte PyInstaller.

## 9. Direccion arquitectonica futura

- Centro de navegacion permanente extensible (ya con Organización/Explorer).
- Herramientas de manipulación basadas en el modelo visual de escenas/previews sin timeline.
- Cambios por etapas pequeñas; cada etapa extiende la arquitectura solo en su alcance aprobado.

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
- **Decision:** cada registro lleva su `ruta` real.
- **Razon:** bug critico Beta 3 por usar estado de navegacion.
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
- **Decision:** se reutiliza miniatura valida (mtime >= video); generación en siguiente ranura libre; nunca sobrescribir ni eliminar.
- **Razon:** preservacion de cache.
- **Alternativas descartadas:** sobrescritura total.

### 10.10 Resolucion centralizada de rutas
- **Decision:** `rutas.py` centraliza rutas independientemente del CWD, con soporte PyInstaller, incluyendo `resolver_destino_drop` y `validar_destino_drop_completo`.
- **Razon:** fallaba al lanzarse desde otra ubicación; empaquetado exige rutas relativas al ejecutable.
- **Alternativas descartadas:** rutas relativas al CWD.

### 10.11 Instalador por usuario con preservación de datos
- **Decision:** instalacion por usuario (`%LOCALAPPDATA%\Programs\VisorVideos`, `PrivilegesRequired=lowest`), AppId independiente, `biblioteca.db` vacía con `onlyifdoesntexist uninsneveruninstall`, **sin** `[UninstallDelete]` destructivo que borre `biblioteca.db`/`configuracion.json`/`miniaturas`; desinstalación conserva datos del usuario (B6.1) y **no** elimina datos persistentes; FFmpeg/FFprobe por PATH, no se empaquetan; DB seed via `preparar_empaquetado.py` con `escanear_videos.conectar_bd`.
- **Razon:** sin permisos de administrador; preserva catalogo en reinstalaciones; evita pérdida irreversible de marcadores/segmentos.
- **Alternativas descartadas:** instalacion por maquina, empaquetado de FFmpeg, desinstalación completa con `[UninstallDelete]` (Beta 3, obsoleta desde B6.1).
