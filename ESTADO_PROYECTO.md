# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** la **Beta 3 está terminada y congelada sobre el código
definitivo**, con su instalador oficial generado (`VisorVideos_Beta3_Setup.exe`,
`Distribucion\Beta3\`) y pendiente únicamente de la validación manual integral
sobre una instalación limpia y su publicación (la Beta 2 permanece como la
última versión estable publicada). Sobre esa base congelada se inició el
**ciclo de desarrollo Beta 4** en la **rama `beta4`** (punto de partida: cierre
de la Beta 3, commit `4408d542`). La primera etapa, **B4.1 — Exploración
temporal interactiva y marcadores visuales**, quedó **aprobada e incorporada**:
cada tarjeta puede expandirse en una **superficie temporal** que representa la
duración completa del video (0–100 %), con marcador móvil que acompaña al
cursor, tiempo correspondiente a la posición, preview existente más cercana al
instante y una **preview móvil** que acompaña horizontalmente al cursor
(funciona con previews horizontales y verticales). Además permite múltiples
**marcadores temporales libres** (tiempo real + marca visual + miniatura fijada,
con solapamiento permitido) y su **eliminación individual** con clic derecho
(sobre la miniatura fijada o sobre la marca roja). La segunda etapa, **B4.2 —
Persistencia de marcadores temporales por video**, quedó **aprobada e
incorporada**: los marcadores creados por el usuario se almacenan
**permanentemente en SQLite** (tabla `marcadores_video`, relacionados mediante
`videos.id`), reaparecen entre sesiones, pueden eliminarse permanentemente y
recuperan su representación visual usando las previews disponibles. El
scrubbing **no ejecuta FFmpeg ni accede a disco por movimiento**.
La tercera etapa, **B4.3.1 — Motor de caché temporal versionada y
reanudable**, quedó **aprobada e incorporada**: es el **motor de disco** de la
caché densa de exploración temporal, con estructura
`miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` +
`fXXXXXXXXXX.jpg`), **versiones aisladas** derivadas de un *fingerprint* de
metadatos baratos (ruta normalizada + tamaño + `mtime_ns` + duración, SHA-256
reducido a 16 hex; **no** es hash de contenido), **reanudación** de
generaciones incompletas (p. ej. 8 de 20 reutiliza los 8 y genera 12),
**JPEG atómicos** válidos individualmente, **invalidación por versión distinta**
sin borrado automático y escritura temporal → `os.replace`. Es un motor puro
(sin UI, sin SQLite): la integración real con la tarjeta será la **B4.3.2**.
**Próxima etapa: B4.3.2 — Integración de la caché temporal en la tarjeta** (ver
`ROADMAP.md`, sección "Beta 4").

## Último commit aprobado

**Mensaje:** Implementar motor de cache temporal versionada y reanudable

**Etapa:** B4.3.1 — Motor de caché temporal versionada y reanudable (rama `beta4`):
- `exploracion_cache.py` — **nuevo**: motor de caché densa de exploración en disco, **sin Qt,
  sin SQLite y sin acoplamiento con `escanear_videos`**. Estructura
  `miniaturas/exploracion/<video_id>/<version_fingerprint>/` con `meta.json` + `f{ms:010d}.jpg`;
  el `video_id` identifica la carpeta y no se repite en el nombre del JPG.
- **Versionado físico por fingerprint**: `fingerprint_actual` (ruta normalizada + tamaño +
  `mtime_ns` + duración) → `version_id_de_fingerprint` = **SHA-256 reducido a 16 hex**. **NO**
  es hash del contenido; **limitación aceptada**: dos archivos con la misma ruta, tamaño,
  mtime y duración no son distinguibles. `version_actual` cuesta ≈ **13 µs** (un `os.stat` +
  SHA-256); impacto CPU/RAM despreciable.
- **API para consumidores** (sin gestionar versiones): `generar_fotogramas`, `listar_fotogramas`,
  `faltantes`, `cache_vigente`, `fotograma_mas_cercano_en_cache`, `ruta_carpeta_actual`,
  `version_actual`.
- **Reanudación**: un `f*.jpg` presente en la versión se reutiliza aunque la versión esté
  incompleta (la escritura es atómica, temporal → `os.replace`; un JPEG presente está completo);
  p. ej. una generación detenida en 8/20 reutiliza los 8 y genera solo 12. El `meta.json` de la
  versión **solo** se escribe si la generación termina sin cancelarse y **completa**
  (`faltantes == 0`); la completitud se deriva de `objetivos - existentes`. `.tmp`/preparados/
  fallidos quedan fuera del índice y de la lista.
- **Invalidación no destructiva**: cualquier cambio en el fingerprint produce una **versión
  distinta**; las versiones antiguas quedan en disco (no se borra nada automáticamente; la
  limpieza queda para una etapa futura). Una versión nunca usa ni lista JPEGs de otra.
- `exploracion_temporal.py` — **densidad y orden**: `cantidad_fotogramas(duracion)` =
  `clamp(round(duración / 2 s), 40, 200)` y `tiempos_objetivo(duracion, cantidad)` = instantes
  (ms) en **orden progresivo de cobertura** por bisección de huecos (50 %, 25/75 %, octavos…),
  pensado para la estrategia híbrida de B4.3.2; `fotograma_mas_cercano(ms_existentes, instante)`
  por `bisect` (empate → el anterior). API de B4.1 intacta.
- `rutas.py` — `ruta_carpeta_exploracion()` = `miniaturas/exploracion`.
- `prueba_exploracion_cache_b431.py` — **nueva**: 29 pruebas (densidad, orden progresivo,
  nearest por bisect, estructura versionada, fingerprint sin hash, invalidación no destructiva,
  reanudación 8/20, fallos parciales, aislamiento A/B/C, atomicidad, nearest solo de la versión
  actual, y aislamiento de la etapa: sin UI, sin SQLite, sin tocar la caché real).

**Pruebas superadas:** `prueba_exploracion_cache_b431.py` **29/29**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_b41.py` **28/28**, `prueba_marcadores_b42.py**
**17/17**, `prueba_previews_progresivas.py` **16/16**, `prueba_smoke.py` OK. `python -m py_compile`
OK. `git diff --check` OK.

## Hitos completados

- Arquitectura general y separación de capas.
- Control de versiones con Git.
- Resolución centralizada de rutas (independiente del CWD).
- Generación de miniaturas con preservación de archivos.
- Infraestructura de trabajos en segundo plano (QThread).
- Escaneo asíncrono de videos.
- Lectura asíncrona del catálogo SQLite.
- Lectura paginada del catálogo (`LIMIT`/`OFFSET`/`COUNT` en SQL).
- Escritura individual y de colección asíncronas.
- Integración asíncrona de la interfaz (carga inicial sin bloquear).
- Selección de carpeta desde la interfaz.
- Escaneo manual y asíncrono de la carpeta elegida.
- Pipeline completo: escaneo → tamaños → FFprobe → miniaturas → guardado → sincronización → recarga.
- Detección de diferencias disco ↔ BD (no destructiva).
- Plan de sincronización y aplicación de incorporaciones.
- Eliminación controlada de registros ausentes.
- Sincronización asíncrona del catálogo e integración en la interfaz.
- Recarga asíncrona del catálogo tras sincronización.
- Carga manual de páginas adicionales (botón "Cargar más").
- Presentación del catálogo en filas horizontales (una tarjeta por video).
- Visualización del tamaño de archivos (B/KB/MB/GB).
- Previews progresivos por video (3 fotogramas al 25/50/75 %).
- Apertura del video por doble clic (módulo de servicio `apertura_videos.py`).
- Persistencia de la última carpeta seleccionada (`configuracion.json`).
- Separación del punto de entrada de producción y del arnés de smoke tests.
- Ejecutable portable (PyInstaller `--onedir --windowed`).
- Instalador Beta funcional (Inno Setup, sin permisos de administrador).
- Feedback visual del procesamiento (barra de progreso indeterminada con texto de etapa).
- Selección visual de filas (simple y múltiple con Ctrl+clic). Base preparada para futuras acciones sobre elementos seleccionados sin agregar menús ni botones todavía.
- Menú contextual con clic derecho sobre filas de videos (abrir, abrir carpeta, copiar ruta).
- Restauración automática de la selección tras reconstruir la lista de tarjetas.
- Selección por rango con Shift+clic basada en un ancla de selección y el orden visible.
- Copia de rutas de los seleccionados mediante menú contextual (primera operación sobre selección múltiple).
- Apertura de carpetas de los seleccionados mediante menú contextual (deduplicación de carpetas).
- Cantidad configurable de previews visibles (3/5/7/9) con persistencia y actualización inmediata de la interfaz.
- Infraestructura de paneles con QSplitter (panel izquierdo placeholder + panel derecho con interfaz existente, PanelPrincipal con minimumSizeHint anulado).
- Árbol de navegación en el panel izquierdo (Etapa 2.1: nodo "Este equipo" + discos del sistema, puramente visual y sin navegación).
- Expansión de discos y carpetas con carga diferida (Etapa 2.2: un solo nivel por expansión, estado de carga en el nodo, ruta absoluta en cada nodo, árbol desacoplado del catálogo).
- Selección funcional del árbol de navegación (Etapa 2.3: `carpeta_actual()` como interfaz oficial, señal `ruta_seleccionada` notificadora, raíz y placeholders excluidos, selección conservada al contraer/expandir).
- Integración de la selección del árbol con la carpeta activa de la aplicación (Etapa 2.4: `carpeta_seleccionada` como única fuente de verdad, handler `_al_carpeta_actual_arbol`, sincronización árbol ↔ diálogo con `seleccionar_ruta`, sin escaneo ni catálogo).
- Persistencia y restauración del Centro de Navegación (Etapa 2.5: la carpeta seleccionada se persiste con `guardar_ultima_carpeta` y se reconstruye al iniciar con `revelar_ruta`, expandiendo solo la rama necesaria; restauración tolerante).
- Integración del árbol con el flujo de escaneo (Etapa 2.6: seleccionar una carpeta válida en el árbol o por el diálogo inicia automáticamente el escaneo mediante `iniciar_escaneo()`, el mismo punto de entrada del botón; un único disparo por acción; restauración inicial sin escaneo).
- Verificación de la paridad de "Incluir subcarpetas" (Etapa 2.7: etapa de validación sin cambios de producción; árbol, botón y diálogo respetan de forma idéntica la casilla, confirmado por `prueba_subcarpetas_arbol.py`).
- Preferencia independiente de escaneo automático (Etapa 2.8: casilla "Escaneo automático" junto a "Incluir subcarpetas", persistida en `configuracion.json` con default `True`; decisión única `_disparar_escaneo_si_automatico()`; el botón "Escanear carpeta" ignora la preferencia; cuatro combinaciones soportadas).
- Indicadores visuales de carpetas escaneadas (Etapa 2.9: `EstadoNodo` + `ROL_ESTADO` + `_icono_para`, marcado por el pipeline al sincronizar; únicamente visual, sin alterar selección/expansión/navegación; el árbol no conoce SQLite).
- **Cierre del Bloque de trabajo 2 y aprobación del Centro de Navegación.** La **Beta 2 queda congelada** y entra en fase de pruebas reales: sin nuevas funcionalidades, únicamente correcciones de errores detectados mediante el uso.
- **Aprobación del alcance de la Beta 3 (Etapa B3.0).** Finalizó la fase de
  recopilación de mejoras del uso real de la Beta 2 y quedó **aprobado el
  alcance de la Beta 3**, con su plan de trabajo en `ROADMAP.md` (Bloque de
  trabajo 3). Etapa exclusivamente documental: sin cambios de código ni
  implementación de funcionalidades.
- **Tiempo sobre las miniaturas de preview (Etapa B3.1).** Primera mejora de la
  Beta 3 implementada (Bloque A): cada preview muestra el instante temporal
  derivado de la duración del catálogo, con overlay exclusivamente visual y sin
  cambios de pipeline, esquema SQLite ni recursos.
- **Duración simplificada (Etapa B3.2).** El campo "Duración" de la tarjeta se
  presenta con `formatear_tiempo` (m:ss / h:mm:ss / "No disponible"), reutilizando
  la función de B3.1; cambio solo de presentación, sin tocar el valor numérico,
  SQLite, consultas, pipeline ni miniaturas.
- **Tamaño configurable de miniaturas (Etapa B3.3).** Presets Pequeño/Mediano/Grande
  con escalado exclusivamente en memoria (reutiliza los pixmaps cargados, sin FFmpeg,
  sin relectura de disco, sin regeneración ni reescaneo); cambio inmediato
  conservando selección, scroll y overlays; preferencia persistida con default
  "Mediano".
- **Vista ampliada al posar el mouse (Etapa B3.4).** Popup único por ventana que
  amplía (~1.6×) la miniatura principal o cualquier preview reutilizando el pixmap
  original en memoria (sin lecturas de disco ni procesos externos); aparece tras un
  retardo, se oculta al salir/scroll/reconstrucción/cierre y se posiciona dentro de
  la pantalla.
- **Preferencias relacionadas con miniaturas (Etapa B3.5).** Botón "Preferencias…"
  con diálogo modal que expone el retardo de la vista ampliada (discreto, default
  400 ms), aplicado de inmediato y persistido con la infraestructura existente; los
  controles Previews y Tamaño permanecen con acceso directo en la barra. Con esto
  el **Bloque A — Experiencia visual queda completo**.
- **Tamaño "Muy grande" (Etapa B3.6).** Cuarto tamaño (512×288) incorporado como
  ampliación de A3, solo ampliando los datos de configuración (sin refactor ni
  lógica específica); confirma el desacople diseñado en B3.3. Miniatura principal,
  previews, overlays, vista ampliada, persistencia y cambio inmediato funcionan
  automáticamente; "Mediano" sigue siendo el default.
- **Tamaño configurable de la vista ampliada (Etapa B3.7).** El factor de ampliación
  (1.2/1.6/2.0/2.5, default 1.6) pasa a ser configurable desde el diálogo
  "Preferencias", aplicado de inmediato y persistido con la infraestructura existente;
  la ampliación sigue siendo proporcional al tamaño de la miniatura y el
  comportamiento por defecto es idéntico al previo.
- **Generación automática de previews faltantes (Etapa B3.8).** Al aumentar la
  cantidad de previews, las tarjetas crecen dinámicamente (sin reconstruirse) y la
  cola existente genera únicamente los índices faltantes en segundo plano, actualizando
  solo las tarjetas afectadas; sin escaneo ni pipeline. Al disminuir solo se ocultan.
- **Pulido técnico del Bloque A (Etapa B3.9).** Mejoras internas sin funcionalidades
  nuevas: acotado de pixmaps originales en memoria (límite 1280, sin releer disco ni
  regenerar), transición limpia del popup, helper `_duracion_valida` y eliminación de
  constantes realmente muertas. Con esto el **Bloque A queda finalizado funcional y
  técnicamente**.
- **Planificación y congelamiento del Bloque B (Etapa B3.10).** Etapa exclusivamente
  documental: se define el orden de implementación del Bloque B (B3.11 a B3.17), sus
  dependencias, las decisiones congeladas (Copiar/Pegar/Eliminar, segundo plano, modo
  selección) y los excluidos. El alcance queda congelado en `ROADMAP.md`.
- **Resumen de selección (Etapa B3.11).** Primera mejora del Bloque B implementada
  (B6): indicador permanente "X de Y seleccionados" basado únicamente en las tarjetas
  visibles, centralizado en `_actualizar_resumen_seleccion()` e integrado con
  selección, búsqueda, carga inicial, reconstrucción y paginación.
- **Modo selección + Checks por fila (Etapa B3.12).** Mejoras B1 + B2: botón toggle
  "Modo selección" en la barra; `QCheckBox` por tarjeta (oculto por defecto, visible
  solo en modo activo); sincronización bidireccional centralizada en `_marcar_tarjeta`
  con `blockSignals` (sin reentradas) y `_nombres_seleccionados` como única fuente de
  verdad. Activarlo/desactivarlo conserva la selección y el resumen.
- **Atajos básicos (Etapa B3.13).** Parte de B7: Ctrl+A (selecciona solo las tarjetas
  visibles, respetando el filtro; con foco en la búsqueda no interfiere con el
  `QLineEdit`) y Esc (sale del Modo Selección, oculta los checks y conserva la
  selección y el resumen), mediante `QShortcut` sobre la ventana.
- **Copiar (Etapa B3.14).** Mejora B3: copia de los archivos de video seleccionados a
  una carpeta destino elegida por el usuario, en segundo plano (tercer gestor
  `gestor_operaciones`), sin sobrescribir, con resumen final (copiados/omitidos/errores)
  visible en la interfaz. Lógica pura en `operaciones.copiar_archivos`.
- **Desactivar la vista ampliada (Etapa B3.14a).** Ampliación del Bloque A: opción
  "Desactivado" (`-1`) en el retardo de la vista ampliada; con ella nunca se inicia el
  timer ni aparece el popup al posar el mouse, y volver a cualquier retardo reactiva la
  funcionalidad.
- **Tamaños grandes de la vista ampliada (Etapa B3.14b).** Ampliación del Bloque A:
  factores 3.0x y 3.5x (máximo 3.5x; la vista ampliada puede ocupar prácticamente toda
  la pantalla, acotada por `_posicion_vista`); integración por datos, sin tratamiento
  especial, default 1.6.
- **Pegar (Etapa B3.15).** Mejora B4: pega en la carpeta actual los archivos copiados
  internamente (portapapeles interno `_portapapeles`, alimentado al copiar), en segundo
  plano reutilizando `gestor_operaciones`, con un único diálogo de colisión
  ("Omitir"/"Cancelar", nunca sobrescribe), resumen final en la interfaz y
  **resincronización incremental**: la cadena existente (tamaños → FFprobe → miniaturas
  → guardado → sincronización → recarga) se reutiliza únicamente para los archivos
  pegados, sin reescaneo completo. Lógica pura en `operaciones.pegar_archivos`.
- **Eliminar (Etapa B3.16).** Mejora B5: envía los archivos seleccionados a la
  **Papelera de reciclaje de Windows mediante la API nativa `SHFileOperationW` vía
  `ctypes`** (sin dependencias externas; nunca borrado permanente), con un único diálogo
  de confirmación ("Eliminar"/"Cancelar", default Cancelar), en segundo plano
  reutilizando `gestor_operaciones` (`TareaEliminarArchivos`), resumen final en la
  interfaz y **actualización incremental del catálogo** que reutiliza la sincronización
  existente (detecta ausentes y los elimina) + recarga, **sin reescaneo completo**.
  Lógica pura en `operaciones.eliminar_archivos`.
- **Atajos de operaciones (Etapa B3.17).** Mejora B7 (completada): **Ctrl+C**, **Ctrl+V**
  y **Supr** vinculados respectivamente a Copiar, Pegar y Eliminar mediante `QShortcut`
  (patrón B3.13). Cada atajo **reutiliza directamente** `_iniciar_copia()`,
  `_iniciar_pegar()` y `_iniciar_eliminar()`, sin lógica paralela ni validaciones
  duplicadas (las existentes cubren sin selección, sin portapapeles y gestor ocupado).
  Con foco en la búsqueda se **preserva el comportamiento nativo del `QLineEdit`**
  (`copy()`/`paste()`/`del_()`), replicando el criterio de Ctrl+A.
- **Corrección técnica del Bloque B (Etapa B3.18).** Corrige la condición de carrera
  detectada en la auditoría (punto I1): `_procesar_archivos_pegados` y
  `_procesar_archivos_eliminados` **capturan la carpeta al inicio** de la operación y la
  fijan en el override temporal `_carpeta_sincronizacion`; `_iniciar_sincronizacion(carpeta=None)`
  resuelve la carpeta por **parámetro → override → carpeta actual** y la sincronización usa
  exactamente la carpeta de la operación aunque el usuario cambie de carpeta durante la
  cadena. El override se limpia automáticamente (`_iniciar_sincronizacion`, `_limpiar_cadena`
  e `iniciar_escaneo`), evitando reutilizaciones accidentales y sin modificar el
  comportamiento normal del pipeline.
- **Infraestructura de progreso (Etapa B3.20).** Primera etapa del Bloque C: cambio
  **aditivo** en `tareas.py` — `TareaBase.progreso = Signal(int, int)` (`(procesado, total)`,
  `total <= 0` = indeterminado), helper `reportar_progreso`, `GestorTareas.tarea_progreso`
  con reenvío por `_RelayTarea` y el mismo criterio del token `_vigente` (descarta emisiones
  tardías). `ejecutar()` intacto y ninguna tarea emite progreso todavía: sin cambio visible.
  La señal queda desacoplada de la interfaz para su uso en B3.21 y B3.22.
- **Progreso real del pipeline de escaneo (Etapa B3.21).** La cadena principal informa
  progreso real en **tamaños, FFprobe, miniaturas y guardado** mediante **callbacks opcionales
  de progreso** en las funciones puras de `escanear_videos` (sin Qt ni bucles movidos a las
  tareas; sin callback el comportamiento es idéntico). `_mostrar_progreso()` restablece
  siempre el modo indeterminado y `_al_progreso_pipeline` (conectado a `gestor.tarea_progreso`)
  fija `setRange(0, total)` + `setValue(procesado)`. Escaneo, sincronización y recarga
  permanecen indeterminados por decisión.
- **Progreso real de las operaciones de archivos (Etapa B3.22).** Copiar, Pegar y Eliminar
  informan progreso real por archivo: callbacks opcionales `on_progreso` en las tres funciones
  puras de `operaciones.py` (sin Qt; incluye omitidos y errores); las tres tareas pasan
  `self.reportar_progreso`; `gestor_operaciones.tarea_progreso` se conecta al **mismo handler**
  `_al_progreso_pipeline` (sin lógica paralela). Se incorpora la **exclusión mutua** entre
  operaciones y pipeline principal (guard en los handlers y en la habilitación de los botones).
- **Pulido visual del sistema de progreso (Etapa B3.23).** La barra muestra simultáneamente el
  nombre de la etapa, la cantidad "N de M" y el porcentaje mediante el formato detallado
  `"{etapa} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar`, aplicado **una
  sola vez por etapa** en `_al_progreso_pipeline`. `_mostrar_progreso` guarda `_texto_progreso`
  y reinicia `_progreso_detallado`; las etapas sin emisión (escaneo, sincronización, recarga)
  siguen indeterminadas con texto simple. Sin cambios en tareas ni infraestructura. Con esto
  el **Bloque C — Progreso queda completo**.
- **Infraestructura de selección de carpetas (Bloque 4, Etapa 1).** Clase pura
  `SeleccionCarpetas` con el conjunto de rutas como única fuente de verdad, persistencia en
  configuración (`carpetas_seleccionadas`), restauración al iniciar con descarte automático de
  rutas inexistentes y API `seleccionar`/`deseleccionar`/`alternar`/`limpiar`/`seleccionar_todas`/
  `obtener_seleccion`. Sin árbol, sin UI, sin cambios en escaneo/SQLite/pipeline. Es la base de
  la "Selección personalizada" del Bloque de trabajo 4.
- **Modo de selección del árbol y herramientas de selección rápida (Bloque 4, entrega conjunta
  Etapas 2-3).** `ArbolNavegacion` se enlaza a `SeleccionCarpetas`: toggle "Modo selección" que
  muestra checks por nodo sincronizados con el conjunto (sin alterar carpeta activa, navegación
  ni escaneos; con el modo desactivado el árbol es idéntico al actual). Herramientas rápidas:
  "Seleccionar todas" del nivel, "Deseleccionar todas", "Invertir" y menú contextual
  (Seleccionar/Deseleccionar: hasta aquí, desde aquí hasta el final) sobre los hermanos
  ordenados. Todas materializan **rutas** en `SeleccionCarpetas`, sin intervalos ni estructuras
  paralelas.
- **Escaneo multicarpeta (Bloque 4, Etapa 4).** `iniciar_escaneo(carpetas=None)` acepta una
  lista de carpetas y encadena el pipeline existente **una vez por carpeta** (cola secuencial),
  produciendo la unión en el catálogo; deduplicación de carpetas y modo tradicional idéntico.
- **Sincronización multicarpeta (Bloque 4, Etapa 5).** Se elimina por completo el flag temporal
  `_omite_sincronizacion` y se implementa una **sincronización real por cada carpeta del alcance**
  efectivo: `detectar_diferencias(..., carpetas_protegidas)` sincroniza **por ruta** en modo
  multicarpeta (una carpeta no elimina registros de otras raíces del mismo alcance; el modo
  tradicional permanece idéntico); `_alcance_sincronizacion` es el mismo conjunto efectivo que la
  cola de escaneo; la **normalización del alcance efectivo** (`_alcance_efectivo`/`_ruta_contiene`)
  elimina raíces descendientes redundantes cuando "Incluir subcarpetas" está activado (comportamiento
  ON/OFF diferenciado), y la **transición A → A+B → A** queda verificada contra SQLite. Sin cambios
  de esquema SQLite.
- **Unificación del selector de alcance (Bloque 4, Etapa 6).** El checkbox "Incluir subcarpetas" es
  reemplazado por un **selector de modo único** (`combo_modo_alcance`) con tres opciones — "Solo
  carpeta actual", "Carpeta actual y todas las subcarpetas" y "Selección personalizada" — como
  **única fuente de verdad visible** del alcance; persistencia (`modo_alcance`) y **migración
  retrocompatible** desde el booleano antiguo; el checkbox queda como **adaptador de compatibilidad
  oculto**.
- **Auditoría integral del Bloque 4 y cierre funcional de la Beta 3 (Bloque 4, Etapa 7).**
  Auditoría final con la batería completa de suites: se detectó y **corrigió la regresión de
  `_duracion_valida`** (restaurado `duracion > 0`; la duración 0 vuelve a ser inválida), se
  incorporó la verificación integrada de transiciones de modo y se confirmó el resto del Bloque 4
  sin problemas. Con esto la **Beta 3 queda funcionalmente cerrada y congelada** sobre el código
  definitivo.
- **Corrección de la regresión de previews (cierre de la Beta 3).** El subsistema de previews
  deja de depender de `carpeta_seleccionada`: cada video usa su propia carpeta real del catálogo
  (columna `ruta` incorporada a `listar_videos`/`listar_videos_paginado`); carpeta única,
  carpeta + subcarpetas y selección personalizada (una o varias carpetas) generan previews
  correctamente, verificadas por `prueba_previews_multicarpeta.py` (5/5).
- **B4.1 — Exploración temporal interactiva y marcadores visuales.** Primera etapa del ciclo
  Beta 4 (rama `beta4`). Cada tarjeta gana un control "Expandir/Colapsar" con **una sola
  tarjeta expandida a la vez**; la segunda fila expandida es una **superficie temporal** que
  mapea horizontalmente 0–100 % de la duración (izquierda = inicio, derecha = final), con
  marcador móvil que acompaña al cursor, tiempo correspondiente a la posición, preview
  existente más cercana al instante (por tiempo real) y una **preview móvil** que acompaña
  horizontalmente al cursor (funciona con previews horizontales y verticales; el extremo
  derecho siempre es alcanzable porque la superficie se acota al ancho visible). El clic sobre
  la superficie crea **marcadores temporales libres** que conservan tiempo real, marca visual
  y miniatura fijada (solapamiento permitido; persisten en memoria mientras vive la tarjeta
  durante la sesión); el clic derecho sobre la miniatura fijada o sobre la marca roja elimina
  **únicamente** ese marcador. `mouseMove` = **cero FFmpeg + cero acceso a disco**. Sin
  persistencia, sin cambios de SQLite ni de `escanear_videos.py`.
- **B4.2 — Persistencia de marcadores temporales por video.** Segunda etapa del ciclo
  Beta 4 (rama `beta4`). Los marcadores creados por el usuario se almacenan
  **permanentemente en SQLite** en la tabla `marcadores_video` (`id INTEGER PRIMARY KEY
  AUTOINCREMENT`, `video_id INTEGER NOT NULL`, `tiempo REAL NOT NULL`, índice
  `idx_marcadores_video_video_id_tiempo`), relacionados mediante **`videos.id`** (la columna
  `id` se expone en el contrato de lectura: `listar_videos` y `listar_videos_paginado`
  devuelven ahora **9 campos**); reaparecen entre sesiones, pueden eliminarse
  permanentemente y recuperan su representación visual usando las previews disponibles.
  Sin cascade automático, sin nombre/ruta como identidad, sin imagen persistida, sin
  nota/color/tipo ni JSON. **Política de conservación**: reescaneo del mismo registro →
  conserva; cambios de metadatos → conserva; reemplazo silencioso manteniendo el mismo
  registro → conserva; si el registro de video desaparece los marcadores **no** se eliminan
  automáticamente (pueden quedar huérfanos); no existe aún reasociación de
  movidos/renombrados ni por nombre/ruta. Deliberado para evitar pérdida automática de datos
  creados por el usuario. `visor_videos.py` **no ejecuta SQLite directamente**: mantiene la
  representación optimista en memoria, carga marcadores al expandir y persiste altas/bajas con
  un gestor dedicado (`gestor_marcadores`) usando `marcador_id` como identidad técnica
  persistente. La carga desde SQLite se trata como **snapshot potencialmente antiguo** y se
  **reconcilia** conservando altas/bajas locales pendientes, IDs persistentes existentes y
  deduplicando por la misma tolerancia temporal de la interacción (carreras cubiertas:
  crear+borrar antes de terminar el INSERT,   cargar+crear, carga+marcador equivalente,
  carga+baja local y recuperación tras DELETE fallido).
- **B4.3.1 — Motor de caché temporal versionada y reanudable.** Tercera etapa del ciclo
  Beta 4 (rama `beta4`), primera subetapa de **B4.3 — Caché densa de exploración temporal**.
  Implementa el **motor de disco** de la caché densa de exploración en `exploracion_cache.py`
  (nuevo): estructura `miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` +
  `f{ms:010d}.jpg`), **versiones aisladas** calculadas por *fingerprint* de metadatos baratos
  (ruta normalizada + tamaño + `mtime_ns` + duración; SHA-256 reducido a 16 hex, **no** es hash
  de contenido), **reanudación** de generaciones incompletas (un JPEG presente está completo:
  escritura atómica temporal → `os.replace`), **invalidación no destructiva** (el cambio de
  fingerprint crea una versión distinta; nada se borra automáticamente), `meta.json` coherente
  con la versión (solo se escribe al completar) y una invocación de FFmpeg por fotograma como
  **mecanismo actual de validación** (no necesariamente el final desde la UI).
  `exploracion_temporal.py` incorpora la **densidad** (`cantidad_fotogramas` =
  `clamp(duración / 2 s, 40, 200)`) y el **orden progresivo** (`tiempos_objetivo` por bisección
  de huecos) con `fotograma_mas_cercano` por `bisect`. Sin UI (la integración es **B4.3.2**),
  sin SQLite (`videos`, `marcadores_video` y `biblioteca.db` intactos) y sin acoplamiento con
  `escanear_videos`. Costo de versión ≈ 13 µs.

## Pendientes prioritarios

1. ~~Mejorar el feedback visual del procesamiento (barra de progreso,~~
   ~~estado visible de tareas en curso).~~ **Implementado.**
2. ~~Incorporar selección visual de filas (selección simple y múltiple,~~
   ~~acciones sobre videos seleccionados).~~ **Implementado.**
3. Evaluar y optimizar el rendimiento con colecciones grandes de videos.
4. Paginación completa automática del catálogo (scroll infinito,
   búsqueda en SQL desde la interfaz, ordenamiento configurable).
5. Deduplicación de nombres repetidos en el plan de sincronización.

Las funcionalidades futuras pendientes se detallan en `ROADMAP.md`.
Los problemas técnicos vigentes se detallan en `DOCUMENTO_TECNICO.md` §8.

## Deuda técnica

- Crecimiento y duplicación de infraestructura entre las suites de
  prueba (helpers, conectores y patrones repetidos).
- Pendiente documental: reducir progresivamente el nivel de detalle de
  implementación en `DOCUMENTO_TECNICO.md`, conservando la información
  arquitectónica pero eliminando detalles que ya refleja el código fuente.
- La selección se restaura automáticamente después de reconstruir
  completamente las tarjetas (`_reemplazar_tarjetas`), pero solo para
  los nombres que siguen existiendo en el nuevo conjunto.
- **Rutas Windows con nombres cortos 8.3** (p. ej. `MARCOS~1`): la
  restauración del árbol (`revelar_ruta`) no las empareja con los nombres
  largos que carga el árbol y cae en el comportamiento tolerante (la
  aplicación inicia sin carpeta seleccionada, sin inconsistencias). No
  afecta el funcionamiento normal; considerarla en una futura etapa de
  robustez del Centro de Navegación (registrada también en
  `DOCUMENTO_TECNICO.md` §8, problema 13).
- **`prueba_aplicar_incorporaciones.py` T15** — falla preexistente y
  ambiental: opera sobre una copia de la base real `biblioteca.db` y asume
  filas preexistentes con `tamano_bytes = NULL`; la base real actual tiene
  `tamano_bytes` poblado. No atribuible a etapas recientes (verificado en la
  Etapa 2.6); la suite no modifica ese subsistema y el resto del pipeline
  funciona correctamente. Revisar el contrato de T15 o aislarlo de la base
  real en una etapa futura.
- **Estado de "escaneada" por sesión** (Etapa 2.9): el indicador de carpetas
  escaneadas vive en memoria (`carpetas_escaneadas` del visor) y se pierde al
  reiniciar; no se persiste ni se deriva del catálogo (requeriría cambios de
  esquema o en módulos restringidos). La API (`EstadoNodo` + `_icono_para`) ya
  está preparada para futuros estados; documentada como deuda técnica para una
  etapa específica de persistencia del estado (registrada también en
  `DOCUMENTO_TECNICO.md` §8, problema 14).
- **`prueba_persistencia_carpeta.py` T11 y T16** — falla **preexistente** (detectada
  en la Etapa B3.3, verificada también en HEAD limpio): los tests asumen que al
  iniciar la aplicación sin preferencias no se crea `configuracion.json`, pero la
  restauración de `escaneo_automatico` (default `True`, Etapa 2.8) escribe el
  archivo en el arranque. No atribuible a B3.3 ni a etapas recientes; corregir en
  una futura etapa específica (p. ej. alinear la restauración con `blockSignals` o
  actualizar el contrato de los tests).

## Próxima etapa

**B4.3.2 — Integración de la caché temporal en la tarjeta.** Segunda subetapa de
**B4.3 — Caché densa de exploración temporal** (el motor de disco quedó implementado en la
**B4.3.1**). Integrar el motor en la interfaz: tarea/gestor de generación, consumo del
fotograma más cercano en la superficie temporal, **fallback a las previews normales** cuando
la caché no exista y **actualización progresiva**. La **estrategia híbrida** (pocos fotogramas
prioritarios distribuidos y luego uno/pocos lotes eficientes) está **registrada pero NO
implementada**; la **cantidad inicial y sus parámetros NO están decididos**. Antes de congelar
MAX, cantidad inicial, tamaño de lote y concurrencia debe realizarse una **prueba real en el
hardware objetivo** (notebook 16 GB RAM, Intel Core i7-7500U @ 2.70 GHz, NVIDIA GeForce 940MX
2 GB, Intel HD Graphics 620): la exploración debe priorizar **agilidad y fluidez**. Se
conservan como funciones futuras: la **reproducción desde el marcador** y la **navegación
entre marcadores durante la reproducción**; la **selección A/B**, los **loops**, la
**selección de fragmentos** y el **corte/unión**; y la **detección de archivos movidos** con
la **reasociación futura de marcadores huérfanos**. Ver la secuencia en `ROADMAP.md`, sección
"Beta 4".

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
