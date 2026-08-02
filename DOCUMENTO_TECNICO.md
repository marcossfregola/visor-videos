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
├── tareas_videos.py       Tareas de video asíncronas (TareaFFprobe, TareaEscaneo)
├── prueba_tareas.py       Pruebas automatizadas de la infraestructura de trabajos
├── prueba_ffprobe.py      Pruebas automatizadas de TareaFFprobe
├── prueba_escaneo.py      Pruebas automatizadas de TareaEscaneo
├── prueba_lectura.py      Pruebas automatizadas de TareaLecturaCatalogo
├── visor_videos.py        Interfaz gráfica (PySide6) + smoke test automático
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
- `conectar_bd()` — acceso a SQLite: crea la tabla `videos` si no existe y aplica migración idempotente de columnas extras (`COLUMNAS_EXTRA`).
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
- `insertar_video`, `actualizar_datos`, `sincronizar_bd` — lógica de sincronización disco ↔ BD: inserta nuevos, actualiza metadatos (incluida `cantidad_miniaturas` tras `asegurar_miniatura`), elimina de la BD los que ya no están en disco.
- `listar_videos(ruta_db=None)` — **capa de lectura** que consume la interfaz: devuelve las filas del catálogo (nombre, duración, ancho, alto, codec, cantidad de miniaturas) ordenadas por nombre. Acepta una ruta de base opcional para pruebas; por defecto usa `ruta_biblioteca()`. Abre y cierra su propia conexión en el hilo que la invoca (sin `check_same_thread=False`). **Base inexistente**: valida `os.path.isfile(ruta_db)` antes de conectar; si la base no existe (falta el archivo o el directorio padre), lanza `FileNotFoundError` sin crear archivos. La lectura nunca crea la base; la creación es responsabilidad de `conectar_bd()`/`main()`.
- `main()` — CLI: sincroniza el catálogo contra `videos_prueba/` (ruta resuelta por `rutas.py`).

### `rutas.py` — capa centralizada de resolución de rutas
Único módulo responsable de derivar las rutas del proyecto a partir de su ubicación real (`os.path.dirname(os.path.abspath(__file__))`), sin depender del directorio de trabajo:

- `ruta_raiz()` — directorio raíz del proyecto.
- `ruta_biblioteca()` — ruta de `biblioteca.db`.
- `ruta_carpeta_miniaturas()` — ruta de `miniaturas/`.
- `ruta_carpeta_videos()` — ruta de `videos_prueba/`.

Diseñado como punto único de extensión para futuras rutas de configuración; no constituye todavía un módulo de configuración completo.

### `visor_videos.py` — interfaz gráfica
- `VisorVideos(QMainWindow)` — ventana principal: barra de búsqueda, contador, grilla de tarjetas dentro de un `QScrollArea`.
- `Tarjeta(QFrame)` — tarjeta por video: miniatura (o recuadro "Sin miniatura") + campos de texto (nombre, duración, resolución, codec, miniaturas).
- `cargar_tarjetas()` — construye las tarjetas a partir de `listar_videos()` (delegado a `escanear_videos`).
- `filtrar(texto)` — filtrado por coincidencia de nombre; mantiene `visibles` y actualiza el contador.
- `miniatura_principal(nombre)` — ubica la primera miniatura cuyo prefijo coincide con el video.
- `main()` — bootstrap de la app + **smoke test automático**: abre la ventana, imprime visibles/contador iniciales, a los 2 s filtra con "real", a los 5 s imprime el resultado final y cierra con `exit 0`.

### `tareas.py` — infraestructura genérica de trabajos en segundo plano
- `Estado` — estados del ciclo de vida: `inactivo`, `ocupado`, `finalizando`, `cerrado`.
- `TareaBase(QObject)` — clase base de tareas asíncronas; señales `inicio`, `finalizada`, `error(str)`, `resultado(object)`. `ejecutar()` emite `inicio`, invoca `_trabajo()` y emite `resultado(valor)`; ante una excepción emite `error(f"{Tipo}: {msg}")`; siempre emite `finalizada`. Las subclases implementan `_trabajo()`.
- `GestorTareas(QObject)` — orquesta cada tarea en un `QThread` propio. Señales `tarea_iniciada`, `tarea_resultado(object)`, `tarea_error(str)`, `tarea_finalizada` y `actividad_cambiada(bool)`. `iniciar(tarea)` valida la tarea, crea el `QThread`, la mueve a él y lo arranca; el hilo termina cuando la tarea emite `finalizada`. `cerrar(timeout_ms)` permite el apagado ordenado.

### `tareas_videos.py` — tareas asíncronas específicas de video
- `rutas_videos()` — rutas absolutas de los videos de `videos_prueba/` detectados por `escanear_videos`.
- `TareaFFprobe(TareaBase)` — ejecuta `obtener_datos_ffprobe` sobre una lista de rutas en segundo plano; devuelve un diccionario con `rutas`, `resultados`, `procesados`, `con_datos` y `con_error`. Cada resultado contiene `ruta`, `datos` y `error` por archivo.
- `TareaEscaneo(TareaBase)` — recibe una carpeta y devuelve la misma lista ordenada de archivos de video que `escanear_videos(carpeta)`. Una carpeta inexistente (`FileNotFoundError`) o una ruta que no es carpeta (`NotADirectoryError`) se propaga mediante la señal `error` de la infraestructura.
- `TareaLecturaCatalogo(TareaBase)` — lee el catálogo en segundo plano invocando `listar_videos(ruta_db)`; devuelve la misma estructura que la lectura síncrona. Acepta una ruta de base opcional (para pruebas); por defecto usa `ruta_biblioteca()`. **Regla de conexión SQLite por hilo**: la conexión se abre y se cierra dentro del hilo de trabajo, se usa únicamente en ese hilo, no se almacena como atributo persistente de la tarea, no se comparte con el hilo principal y no se usa `check_same_thread=False`. Los errores de lectura (`FileNotFoundError` si la base no existe, `sqlite3.OperationalError`, `sqlite3.DatabaseError`, etc.) se convierten en la señal `error` gestionada por `TareaBase`. La lectura no crea archivos: si la base no existe, se comunica `FileNotFoundError` sin crear la base.

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
| Caché | — | **No existe** un módulo de caché; la BD cumple parcialmente ese rol para metadatos. |
| Configuración | `rutas.py` | Resolución de rutas del proyecto (raíz, BD, miniaturas, videos) centralizada e independiente del CWD. Aún no hay módulo de configuración completo. |

## 5. Flujo de ejecución (apertura → tarjetas)

1. `python visor_videos.py` → `main()` crea `QApplication`.
2. `VisorVideos.__init__` crea la barra de búsqueda, el contador y el `QScrollArea`.
3. `cargar_tarjetas()` llama a `escanear_videos.listar_videos()`:
   - abre `biblioteca.db`;
   - `SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas FROM videos ORDER BY nombre`;
   - cierra la conexión.
4. Para cada fila crea una `Tarjeta` y la ubica en la `QGridLayout` (2 columnas, con estiramiento de columnas).
5. Se muestra la ventana; la `QScrollArea` permite recorrer las tarjetas.
6. Cada tarjeta consulta `miniatura_principal(nombre)` sobre `miniaturas/`; si no encuentra imagen, muestra el recuadro "Sin miniatura".
7. El `QLineEdit` filtra en vivo (`filtrar`) y el contador muestra "N videos".

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
2. **Ejecución asíncrona** — **en curso**: el escaneo (`TareaEscaneo`), FFprobe (`TareaFFprobe`) y la **lectura del catálogo SQLite** (`TareaLecturaCatalogo`, solo lectura) ya se ejecutan en segundo plano mediante `tareas.py`. Pendiente: escritura y sincronización SQLite asíncronas, el encadenamiento del pipeline Escaneo → SQLite, FFmpeg asíncrono e integración con la ventana.
3. **Módulo de configuración** — centralizar rutas (`videos_prueba`, `miniaturas`, `biblioteca.db`), extensiones, tamaños de tarjeta y número de columnas.
4. **Caché de miniaturas/metadatos** — formalizar la BD como caché de metadatos y evitar re-escaneos.
5. **Lectura/vistas del catálogo** — sobre `listar_videos()`, agregar orden/agrupación/filtros adicionales sin tocar la UI.
6. **Autenticación de rutas absolutas** — **implementada** en `rutas.py`: `biblioteca.db`, `miniaturas/` y `videos_prueba/` se resuelven desde la ubicación real del módulo, independientemente del directorio de trabajo.

## 8. Problemas detectados

| # | Severidad | Problema |
| --- | --- | --- |
| 1 | Media | La interfaz (`visor_videos.py`) accedía a SQLite directamente y duplicaba el nombre de BD (`"biblioteca.db"`). **Corregido** en esta etapa. |
| 2 | Media | Rutas relativas (`miniaturas/`, `videos_prueba/`, `biblioteca.db`) dependían del directorio de trabajo; la app fallaba si se lanzaba desde otra ubicación. **Resuelto** (ver §9, etapa de rutas). |
| 3 | Media | No existía generación de miniaturas; solo conteo. **Resuelto** (ver §6). |
| 4 | Media | FFprobe se ejecutaba en el hilo principal con timeout de 30 s por video; el escaneo bloquea. **Resuelto en parte**: FFprobe se movió a segundo plano con `TareaFFprobe`. FFmpeg y la integración de tareas con la ventana continúan pendientes. |
| 5 | Baja | `contar_miniaturas`/`miniatura_principal` usan coincidencia por prefijo (`startswith`); un video `video_real.mp4` podría matchear miniaturas de un hipotético `video_realista.mp4`. Pendiente. |
| 6 | Baja | Los videos vacíos (0 bytes) quedan sin metadatos; comportamiento correcto pero debe documentarse para el usuario. Pendiente. |
| 7 | Informativa | `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` son artefactos de prueba ajenos al visor. Se preservaron por política de esta etapa. |
| 8 | Media | Crecimiento acumulativo de miniaturas: la regeneración escribe una ranura nueva (`_NN`) en lugar de sobrescribir; si el video cambia varias veces se acumulan archivos y `cantidad_miniaturas` crece. Pendiente. |
| 9 | Baja | La interfaz muestra la primera miniatura por orden alfabético (`_01`), incluso cuando una versión más nueva (`_02`) es la vigente. Pendiente. |
| 10 | Media | El criterio de reutilización usa únicamente `mtime` (sin hash ni validación de integridad); no detecta cambios de contenido que conserven la fecha. Pendiente (mejora diferida). |
| 11 | Media | Falta una limpieza controlada de versiones antiguas de miniaturas; por regla, los archivos nunca se eliminan automáticamente, por lo que requiere autorización expresa. Pendiente. |
| 12 | Media | FFmpeg escribe directamente en la ruta definitiva de la miniatura; si falla después de comenzar la escritura puede quedar un archivo parcial o corrupto. Actualmente ese archivo no se elimina ni se valida, y por existencia y `mtime` podría ser contado o considerado vigente. Pendiente. |

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

## 10. Recomendaciones priorizadas

1. **Alta — Configurar rutas absolutas** (`escanear_videos.py`, `visor_videos.py`): resolver `miniaturas/`, `videos_prueba/` y `biblioteca.db` a partir de `os.path.dirname(__file__)` o un módulo de configuración. **Resuelto** — implementado en `rutas.py` (capa de rutas; sin módulo de configuración completo todavía).
2. **Alta — Limpieza controlada de miniaturas obsoletas**: definir una política segura para archivar o eliminar versiones antiguas y evitar el crecimiento acumulativo de ranuras `_NN`. **Ninguna eliminación, sobrescritura, movimiento o archivado automático puede implementarse sin: una política segura previamente definida, autorización expresa y verificación de que no se perderán datos necesarios.** (La generación con FFmpeg ya está implementada.)
3. **Media — Trabajos en segundo plano**: **en curso** — infraestructura implementada en `tareas.py` con `TareaFFprobe`, `TareaEscaneo` y la lectura del catálogo (`TareaLecturaCatalogo`). Pendiente: escritura/sincronización SQLite asíncronas, encadenamiento del pipeline, FFmpeg asíncrono, integración con la ventana y barra de progreso.
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

## 12. Registro de cambios

1. **Arquitectura congelada** — línea base aprobada (2026-08-02). Este documento quedó como referencia.
2. **Incorporación de Git** — se añadió control de versiones al proyecto.
3. **Primera generación de miniaturas con preservación de archivos** — se implementó la generación automática (como máximo una miniatura nueva por video por escaneo, solo si no existe ninguna vigente) con reutilización por `mtime`; las miniaturas existentes nunca se sobrescriben ni se eliminan automáticamente.
4. **Rutas independientes del directorio de trabajo** — se creó `rutas.py` como capa centralizada de resolución de rutas y se reemplazaron los literales relativos (`biblioteca.db`, `miniaturas/`, `videos_prueba/`) en `escanear_videos.py` y `visor_videos.py`. La aplicación ahora funciona sin importar desde dónde se ejecute Python.
5. **Infraestructura reutilizable de trabajos en segundo plano** — se creó `tareas.py` con `Estado`, `TareaBase` y `GestorTareas`, ejecutando cada tarea en un `QThread` propio con señales para resultados y errores; se agregó `prueba_tareas.py`.
6. **Procesamiento asíncrono de metadatos FFprobe** — se creó `tareas_videos.py` con `rutas_videos()` y `TareaFFprobe`, más `prueba_ffprobe.py`.
7. **Escaneo asíncrono** — se agregó `TareaEscaneo` a `tareas_videos.py` (reutiliza `escanear_videos`) y `prueba_escaneo.py`.
8. **Lectura asíncrona del catálogo** — `listar_videos` admite una ruta de base opcional; se agregó `TareaLecturaCatalogo` a `tareas_videos.py` (lectura SQLite en segundo plano con conexión por hilo) y `prueba_lectura.py`. La lectura valida la existencia previa de la base (`os.path.isfile`) antes de conectar: una base inexistente produce `FileNotFoundError` sin crear archivos (comportamiento definido y cubierto por pruebas).
