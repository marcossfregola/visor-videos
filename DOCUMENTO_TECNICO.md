# Documento técnico — Visor de Videos

Estado de la arquitectura congelada. Fecha: 2026-08-02.
Este documento es referencia para las próximas etapas de desarrollo.

---

## Documentación del proyecto

El proyecto se documenta con cuatro documentos que cumplen roles distintos y complementarios. En conjunto constituyen la fuente principal de contexto del proyecto.

| Documento | Rol | Contenido y responsabilidad |
| --- | --- | --- |
| `DOCUMENTO_TECNICO.md` | Referencia técnica de la arquitectura | Describe la arquitectura: módulos, separación de responsabilidades, flujos, problemas detectados, cambios aplicados, verificación ejecutada y registro de cambios. Se actualiza cuando cambia la arquitectura o el comportamiento técnico (ver `REGLAS_PROYECTO.md`, §9). |
| `REGLAS_PROYECTO.md` | Reglas permanentes de desarrollo | Define cómo se desarrolla el proyecto: metodología por etapas, inspección previa, alcance de los cambios, auditoría, flujo de commits, preservación de archivos, separación de arquitectura, evidencia y prioridades de calidad. Son permanentes y solo cambian con autorización expresa. |
| `ESTADO_PROYECTO.md` | Estado actual del proyecto | Indica dónde está el proyecto: última etapa aprobada, último commit, arquitectura completada/en desarrollo, pendientes prioritarios, problemas abiertos y próxima etapa. Se actualiza al aprobar cada etapa. |
| `ROADMAP.md` | Dirección de desarrollo | Reúne las funcionalidades previstas (prioridad inmediata, experiencia de usuario, calidad de miniaturas, organización, administración y futuro). No describe el estado actual sino la dirección; su orden puede cambiar según las decisiones arquitectónicas. |

Para evitar duplicación de información, cada documento responde una pregunta distinta:

- `REGLAS_PROYECTO.md` — **cómo** se desarrolla (proceso, permanente).
- `ESTADO_PROYECTO.md` — **dónde estamos** (estado actual y próximos pasos).
- `ROADMAP.md` — **hacia dónde vamos** (funcionalidades futuras, sin comprometer el estado actual).
- `DOCUMENTO_TECNICO.md` — **qué es el sistema** (arquitectura y detalle técnico).

La información de estado y de problemas abiertos vive en `ESTADO_PROYECTO.md` y `DOCUMENTO_TECNICO.md`; el detalle técnico de los problemas se remite a `DOCUMENTO_TECNICO.md` en lugar de repetirse. Las funcionalidades futuras no se describen como estado: solo pasan de `ROADMAP.md` al desarrollo cuando existe una etapa aprobada que las implemente.

Al iniciar un nuevo hilo de desarrollo, estos documentos deben consultarse en conjunto y constituyen la fuente principal de contexto del proyecto.

---

## 1. Árbol de directorios

```
prueba/
├── biblioteca.db          Base de datos SQLite del catálogo
├── datos.txt              Salida del script de prueba main.py (ajeno al visor)
├── main.py                Script de prueba de operaciones (ajeno al visor)
├── operaciones.py         Helper trivial de prueba (ajeno al visor)
├── prueba_agente.py       Artifacto de prueba (ajeno al visor)
├── escanear_videos.py     CLI / backend: escaneo + SQLite + FFprobe
├── rutas.py               Resolución centralizada de rutas del proyecto (independiente del CWD)
├── tareas.py              Infraestructura reutilizable de trabajos en segundo plano (QThread)
├── tareas_videos.py       Tareas de video asíncronas (TareaFFprobe, TareaEscaneo, TareaLecturaCatalogo, TareaLecturaCatalogoPaginada, TareaGuardarVideo, TareaGuardarVideos)
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
├── prueba_escaneo_guardado.py  Pruebas automatizadas del encadenamiento escaneo → registros básicos → guardado (16)
├── visor_videos.py        Interfaz gráfica (PySide6): carga asíncrona de la primera página + selección de carpeta + escaneo asíncrono de la carpeta elegida + encadenamiento escaneo → FFprobe → registros con metadatos → guardado + smoke test automático
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
| `videos_prueba/` | Dataset de prueba con el que `escanear_videos.py` sincroniza el catálogo. Contiene archivos vacíos (sin metadatos) y un video real. |
| `__pycache__/` | Caché de bytecode de Python. Generado automáticamente, debe ignorarse en VCS. |

## 3. Propósito de cada módulo

### `escanear_videos.py` — backend / lógica del catálogo
Único módulo con responsabilidad sobre el **dominio** y los **datos**:

- `escanear_videos(carpeta)` — escaneo de archivos: lista archivos del directorio filtrando por extensión (`.mp4`, `.mkv`, `.avi`), ordenados.
- `preparar_registros_basicos(videos, carpeta)` — **preparación de registros básicos del catálogo** a partir de los archivos detectados por el escaneo. Recibe la lista de nombres de archivos y la carpeta escaneada; devuelve una lista de registros con las claves exactas `{nombre, ruta, extension, fecha_importacion}`. `ruta` es la ruta **absoluta** del archivo dentro de la carpeta escaneada (`os.path.join(carpeta, nombre)`), `extension` es la extensión en minúsculas y `fecha_importacion` es una marca de tiempo ISO (`datetime.now().isoformat()`) común a los registros de la preparación. **Validación previa**: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vacía (`ValueError` en caso contrario).   No detecta archivos, no abre SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas: es la capa de transformación entre el escaneo y la escritura (`guardar_videos`).
- `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)` — **combinación de registros con metadatos FFprobe**: capa de catálogo **pura** que transforma los archivos detectados por el escaneo y el resultado de `TareaFFprobe` en registros con metadatos. Parte de `preparar_registros_basicos` (claves básicas `{nombre, ruta, extension, fecha_importacion}`) y luego integra los metadatos de FFprobe por ruta: para cada registro busca el `datos` asociado a su `ruta` dentro de `resultado_ffprobe["resultados"]` (los ítems que no son `dict` o no tienen `ruta` se ignoran; un `datos` no-dict se trata como `None`) y aplica las claves de `CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")`; si el video no tiene `datos` (resultado vacío, incompleto o fallo individual), las claves se escriben como `NULL` (`None`). Las rutas se comparan con la normalización interna `_normalizar_ruta` (`os.path.normcase(os.path.normpath(ruta))`; `None` si la entrada es `None`). No abre SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas ni toca la interfaz: es la capa de transformación entre el escaneo y la escritura (`guardar_videos`).
- `conectar_bd(ruta_db=None)` — acceso a SQLite: crea la tabla `videos` si no existe y aplica migración idempotente de columnas extras (`COLUMNAS_EXTRA`). Acepta una ruta de base opcional (por defecto `ruta_biblioteca()`); el smoke test reutiliza este esquema para crear una base SQLite temporal válida sin depender de `biblioteca.db`.
- `obtener_datos_ffprobe(ruta)` — integración con **FFprobe**: extrae duración, ancho, alto y codec del primer stream de video. Timeout 30 s; devuelve `None` ante cualquier fallo.
- `ffmpeg_disponible()` — integración con **FFmpeg**: verifica disponibilidad del ejecutable (`shutil.which`).
- `ruta_miniatura(video, indice=1)` — ruta canónica `miniaturas/<prefijo>_<NN>.jpg`.
- `calcular_tiempo_miniatura(duracion)` — tiempo representativo para extraer el fotograma (10 % de la duración, acotado entre 0.1 y 10 s; 1 s si se desconoce).
- `miniatura_vigente(ruta_video, ruta_miniatura)` — criterio de reutilización por `mtime`: la miniatura es válida si existe y su `mtime` es ≥ al del video.
- `generar_miniatura(ruta_video, ruta_miniatura)` — extrae un fotograma con FFmpeg (`-ss`, `-frames:v 1`). Timeout 30 s; devuelve `False` ante cualquier fallo.
- `siguiente_indice_libre(video)` — primer índice `_NN` sin archivo existente.
- `miniatura_reutilizable(video, ruta_video)` — primera miniatura existente del video que sea válida (orden alfabético) o `None`.
- `asegurar_miniatura(video, ruta_video)` — reutiliza una miniatura válida si existe; si no, genera una nueva en la **siguiente ranura libre**. Nunca sobrescribe ni elimina archivos.
- `contar_miniaturas(video)` — cuenta miniaturas existentes en `miniaturas/` cuyo nombre empieza con el prefijo del video.
- `insertar_video`, `actualizar_datos`, `sincronizar_bd` — lógica de sincronización disco ↔ BD: inserta nuevos, actualiza metadatos (incluida `cantidad_miniaturas` tras `asegurar_miniatura`), elimina de la BD los que ya no están en disco. Operan sobre una conexión administrada por el llamador (el `commit` lo hace `main()`).
- `guardar_video(datos, ruta_db=None)` — **escritura individual transaccional** de un único registro. Recibe el registro ya preparado como `dict` con las claves de las columnas reales. Obligatorias: `nombre`, `ruta`, `extension`, `fecha_importacion`; opcionales (se guardan como `NULL` si faltan o son `None`): `duracion_segundos`, `ancho`, `alto`, `codec_video`, `cantidad_miniaturas`. Reutiliza la validación y el upsert internos compartidos (`_validar_registro_video`, `_upsert_video`) con `guardar_videos`; no duplica SQL ni validación. **Validación previa a SQL**: si `datos` no es un `dict` lanza `TypeError`; si falta una clave obligatoria lanza `ValueError` con el nombre de la clave; ambas se verifican **antes de conectar** (no se abre ni modifica la base). Inserta si `nombre` no existe o actualiza el mismo registro (`ON CONFLICT(nombre) DO UPDATE`), sin duplicar. Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos (mismo contrato que `listar_videos`). Ciclo: abre la conexión, ejecuta el upsert, hace `commit` solo si la operación terminó correctamente, hace `rollback` ante cualquier error y cierra siempre en `finally`. Devuelve `{"guardado": True, "nombre": ...}`. No ejecuta escaneo, FFprobe ni FFmpeg; no modifica miniaturas.
- `guardar_videos(datos_videos, ruta_db=None)` — **escritura de colección transaccional** en una **única transacción atómica**. Recibe una colección materializable de registros con el mismo contrato de `guardar_video` (una lista/tupla/iterable de `dict`; se rechaza el texto). **Validación completa previa**: la entrada debe ser iterable y no texto (`TypeError` en caso contrario), se materializa en una lista, se validan **todos** los registros (`_validar_registro_video`: no-dict → `TypeError`; clave obligatoria ausente → `ValueError`) y se toman **copias superficiales** de cada uno; si un registro es inválido se rechaza la colección completa **sin abrir SQLite**. Inserta o actualiza cada registro (mismo upsert `ON CONFLICT(nombre) DO UPDATE` que `guardar_video`, sin duplicar SQL). **Ciclo atómico**: abre **una sola** conexión, ejecuta **todos** los upserts, realiza **un solo** `commit` al terminar, ejecuta `rollback` ante cualquier excepción (ningún registro anterior persiste; los preexistentes conservan sus valores originales; no queda transacción abierta) y cierra siempre en `finally`. **Colección vacía**: devuelve éxito con cero registros y no modifica la base. **Base inexistente**: `FileNotFoundError` sin crear archivos. Devuelve el resumen simple `{"guardados": <cantidad>, "nombres": [nombres en el orden de la colección]}`. No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg, no genera miniaturas, **no elimina registros** y no compara disco ↔ base: la sincronización del catálogo sigue pendiente.
- `listar_videos(ruta_db=None)` — **capa de lectura** que consume la interfaz: devuelve las filas del catálogo (nombre, duración, ancho, alto, codec, cantidad de miniaturas) ordenadas por nombre. Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. Abre y cierra su propia conexión en el hilo que la invoca (sin `check_same_thread=False`). **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar; si la base no existe (falta el archivo o el directorio padre), lanza `FileNotFoundError` sin crear archivos. La lectura nunca crea la base; la creación es responsabilidad de `conectar_bd()`/`main()`.
- `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` — **lectura paginada del catálogo**, claramente diferenciada de `listar_videos()` y preparada para que la interfaz consuma catálogos de decenas de miles de videos sin cargar todos los registros en memoria. Ejecuta en SQLite dos consultas con el **mismo filtro**: una consulta paginada (`SELECT ... FROM videos ORDER BY nombre LIMIT ? OFFSET ?`) y un `COUNT(*)`. Sin texto de búsqueda, cuenta y lista todo el catálogo; con texto, aplica a ambas consultas una coincidencia **parcial de nombre** (`LIKE` con patrón `%texto%`). Todos los valores (límite, desplazamiento, patrón) se pasan mediante **parámetros SQL**; nunca se interpola el texto buscado en el SQL. No lee primero toda la tabla, no cambia el esquema, no crea índices y no implementa ordenamiento configurable. **Validación previa a SQL**: `limite` debe ser entero positivo (bool → `TypeError`; ≤ 0 → `ValueError`); `desplazamiento` debe ser entero ≥ 0 (bool → `TypeError`; < 0 → `ValueError`); `texto` debe ser `None` o texto (`TypeError` en caso contrario). Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar y lanza `FileNotFoundError` sin crear archivos. Devuelve la estructura estable `{"videos": [...], "total": <int>, "limite": <int>, "desplazamiento": <int>}`, donde cada elemento de `videos` conserva exactamente los mismos campos y el mismo formato que `listar_videos()` (tuplas `(nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas)`). Abre y cierra su propia conexión en el hilo que la invoca (sin `check_same_thread=False`). **Limitación conocida**: `%` y `_` del texto actúan como comodines SQL `LIKE` (no como caracteres literales); la comilla simple sí se trata literalmente. Pendiente de decisión si se acepta como contrato.
- `main()` — CLI: sincroniza el catálogo contra `videos_prueba/` (ruta resuelta por `rutas.py`).

### `rutas.py` — capa centralizada de resolución de rutas
Único módulo responsable de derivar las rutas del proyecto a partir de su ubicación real (`os.path.dirname(os.path.abspath(__file__))`), sin depender del directorio de trabajo:

- `ruta_raiz()` — directorio raíz del proyecto.
- `ruta_biblioteca()` — ruta de `biblioteca.db`.
- `ruta_carpeta_miniaturas()` — ruta de `miniaturas/`.
- `ruta_carpeta_videos()` — ruta de `videos_prueba/`.

Diseñado como punto único de extensión para futuras rutas de configuración; no constituye todavía un módulo de configuración completo.

### `visor_videos.py` — interfaz gráfica
- `VisorVideos(QMainWindow)` — ventana principal: fila de selección de carpeta (botón + etiqueta de ruta), barra de búsqueda, contador, grilla de tarjetas dentro de un `QScrollArea`. Se construye **sin consultas SQLite**; la primera página del catálogo se carga en segundo plano mediante `GestorTareas` + `TareaLecturaCatalogoPaginada` (constantes `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO = "Cargando catálogo…"`, `MENSAJE_ERROR = "No se pudo cargar el catálogo"`, `MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"`, `MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"`, `MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"`, `MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"`).
- `carpeta_seleccionada` — atributo de sesión con la carpeta elegida; comienza como `None` y **no persiste** entre ejecuciones.
- `boton_seleccionar_carpeta` / `etiqueta_carpeta` / `mensaje_carpeta` — botón "Seleccionar carpeta" (`QPushButton`), etiqueta de solo lectura con la ruta elegida (`QLabel` con `Qt.TextSelectableByMouse`) y etiqueta de mensajes de error, integrados en una fila superior sin rediseñar la ventana.
- `seleccionar_carpeta()` — abre `QFileDialog.getExistingDirectory`; si el usuario cancela, conserva la selección anterior; si la ruta es válida, la **normaliza con `os.path.abspath`** (ruta absoluta), la **valida con `os.path.isdir`** (existe y es directorio), la muestra en la etiqueta y la guarda en `carpeta_seleccionada`; si la ruta no existe o no es un directorio, rechaza la selección, conserva la anterior y muestra `MENSAJE_RUTA_INVALIDA` sin cerrar la ventana. **Ausencia deliberada**: seleccionar la carpeta no escanea su contenido, no abre SQLite, no ejecuta FFprobe ni FFmpeg y no genera miniaturas; la selección no es persistente (vive solo en la sesión). La acción de escanear queda separada en el botón "Escanear carpeta".
- `boton_escanear` / `estado_escaneo` — botón "Escanear carpeta" (`QPushButton`) y etiqueta de estado del escaneo (`QLabel`), integrados en la fila de selección de carpeta. El botón queda habilitado solo si existe una carpeta válida y el gestor está `inactivo`.
- `videos_detectados` — atributo de la operación de escaneo: lista de archivos de video detectados en la última ejecución exitosa; comienza como `None` (aún no se escaneó) y no persiste entre ejecuciones.
- `iniciar_escaneo()` — acción manual del botón "Escanear carpeta": si el gestor está ocupado retorna; revalida la carpeta con `os.path.isdir`; crea una `TareaEscaneo(carpeta)` y la inicia con el **mismo** `GestorTareas` de la ventana (reutilizado para la carga inicial y para los escaneos sucesivos); marca `_escaneo_pendiente = True`, resetea el estado del encadenamiento (`_ffprobe_pendiente = False`, `_guardado_pendiente = False`, `tarea_escaneo = None`, `tarea_ffprobe = None`, `tarea_guardado = None`, `resultado_ffprobe = None`, `registros_guardados = None`), guarda la tarea en `tarea_escaneo` y muestra `MENSAJE_ESCANEANDO` ("Escaneando carpeta…"). Si `gestor.iniciar()` rechaza la tarea, vuelve al estado anterior. **El escaneo encadena la cadena completa**: al terminar el escaneo se inicia `TareaFFprobe` sobre las rutas detectadas, luego se combinan los registros con los metadatos y se persisten con `TareaGuardarVideos`, siempre con el mismo gestor.
- `_al_resultado_escaneo(videos)` — al recibir la lista, la copia en `videos_detectados`, limpia `_escaneo_pendiente`, **marca `_ffprobe_pendiente = True`** (para que el resultado/error siguiente pertenezca a FFprobe) y muestra el conteo en `estado_escaneo` ("1 video detectado" / "N videos detectados"). No crea tarjetas ni recarga el catálogo.
- `_al_error_escaneo(mensaje)` — ante un fallo (carpeta inexistente, ruta que no es carpeta, etc.): limpia `_escaneo_pendiente` y `_guardado_pendiente` y muestra `MENSAJE_ERROR_ESCANEO` ("No se pudo escanear la carpeta"). **El último resultado exitoso se conserva**: `videos_detectados` no se borra si ya tenía un valor previo.
- `_ffprobe_pendiente` / `tarea_ffprobe` / `resultado_ffprobe` — atributos del **paso de metadatos FFprobe** del encadenamiento: estado interno que enruta el resultado/error de FFprobe, la tarea `TareaFFprobe` en curso y el último resultado de FFprobe (`None` hasta que termina).
- `_iniciar_ffprobe()` — se lanza al recibir `tarea_finalizada` del escaneo (gestor `inactivo` y `_ffprobe_pendiente` activo): construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta, nombre)`) de los videos detectados, crea `TareaFFprobe(rutas)` y la inicia con el mismo `GestorTareas`; si el gestor rechaza la tarea o faltan datos previos, limpia la cadena.
- `_al_resultado_ffprobe(resultado)` — al recibir el resumen de `TareaFFprobe`: limpia `_ffprobe_pendiente`, **marca `_guardado_pendiente = True`** (para que el resultado/error siguiente pertenezca al guardado), guarda el resultado en `resultado_ffprobe` y libera `tarea_ffprobe`. No crea tarjetas ni recarga el catálogo.
- `_al_error_ffprobe(mensaje)` — ante un fallo global de FFprobe (subproceso ausente, error del ejecutable, etc.): limpia la cadena y muestra `MENSAJE_ERROR_FFPROBE` ("No se pudieron obtener los metadatos"). **El último resultado exitoso se conserva**: `videos_detectados` no se borra.
- `_guardado_pendiente` / `tarea_guardado` / `registros_guardados` — atributos del **encadenamiento de guardado**: estado interno que enruta el resultado/error del guardado, la tarea `TareaGuardarVideos` en curso y la cantidad de registros persistidos (`None` hasta que termina el guardado).
- `_al_tarea_finalizada()` — **dispara el paso siguiente de la cadena al terminar cada tarea**: cuando el gestor vuelve a `inactivo` (el gestor solo admite una tarea a la vez), enruta según el flag activo: si `_escaneo_pendiente` está activo no hace nada (el resultado del escaneo ya marcó el siguiente flag); si `_ffprobe_pendiente` está activo inicia `TareaFFprobe` (ver `_iniciar_ffprobe`); si `_guardado_pendiente` está activo inicia `TareaGuardarVideos` (ver `_iniciar_guardado`); si no hay flag activo y el gestor vuelve a `inactivo`, limpia la cadena.
- `_iniciar_guardado()` — se lanza al recibir `tarea_finalizada` de FFprobe (gestor `inactivo` y `_guardado_pendiente` activo): valida que existan `tarea_escaneo`, `videos_detectados` y `resultado_ffprobe`, prepara los registros con `combinar_registros_con_ffprobe(videos_detectados, tarea_escaneo.carpeta, resultado_ffprobe)` (claves básicas + metadatos FFprobe; `NULL` si faltan) y los persiste con `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo `GestorTareas`; si el inicio falla, limpia la cadena. No se ejecuta FFmpeg ni se generan miniaturas en este paso.
- `_al_resultado_guardado(resultado)` — al recibir `{"guardados": n, "nombres": [...]}`: limpia `_guardado_pendiente`, libera `resultado_ffprobe`, guarda la cantidad en `registros_guardados` y habilita de nuevo el botón de escaneo (gestor `inactivo`). No crea tarjetas ni recarga el catálogo.
- `_al_error_guardado(mensaje)` — ante un fallo de escritura (base inexistente, base corrupta, contrato inválido): limpia `_guardado_pendiente` y muestra `MENSAJE_ERROR_GUARDADO` ("No se pudieron guardar los videos"). El gestor queda `inactivo` y la interfaz es recuperable: se puede iniciar un nuevo escaneo. No se eliminan registros preexistentes ni se recarga el catálogo.
- `_mostrar_estado_escaneo()` — pluraliza el conteo: `videos_detectados is None` → `MENSAJE_SIN_ESCANEO` ("Sin escanear"); 1 → "1 video detectado"; n → "n videos detectados".
- `_actualizar_botones_carpeta()` — mantiene habilitado el botón "Escanear carpeta" solo con carpeta válida y gestor `inactivo`; mientras el escaneo (o la carga inicial) está en curso, los botones de la fila quedan deshabilitados.
- Enrutado por estado: `_al_resultado` / `_al_error` reenvían el resultado/error a los handlers de escaneo (`_al_resultado_escaneo` / `_al_error_escaneo`) **cuando `_escaneo_pendiente` está activo**, a los de FFprobe (`_al_resultado_ffprobe` / `_al_error_ffprobe`) **cuando `_ffprobe_pendiente` está activo** y a los de guardado (`_al_resultado_guardado` / `_al_error_guardado`) **cuando `_guardado_pendiente` está activo**; la cadena se produce porque el escaneo, FFprobe y el guardado son tareas sucesivas con el mismo gestor (el paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior, no en el handler del resultado). Es suficiente para una única tarea activa a la vez y debe revisarse si la interfaz incorpora más tipos de tarea. **Ausencia deliberada**: el pipeline escribe registros con metadatos FFprobe (duración, resolución, codec; `NULL` si FFprobe no puede obtenerlos) mediante el upsert transaccional existente, conservando los registros preexistentes; no recorre subcarpetas, no ejecuta FFmpeg, no genera miniaturas, no elimina registros ausentes, no crea tarjetas y no recarga el catálogo; no constituye la sincronización completa.
- `Tarjeta(QFrame)` — tarjeta por video: miniatura (o recuadro "Sin miniatura") + campos de texto (nombre, duración, resolución, codec, miniaturas).
- `_iniciar_carga()` — crea `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)` y la inicia con `gestor.iniciar()`.
- `_al_resultado(resultado)` — al recibir el resultado: oculta el estado de carga, crea las tarjetas (`_crear_tarjetas`) y marca `_carga_completada`.
- `_al_error(mensaje)` — al fallar la lectura: muestra `MENSAJE_ERROR` sin cerrar la ventana.
- `_crear_tarjetas(filas)` — construye una `Tarjeta` por fila en la `QGridLayout` (2 columnas) y reaplica el filtro vigente.
- `filtrar(texto)` — filtrado por coincidencia de nombre **sobre las tarjetas ya cargadas** (primera página); mantiene `visibles` y actualiza el contador.
- `actualizar_contador()` — muestra "N videos" / "1 video" según las tarjetas visibles.
- `closeEvent(event)` — apagado ordenado: llama `gestor.cerrar()` (timeout por defecto 5000 ms) y acepta el evento.
- `miniatura_principal(nombre)` — ubica la primera miniatura cuyo prefijo coincide con el video.
- `main()` — bootstrap de la app + **smoke test automático**: crea una **base SQLite temporal** reutilizando el esquema existente (`conectar_bd(ruta_db)` + `commit()` + `close()`, sin depender de `biblioteca.db`), abre la ventana, verifica el estado inicial sin carpeta ("Sin escanear" y botón de escanear deshabilitado), simula la selección de una carpeta temporal (diálogo inyectado y siempre restaurado) con archivos de video y no-video, simula cancelación y verifica que se conserva la selección, espera la carga asíncrona, dispara el escaneo real con `boton_escanear.click()`, observa "Escaneando carpeta…" mientras el gestor está ocupado, espera la cadena completa escaneo → FFprobe → guardado, imprime `videos_detectados` (3 videos), la cantidad de registros guardados (`guardado_total=3`), el estado final y el filtro con "real", y cierra con `exit 0`.

### `tareas.py` — infraestructura genérica de trabajos en segundo plano
- `Estado` — estados del ciclo de vida: `inactivo`, `ocupado`, `finalizando`, `cerrado`.
- `TareaBase(QObject)` — clase base de tareas asíncronas; señales `inicio`, `finalizada`, `error(str)`, `resultado(object)`. `ejecutar()` emite `inicio`, invoca `_trabajo()` y emite `resultado(valor)`; ante una excepción emite `error(f"{Tipo}: {msg}")`; siempre emite `finalizada`. Las subclases implementan `_trabajo()`.
- `GestorTareas(QObject)` — orquesta cada tarea en un `QThread` propio. Señales `tarea_iniciada`, `tarea_resultado(object)`, `tarea_error(str)`, `tarea_finalizada` y `actividad_cambiada(bool)`. `iniciar(tarea)` valida la tarea, crea el `QThread`, la mueve a él y lo arranca; el hilo termina cuando la tarea emite `finalizada`. `cerrar(timeout_ms)` permite el apagado ordenado.

### `tareas_videos.py` — tareas asíncronas específicas de video
Capa de **tareas asíncronas**: no define lógica de catálogo ni de datos. Re-exporta desde `escanear_videos.py` las funciones que la interfaz necesita importar (entre ellas `preparar_registros_basicos`, `combinar_registros_con_ffprobe` y `conectar_bd`), lo que evita que `visor_videos.py` dependa directamente del backend de catálogo.
- `rutas_videos()` — rutas absolutas de los videos de `videos_prueba/` detectados por `escanear_videos`.
- `TareaFFprobe(TareaBase)` — ejecuta `obtener_datos_ffprobe` sobre una lista de rutas en segundo plano; devuelve un diccionario con `rutas`, `resultados`, `procesados`, `con_datos` y `con_error`. Cada resultado contiene `ruta`, `datos` y `error` por archivo.
- `TareaEscaneo(TareaBase)` — recibe una carpeta y devuelve la misma lista ordenada de archivos de video que `escanear_videos(carpeta)`. Una carpeta inexistente (`FileNotFoundError`) o una ruta que no es carpeta (`NotADirectoryError`) se propaga mediante la señal `error` de la infraestructura.
- `TareaLecturaCatalogo(TareaBase)` — lee el catálogo en segundo plano invocando `listar_videos(ruta_db)`; devuelve la misma estructura que la lectura síncrona. Acepta una ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Regla de conexión SQLite por hilo**: la conexión se abre y se cierra dentro del hilo de trabajo, se usa únicamente en ese hilo, no se almacena como atributo persistente de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores de lectura (`FileNotFoundError` si la base no existe, `sqlite3.OperationalError`, `sqlite3.DatabaseError`, etc.) se convierten en la señal `error` gestionada por `TareaBase`. La lectura no crea archivos: si la base no existe, se comunica `FileNotFoundError` sin crear la base.
- `TareaLecturaCatalogoPaginada(TareaBase)` — lectura **paginada** del catálogo en segundo plano. Recibe los mismos parámetros que `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` (ruta de base opcional; por defecto `ruta_biblioteca()`). El constructor conserva una instantánea de los parámetros (escalares inmutables) y expone las propiedades `limite`, `desplazamiento`, `texto` y `ruta_db`. `_trabajo()` invoca `listar_videos_paginado` y devuelve exactamente su resultado `{"videos", "total", "limite", "desplazamiento"}`. **Regla de conexión SQLite por hilo**: la conexión se abre y se cierra dentro del hilo de trabajo (mediante la función síncrona), se usa únicamente en ese hilo, no se almacena como atributo y no se usa `check_same_thread=False`. Los errores de contrato (`TypeError`/`ValueError`), `FileNotFoundError` si la base no existe y `sqlite3.DatabaseError` si la base está corrupta se convierten en la señal `error` gestionada por `TareaBase`. No accede a la interfaz, no escanea archivos, no ejecuta FFprobe ni FFmpeg y no escribe en SQLite. `TareaLecturaCatalogo` conserva su contrato sin cambios.
- `TareaGuardarVideo(TareaBase)` — guarda un único registro de video en segundo plano invocando `guardar_video(datos, ruta_db)`; devuelve el resultado simple `{"guardado": True, "nombre": ...}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instantánea del registro**: el constructor toma una copia superficial (`self._datos = dict(datos)`), de modo que mutaciones posteriores del diccionario original del llamador no afectan la ejecución; la propiedad `datos` devuelve una copia y nunca expone el diccionario interno. Un valor que `dict()` no pueda copiar se conserva como `datos` inválido y `_trabajo()` lo comunica mediante `error` (`TypeError`) sin tocar la base. **Regla de conexión SQLite por hilo**: la conexión se abre dentro de `_trabajo()` (mediante la función síncrona), se usa únicamente en ese hilo, el `commit` se ejecuta en el hilo de trabajo solo si toda la operación terminó correctamente, se ejecuta `rollback` ante cualquier error posterior al inicio de la transacción, se cierra siempre en `finally`, no se almacena como atributo de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores (`FileNotFoundError` si la base no existe, `sqlite3.DatabaseError` si la base está corrupta, `ValueError`/`TypeError` por contrato inválido, etc.) se convierten en la señal `error`. No sincroniza el catálogo, no elimina registros, no encadena tareas y no se conecta a la interfaz.
- `TareaGuardarVideos(TareaBase)` — guarda una **colección de registros** en segundo plano invocando `guardar_videos(datos_videos, ruta_db)`; devuelve el resumen `{"guardados": <cantidad>, "nombres": [...]}`. Acepta la ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Instantánea de la colección y de cada registro**: el constructor materializa la colección (`list(...)`) y toma una **copia superficial por registro** (`dict(d)`) al construirse; no conserva la colección mutable original, de modo que mutaciones posteriores de la lista o de los diccionarios del llamador no afectan la ejecución; la propiedad `datos` devuelve copias frescas y nunca expone el estado interno. **El constructor nunca lanza ante entradas inválidas**: si la colección no es iterable, es texto, contiene un elemento no copiable, o incluso si su materialización falla a mitad de la iteración (p. ej. un generador que lanza una excepción), la tarea se construye igualmente, se conserva la causa como colección inválida y `_trabajo()` la comunica mediante `error` (un `TypeError` que envuelve la causa) sin tocar la base; los errores de contrato que solo `guardar_videos` detecta al validar (p. ej. una clave obligatoria ausente en un registro ya copiado) también se comunican por `error` durante la ejecución. **Regla de conexión SQLite por hilo**: la conexión se abre dentro de `_trabajo()` (mediante la función síncrona) y realiza un único `commit` por colección en el hilo de trabajo; `rollback` ante cualquier error; se cierra siempre en `finally`; no se almacena como atributo de la tarea; sin `check_same_thread=False`. Los errores (`FileNotFoundError`, `sqlite3.DatabaseError`, `ValueError`/`TypeError` por contrato inválido, fallo durante el registro intermedio con rollback total) se convierten en la señal `error`. No sincroniza el catálogo, no elimina registros, no encadena tareas, no implementa escritura por lotes concurrentes y no se conecta a la interfaz.

### Módulos ajenos al visor (preservados, no forman parte de la arquitectura)
- `operaciones.py` — función `sumar`; usado solo por `main.py`.
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
| FFmpeg | `escanear_videos.generar_miniatura` | Extrae un fotograma del video; genera la miniatura automáticamente. |
| Generación de miniaturas | `escanear_videos.asegurar_miniatura` | Genera o reutiliza; escribe solo en la siguiente ranura libre y preserva los archivos existentes. |
| Trabajos en segundo plano | `tareas.py` | `TareaBase` + `GestorTareas` (`QThread` por ejecución); señales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada`. |
| Escaneo asíncrono | `tareas_videos.TareaEscaneo` | Envuelve `escanear_videos` en segundo plano; errores por señal `error`. |
| FFprobe asíncrono | `tareas_videos.TareaFFprobe` | Metadatos de video en segundo plano; resultado y error por ruta. |
| Lectura del catálogo | `escanear_videos.listar_videos` | Capa de lectura SQLite; abre y cierra su propia conexión en el hilo que la invoca. |
| Lectura asíncrona del catálogo | `tareas_videos.TareaLecturaCatalogo` | Lectura SQLite en segundo plano; errores por señal `error`; conexión por hilo (sin `check_same_thread=False`). |
| Lectura paginada del catálogo | `escanear_videos.listar_videos_paginado` + `tareas_videos.TareaLecturaCatalogoPaginada` | Página (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro en SQL; búsqueda parcial por `LIKE` parametrizada; sin leer toda la tabla; consumida por la interfaz para la carga inicial asíncrona de la primera página. |
| Carga inicial asíncrona de la interfaz | `visor_videos.VisorVideos` + `tareas.GestorTareas` + `tareas_videos.TareaLecturaCatalogoPaginada` | La ventana se construye sin consultas SQL; `_iniciar_carga()` lee la primera página en segundo plano; estados de carga/error visibles y apagado ordenado en `closeEvent` (`gestor.cerrar()`). |
| Selección de carpeta desde la interfaz | `visor_videos.VisorVideos.seleccionar_carpeta` | `QFileDialog` + `os.path.abspath`/`os.path.isdir`; ruta en `carpeta_seleccionada`; no escanea, no toca SQLite/FFprobe/FFmpeg/miniaturas. |
| Escaneo asíncrono desde la interfaz | `visor_videos.VisorVideos.iniciar_escaneo` + `tareas_videos.TareaEscaneo` + `tareas.GestorTareas` | Botón "Escanear carpeta"; reutiliza el mismo `GestorTareas` de la ventana; estados internos `_escaneo_pendiente`/`tarea_escaneo`; resultado en `videos_detectados` con conteo visible; bloqueo de controles mientras el gestor está ocupado; sin SQLite/FFprobe/FFmpeg/miniaturas/tarjetas/recarga del catálogo. |
| Escritura individual | `escanear_videos.guardar_video` | Upsert transaccional de un único registro (datos preparados); `commit`/`rollback`/`close` propios; base inexistente → `FileNotFoundError` sin crear archivos. |
| Escritura individual asíncrona | `tareas_videos.TareaGuardarVideo` | Guarda un registro en segundo plano; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardado": True, "nombre": ...}`. |
| Escritura de colección | `escanear_videos.guardar_videos` | Upsert de una colección de registros en una **única transacción atómica** (un solo `connect` y un solo `commit`; `rollback` total ante cualquier fallo); validación completa y copias previas a SQL; resultado `{"guardados": n, "nombres": [...]}`; no elimina registros. |
| Escritura de colección asíncrona | `tareas_videos.TareaGuardarVideos` | Guarda una colección en segundo plano; instantánea de la lista y de cada registro; `commit` y `rollback` dentro del hilo de trabajo; resultado `{"guardados": n, "nombres": [...]}`. |
| Preparación de registros básicos | `escanear_videos.preparar_registros_basicos` | Transforma los archivos detectados por el escaneo en registros con claves exactas `{nombre, ruta, extension, fecha_importacion}` (ruta absoluta en la carpeta escaneada); validación previa (no texto, iterable, carpeta no vacía); sin SQLite/FFprobe/FFmpeg/miniaturas. |
| Combinación de registros con metadatos FFprobe | `escanear_videos.combinar_registros_con_ffprobe` | Transforma los archivos detectados y el resultado de `TareaFFprobe` en registros con claves básicas `{nombre, ruta, extension, fecha_importacion}` + metadatos FFprobe (`duracion_segundos`, `ancho`, `alto`, `codec_video`; `NULL` si el video no tiene `datos`); pura, sin SQLite/FFprobe/FFmpeg/miniaturas; normalización interna de rutas. |
| Encadenamiento del pipeline desde la interfaz | `visor_videos.VisorVideos` + `tareas_videos.TareaEscaneo`/`TareaFFprobe`/`TareaGuardarVideos` + `escanear_videos.combinar_registros_con_ffprobe` | Tareas sucesivas con el mismo `GestorTareas`: `TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaGuardarVideos`. El paso siguiente se lanza al recibir `tarea_finalizada` de la tarea anterior (el gestor `Ocupado` rechaza una segunda tarea mientras otra corre); resultado/error del guardado limpian `_guardado_pendiente`; tras un error de guardado o de FFprobe el gestor queda `inactivo` y un nuevo escaneo es posible. No es la sincronización completa del catálogo. |
| Caché | — | **No existe** un módulo de caché; la BD cumple parcialmente ese rol para metadatos. |
| Configuración | `rutas.py` | Resolución de rutas del proyecto (raíz, BD, miniaturas, videos) centralizada e independiente del CWD. Aún no hay módulo de configuración completo. |

## 5. Flujo de ejecución (apertura → tarjetas)

1. `python visor_videos.py` → `main()` crea `QApplication` y la `VisorVideos`.
2. `VisorVideos.__init__` crea la barra de búsqueda, el contador, el estado de carga ("Cargando catálogo…") y el `QScrollArea`. **No abre SQLite**: crea `GestorTareas(self)` y arranca `_iniciar_carga()`.
3. `_iniciar_carga()` construye `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)` y la ejecuta en un `QThread` mediante `gestor.iniciar()`.
4. En el hilo de trabajo, `TareaLecturaCatalogoPaginada._trabajo()` invoca `listar_videos_paginado`, que abre su propia conexión, ejecuta `SELECT ... ORDER BY nombre LIMIT ? OFFSET ?` y `SELECT COUNT(*) ...`, la cierra y devuelve `{"videos": [...], "total": n, "limite": n, "desplazamiento": n}`.
5. Al emitirse `tarea_resultado`, `_al_resultado` oculta el estado de carga, `_crear_tarjetas` crea una `Tarjeta` por fila en la `QGridLayout` (2 columnas) y se aplica el filtro vigente.
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

Encadenamiento del pipeline escaneo → FFprobe → guardado (tareas
sucesivas con el mismo gestor):

6. Al terminar el hilo del escaneo, `GestorTareas` vuelve a `inactivo` y
   emite `tarea_finalizada`. `_al_tarea_finalizada()` detecta
   `_ffprobe_pendiente` activo y el gestor `inactivo`, y `_iniciar_ffprobe()`
   construye las rutas absolutas (`os.path.join(tarea_escaneo.carpeta,
   nombre)`) de los videos detectados e inicia `TareaFFprobe(rutas)` con
   el mismo `GestorTareas`. El paso siguiente no se lanza en el handler
   del resultado del escaneo: el gestor `Ocupado` rechazaría una segunda
   tarea.
7. En el hilo de trabajo, `TareaFFprobe._trabajo()` ejecuta
   `obtener_datos_ffprobe` por ruta (timeout 30 s) y devuelve el resumen
   con `resultados` (`ruta`, `datos`, `error` por archivo), `procesados`,
   `con_datos` y `con_error`. `_al_resultado_ffprobe` (enrutado por
   `_ffprobe_pendiente`) guarda el resultado en `resultado_ffprobe`,
   limpia el flag y **marca `_guardado_pendiente = True`**. Ante un
   error global de FFprobe, `_al_error_ffprobe` limpia la cadena y
   muestra "No se pudieron obtener los metadatos".
8. Al terminar FFprobe, `_al_tarea_finalizada()` detecta
   `_guardado_pendiente` activo y `_iniciar_guardado()` prepara los
   registros con `combinar_registros_con_ffprobe(videos_detectados,
   tarea_escaneo.carpeta, resultado_ffprobe)` (claves básicas
   `{nombre, ruta, extension, fecha_importacion}` con ruta absoluta +
   metadatos FFprobe `{duracion_segundos, ancho, alto, codec_video}`;
   `NULL` si el video no tiene `datos`) y los persiste con
   `TareaGuardarVideos(registros, ruta_db)` iniciada con el mismo
   `GestorTareas`.
9. En el hilo de trabajo, `TareaGuardarVideos._trabajo()` invoca
   `guardar_videos`, que valida la colección, ejecuta el upsert
   transaccional (inserta o actualiza sin duplicar, **conservando los
   registros preexistentes** y sin eliminar ninguno) y hace un único
   `commit`; devuelve `{"guardados": n, "nombres": [...]}`.
10. `_al_resultado` reenvía el resultado a `_al_resultado_guardado`
   (enrutado por `_guardado_pendiente`), que limpia el flag, libera
   `resultado_ffprobe`, guarda la cantidad en `registros_guardados` y
   habilita de nuevo el botón de escaneo. No se crean tarjetas ni se
   recarga el catálogo.
11. Ante un error de escritura, `_al_error_guardado` limpia
   `_guardado_pendiente`, muestra "No se pudieron guardar los videos" y
   el gestor queda `inactivo`: la interfaz es recuperable y un nuevo
   escaneo es posible. Los registros preexistentes permanecen intactos.
12. El pipeline **no constituye la sincronización completa**: ejecuta
   FFprobe para completar duración, resolución y codec (con `NULL` ante
   vacíos, incompletos o fallos individuales), pero no genera
   miniaturas, no elimina registros ausentes, no recarga la grilla ni
   recorre subcarpetas.

La carga inicial muestra únicamente la primera página del catálogo
(primeros `TAMANIO_PAGINA_INICIAL` registros); el resto del catálogo no
se carga todavía (paginación adicional, scroll infinito y búsqueda en
SQL quedan para etapas futuras).

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

Durante un escaneo se genera **como máximo una miniatura nueva por video**, y únicamente cuando no existe ninguna miniatura considerada vigente (criterio `mtime`). Pueden coexistir varias miniaturas del mismo video en distintas ranuras `_NN`. La convención `<prefijo>_NN.jpg` permite convivir con miniaturas preexistentes sin perderlas. Los videos vacíos (0 bytes) no generan miniatura.

## 7. Puntos de extensión previstos

1. **Generación de miniaturas con FFmpeg** — **implementada** en `escanear_videos.py` (`asegurar_miniatura`/`generar_miniatura`): genera como máximo una miniatura nueva por video por escaneo, preservando los archivos existentes.
2. **Ejecución asíncrona** — **en curso**: el escaneo (`TareaEscaneo`), FFprobe (`TareaFFprobe`), la **lectura del catálogo SQLite** (`TareaLecturaCatalogo`, solo lectura), la **lectura paginada del catálogo SQLite** (`TareaLecturaCatalogoPaginada`, con `LIMIT`/`OFFSET`/`COUNT` en SQL), la **escritura individual SQLite** (`TareaGuardarVideo`, un registro por operación) y la **escritura de colección SQLite** (`TareaGuardarVideos`, colección limitada en una única transacción) ya se ejecutan en segundo plano mediante `tareas.py`. **La integración de la lectura paginada con la ventana está completa**: `visor_videos.py` carga la primera página en segundo plano con estado de carga y manejo de errores. **La selección de carpeta desde la interfaz está completa** y **el escaneo manual y asíncrono de la carpeta elegida está completo**: `visor_videos.py` permite elegir la carpeta de videos y escanearla con `TareaEscaneo` mediante el mismo `GestorTareas`, mostrando la cantidad de videos detectados. **El encadenamiento del pipeline está completo**: `TareaEscaneo` → `TareaFFprobe` → combinación de registros (`combinar_registros_con_ffprobe`, capa de catálogo en `escanear_videos.py`) → `TareaGuardarVideos`, ejecutado como tareas sucesivas con el mismo gestor; los archivos detectados se escriben en SQLite con metadatos FFprobe (duración, resolución, codec; `NULL` ante vacíos/incompletos/fallos individuales) mediante el upsert transaccional existente, conservando los registros preexistentes y recuperándose la interfaz tras errores de guardado. Pendiente: la **sincronización completa** del catálogo disco ↔ BD (escritura masiva con detección de archivos y eliminación de registros ausentes) y FFmpeg asíncrono.
3. **Módulo de configuración** — centralizar rutas (`videos_prueba`, `miniaturas`, `biblioteca.db`), extensiones, tamaños de tarjeta y número de columnas.
4. **Caché de miniaturas/metadatos** — formalizar la BD como caché de metadatos y evitar re-escaneos.
5. **Lectura/vistas del catálogo** — sobre `listar_videos()` y `listar_videos_paginado()`, agregar orden/agrupación/filtros adicionales sin tocar la UI. La lectura paginada con búsqueda en SQL está implementada y la primera página ya se integra con la interfaz; la paginación completa (scroll infinito, búsqueda en SQL) queda para etapas posteriores.
6. **Autenticación de rutas absolutas** — **implementada** en `rutas.py`: `biblioteca.db`, `miniaturas/` y `videos_prueba/` se resuelven desde la ubicación real del módulo, independientemente del directorio de trabajo.

## 8. Problemas detectados

| # | Severidad | Problema |
| --- | --- | --- |
| 1 | Media | La interfaz (`visor_videos.py`) accedía a SQLite directamente y duplicaba el nombre de BD (`"biblioteca.db"`). **Corregido** en esta etapa. |
| 2 | Media | Rutas relativas (`miniaturas/`, `videos_prueba/`, `biblioteca.db`) dependían del directorio de trabajo; la app fallaba si se lanzaba desde otra ubicación. **Resuelto** (ver §9, etapa de rutas). |
| 3 | Media | No existía generación de miniaturas; solo conteo. **Resuelto** (ver §6). |
| 4 | Media | FFprobe se ejecutaba en el hilo principal con timeout de 30 s por video; el escaneo bloquea. **Resuelto en parte**: FFprobe se movió a segundo plano con `TareaFFprobe` y la carga inicial del catálogo se integró con las tareas asíncronas (`visor_videos.py` + `TareaLecturaCatalogoPaginada`). FFmpeg asíncrono y la sincronización completa del catálogo continúan pendientes. |
| 5 | Baja | `contar_miniaturas`/`miniatura_principal` usan coincidencia por prefijo (`startswith`); un video `video_real.mp4` podría matchear miniaturas de un hipotético `video_realista.mp4`. Pendiente. |
| 6 | Baja | Los videos vacíos (0 bytes) quedan sin metadatos; comportamiento correcto pero debe documentarse para el usuario. Pendiente. |
| 7 | Informativa | `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` son artefactos de prueba ajenos al visor. Se preservaron por política de esta etapa. |
| 8 | Media | Crecimiento acumulativo de miniaturas: la regeneración escribe una ranura nueva (`_NN`) en lugar de sobrescribir; si el video cambia varias veces se acumulan archivos y `cantidad_miniaturas` crece. Pendiente. |
| 9 | Baja | La interfaz muestra la primera miniatura por orden alfabético (`_01`), incluso cuando una versión más nueva (`_02`) es la vigente. Pendiente. |
| 10 | Media | El criterio de reutilización usa únicamente `mtime` (sin hash ni validación de integridad); no detecta cambios de contenido que conserven la fecha. Pendiente (mejora diferida). |
| 11 | Media | Falta una limpieza controlada de versiones antiguas de miniaturas; por regla, los archivos nunca se eliminan automáticamente, por lo que requiere autorización expresa. Pendiente. |
| 12 | Media | FFmpeg escribe directamente en la ruta definitiva de la miniatura; si falla después de comenzar la escritura puede quedar un archivo parcial o corrupto. Actualmente ese archivo no se elimina ni se valida, y por existencia y `mtime` podría ser contado o considerado vigente. Pendiente. |
| 13 | Baja | El pipeline limitado escribía registros **básicos** (nombre, ruta absoluta, extensión, fecha de importación) sin ejecutar FFprobe; los videos quedaban sin duración, resolución ni codec. **Resuelto** en esta etapa: FFprobe se integró en el pipeline (`TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaGuardarVideos`) y los registros se guardan con los metadatos disponibles (`NULL` ante vacíos, incompletos o fallos individuales). |

## 9. Cambios aplicados en esta etapa

Mínimos y justificados (etapa de congelamiento, sin funcionalidad nueva):

- `escanear_videos.py`
  - Nueva constante `NOMBRE_DB = "biblioteca.db"` (elimina el literal duplicado).
  - `conectar_bd()` usa `NOMBRE_DB`.
  - Nueva función `listar_videos()`: única capa de lectura SQLite consumida por la interfaz.
- `visor_videos.py`
  - Eliminados `import sqlite3` y la constante `NOMBRE_DB`.
  - Eliminada la función local `cargar_videos()` (acceso directo a SQLite).
  - `cargar_tarjetas()` ahora consume `listar_videos()` importado desde `escanear_videos`.

### Etapa de generación de miniaturas (posterior a la congelación)

- `escanear_videos.py`
  - Nuevas constantes `CARPETA_MINIATURAS` y `EXTENSION_MINIATURA`.
  - Nuevas funciones `ffmpeg_disponible`, `ruta_miniatura`, `calcular_tiempo_miniatura`, `miniatura_vigente`, `generar_miniatura`, `siguiente_indice_libre`, `miniatura_reutilizable`, `asegurar_miniatura`.
  - `sincronizar_bd()` invoca `asegurar_miniatura` para cada video antes de `actualizar_datos` (reutiliza si existe una miniatura válida; si no, escribe en la siguiente ranura libre, sin sobrescribir ni eliminar).

### Etapa de rutas independientes del directorio de trabajo

- `rutas.py` (nuevo)
  - Capa centralizada de resolución de rutas: `ruta_raiz()`, `ruta_biblioteca()`, `ruta_carpeta_miniaturas()`, `ruta_carpeta_videos()`.
  - La raíz se ancla en `os.path.dirname(os.path.abspath(__file__))`, por lo que el proyecto funciona sin importar desde dónde se ejecute Python.
- `escanear_videos.py`
  - Eliminadas las constantes relativas `NOMBRE_DB` y `CARPETA_MINIATURAS`.
  - `conectar_bd()`, `listar_videos()`, `ruta_miniatura()`, `miniatura_reutilizable()`, `asegurar_miniatura()`, `contar_miniaturas()` y `main()` resuelven `biblioteca.db`, `miniaturas/` y `videos_prueba/` a través de `rutas.py`.
  - No se modificaron SQLite, el escaneo ni el algoritmo de miniaturas.
- `visor_videos.py`
  - `miniatura_principal()` resuelve `miniaturas/` a través de `rutas.py`. Sin cambios de interfaz.

### Etapa de infraestructura reutilizable de trabajos en segundo plano

- `tareas.py` (nuevo)
  - `Estado`, `TareaBase` y `GestorTareas`: ejecución de tareas en un `QThread` propio por ejecución, con señales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada` y `actividad_cambiada`. Ciclo de vida `inactivo` → `ocupado` → `inactivo`; `cerrar()` permite el apagado ordenado.
- `prueba_tareas.py` (nuevo)
  - Pruebas de la infraestructura: ejecución en hilo, orden de señales, errores, concurrencia de gestores, rechazos y ciclo de vida del hilo.

### Etapa de procesamiento asíncrono de metadatos (TareaFFprobe)

- `tareas_videos.py` (nuevo)
  - `rutas_videos()` y `TareaFFprobe(TareaBase)`: metadatos FFprobe en segundo plano, con resultado por ruta (`ruta`, `datos`, `error`) y resumen (`procesados`, `con_datos`, `con_error`).
- `prueba_ffprobe.py` (nuevo)
  - Pruebas de `TareaFFprobe` mediante `GestorTareas`: video real, archivos vacíos, rutas inexistentes, hilo de trabajo, señales y rechazos.

### Etapa de escaneo asíncrono (TareaEscaneo)

- `tareas_videos.py`
  - `TareaEscaneo(TareaBase)`: recibe una carpeta y devuelve en segundo plano la misma lista que `escanear_videos(carpeta)`. Los errores de carpeta inexistente o ruta que no es carpeta se propagan mediante la señal `error` de la infraestructura.
- `prueba_escaneo.py` (nuevo)
  - Pruebas de `TareaEscaneo` con directorios temporales: equivalencia con la función síncrona, orden, filtrado de extensiones, carpeta vacía, carpeta inexistente, ruta-archivo, fallo controlado por señal, ausencia de SQLite/FFprobe/FFmpeg y ciclo de vida del hilo.

### Etapa de lectura asíncrona del catálogo (TareaLecturaCatalogo)

- `escanear_videos.py`
  - `listar_videos(ruta_db=None)`: parámetro opcional de ruta de base (por defecto `ruta_biblioteca()`) para permitir lecturas con bases temporales en pruebas; comportamiento por defecto sin cambios. Validación previa mínima: si la base no existe (archivo o directorio padre), lanza `FileNotFoundError` antes de conectar y **no crea archivos** (la lectura no crea la base; se evita que `sqlite3.connect` deje un archivo vacío de 0 bytes). Confirmado por diagnóstico aislado: `sqlite3.connect` sobre un archivo inexistente en un directorio existente crea un archivo de 0 bytes y el SELECT falla con `no such table: videos`; con directorio padre inexistente lanza `unable to open database file` sin crear archivo. Con la validación, ambos casos producen `FileNotFoundError` sin efectos secundarios.
- `tareas_videos.py`
  - `TareaLecturaCatalogo(TareaBase)`: lee el catálogo en segundo plano vía `listar_videos`; conexión SQLite abierta y cerrada dentro del hilo de trabajo, sin `check_same_thread=False`, sin conexión compartida con el hilo principal. Por heredar la validación de `listar_videos`, la lectura asíncrona tampoco crea archivos y comunica `FileNotFoundError` por la señal `error` cuando la base no existe.
- `prueba_lectura.py` (nuevo)
  - Pruebas de `TareaLecturaCatalogo` con bases temporales: equivalencia síncrona/asíncrona, ejecución en `QThread`, conexión abierta/cerrada en el hilo de trabajo, base vacía, varias filas, orden, `NULL`, base inexistente, directorio padre inexistente, base corrupta, única finalización, liberación del hilo, ausencia de escritura, ausencia de escaneo/FFprobe/FFmpeg y **no deja archivos inesperados** (el listado del directorio temporal queda idéntico tras lecturas con base válida, base corrupta y base inexistente).

### Etapa de escritura individual asíncrona (TareaGuardarVideo)

- `escanear_videos.py`
  - `guardar_video(datos, ruta_db=None)`: operación síncrona transaccional para **insertar o actualizar un único registro** de video recibido ya preparado como `dict`. No envuelve `insertar_video`/`actualizar_datos` (dependen de conexión externa, derivan datos de disco/FFprobe y `actualizar_datos` ejecuta FFprobe); usa un upsert `INSERT ... ON CONFLICT(nombre) DO UPDATE` que conserva el contrato y campos reales de la tabla. **Validación previa a SQL**: `datos` no-dict → `TypeError`; ausencia de `nombre`, `ruta`, `extension` o `fecha_importacion` → `ValueError`; ambas antes de conectar (sin abrir ni modificar la base). Valida `os.path.isfile(ruta_db)` antes de conectar (base inexistente → `FileNotFoundError`, sin crear archivos). Ciclo exacto: `sqlite3.connect(ruta_db)` → upsert (transacción implícita al primer DML) → `commit()` si la operación terminó correctamente → `rollback()` ante cualquier excepción → `close()` siempre en `finally`. Devuelve `{"guardado": True, "nombre": ...}`.
- `tareas_videos.py`
  - `TareaGuardarVideo(TareaBase)`: recibe `datos` y `ruta_db` opcional; el constructor guarda una **instantánea** (`self._datos = dict(datos)`), de modo que mutaciones posteriores del diccionario original no afectan la ejecución, y si `dict()` no puede copiar el valor lo conserva como datos inválidos que `_trabajo()` comunica por `error` (`TypeError`) sin tocar la base; la propiedad `datos` devuelve una copia (nunca expone el diccionario interno). `_trabajo()` valida antes de SQL y luego invoca `guardar_video` y devuelve su resultado. La conexión se abre, usa y cierra dentro del hilo de trabajo; `commit` en el hilo de trabajo; `rollback` ante errores posteriores al inicio de la transacción; sin conexión almacenada como atributo; sin `check_same_thread=False`; sin compartir con el hilo principal.
- `prueba_guardar.py` (nuevo)
  - Pruebas con bases SQLite temporales: inserción de registro nuevo, actualización sin duplicar, conservación de todos los campos, `NULL` permitidos, operación real con `GestorTareas`/`QThread`, conexión/`commit`/cierre en el hilo de trabajo, resultado en el hilo principal, ausencia de conexión almacenada, única `finalizada`, rollback con fallo controlado real y **ausencia de cambios parciales** (contenido y bytes de la base idénticos tras el rollback), base inexistente (archivo y directorio padre) sin crear archivos, base corrupta por señal `error`, liberación del hilo/gestor, ausencia de escaneo/FFprobe/FFmpeg/subprocesos, datos reales (`biblioteca.db`, `miniaturas/`, `videos_prueba/`) intactos, **instantánea del registro** (mutar el diccionario original tras construir la tarea no altera lo guardado), **entrada inválida no-dict** (`None`, `int`, `str` → `error` con `TypeError` sin cambios en la base), **clave obligatoria ausente** (`nombre`/`ruta`/`extension`/`fecha_importacion` → `error` con `ValueError` y sin insert/update), **opcionales ausentes → `NULL`** de forma explícita y **liberación tras errores** (tras errores de contrato y una operación correcta no quedan hilos, gestores, tareas ni avisos de destrucción).

### Etapa de escritura de colección (guardar_videos / TareaGuardarVideos)

- `escanear_videos.py`
  - Se extrajeron los internos compartidos `_validar_registro_video(datos)` (contrato de claves obligatorias) y `_upsert_video(conn, datos)` (upsert `INSERT ... ON CONFLICT(nombre) DO UPDATE` sin `commit`/`rollback`/`close`). `guardar_video` y `guardar_videos` reutilizan ambos: **no se duplica SQL ni validación** y `guardar_video` conserva su contrato y ciclo de conexión propios (regresión cubierta por `prueba_guardar.py` y por la nueva suite).
  - `guardar_videos(datos_videos, ruta_db=None)`: escritura de colección en **una única transacción atómica**. Validación completa previa a SQL: entrada iterable y no texto (texto → `TypeError`), materialización en lista, validación de todos los registros y **copias superficiales** de cada uno; una colección con un registro inválido se rechaza completa **antes de abrir SQLite**. Ciclo: un solo `connect` → todos los upserts → **un solo** `commit` → `rollback` ante cualquier excepción (ningún registro anterior persiste; los preexistentes conservan sus valores; no queda transacción abierta) → `close` siempre en `finally`. Colección vacía: éxito con cero registros sin modificar la base. Base inexistente: `FileNotFoundError` sin crear archivos. Devuelve `{"guardados": n, "nombres": [...]}` (orden de la colección). No detecta archivos, no ejecuta escaneo/FFprobe/FFmpeg, no genera miniaturas, **no elimina registros** y no compara disco ↔ base; la sincronización completa del catálogo sigue pendiente.
- `tareas_videos.py`
  - `TareaGuardarVideos(TareaBase)`: recibe la colección y `ruta_db` opcional; el constructor materializa la colección y toma una **instantánea por registro** (`dict(d)`), de modo que mutaciones posteriores de la lista o de los diccionarios originales no afectan la ejecución; ante cualquier fallo al materializar o copiar la colección (no iterable, texto, elemento no copiable, o un generador que lanza a mitad de la iteración) la tarea se construye igualmente y `_trabajo()` comunica la causa por `error` (`TypeError` envolviendo la causa) sin tocar la base. `_trabajo()` invoca `guardar_videos` y devuelve su resumen. Conexión, un único `commit`, `rollback` y `close` dentro del hilo de trabajo; sin conexión almacenada como atributo; sin `check_same_thread=False`; sin compartir con el hilo principal. No implementa eliminación, sincronización, pipeline ni interfaz.
- `prueba_guardar_videos.py` (nuevo)
  - Pruebas con bases SQLite temporales: colección vacía, un registro, varios registros nuevos, actualización de varios existentes, mezcla de inserciones y actualizaciones, conservación de todos los campos, opcionales ausentes → `NULL`, orden del resumen devuelto, **una sola conexión** y **un solo commit** por colección, conexión/`commit`/cierre en el hilo de trabajo, resultado en el hilo principal, **instantánea de la lista original** y **de cada diccionario**, entrada no iterable y texto rechazados (síncrono y asíncrono), registro inválido y clave obligatoria ausente **detectados antes de abrir SQLite** (sin conexión), fallo real durante el registro intermedio, **rollback total** (contenido y bytes de la base idénticos), **ausencia de inserciones parciales**, **restauración de valores previos** tras el rollback, base inexistente (archivo y directorio padre) sin creación accidental, base corrupta por señal `error`, única `finalizada`, liberación de hilo/gestor/conexión, cero llamadas a escaneo/FFprobe/FFmpeg/subprocesos, datos reales (`biblioteca.db`, `miniaturas/`, `videos_prueba/`) intactos y regresiones de `guardar_video` y `TareaGuardarVideo`.

### Etapa de observación: contrato de TareaGuardarVideos ante entradas inválidas

Observación resuelta antes de crear el commit de la etapa de colección. Se inspeccionaron siete casos de entrada al constructor (inspección aislada con `GestorTareas` y un contador de `sqlite3.connect`): `None`, un entero, texto (`str`/`bytes`), una colección con un elemento no-dict, un **generador que lanza `RuntimeError` a mitad de la iteración**, una colección mutada externamente y diccionarios mutados externamente.

- `tareas_videos.py`
  - **Corrección**: el constructor de `TareaGuardarVideos` amplió la captura de `(TypeError, ValueError)` a `Exception` al materializar/instantánea de la colección. Antes, un generador que lanzaba a mitad de la iteración propagaba `RuntimeError` **sincrónicamente** desde el constructor (violaba el contrato "los errores de contrato se producen durante `_trabajo()`"); ahora cualquier fallo de materialización/copia se conserva como colección inválida y `_trabajo()` lo comunica mediante `error`. **Contrato definitivo**: el constructor **nunca lanza** ante entradas inválidas y toma la instantánea cuando puede; todos los errores de contrato (entrada no iterable o texto, elemento no copiable, generador fallido, o clave obligatoria ausente que solo `guardar_videos` detecta al validar) se comunican exclusivamente por la señal `error` durante la ejecución, sin abrir SQLite ni modificar la base. No se duplicó la validación de `guardar_videos` dentro del constructor.
- `prueba_guardar_videos.py`
  - Se amplió de 31 a **34 pruebas**: T32 (`test_31`) — generador que lanza `RuntimeError` a mitad de la materialización: el constructor termina, la tarea comunica el fallo por `error`, sin conexiones y sin cambios en la base; T33 (`test_32`) — entradas inválidas de contrato detectadas al construir la instantánea (`None`, entero, `str`, `bytes`, elemento no-dict): constructor sin lanzar, señal `error` con `TypeError`, cero conexiones, cero cambios, gestor/hilo liberados y una sola `finalizada` en todos los casos; T34 (`test_33`) — error de contrato diferido a la validación de `guardar_videos` (clave obligatoria ausente en un registro ya copiado): el constructor toma la instantánea sin lanzar y la tarea comunica `ValueError` por `error` con cero conexiones y cero cambios.

### Etapa de lectura paginada del catálogo (listar_videos_paginado / TareaLecturaCatalogoPaginada)

- `escanear_videos.py`
  - Nueva función pública `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)`, diferenciada de `listar_videos`: consulta paginada (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro, ambas en SQLite, sin leer toda la tabla. Orden determinista por `nombre`; búsqueda por coincidencia parcial de nombre con `LIKE` (patrón `%texto%`) pasada mediante parámetros SQL (sin interpolación del texto). Validación previa a SQL: `limite` entero positivo (bool → `TypeError`; ≤ 0 → `ValueError`), `desplazamiento` entero ≥ 0 (bool → `TypeError`; < 0 → `ValueError`), `texto` `None` o texto (`TypeError` en caso contrario); base inexistente → `FileNotFoundError` sin crear archivos. Devuelve `{"videos": [...], "total": n, "limite": n, "desplazamiento": n}`, donde cada elemento de `videos` conserva los mismos campos y formato que `listar_videos()`. No cambia el esquema, no crea índices, no implementa orden configurable, abre/cierra su propia conexión en el hilo que la invoca y no usa `check_same_thread=False`.
- `tareas_videos.py`
  - Nueva tarea `TareaLecturaCatalogoPaginada(TareaBase)`: recibe los mismos parámetros de la función síncrona; conserva una instantánea de los parámetros (escalares inmutables); invoca `listar_videos_paginado` dentro de `_trabajo()` y devuelve exactamente su resultado; la conexión SQLite se abre y cierra dentro del hilo de trabajo (sin `check_same_thread=False`, sin conexión almacenada como atributo); los errores se comunican por la señal `error`. No accede a la interfaz, no escanea, no ejecuta FFprobe/FFmpeg y no escribe en SQLite. `TareaLecturaCatalogo` conserva su contrato sin cambios.
- `prueba_lectura_paginada.py` (nuevo)
  - 32 pruebas con bases SQLite temporales: catálogo vacío, primera/intermedia/última página, desplazamiento posterior al final, límite de un registro, páginas concatenadas ≡ listado completo, ausencia de duplicados, orden determinista, total sin/con filtro, búsqueda parcial y sin coincidencias, caracteres especiales (`'`, `%`) como parámetros SQL, `NULL` conservados, equivalencia síncrona/asíncrona, ejecución en `QThread`, resultado en hilo principal, conexión abierta/cerrada en el hilo de trabajo, única finalización, liberación de hilo/gestor, base inexistente (archivo y directorio padre) sin creación, base corrupta por `error`, `limite`/`desplazamiento`/`texto` inválidos rechazados antes de conectar (0 conexiones), cero escrituras (bytes y hash idénticos), cero escaneo/FFprobe/subprocesos y datos reales intactos.

### Etapa de integración de la lectura paginada con la interfaz (visor_videos.py)

- `visor_videos.py`
  - **Carga inicial asíncrona**: se eliminó la lectura síncrona del catálogo en el hilo principal (ya no se importa `sqlite3` ni `listar_videos`); `VisorVideos` ahora usa `GestorTareas` y `TareaLecturaCatalogoPaginada` para cargar la primera página en segundo plano. Constantes nuevas `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO = "Cargando catálogo…"` y `MENSAJE_ERROR = "No se pudo cargar el catálogo"`.
  - `VisorVideos(ruta_db=None)` — la ventana se construye **sin consultas SQLite** (verificado por conteo de `sqlite3.connect` durante la construcción = 0); crea `self.gestor = GestorTareas(self)`, conecta `tarea_resultado → _al_resultado` y `tarea_error → _al_error`, y arranca `_iniciar_carga()`. No almacena conexiones y no usa `check_same_thread=False`.
  - `_iniciar_carga()` — construye `TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, self._ruta_db)` y la ejecuta con `gestor.iniciar()`.
  - `_al_resultado()` / `_al_error()` — estado de carga oculto al recibir el resultado y creación de tarjetas; ante error, texto `MENSAJE_ERROR` visible sin cerrar la ventana. Ambas se resguardan con `_carga_completada` para finalizar una sola vez.
  - `filtrar()` — filtra **solo las tarjetas ya cargadas** (primera página); la búsqueda en SQL queda para etapas futuras.
  - `closeEvent()` — apagado ordenado: `self.gestor.cerrar()` (timeout por defecto 5000 ms) y aceptación del evento; sin avisos `QThread: Destroyed while thread is still running`.
  - `main()` — smoke test adaptado: espera la carga asíncrona (hasta 10 s), imprime visibles/contador inicial y tras la carga, filtra "real" y cierra con `exit 0`.
- `prueba_interfaz_asincrona.py` (nuevo)
  - 29 pruebas con ejecución real de Qt y bases SQLite temporales: construcción sin SQLite, lectura vía `TareaLecturaCatalogoPaginada` en el hilo correcto, SQLite abierto/cerrado en el hilo de trabajo (distinto del principal), ausencia de tarjetas antes del resultado, fluidez de la UI durante una lectura bloqueada (`Estado.OCUPADO`), primera página (tamaño, orden, contador, sin tarjetas extra por el total), filtro visual sobre tarjetas cargadas, catálogo vacío, base inexistente/corrupta sin crear archivos ni cerrar la ventana, finalización única, liberación del gestor tras éxito/error, cierre durante una lectura activa sin hilos colgados, ausencia de avisos `QThread: Destroyed`, ausencia de `sqlite3`/llamadas directas a `listar_videos`/`listar_videos_paginado` (AST + monkeypatch), ausencia de escaneo/FFprobe/subprocesos, cero escrituras SQLite (bytes y hash idénticos), datos reales intactos y smoke test real en subproceso con exit 0.

### Etapa de selección de carpeta en la interfaz (visor_videos.py)

- `visor_videos.py`
  - **Nuevos controles**: botón "Seleccionar carpeta" (`boton_seleccionar_carpeta`, `QPushButton`), etiqueta de solo lectura con la ruta (`etiqueta_carpeta`, `QLabel` con `Qt.TextSelectableByMouse`) y etiqueta de mensajes (`mensaje_carpeta`), integrados en una fila superior sin rediseñar la ventana.
  - Nuevo atributo de sesión `carpeta_seleccionada` (comienza como `None`; no persiste entre ejecuciones).
  - Nuevo método `seleccionar_carpeta()` — abre `QFileDialog.getExistingDirectory`; al cancelar conserva la selección anterior; con una ruta válida **normaliza con `os.path.abspath`** (ruta absoluta), **valida con `os.path.isdir`** (existe y es directorio), muestra la ruta en la etiqueta y la guarda en `carpeta_seleccionada`; ante una ruta inexistente o que es un archivo rechaza la selección, conserva la anterior y muestra `MENSAJE_RUTA_INVALIDA` sin cerrar la ventana.
  - **Ausencia deliberada**: seleccionar la carpeta no escanea su contenido (sin `TareaEscaneo`, sin listado de la carpeta), no abre SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas.
  - `main()` — smoke test ampliado: verifica el estado inicial sin carpeta, simula la selección de una carpeta temporal y la cancelación (diálogo `QFileDialog.getExistingDirectory` inyectado y siempre restaurado en `finally`), y confirma que la carga asíncrona y el filtro "real" siguen funcionando; cierra con `exit 0`.
- `prueba_seleccion_carpeta.py` (nuevo)
  - 26 pruebas con Qt real: construcción sin carpeta y sin diálogo automático, botón existente y conectado, ruta válida guardada como absoluta, ruta mostrada, conservación durante la sesión, cancelación sin/con selección previa, ruta inexistente y ruta-archivo rechazadas, relativa normalizada a absoluta, rutas con espacios y Unicode, error visible sin cerrar la ventana, carga asíncrona y filtro intactos, ausencia de escaneo/FFprobe/FFmpeg/subprocesos/SQLite (apertura y escritura) al seleccionar, datos reales intactos, gestor liberado al cerrar, sin avisos `QThread: Destroyed` y smoke test real en subproceso (selección simulada + filtro + exit 0).

### Etapa de escaneo asíncrono desde la interfaz (visor_videos.py)

- `visor_videos.py`
  - **Nuevos controles**: botón "Escanear carpeta" (`boton_escanear`, `QPushButton`) y etiqueta de estado (`estado_escaneo`, `QLabel`), integrados en la fila de selección de carpeta. El botón queda deshabilitado hasta que exista una carpeta válida y el gestor esté `inactivo`.
  - Nuevos atributos de la operación de escaneo: `videos_detectados` (lista de rutas detectadas; `None` antes del primer escaneo), `tarea_escaneo` (tarea `TareaEscaneo` en curso) y `_escaneo_pendiente` (estado interno que enruta el resultado/error en vuelo).
  - Nuevas constantes `MENSAJE_ESCANEANDO = "Escaneando carpeta…"`, `MENSAJE_ERROR_ESCANEO = "No se pudo escanear la carpeta"` y `MENSAJE_SIN_ESCANEO = "Sin escanear"`.
  - Nuevo método `iniciar_escaneo()` — acción manual: retorna si el gestor está ocupado; revalida la carpeta con `os.path.isdir`; crea `TareaEscaneo(carpeta)` y la inicia con el **mismo** `GestorTareas` de la ventana (se reutiliza para las sucesivas operaciones: carga inicial y escaneos). Marca `_escaneo_pendiente = True`, guarda la tarea y muestra `MENSAJE_ESCANEANDO`.
  - **Enrutado por estado**: `_al_resultado`/`_al_error` reenvían a `_al_resultado_escaneo`/`_al_error_escaneo` cuando `_escaneo_pendiente` está activo. Es suficiente para una única tarea activa; debe revisarse si la interfaz incorpora más tipos de tarea.
  - `_al_resultado_escaneo(videos)` — copia la lista en `videos_detectados`, limpia el flag y muestra el conteo ("1 video detectado" / "N videos detectados"). No crea tarjetas ni recarga el catálogo.
  - `_al_error_escaneo(mensaje)` — ante un fallo muestra `MENSAJE_ERROR_ESCANEO` y **preserva el último resultado exitoso** en `videos_detectados`.
  - `_mostrar_estado_escaneo()` — muestra `MENSAJE_SIN_ESCANEO` si `videos_detectados` es `None`; si no, pluraliza el conteo.
  - `_actualizar_botones_carpeta()` — bloquea los botones de la fila mientras el gestor está ocupado y habilita "Escanear carpeta" solo con carpeta válida y gestor `inactivo`.
  - **Ausencia deliberada**: el escaneo desde la interfaz solo cuenta los archivos de video de la carpeta elegida (misma lista ordenada que `escanear_videos`); no recorre subcarpetas, no escribe en SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas, no crea tarjetas y no recarga el catálogo.
  - `main()` — smoke test ampliado: verifica el estado inicial del escaneo ("Sin escanear" y botón deshabilitado), la habilitación del botón tras la carga del catálogo con una carpeta seleccionada, dispara el escaneo real con `boton_escanear.click()`, observa "Escaneando carpeta…" mientras el gestor está ocupado y, al terminar, imprime `videos_detectados` (3 videos: `clip.avi`, `peli.mp4`, `serie.mkv`), el estado final y el filtro con "real"; cierra con `exit 0`.
- `prueba_escaneo_interfaz.py` (nuevo)
  - 36 pruebas con Qt real: construcción sin carpeta (estado "Sin escanear", botón deshabilitado, sin `TareaEscaneo`), botón existente y conectado, deshabilitado sin carpeta válida y habilitado con carpeta válida + gestor inactivo, escaneo real con `TareaEscaneo` en `QThread`, "Escaneando carpeta…" visible durante la ejecución, resultados de carpeta con videos y vacía, orden y filtrado de extensiones, `videos_detectados` como lista ordenada, conteo singular/plural, doble clic durante un escaneo activo sin duplicar tareas, reutilización del mismo `GestorTareas`, bloqueo de controles durante el escaneo, error de carpeta inexistente y ruta-archivo con `MENSAJE_ERROR_ESCANEO`, **preservación del último resultado exitoso ante un error posterior**, ausencia de SQLite (apertura y escritura) y de FFprobe/FFmpeg/subprocesos, ausencia de tarjetas/recarga del catálogo al escanear, datos reales intactos, gestor liberado al cerrar, sin avisos `QThread: Destroyed` y smoke test real en subproceso (escaneo simulado con 3 videos detectados + filtro + exit 0).

### Etapa de integración del pipeline limitado (escaneo → registros básicos → guardado)

Corrección de la desviación arquitectónica señalada en la revisión: la preparación de registros básicos pertenece a la **capa de catálogo/transformación**, no a la capa de tareas.

- `escanear_videos.py`
  - Nueva función `preparar_registros_basicos(videos, carpeta)` — **lógica de catálogo** que transforma los archivos detectados por el escaneo en registros con las claves exactas `{nombre, ruta, extension, fecha_importacion}`: `ruta` absoluta dentro de la carpeta escaneada (`os.path.join(carpeta, nombre)`), `extension` en minúsculas y `fecha_importacion` ISO (`datetime.now().isoformat()`) común a la preparación. Validación previa: `videos` no puede ser texto (`str`/`bytes`/`bytearray`) ni un valor no iterable (`TypeError`); `carpeta` debe ser una ruta de texto no vacía (`ValueError`). Ubicada entre `escanear_videos()` y `conectar_bd()`, sin cambios de comportamiento respecto de la versión previa.
  - `conectar_bd(ruta_db=None)` — firma extendida con ruta de base opcional (por defecto `ruta_biblioteca()`), reutilizada por el smoke test para crear una base temporal con el esquema existente.
- `tareas_videos.py`
  - Eliminada la definición local de `preparar_registros_basicos` (y el import de `datetime`): la capa de tareas asíncronas ya no duplica lógica de catálogo.
  - Re-exporta `preparar_registros_basicos` y `conectar_bd` desde `escanear_videos`: `visor_videos.py` sigue importando desde `tareas_videos.py` (AST de `prueba_escaneo_interfaz.py` intacto) sin crear ciclos de importación.
- `visor_videos.py`
  - **Encadenamiento escaneo → guardado** con el mismo `GestorTareas`: `_al_resultado_escaneo` marca `_guardado_pendiente = True`; `_al_tarea_finalizada` (gestor `inactivo` tras la finalización del escaneo) prepara los registros con `preparar_registros_basicos(videos_detectados, tarea_escaneo.carpeta)` y los persiste con `TareaGuardarVideos(registros, ruta_db)`. El guardado no se lanza en el handler del resultado (el gestor `Ocupado` rechaza la segunda tarea mientras la primera corre).
  - Nuevos atributos/estados `_guardado_pendiente`, `tarea_guardado` y `registros_guardados`; handlers `_al_resultado_guardado` (limpia el flag y habilita el botón) y `_al_error_guardado` (mensaje `MENSAJE_ERROR_GUARDADO`, gestor `inactivo`, interfaz recuperable con nuevo escaneo posible).
  - `main()` — smoke test independizado de `biblioteca.db`: crea una base temporal con `conectar_bd(ruta_db)` (esquema existente) y verifica el escaneo + guardado reales (`guardado_total=3`).
  - **Sin cambios de comportamiento de la cadena**: se conserva la escritura real en SQLite mediante el upsert transaccional existente, se preservan los registros preexistentes y no se ejecuta FFprobe/FFmpeg/miniaturas, no se elimina nada, no se recarga el catálogo ni se reconstruyen tarjetas.
- `prueba_escaneo_guardado.py` (nuevo)
  - 16 pruebas con bases SQLite temporales: AST (definición en `escanear_videos.py`, ausente en `tareas_videos.py`, importada desde `tareas_videos`), claves exactas `{nombre, ruta, extension, fecha_importacion}` con ruta absoluta, entradas inválidas (texto, no iterable, carpeta vacía), cadena completa escaneo → preparación → guardado con `_guardado_pendiente` final `False`, resultado de la carga inicial sin interpretarse como escaneo/guardado, **exactamente 1 llamada a `guardar_videos` por escaneo**, ausencia de subprocess/FFprobe/FFmpeg, ausencia de funciones de miniaturas (comparando el estado real antes/después), error de guardado controlado con `MENSAJE_ERROR_GUARDADO`, `_guardado_pendiente` `False`, gestor `INACTIVO`, botón habilitado y nuevo escaneo exitoso, sin borrado de registros preexistentes y sin recarga/reconstrucción de tarjetas.
- `prueba_escaneo_interfaz.py`
  - Reforzadas las verificaciones del contrato de persistencia (imports y asserts) sin cambiar el contrato de 36 pruebas.

### Etapa de integración de FFprobe en el pipeline (escaneo → FFprobe → guardado)

- `escanear_videos.py`
  - Nueva constante `CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")` y nuevo helper interno `_normalizar_ruta(ruta)` (`os.path.normcase(os.path.normpath(ruta))`; `None` si la entrada es `None`).
  - Nueva función `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)` — **lógica de catálogo pura** que transforma los archivos detectados y el resultado de `TareaFFprobe` en registros: parte de `preparar_registros_basicos` (claves `{nombre, ruta, extension, fecha_importacion}` con ruta absoluta) e integra los metadatos FFprobe por ruta normalizada (ignora ítems que no son `dict` o sin `ruta`; un `datos` no-dict se trata como `None`; por cada clave de `CLAVES_METADATOS_FFPROBE` se copia el valor de `datos` o se escribe `NULL`). Definida solo en `escanear_videos.py`.
- `tareas_videos.py`
  - Re-exporta `combinar_registros_con_ffprobe` desde `escanear_videos` (junto a `preparar_registros_basicos` y `conectar_bd`): la interfaz sigue importando desde `tareas_videos.py` sin crear ciclos de importación.
- `visor_videos.py`
  - **Encadenamiento escaneo → FFprobe → guardado** con el mismo `GestorTareas`: `_al_resultado_escaneo` marca `_ffprobe_pendiente = True`; `_al_tarea_finalizada` (gestor `inactivo`) inicia `TareaFFprobe(rutas)` con `_iniciar_ffprobe()`; `_al_resultado_ffprobe` guarda el resultado y marca `_guardado_pendiente = True`; al terminar FFprobe, `_iniciar_guardado()` prepara los registros con `combinar_registros_con_ffprobe` y los persiste con `TareaGuardarVideos`.
  - Nuevos atributos/estados `_ffprobe_pendiente`, `tarea_ffprobe` y `resultado_ffprobe`; handlers `_al_resultado_ffprobe` y `_al_error_ffprobe`; constante `MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"`.
  - `_limpiar_cadena()` limpia los flags y referencias temporales del escaneo, FFprobe y guardado **sin borrar `videos_detectados`**: se conserva el último escaneo exitoso aunque falle FFprobe o el guardado posterior.
  - `_iniciar_guardado()` valida que existan `tarea_escaneo`, `videos_detectados` y `resultado_ffprobe` antes de combinar y persistir; si falta alguno, limpia la cadena.
  - `main()` — smoke test: espera la cadena completa escaneo → FFprobe → guardado y verifica `guardado_total=3` (los metadatos de FFprobe se integran por ruta; sin `biblioteca.db`).
- `prueba_escaneo_guardado.py`
  - Ampliada de 16 a **19 pruebas**: definición de `combinar_registros_con_ffprobe` en `escanear_videos.py` y ausencia en `tareas_videos.py` (AST), importación desde `tareas_videos`, combinación con metadatos completos/vacíos/NULL y cadena completa escaneo → FFprobe → guardado con `_ffprobe_pendiente`/`_guardado_pendiente` finales `False` y liberación de `tarea_ffprobe`/`resultado_ffprobe`.
- `prueba_escaneo_interfaz.py`
  - Reforzadas las verificaciones del contrato de FFprobe en el pipeline (imports, estados `_ffprobe_pendiente`/`tarea_ffprobe`/`resultado_ffprobe`, enrutado de resultado/error y `MENSAJE_ERROR_FFPROBE`) sin cambiar el contrato de 36 pruebas.

## 10. Recomendaciones priorizadas

1. **Alta — Configurar rutas absolutas** (`escanear_videos.py`, `visor_videos.py`): resolver `miniaturas/`, `videos_prueba/` y `biblioteca.db` a partir de `os.path.dirname(__file__)` o un módulo de configuración. **Resuelto** — implementado en `rutas.py` (capa de rutas; sin módulo de configuración completo todavía).
2. **Alta — Limpieza controlada de miniaturas obsoletas**: definir una política segura para archivar o eliminar versiones antiguas y evitar el crecimiento acumulativo de ranuras `_NN`. **Ninguna eliminación, sobrescritura, movimiento o archivado automático puede implementarse sin: una política segura previamente definida, autorización expresa y verificación de que no se perderán datos necesarios.** (La generación con FFmpeg ya está implementada.)
3. **Media — Trabajos en segundo plano**: **en curso** — infraestructura implementada en `tareas.py` con `TareaFFprobe`, `TareaEscaneo`, la lectura del catálogo (`TareaLecturaCatalogo`), la **escritura individual** (`TareaGuardarVideo`) y la **escritura de colección** (`TareaGuardarVideos`). **Integración con la ventana**: la carga inicial asíncrona de la primera página del catálogo ya está integrada en `visor_videos.py` y el **pipeline escaneo → FFprobe → guardado** (`TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaGuardarVideos`) ya se encadena desde la interfaz. Pendiente: la sincronización completa del catálogo (escritura masiva con detección de archivos y eliminación de registros ausentes), FFmpeg asíncrono y barra de progreso.
4. **Media — Módulo de configuración** centralizado (rutas, extensiones, dimensiones, columnas).
5. **Baja — Robustecer coincidencia de miniaturas**: usar coincidencia de prefijo con delimitador (`prefijo + "_"`) o patrón rígido `<video>_<NN>.jpg`.
6. **Baja — Reubicación de artefactos de prueba**: Git y `.gitignore` ya están implementados; `biblioteca.db`, `datos.txt`, `miniaturas/`, `__pycache__/` y los archivos `.pyc` ya están ignorados. La recomendación futura se limita a evaluar la reubicación de los artefactos de prueba (`main.py`, `operaciones.py`, `prueba_agente.py`) en una etapa autorizada, sin moverlos ahora.

## 11. Verificación ejecutada

| Prueba | Comando | Resultado |
| --- | --- | --- |
| Compilación de ambos módulos | `python -m py_compile escanear_videos.py visor_videos.py` | OK (exit 0) |
| Sincronización de catálogo | `python escanear_videos.py` | OK (exit 0) |
| Metadatos FFprobe en BD | consulta SQL | `video_real.mp4` → 5.0 s, 640x360, h264; videos vacíos → NULL/0 (esperado) |
| Smoke test GUI (línea base, previo a cambios) | `python visor_videos.py` | `visibles_inicio=4 videos`, filtro "real" → `1 video`, exit 0 |
| Smoke test GUI (post cambios) | `python visor_videos.py` | Salida idéntica a la línea base, exit 0 — **sin regresiones** |
| Generación de miniaturas (etapa posterior) | `python escanear_videos.py` | Se genera una miniatura cuando no existe ninguna válida; se escribe en la siguiente ranura libre (`_NN`). |
| Reutilización (etapa posterior) | `python escanear_videos.py` (2.º escaneo) | Miniatura válida reutilizada; sin archivos nuevos ni modificados. |
| Regeneración (etapa posterior) | `python escanear_videos.py` (video con `mtime` posterior) | Se crea una ranura nueva (`_02`) sin sobrescribir `_01`; `cantidad_miniaturas` = 2. |
| Smoke test GUI (etapa posterior) | `python visor_videos.py` | Salida idéntica a la línea base (`4 videos` → filtro `real` → `1 video`), exit 0 — **sin regresiones** |
| Compilación (etapa de rutas) | `python -m py_compile rutas.py escanear_videos.py visor_videos.py` | OK (exit 0) |
| Sincronización (etapa de rutas, CWD = proyecto) | `python escanear_videos.py` | OK (exit 0); miniaturas reutilizadas, sin archivos nuevos |
| Regeneración (etapa de rutas) | escaneo con `mtime` del video posterior | Se creó `video_real_03.jpg` en la ranura siguiente; `_01` y `_02` preservados; `cantidad_miniaturas` = 3 |
| Smoke test GUI (etapa de rutas, CWD = proyecto) | `python visor_videos.py` | `4 videos` → filtro `real` → `1 video`, exit 0 — **sin regresiones** |
| Escaneo desde directorio ajeno al proyecto | `python C:\prueba\escanear_videos.py` (CWD = `%TEMP%\opencode`) | OK (exit 0); `biblioteca.db` y `miniaturas/` actualizados en `C:\prueba`; no se crearon archivos en el CWD |
| Interfaz desde directorio ajeno al proyecto | `python C:\prueba\visor_videos.py` (CWD = `%TEMP%\opencode`) | Salida idéntica (`4 videos` → `1 video`), exit 0 — rutas independientes del CWD |
| Pruebas de infraestructura de tareas | `python prueba_tareas.py` | 13/13 OK (RESULTADO_FINAL=OK, exit 0) |
| Pruebas de TareaFFprobe (regresión) | `python prueba_ffprobe.py` | 12/12 OK (RESULTADO_FINAL=OK, exit 0) |
| Compilación (etapa de escaneo asíncrono) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py prueba_escaneo.py` | OK (exit 0) |
| Pruebas de TareaEscaneo | `python prueba_escaneo.py` | 12/12 OK (RESULTADO_FINAL=OK, exit 0) |
| Compilación (etapa de lectura asíncrona) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py` | OK (exit 0) |
| Pruebas de TareaLecturaCatalogo | `python prueba_lectura.py` | 15/15 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa de lectura asíncrona) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py` | 13/13, 12/12 y 12/12 OK — sin regresiones |
| Lectura por defecto sin regresiones | `python -c "from escanear_videos import listar_videos; print(len(listar_videos()))"` | 4 filas (lectura), exit 0 |
| Compilación (etapa de escritura individual) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py prueba_guardar.py` | OK (exit 0) |
| Pruebas de TareaGuardarVideo | `python prueba_guardar.py` | 19/19 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa de escritura individual) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py` | 13/13, 12/12, 12/12 y 15/15 OK — sin regresiones |
| Compilación (observación: aislamiento y validación previa) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py prueba_guardar.py` | OK (exit 0) |
| Pruebas de TareaGuardarVideo (observación) | `python prueba_guardar.py` | 19/19 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (observación: aislamiento y validación previa) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py` | 13/13, 12/12, 12/12 y 15/15 OK — sin regresiones |
| Compilación (etapa de escritura de colección) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py prueba_guardar.py prueba_guardar_videos.py` | OK (exit 0) |
| Pruebas de TareaGuardarVideos | `python prueba_guardar_videos.py` | 31/31 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa de escritura de colección) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_guardar.py` | 13/13, 12/12, 12/12, 15/15 y 19/19 OK — sin regresiones |
| Inspección del constructor (observación) | script aislado en `%TEMP%\opencode` (7 casos con contador de `sqlite3.connect`) | 6/7 correctos; el caso "generador que lanza" escapaba `RuntimeError` del constructor (confirmado); corregido |
| Inspección del constructor (post corrección) | mismo script aislado | 7/7: el constructor nunca lanza; todos los errores por señal `error`; 0 conexiones y 0 cambios |
| Compilación (observación de la etapa de colección) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py main.py operaciones.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py prueba_guardar.py prueba_guardar_videos.py prueba_agente.py` | OK (exit 0) |
| Pruebas de TareaGuardarVideos (observación) | `python prueba_guardar_videos.py` | 34/34 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (observación de la etapa de colección) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_guardar.py` | 13/13, 12/12, 12/12, 15/15 y 19/19 OK — sin regresiones |
| Limpieza del diff | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa de lectura paginada) | `python -m py_compile tareas.py tareas_videos.py escanear_videos.py rutas.py visor_videos.py prueba_tareas.py prueba_ffprobe.py prueba_escaneo.py prueba_lectura.py prueba_guardar.py prueba_guardar_videos.py prueba_lectura_paginada.py` | OK (exit 0) |
| Pruebas de lectura paginada | `python prueba_lectura_paginada.py` | 32/32 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa de lectura paginada) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_guardar.py`, `python prueba_guardar_videos.py` | 13/13, 12/12, 12/12, 15/15, 19/19 y 34/34 OK — sin regresiones |
| Auditoría de evidencia (lectura paginada) | `git diff --check`; script aislado de validación previa con contador de `sqlite3.connect`; captura y cierre de la conexión; semántica de comodines `%`/`_`/`'` | exit 0; 5/5 casos con 0 conexiones; conexión cerrada (ProgrammingError al reutilizarla); comodines documentados (pendiente de decisión como contrato) |
| Limpieza del diff (etapa de lectura paginada) | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa de integración de la interfaz) | `python -m py_compile visor_videos.py tareas.py tareas_videos.py escanear_videos.py rutas.py prueba_interfaz_asincrona.py` | OK (exit 0) |
| Pruebas de integración asíncrona de la interfaz | `python prueba_interfaz_asincrona.py` | 29/29 OK (RESULTADO_FINAL=OK, exit 0) |
| Smoke test GUI (integración asíncrona) | `python visor_videos.py` | `visibles_inicio=[]`, `estado_inicio=Cargando catálogo…`, `visibles_cargados=4 videos`, filtro "real" → `1 video`, exit 0 — **sin bloqueos ni avisos `QThread: Destroyed`** |
| Regresiones (etapa de integración de la interfaz) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_lectura_paginada.py`, `python prueba_guardar.py`, `python prueba_guardar_videos.py` | 13/13, 12/12, 12/12, 15/15, 32/32, 19/19 y 34/34 OK — sin regresiones |
| Auditoría de evidencia (integración) | script aislado con lectura bloqueada; estados del gestor en 5 momentos; cierre con tarea activa y timeout | Durante la lectura: `instancias_de_Tarjeta=0`, `self.tarjetas=[]`, 0 widgets en la grilla; gestor `ocupado` → `inactivo` (éxito/error) → `cerrado` (cierre); `cerrar(timeout_ms=300)` retorna `False` si la tarea no termina (la ventana igual cierra); reutilizable tras éxito/error, no tras cerrar |
| Limpieza del diff (etapa de integración de la interfaz) | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa de selección de carpeta) | `python -m py_compile visor_videos.py tareas.py tareas_videos.py escanear_videos.py rutas.py prueba_seleccion_carpeta.py` | OK (exit 0) |
| Pruebas de selección de carpeta en la interfaz | `python prueba_seleccion_carpeta.py` | 26/26 OK (RESULTADO_FINAL=OK, exit 0) |
| Smoke test GUI (selección de carpeta) | `python visor_videos.py` | `carpeta_inicio=None`, `carpeta_seleccion=...` igual a `carpeta_tras_cancelar=...`, carga asíncrona (`4 videos`), filtro "real" → `1 video`, exit 0 — **sin avisos `QThread: Destroyed`** |
| Regresiones (etapa de selección de carpeta) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_lectura_paginada.py`, `python prueba_guardar.py`, `python prueba_guardar_videos.py`, `python prueba_interfaz_asincrona.py` | 13/13, 12/12, 12/12, 15/15, 32/32, 19/19, 34/34 y 29/29 OK — sin regresiones |
| Limpieza del diff (etapa de selección de carpeta) | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa de escaneo desde la interfaz) | `python -m py_compile visor_videos.py tareas.py tareas_videos.py escanear_videos.py rutas.py prueba_escaneo_interfaz.py` | OK (exit 0) |
| Pruebas de escaneo asíncrono desde la interfaz | `python prueba_escaneo_interfaz.py` | 36/36 OK (RESULTADO_FINAL=OK, exit 0) |
| Smoke test GUI (escaneo desde la interfaz) | `python visor_videos.py` | `estado_escaneo_inicio=Sin escanear`, `escanear_boton_inicio=False`, tras la carga del catálogo `escanear_boton_habilitado=True`, `estado_escaneo_mientras=Escaneando carpeta…`, `videos_detectados=['clip.avi', 'peli.mp4', 'serie.mkv']`, `estado_escaneo_final=3 videos detectados`, filtro "real" → `visibles_filtro=['video_real.mp4']` (`1 video`), exit 0 — **sin avisos `QThread: Destroyed`** |
| Regresiones (etapa de escaneo desde la interfaz) | `python prueba_tareas.py`, `python prueba_ffprobe.py`, `python prueba_escaneo.py`, `python prueba_lectura.py`, `python prueba_lectura_paginada.py`, `python prueba_guardar.py`, `python prueba_guardar_videos.py`, `python prueba_interfaz_asincrona.py`, `python prueba_seleccion_carpeta.py` | 13/13, 12/12, 12/12, 15/15, 32/32, 19/19, 34/34, 29/29 y 26/26 OK — sin regresiones |
| Limpieza del diff (etapa de escaneo desde la interfaz) | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa del pipeline limitado) | `python -m py_compile escanear_videos.py tareas_videos.py visor_videos.py prueba_escaneo_guardado.py prueba_escaneo_interfaz.py` | OK (exit 0) |
| Pruebas del pipeline limitado | `python prueba_escaneo_guardado.py` | 16/16 OK (RESULTADO_FINAL=OK, exit 0) |
| Pruebas de escaneo desde la interfaz (reforzadas) | `python prueba_escaneo_interfaz.py` | 36/36 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa del pipeline limitado) | `python prueba_tareas.py`, `python prueba_escaneo.py`, `python prueba_ffprobe.py`, `python prueba_guardar_videos.py`, `python prueba_guardar.py`, `python prueba_interfaz_asincrona.py`, `python prueba_lectura_paginada.py`, `python prueba_lectura.py`, `python prueba_seleccion_carpeta.py` | 13/13, 12/12, 12/12, 34/34, 19/19, 29/29, 32/32, 15/15 y 26/26 OK — sin regresiones (244/244 en total) |
| Smoke test GUI (pipeline limitado) | `python visor_videos.py` | Base SQLite temporal creada con `conectar_bd(ruta_db)` (esquema existente, sin `biblioteca.db`); `estado_escaneo_inicio=Sin escanear`, `escanear_boton_inicio=False`, `contador_cargado=0 videos`, `escanear_boton_habilitado=True`, `estado_escaneo_mientras=Escaneando carpeta…`, `videos_detectados=['clip.avi', 'peli.mp4', 'serie.mkv']`, `estado_escaneo_final=3 videos detectados`, `guardado_total=3`, `contador_final=0 videos`, exit 0 — **sin avisos `QThread: Destroyed`** |
| Limpieza del diff (etapa del pipeline limitado) | `git diff --check` | Sin espacios en blanco en líneas agregadas |
| Compilación (etapa de FFprobe en el pipeline) | `python -m py_compile escanear_videos.py tareas_videos.py visor_videos.py prueba_escaneo_guardado.py prueba_escaneo_interfaz.py` | OK (exit 0) |
| Pruebas del pipeline escaneo → FFprobe → guardado | `python prueba_escaneo_guardado.py` | 19/19 OK (RESULTADO_FINAL=OK, exit 0) |
| Pruebas de escaneo desde la interfaz (reforzadas) | `python prueba_escaneo_interfaz.py` | 36/36 OK (RESULTADO_FINAL=OK, exit 0) |
| Regresiones (etapa de FFprobe en el pipeline) | `python prueba_tareas.py`, `python prueba_escaneo.py`, `python prueba_ffprobe.py`, `python prueba_guardar_videos.py`, `python prueba_guardar.py`, `python prueba_interfaz_asincrona.py`, `python prueba_lectura_paginada.py`, `python prueba_lectura.py`, `python prueba_seleccion_carpeta.py` | 13/13, 12/12, 12/12, 34/34, 19/19, 29/29, 32/32, 15/15 y 26/26 OK — sin regresiones (247/247 en total) |
| Smoke test GUI (FFprobe en el pipeline) | `python visor_videos.py` | Base SQLite temporal; `videos_detectados=['clip.avi', 'peli.mp4', 'serie.mkv']`, `estado_escaneo_final=3 videos detectados`, `guardado_total=3`, exit 0 — **sin avisos `QThread: Destroyed`** |
| Limpieza del diff (etapa de FFprobe en el pipeline) | `git diff --check` | Sin espacios en blanco en líneas agregadas |

## 12. Registro de cambios

1. **Arquitectura congelada** — línea base aprobada (2026-08-02). Este documento quedó como referencia.
2. **Incorporación de Git** — se añadió control de versiones al proyecto.
3. **Primera generación de miniaturas con preservación de archivos** — se implementó la generación automática (como máximo una miniatura nueva por video por escaneo, solo si no existe ninguna vigente) con reutilización por `mtime`; las miniaturas existentes nunca se sobrescriben ni se eliminan automáticamente.
4. **Rutas independientes del directorio de trabajo** — se creó `rutas.py` como capa centralizada de resolución de rutas y se reemplazaron los literales relativos (`biblioteca.db`, `miniaturas/`, `videos_prueba/`) en `escanear_videos.py` y `visor_videos.py`. La aplicación ahora funciona sin importar desde dónde se ejecute Python.
5. **Infraestructura reutilizable de trabajos en segundo plano** — se creó `tareas.py` con `Estado`, `TareaBase` y `GestorTareas`, ejecutando cada tarea en un `QThread` propio con señales para resultados y errores; se agregó `prueba_tareas.py`.
6. **Procesamiento asíncrono de metadatos FFprobe** — se creó `tareas_videos.py` con `rutas_videos()` y `TareaFFprobe`, más `prueba_ffprobe.py`.
7. **Escaneo asíncrono** — se agregó `TareaEscaneo` a `tareas_videos.py` (reutiliza `escanear_videos`) y `prueba_escaneo.py`.
8. **Lectura asíncrona del catálogo** — `listar_videos` admite una ruta de base opcional; se agregó `TareaLecturaCatalogo` a `tareas_videos.py` (lectura SQLite en segundo plano con conexión por hilo) y `prueba_lectura.py`. La lectura valida la existencia previa de la base (`os.path.isfile`) antes de conectar: una base inexistente produce `FileNotFoundError` sin crear archivos (comportamiento definido y cubierto por pruebas).
9. **Escritura individual asíncrona de video** — se agregó `guardar_video(datos, ruta_db=None)` a `escanear_videos.py` (upsert transaccional de un único registro: `connect` → upsert → `commit` → `rollback` ante error → `close` en `finally`; base inexistente → `FileNotFoundError` sin crear archivos) y `TareaGuardarVideo` a `tareas_videos.py` (escritura en segundo plano con `commit`/`rollback` dentro del hilo de trabajo), más `prueba_guardar.py`. Solo existe escritura individual; la sincronización completa del catálogo, la escritura masiva, la eliminación de registros y el encadenamiento del pipeline siguen pendientes.
10. **Aislamiento del registro y validación previa a SQL** (observación resuelta de la etapa de escritura individual) — `TareaGuardarVideo` toma una **instantánea** del diccionario en el constructor (`self._datos = dict(datos)`), de modo que las mutaciones posteriores del llamador no afectan la ejecución, y `guardar_video` valida el contrato (no-dict → `TypeError`; ausencia de `nombre`, `ruta`, `extension` o `fecha_importacion` → `ValueError`) **antes de abrir la conexión**, sin modificar la base ni dejar conexiones abiertas; la propiedad `datos` devuelve una copia y no expone el diccionario interno. Se amplió `prueba_guardar.py` a 19 pruebas (instantánea, entrada inválida, clave obligatoria ausente, opcionales ausentes → `NULL` y liberación tras errores). Sin `deepcopy`, dataclasses, modelos ni capa de validación nueva; la escritura sigue siendo individual.
11. **Escritura de colección transaccional asíncrona** — se agregó `guardar_videos(datos_videos, ruta_db=None)` a `escanear_videos.py` (escritura de una colección en **una única transacción atómica**: validación completa previa con copias superficiales, un solo `connect`, todos los upserts, **un solo** `commit`, `rollback` total ante cualquier fallo, `close` en `finally`; resultado `{"guardados": n, "nombres": [...]}`) y `TareaGuardarVideos` a `tareas_videos.py` (instantánea de la colección y de cada registro; un solo `commit` dentro del hilo de trabajo), más `prueba_guardar_videos.py` (31 pruebas, incluidas atomicidad con consulta real de la base tras el fallo, rollback total con bytes idénticos, ausencia de inserciones parciales y restauración de valores previos). Se extrajeron los internos compartidos `_validar_registro_video` y `_upsert_video` para que `guardar_video` y `guardar_videos` reutilicen la misma validación y el mismo upsert sin duplicación. Sigue sin existir sincronización disco ↔ catálogo, detección de archivos, FFprobe/FFmpeg/miniaturas en la escritura ni **eliminación de registros**; el pipeline y la interfaz no se tocaron.
12. **Contrato definitivo de `TareaGuardarVideos` ante entradas inválidas** (observación resuelta antes del commit de la etapa de colección) — el constructor **nunca lanza** ante entradas inválidas: amplió la captura a `Exception` al materializar/instantánea, de modo que incluso un generador que lanza `RuntimeError` a mitad de la iteración se conserva como colección inválida y `_trabajo()` lo comunica por `error` (`TypeError` envolviendo la causa) sin abrir SQLite ni modificar la base; los errores de contrato que solo `guardar_videos` detecta al validar (clave obligatoria ausente) también se comunican por `error` durante la ejecución. Se amplió `prueba_guardar_videos.py` de 31 a **34 pruebas** (generador fallido, entradas inválidas detectadas en la construcción con cero conexiones/cero cambios y gestor liberado, y error diferido a la validación con cero conexiones/cero cambios). No se duplicó la validación de `guardar_videos` dentro del constructor.
13. **Lectura paginada del catálogo** — se agregó `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)` a `escanear_videos.py` (consulta paginada con `LIMIT`/`OFFSET` y `COUNT` con el mismo filtro, ambos en SQL; búsqueda parcial por `LIKE` con parámetros SQL; orden determinista por `nombre`; validación previa a SQL de `limite`, `desplazamiento` y `texto`; base inexistente → `FileNotFoundError` sin crear archivos; resultado `{"videos": [...], "total": n, "limite": n, "desplazamiento": n}` con el mismo formato de fila que `listar_videos()`) y `TareaLecturaCatalogoPaginada` a `tareas_videos.py` (mismos parámetros, instantánea de escalares, invocación síncrona en `_trabajo()`, conexión por hilo de trabajo, errores por señal `error`, sin interfaz/escaneo/FFprobe/FFmpeg/escritura), más `prueba_lectura_paginada.py` (32 pruebas). La operación está preparada para catálogos de decenas de miles de registros pero **no se conecta todavía con la interfaz**; la integración de la primera carga asíncrona paginada en `visor_videos.py` queda para una etapa futura.
14. **Integración de la lectura paginada con la interfaz (carga inicial asíncrona)** — `visor_videos.py` dejó de leer SQLite en el hilo principal: `VisorVideos` usa `GestorTareas` + `TareaLecturaCatalogoPaginada` para cargar la primera página del catálogo en segundo plano (`TAMANIO_PAGINA_INICIAL = 100`), con estado de carga ("Cargando catálogo…"), manejo de errores visible sin cerrar la ventana ("No se pudo cargar el catálogo"), filtrado sobre las tarjetas ya cargadas y apagado ordenado en `closeEvent` (`gestor.cerrar()`, timeout por defecto 5000 ms). Sin `sqlite3` en la UI, sin conexiones almacenadas, sin `check_same_thread=False` y sin trabajo pesado en el hilo principal. Se agregó `prueba_interfaz_asincrona.py` (29 pruebas, incluida la evidencia de que no existen tarjetas antes del resultado y la fluidez durante una lectura bloqueada). El filtrado sigue siendo visual sobre la primera página; la paginación completa, la búsqueda en SQL y el escaneo real de carpetas quedan para etapas futuras.
15. **Selección de carpeta en la interfaz** — `visor_videos.py` incorpora el botón "Seleccionar carpeta" (`boton_seleccionar_carpeta`), la etiqueta de solo lectura con la ruta (`etiqueta_carpeta`), el atributo de sesión `carpeta_seleccionada` y el método `seleccionar_carpeta()`: abre `QFileDialog.getExistingDirectory`, normaliza la ruta con `os.path.abspath` y la valida con `os.path.isdir` (existe y es directorio), conserva la selección anterior al cancelar y rechaza rutas inválidas con un mensaje visible sin cerrar la ventana. **Limitación actual**: la selección no es persistente (vive solo en la sesión) y todavía no inicia el escaneo (no se escanea la carpeta, no se abre SQLite, no se ejecuta FFprobe/FFmpeg ni se generan miniaturas). Se agregó `prueba_seleccion_carpeta.py` (26 pruebas). **Deuda futura**: el smoke test automático deberá separarse del arranque normal antes de distribuir una beta.
16. **Escaneo manual y asíncrono de la carpeta seleccionada desde la interfaz** — `visor_videos.py` incorpora el botón "Escanear carpeta" (`boton_escanear`), la etiqueta de estado `estado_escaneo`, el atributo `videos_detectados` y el método `iniciar_escaneo()`: revalida la carpeta con `os.path.isdir`, crea una `TareaEscaneo(carpeta)` y la ejecuta con el **mismo** `GestorTareas` de la ventana (reutilizado para la carga inicial y los escaneos sucesivos). El resultado se enruta a `_al_resultado_escaneo` mediante el estado interno `_escaneo_pendiente` y muestra el conteo ("1 video detectado" / "N videos detectados") sin crear tarjetas ni recargar el catálogo; ante un error se muestra "No se pudo escanear la carpeta" **preservando el último resultado exitoso**; los controles quedan bloqueados mientras el gestor está ocupado. **Ausencia deliberada**: el escaneo solo cuenta los archivos de video de la carpeta elegida (sin subcarpetas), no escribe en SQLite, no ejecuta FFprobe/FFmpeg, no genera miniaturas, no crea tarjetas ni recarga el catálogo. Se agregó `prueba_escaneo_interfaz.py` (36 pruebas). **Limitaciones**: los archivos detectados todavía no se convierten en registros del catálogo; el enrutado por `_escaneo_pendiente` es suficiente para una única tarea activa pero debe revisarse si la interfaz incorpora más tipos de tarea; `closeEvent()` puede esperar hasta 5 s por una tarea activa (deuda futura para tareas largas).
17. **Integración del pipeline limitado (escaneo → registros básicos → guardado)** — se corrigió la desviación arquitectónica (la preparación de registros pertenece a la capa de catálogo, no a la de tareas) y se implementó el encadenamiento `TareaEscaneo` → `preparar_registros_basicos` → `TareaGuardarVideos`. `escanear_videos.py` incorpora `preparar_registros_basicos(videos, carpeta)` (registros con `{nombre, ruta, extension, fecha_importacion}`, ruta absoluta, `fecha_importacion` ISO; validación de entradas) y extiende `conectar_bd(ruta_db=None)`. `tareas_videos.py` elimina la definición local y re-exporta `preparar_registros_basicos`/`conectar_bd`. `visor_videos.py` encadena ambas tareas con el mismo `GestorTareas`: el guardado se lanza al recibir `tarea_finalizada` del escaneo (el gestor `Ocupado` rechaza una segunda tarea), con `_guardado_pendiente`, `tarea_guardado` y `registros_guardados`, handlers de resultado/error del guardado (`MENSAJE_ERROR_GUARDADO`) y recuperación de la interfaz tras errores; `main()` crea una base SQLite temporal con el esquema existente (`conectar_bd(ruta_db)`) sin depender de `biblioteca.db`. Se agregó    `prueba_escaneo_guardado.py` (16 pruebas) y se reforzó `prueba_escaneo_interfaz.py` (36 pruebas). **Alcance**: escritura real en SQLite con el upsert transaccional existente, conservación de registros preexistentes, sin FFprobe/FFmpeg/miniaturas, sin eliminación de registros ausentes, sin recarga de tarjetas y sin subcarpetas; **no es la sincronización completa del catálogo**. Aprobada con observaciones.
18. **Integración de FFprobe en el pipeline (escaneo → FFprobe → guardado)** — se extendió el encadenamiento de la interfaz para que los registros se guarden con metadatos FFprobe. `escanear_videos.py` incorpora `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)` (lógica de catálogo pura que parte de `preparar_registros_basicos` e integra los metadatos FFprobe por ruta normalizada con la constante `CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")` y el helper `_normalizar_ruta`; `NULL` si el video no tiene `datos`). `tareas_videos.py` re-exporta `combinar_registros_con_ffprobe`. `visor_videos.py` encadena `TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaGuardarVideos` con el mismo `GestorTareas` (estados `_ffprobe_pendiente`/`tarea_ffprobe`/`resultado_ffprobe`, handlers `_al_resultado_ffprobe`/`_al_error_ffprobe` y `MENSAJE_ERROR_FFPROBE`); `_limpiar_cadena()` limpia la cadena **sin borrar `videos_detectados`** (se conserva el último escaneo exitoso aunque falle FFprobe o el guardado posterior). Se amplió `prueba_escaneo_guardado.py` a 19 pruebas y se reforzó `prueba_escaneo_interfaz.py` (36 pruebas). **Alcance**: escritura real con metadatos FFprobe mediante el upsert transaccional existente; sin FFmpeg/miniaturas, sin eliminación de registros ausentes, sin recarga de tarjetas y sin subcarpetas; **no es la sincronización completa del catálogo**. Aprobada con observaciones.
