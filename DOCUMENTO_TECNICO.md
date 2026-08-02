# Documento técnico — Visor de Videos

Estado de la arquitectura congelada. Fecha: 2026-08-02.
Este documento es referencia para las próximas etapas de desarrollo.

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
├── visor_videos.py        Interfaz gráfica (PySide6) + smoke test automático
├── DOCUMENTO_TECNICO.md   Este documento
├── miniaturas/            Imágenes de miniatura (JPG)
│   ├── video_real_01.jpg
│   ├── video_real_02.jpg
│   ├── video_real_03.jpg
│   └── video_real_04.jpg
├── videos_prueba/         Videos de prueba (datos de ejemplo)
│   ├── video_01.mp4       (0 bytes)
│   ├── video_03.avi       (0 bytes)
│   ├── video_04.mp4       (0 bytes)
│   └── video_real.mp4     (5756 bytes, 640x360 h264 5s)
└── __pycache__/           Compilados de Python (generados, no versionados)
```

## 2. Propósito de cada carpeta

| Carpeta | Propósito |
| --- | --- |
| `miniaturas/` | Almacena las miniaturas generadas de cada video. El visor lee de aquí para mostrar la tarjeta. El backend solo **cuenta** las miniaturas; hoy **no** las genera. |
| `videos_prueba/` | Dataset de prueba con el que `escanear_videos.py` sincroniza el catálogo. Contiene archivos vacíos (sin metadatos) y un video real. |
| `__pycache__/` | Caché de bytecode de Python. Generado automáticamente, debe ignorarse en VCS. |

## 3. Propósito de cada módulo

### `escanear_videos.py` — backend / lógica del catálogo
Único módulo con responsabilidad sobre el **dominio** y los **datos**:

- `escanear_videos(carpeta)` — escaneo de archivos: lista archivos del directorio filtrando por extensión (`.mp4`, `.mkv`, `.avi`), ordenados.
- `conectar_bd()` — acceso a SQLite: crea la tabla `videos` si no existe y aplica migración idempotente de columnas extras (`COLUMNAS_EXTRA`).
- `obtener_datos_ffprobe(ruta)` — integración con **FFprobe**: extrae duración, ancho, alto y codec del primer stream de video. Timeout 30 s; devuelve `None` ante cualquier fallo.
- `contar_miniaturas(video)` — cuenta miniaturas existentes en `miniaturas/` cuyo nombre empieza con el prefijo del video.
- `insertar_video`, `actualizar_datos`, `sincronizar_bd` — lógica de sincronización disco ↔ BD: inserta nuevos, actualiza metadatos, elimina los que ya no están.
- `listar_videos()` — **capa de lectura** que consume la interfaz: devuelve las filas del catálogo (nombre, duración, ancho, alto, codec, cantidad de miniaturas) ordenadas por nombre.
- `main()` — CLI: sincroniza el catálogo contra `videos_prueba/`.

### `visor_videos.py` — interfaz gráfica
- `VisorVideos(QMainWindow)` — ventana principal: barra de búsqueda, contador, grilla de tarjetas dentro de un `QScrollArea`.
- `Tarjeta(QFrame)` — tarjeta por video: miniatura (o recuadro "Sin miniatura") + campos de texto (nombre, duración, resolución, codec, miniaturas).
- `cargar_tarjetas()` — construye las tarjetas a partir de `listar_videos()` (delegado a `escanear_videos`).
- `filtrar(texto)` — filtrado por coincidencia de nombre; mantiene `visibles` y actualiza el contador.
- `miniatura_principal(nombre)` — ubica la primera miniatura cuyo prefijo coincide con el video.
- `main()` — bootstrap de la app + **smoke test automático**: abre la ventana, imprime visibles/contador iniciales, a los 2 s filtra con "real", a los 5 s imprime el resultado final y cierra con `exit 0`.

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
| FFmpeg | — | **No usado aún.** No existe generación de miniaturas. |
| Generación de miniaturas | — | **Ausente** (solo conteo). Punto de extensión. |
| Caché | — | **No existe** un módulo de caché; la BD cumple parcialmente ese rol para metadatos. |
| Configuración | — | **No existe**; constantes y rutas fijas en código. |
| Trabajos en segundo plano | — | **Ausente**; FFprobe se ejecuta en el hilo principal y bloquea. |

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
   - para cada uno: `obtener_datos_ffprobe` (si no está vacío) + `contar_miniaturas` → `UPDATE`;
   - elimina de la BD los que ya no están en disco.
4. `commit()` y cierre.

## 6. Flujo de generación de miniaturas

**Estado actual: no existe generación.** El pipeline completo está implementado hasta FFprobe; las miniaturas presentes en `miniaturas/` fueron producidas fuera del proyecto. El backend solo las cuenta (`contar_miniaturas`) y el visor las muestra (`miniatura_principal`).

**Flujo previsto (punto de extensión):** escanear video → FFprobe para metadatos → FFmpeg para extraer N fotogramas (p. ej. `-ss` distribuidos sobre la duración, `-frames:v 1`) → escribir `miniaturas/<video>_NN.jpg` → actualizar `cantidad_miniaturas` en la BD → la tarjeta ya las muestra sin cambios de interfaz.

## 7. Puntos de extensión previstos

1. **Generación de miniaturas con FFmpeg** — integrar en `escanear_videos.py` un módulo/helper que produzca `miniaturas/<video>_NN.jpg`. La interfaz y el conteo ya están preparados.
2. **Ejecución asíncrona** — mover FFprobe/FFmpeg a trabajos en segundo plano (hilos/`QThread`/procesos) para no bloquear el escaneo ni la UI.
3. **Módulo de configuración** — centralizar rutas (`videos_prueba`, `miniaturas`, `biblioteca.db`), extensiones, tamaños de tarjeta y número de columnas.
4. **Caché de miniaturas/metadatos** — formalizar la BD como caché de metadatos y evitar re-escaneos.
5. **Lectura/vistas del catálogo** — sobre `listar_videos()`, agregar orden/agrupación/filtros adicionales sin tocar la UI.
6. **Autenticación de rutas absolutas** — resolver `miniaturas/` y `videos_prueba/` respecto de la ubicación del módulo para independizar del directorio de trabajo.

## 8. Problemas detectados

| # | Severidad | Problema |
| --- | --- | --- |
| 1 | Media | La interfaz (`visor_videos.py`) accedía a SQLite directamente y duplicaba el nombre de BD (`"biblioteca.db"`). **Corregido** en esta etapa. |
| 2 | Media | Rutas relativas (`miniaturas/`, `videos_prueba/`, `biblioteca.db`) dependen del directorio de trabajo; la app falla si se lanza desde otra ubicación. Pendiente. |
| 3 | Media | No existe generación de miniaturas (FFmpeg ausente); solo conteo. Pendiente (por diseño, ver §6). |
| 4 | Media | FFprobe se ejecuta en el hilo principal con timeout de 30 s por video; el escaneo bloquea. Pendiente. |
| 5 | Baja | `contar_miniaturas`/`miniatura_principal` usan coincidencia por prefijo (`startswith`); un video `video_real.mp4` podría matchear miniaturas de un hipotético `video_realista.mp4`. Pendiente. |
| 6 | Baja | Los videos vacíos (0 bytes) quedan sin metadatos; comportamiento correcto pero debe documentarse para el usuario. Pendiente. |
| 7 | Informativa | `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` son artefactos de prueba ajenos al visor. Se preservaron por política de esta etapa. |

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

## 10. Recomendaciones priorizadas

1. **Alta — Configurar rutas absolutas** (`escanear_videos.py`, `visor_videos.py`): resolver `miniaturas/`, `videos_prueba/` y `biblioteca.db` a partir de `os.path.dirname(__file__)` o un módulo de configuración.
2. **Alta — Generación de miniaturas con FFmpeg**: cerrar el pipeline prometido por la UI (tarjetas ya soportan imágenes).
3. **Media — Trabajos en segundo plano**: mover FFprobe/FFmpeg fuera del hilo principal (hilos o `QThread`), con barras de progreso.
4. **Media — Módulo de configuración** centralizado (rutas, extensiones, dimensiones, columnas).
5. **Baja — Robustecer coincidencia de miniaturas**: usar coincidencia de prefijo con delimitador (`prefijo + "_"`) o patrón rígido `<video>_<NN>.jpg`.
6. **Baja — Versionado**: agregar `.gitignore` para `__pycache__/` y considerar ignorar `biblioteca.db` y `datos.txt`; mover `main.py`/`operaciones.py`/`prueba_agente.py` a una carpeta `pruebas/` en una etapa futura (no se hizo ahora por política).

## 11. Verificación ejecutada

| Prueba | Comando | Resultado |
| --- | --- | --- |
| Compilación de ambos módulos | `python -m py_compile escanear_videos.py visor_videos.py` | OK (exit 0) |
| Sincronización de catálogo | `python escanear_videos.py` | OK (exit 0) |
| Metadatos FFprobe en BD | consulta SQL | `video_real.mp4` → 5.0 s, 640x360, h264, 4 miniaturas; videos vacíos → NULL/0 (esperado) |
| Smoke test GUI (línea base, previo a cambios) | `python visor_videos.py` | `visibles_inicio=4 videos`, filtro "real" → `1 video`, exit 0 |
| Smoke test GUI (post cambios) | `python visor_videos.py` | Salida idéntica a la línea base, exit 0 — **sin regresiones** |
