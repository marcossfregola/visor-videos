# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** la **Beta 4 está CERRADA y aprobada** (cierre formal
2026-08-10): build final **`Beta 4 — B4.12`** (commit técnico
`198cdf533986b88c6e25dc0087722cf2b86e5f99`; instalador
`VisorVideos_Beta4_Setup.exe`, SHA-256
`730B4DAB1CD2F1F5CFDD184D2DC6FE80CF0481B8754080F0FF10CF991F89431F`), validada en la
notebook objetivo (B4.11: validación manual amplia; B4.12: validación final
corta) y con la suite integral posterior a las correcciones en **87 suites /
1570/1570 pruebas funcionales OK / 0 FAIL funcional**. La **Beta 3** quedó
finalizada y congelada en su momento con su instalador
(`VisorVideos_Beta3_Setup.exe`); la **Beta 2** permanece como la última versión
estable publicada. El ciclo Beta 4 se desarrolló sobre la **rama `beta4`**
(punto de partida: cierre de la Beta 3, commit `4408d542`). **Beta 5 CERRADA
internamente (cierre formal 2026-08-15, rama `beta5`):** commit técnico principal
`969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
`VisorVideos_Beta5_ValidacionFinal_Setup.exe` (SHA-256
`F40ACF41FE7D3931FF042AC718B6D2805460AE380092E9E782A918C42A650133`), aprobado en la
notebook objetivo; identidad definitiva **`Beta 5 — B5.0`**. Sin distribución
pública, sin merge a `main`, sin GitHub Release (ver "Próxima fase").
La primera etapa, **B4.1 — Exploración
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
(sin UI, sin SQLite). La cuarta etapa, **B4.3.2 — Cobertura rápida asíncrona
integrada con la UI**, quedó **aprobada e incorporada**: la tarjeta consume el
motor con **`FOTOGRAMAS_INICIALES = 15` provisional**, con **fallback inmediato
a las previews normales** mientras no hay caché, **generación asíncrona**,
**resultados parciales progresivos** antes de completar los 15, **lectura y
decodificación JPEG en el worker mediante `QImage`** (emitida por señal) con
**conversión/aplicación final a `QPixmap` en la GUI**, `mouseMove`
exclusivamente en RAM, selección temporal por la imagen más cercana entre
preview normal y densa (la preview normal gana el empate), **cancelación
cooperativa**, **aislamiento A→B**, **colapso que libera las referencias densas
de RAM** y **reexpansión que reutiliza la caché**; los **marcadores** conservan
su tiempo/id y pueden mejorar visualmente al llegar fotogramas densos. La
validación visual manual (puntos A–G) en el PC de desarrollo fue **aprobada por
Marcos**, y la cobertura rápida también quedó validada en la **notebook objetivo**
(expansión y scrub correctos con un video real de ~56 min).
La quinta etapa, **B4.3.2 — Etapa 2: Densidad secundaria adaptativa**, quedó
**aprobada e incorporada**: tras el **benchmark de estrategias** sobre un video
de 56 min, por **decisión de producto** se adoptó la **generación individual y
secuencial (un FFmpeg por objetivo, sin batch, sin paralelismo)**. Los **15
prioritarios** se mantienen exactamente como en la Etapa 1 y la **fase
secundaria** (solo después de la fase rápida, sin solapamiento) completa hasta
`objetivo_total_densidad(duración)` = `clamp(max(15, ceil(d/30 s)), 15, 200)` —
valores **provisionales** (30 s / mín 15 / máx 200) centralizados en
`exploracion_cache.py` para configurarlos después, **sin controles visibles por
ahora**. Reutiliza lo existente (nunca regenera los presentes), es
**progresiva**, **reanudable** y **cancelable**; cambiar/colapsar detiene la
continuación y lo generado queda reutilizable. Validada en el PC de desarrollo
(app real + FFmpeg real) y posteriormente en la **notebook objetivo** (B4.3 en
conjunto quedó validada satisfactoriamente en la notebook).
La sexta etapa, **B4.3.3 — Ajustes de interacción y densidad manual**, quedó
**aprobada e incorporada**: (A) **prioridad visual de la preview dinámica**
durante el hover: al mover el puntero por la tira temporal la miniatura dinámica
queda **por encima** de las miniaturas fijas de marcadores (un marcador nunca
tapa el instante que se está explorando activamente); los tiempos/ids de los
marcadores no cambian y al salir del hover las fijas vuelven a su orden visual
normal. (B) **densidad manual**: control `Auto | 15 | 30 | 60 | 120 | 200` en la
tarjeta expandida; los valores manuales representan el **total objetivo
independiente de la duración** (video de 30 s: Auto → 15, manual 60 → 60, manual
120 → 120); siempre los **15 prioritarios primero**; **aumentar** reutiliza lo
existente (15→60, 60→120); **disminuir** no borra disco ni regenera (la RAM se
limita al conjunto objetivo `tiempos_objetivo(duración, cantidad_actual)`; la
caché puede contener un **superset** y la tarea emite/decodifica solo el
subconjunto permitido); **volver a Auto** recalcula el objetivo y conserva los
extras de disco. El valor de densidad es **por tarjeta/sesión** (se conserva en
colapso/reexpansión de la misma tarjeta; vuelve a Auto si se reconstruye por
recarga); **sin SQLite y sin persistencia en `configuracion.json`**.
La séptima etapa, **B4.4 — Reproducción de marcadores en VLC**, quedó **aprobada e
incorporada** (Etapa 1: inspección y validación física de la estrategia **playlist
pura** con VLC **3.0.23**; Etapa 2: integración mínima). La acción **"Reproducir
marcadores en VLC"** (menú contextual, habilitada con al menos un video seleccionado)
lee los marcadores persistentes (B4.2) y genera una playlist temporal `.m3u` con una
entrada por marcador (`#EXTVLCOPT:start-time`, precisión decimal) en el **orden visible
actual del catálogo** y con marcadores **cronológicos ascendentes**; abre **VLC una
única vez**. **Siguiente/Anterior visibles de VLC recorren la secuencia naturalmente** y
Play/Pause, volumen, fullscreen y seek manual permanecen intactos. Videos seleccionados
sin marcadores → **diálogo por ocasión** (Omitir / Reproducir desde el inicio / Cancelar,
sin persistir). Archivos inexistentes → omitidos con aviso (sin borrar marcadores ni
registros). VLC ausente → mensaje claro, sin instalar. Playlists temporales
`visor_marcadores_*.m3u` en `%TEMP%` con encoding **UTF-8** (espacios/acentos/Unicode) y
**limpieza propia previa** (solo patrón propio; bloqueos ignorados; no se borra la recién
lanzada). Sin HTTP, sin python-vlc/libVLC, sin loop automático. Se conserva como
**pendiente separado**: la demora perceptible al **cargar una carpeta de 121 videos** y
generar las miniaturas normales iniciales (no corresponde a B4.4; sin optimizar aún). El
**batch NO está implementado** (ver `ROADMAP.md`, sección "Beta 4").

La octava etapa, **B4.5 — Rendimiento de carga inicial**, quedó **aprobada e incorporada**
(Etapa 1: diagnóstico del cuello de botella; Etapa 2: eliminación de FFprobe redundante; Etapa 3:
reutilización de metadata en reescaneos). El
diagnóstico (dataset temporal de 121 videos funcionales, base y caché temporales) midió el
pipeline normal de catálogo/miniaturas en la PC de desarrollo: escaneo, tamaños, SQLite y
lectura despreciables; **FFprobe de metadata ~4.5 s (121 procesos, secuenciales)**; **miniaturas
normales ~12.3 s** (121 FFmpeg + 121 FFprobe internos); **previews normales ~38.6 s** (363 FFmpeg
+ 363 FFprobe internos); reescaneo caliente con **FFprobe de metadata redundante (~4.6 s de
~4.9 s)**. El cuello dominante es el **FFmpeg+FFprobe de las previews normales (~70 % del tiempo
en frío)**. La Etapa 2 eliminó los **FFprobe internos redundantes**: `generar_miniatura` y
`generar_preview` aceptan `duracion_segundos=None` (válida → usa esa duración sin FFprobe
interno y con el mismo cálculo temporal y FFmpeg; inválida o ausente → fallback FFprobe
anterior); `asegurar_miniaturas`/`generar_previews_faltantes` y sus tareas
(`TareaMiniaturas`/`TareaPreviewsProgresivas`) propagan las duraciones, que la interfaz toma de
`TareaFFprobe` (miniaturas) y de la tarjeta (previews). En frío con 121 videos: **484 FFprobe
internos → 0**, mismos 484 FFmpeg; total backend **~55.6 s → ~37.1 s** (miniaturas 12.3→7.9 s,
previews 38.6→24.8 s) como medición de la PC de desarrollo (no extrapolable a la notebook). Sin
cambios de cantidad, posiciones, calidad, progresividad, lotes, caché, paralelismo ni FFmpeg.
La **Etapa 3** reutiliza metadata en reescaneos sin cambios con el criterio barato
**`ruta normalizada + tamano_bytes + mtime_ns`** (sin hash de contenido): 0 FFprobe solo si hay
registro previo, `mtime_ns` no NULL, ruta/tamaño/`mtime_ns` coinciden y la metadata es válida;
fuerzan FFprobe archivo nuevo, registro sin `mtime_ns`, ruta/tamaño/`mtime_ns` cambiados o
metadata inválida. Migración aditiva e idempotente `videos.mtime_ns INTEGER NULL`; bases antiguas
hacen FFprobe en la primera pasada y se rellenan. `obtener_tamanos_archivos` obtiene
tamaño+`mtime_ns` con un `os.stat` por archivo; `listar_registros_por_nombres` consulta por lote
(una SELECT); `TareaFFprobe` clasifica y solo probea lo necesario; `guardar_videos` persiste
`mtime_ns`. Reescaneo caliente de 121 videos: **121 FFprobe → 0**, backend **~4.9 s → ~0.1–0.5 s**
(referencia de PC de desarrollo). Verificación empírica con 10 archivos físicos independientes
(10 inodos): **10 → 0 → 1 → 0**. `video_id` y marcadores intactos; un cambio de ruta fuerza
FFprobe conservando la identidad por nombre/upsert. **Riesgo residual aceptado**: si un archivo
distinto reemplaza al original conservando ruta+tamaño+`mtime_ns`, la metadata puede reutilizarse
(sin hash). **Pendiente técnico registrado, sin corregir**: las previews existentes se consideran
reutilizables por existencia del archivo (sin validación por cambio del video). **B4.5 queda
completada en sus Etapas 1-3; no se declara la Beta 4 completa todavía.**
La novena etapa, **B4.6 — Rendimiento de carga visual**, quedó **aprobada e incorporada**
(Etapa 1: diagnóstico de construcción/población de tarjetas; Etapa 2: carga diferida de previews
cacheadas). El diagnóstico con 100 tarjetas/300 previews cacheadas descompuso el costo de la
carga visual: construcción de widgets ~0.42 s (dominada por `_construir_exploracion`);
`miniatura_principal` ~0.05 s (un `os.listdir` por tarjeta); **`_crear_tarjetas` cargaba y
escalaba las 300 previews de golpe (0.74 s caliente / ~3.5 s frío)**; bloqueo síncrono total
1.4–4.4 s; `_reemplazar_tarjetas` re-decodificaba las mismas previews; RAM ~+690 MB por retención
de pixmaps originales. La Etapa 2 difiere la carga de previews cacheadas: `_crear_tarjetas`/
`_agregar_tarjetas`/`_reemplazar_tarjetas` ya **no** las cargan de golpe; las tarjetas parten con
textos + miniatura principal + placeholders y las previews (existentes o faltantes) se incorporan
**progresivamente** por la tubería existente (`_programar_previews` → `_encolar_previews` →
`TareaPreviewsProgresivas` → `generar_previews_faltantes` → `_aplicar_previews`). Con caché
completa **0 FFmpeg**; con faltantes la generación normal. `Tarjeta._previews_completas`
(estado interno, no persistido) decide si una tarjeta entra a la cola; protección de resultados
tardíos en `_aplicar_previews` (cambio A→B sin imágenes cruzadas ni crash); ajuste de integración
en `_reconstruir_previews_exploracion` (fallback a las previews de disco si las etiquetas aún no
las tienen; sin modificar el motor B4.3, scrub, densidad ni marcadores). Medición (PC de
desarrollo): `_crear_tarjetas(100)` **0.69–0.85 s** (antes 1.4–4.4 s); tarjetas visibles ~0.72 s;
primera preview ~1.0 s; **300 previews completas ~2.1 s**; máximo bloqueo continuo **~0.7 s**;
lotes ~20–30 ms; reemplazo ~0.73 s sin recargar previews de golpe. **La interfaz queda utilizable
antes de terminar de cargar las previews.** Pendientes separados, sin implementar: retención de
pixmaps originales/RAM (~+690 MB), `_construir_exploracion` en tarjetas colapsadas,
reconciliación de `_reemplazar_tarjetas` y `miniatura_principal` con `os.listdir`. **B4.6
completada en sus Etapas 1-2; no se declara la Beta 4 completa todavía.**
La mejora de diagnóstico **identificación visible de versión/build** quedó **aprobada e
incorporada**: la ventana principal muestra en la **status bar** inferior un texto discreto con la
versión/build en ejecución (`Beta 4 — B4.12`), definida por constantes centrales en
`configuracion.py` (`VERSION_PRODUCTO`, `BUILD_IDENTIFICADOR`, `TEXTO_VERSION_BUILD`). La
identificación visible es **independiente del SHA Git** (el identificador se incrementa manualmente
por autorización; sin automatización) y para cada build de validación se registra la asociación
**identificador visible → SHA Git exacto → SHA-256 del instalador**.
La corrección técnica previa al cierre quedó **aprobada e incorporada**: (1) la resolución de
existencia de la ruta de video se movió de la UI (`visor_videos.py`) a `rutas.py`
(`ruta_video_existente`), restaurando la regla "la UI no accede al filesystem"; (2) los
contract-tests quedaron reconciliados con el contrato actual (previews progresivas de B4.6, esquema
vigente con `mtime_ns`, tareas legítimas de marcadores); (3) la suite integral quedó en **87 suites
/ 1570 pruebas, 0 FAIL** en la corrida final, con la única flakiness residual conocida de teardown
de `prueba_exploracion_densidad_b432.py` (ocasional `0xC0000409`; 12/12 funcionales; no bloqueante).
**Transición de builds:** `B4.11` = build ampliamente validada en la notebook; `B4.12` = build final
validada en la notebook (validación final corta). **La Beta 4 quedó CERRADA y aprobada (ver
"Próxima fase").**

## Cierre interno de Beta 5

**Fecha:** 2026-08-15 · **Rama:** `beta5`

**Commit técnico principal:** `969efcd9d71e78c1ca538bfa238a3e27f1484d9e`
(«Pulir interacción, edición y visualización de segmentos en Beta 5»).

**Identidad definitiva:** `Beta 5 — B5.0` (constantes en `configuracion.py`).

**Instalador interno validado en notebook:** `VisorVideos_Beta5_ValidacionFinal_Setup.exe`
(SHA-256 `F40ACF41FE7D3931FF042AC718B6D2805460AE380092E9E782A918C42A650133`), aprobado.

**Funcionalidad incorporada en Beta 5:**
- doble clic temporal → VLC desde instante;
- modelo persistente de segmentos A–B;
- carga lazy/asíncrona de segmentos;
- creación visual A+B;
- robustez y ciclo de vida de segmentos;
- reproducción individual A→B; bucle A→B; secuencia de segmentos;
- creación de segmentos por drag;
- edición de extremos A/B conservando id;
- feedback visual de edición (handle/cursor);
- mejora de visibilidad de segmentos;
- scroll horizontal local de previews.

**Correcciones B5.9.2:** doble clic interceptado por `MiniaturaMarcador`; creación de
marcadores cercanos bloqueada por solapamiento.

**Persistencia de edición:** UPDATE por id; tarea asíncrona; rollback en error.

**Validación final:** suites verdes; auditoría integral aprobada; notebook objetivo aprobada.

**Estado de cierre:** cierre interno y local. **Sin distribución pública; sin merge a `main`;
sin GitHub Release.** Deudas registradas: uninstaller destructivo (bloqueante futuro para
distribución pública), retención de pixmaps densos (deuda de Beta 4, no empeoró), flake
ocasional de timing en pruebas VLC/PySide6, seek VLC aproximado por keyframes.

---

## Protocolo de colaboración y materialización de persistencia

**Fecha:** 2026-08-17

El protocolo de colaboración **ChatGPT ↔ Bridge ↔ OpenCode** (con
Bridge/MCP/Telegram como transporte) está **activo**. Su autoridad detallada
— actores, flujo, estados, auditoría, persistencia y seguridad — es
`METODOLOGIA_DESARROLLO.md`.

La **inspección de persistencia** quedó **cerrada y aprobada**, y la
**materialización de la autoridad documental** (documento metodológico,
reglas y protecciones Git) está **en curso**, como etapa previa a **B6.2**.
Las normas permanentes del protocolo constan en `REGLAS_PROYECTO.md`; no se
insertan aquí la matriz completa ni el detalle operativo (ver
`METODOLOGIA_DESARROLLO.md`).

---

## Último commit aprobado

**Mensaje:** Cerrar regresiones y contratos de prueba de Beta 4

**Corrección previa al cierre** (rama `beta4`):
- `rutas.py` — nuevo `ruta_video_existente(carpeta, nombre)`: resuelve y valida la existencia de la
  ruta de video fuera de la UI.
- `visor_videos.py` — `_ruta_video_de` delega en `ruta_video_existente`; **ya no usa
  `os.path.isfile`** (regla arquitectónica "la UI no accede al filesystem" restaurada; verificado por
  `prueba_doble_clic.py` T14 sin modificar el test).
- `configuracion.py` — `BUILD_IDENTIFICADOR = "B4.12"` (la etapa modifica código de producción, por
  lo que no conserva el identificador B4.11); texto visible `Beta 4 — B4.12`.
- Contract-tests reconciliados con el contrato actual: 7 suites de vista ampliada/previews adaptadas
  al contrato progresivo de B4.6; `prueba_filas_horizontales.py` T15 (uso real vs docstrings);
  `prueba_eliminar_candidatos.py` T02 (regla AST precisa ante `TareaEliminarMarcador` legítimo);
  `prueba_persistencia_carpeta.py` T11/T16 (config creada en el arranque por `escaneo_automatico`);
  `prueba_aplicar_incorporaciones.py` T15 (esquema vigente con `mtime_ns` y `tamano_bytes`).
- `prueba_version_build.py` — adaptada a `Beta 4 — B4.12` (3 pruebas).

**Suite integral:** 87 suites, **1570/1570** pruebas, **0 FAIL** en la corrida final. Flakiness
residual conocida (documentada, no bloqueante): teardown ocasional de
`prueba_exploracion_densidad_b432.py` (`0xC0000409`; 12/12 comprobaciones funcionales).

**Transición:** `B4.11` = build ampliamente validada en la notebook; `B4.12` = build final validada en
la notebook. **La Beta 4 quedó CERRADA y aprobada (ver "Próxima fase").**

**Pruebas superadas:** `prueba_version_build.py` **3/3**, `prueba_doble_clic.py` **14/14**, las 7
suites B4.6 reconciliadas (vista_ampliada **24/24**, vista_ampliada_desactivada **20/20**,
preferencias_miniaturas **31/31**, pulido_bloque_a **29/29**, tamano_muy_grande **27/27**,
tiempo_previews **35/35**, tamano_vista_ampliada **38/38**), filas_horizontales **16/16**,
persistencia_carpeta **20/20**, eliminar_candidatos **16/16**, aplicar_incorporaciones **15/15**,
regresiones B4.1–B4.6 verdes y `prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check`
OK.

---

**Commit anterior — Mensaje:** Mostrar identificador de version y build en la interfaz

**Mejora:** Identificación visible de versión/build (`Beta 4 — B4.11`, rama `beta4`):
- `configuracion.py` — constantes centrales `VERSION_PRODUCTO = "Beta 4"`,
  `BUILD_IDENTIFICADOR = "B4.11"` y `TEXTO_VERSION_BUILD = "Beta 4 — B4.11"` (fuente única de
  verdad; independientes del SHA Git; embebidas en la build congelada, sin Git en runtime).
- `visor_videos.py` — `QLabel` discreto con `TEXTO_VERSION_BUILD` en la **status bar** inferior de
  la ventana principal; sin tocar el layout principal ni otra funcionalidad.
- `prueba_version_build.py` — **nueva**: 3 pruebas (constantes; texto exacto `Beta 4 — B4.11`;
  etiqueta visible en la status bar).

**Build de validación:** `B4.11` es la build usada para continuar la validación manual en la
notebook. **No es el cierre definitivo de la Beta 4.**

**Pruebas superadas:** `prueba_version_build.py` **3/3**, `prueba_exploracion_b433.py` **22/22**,
`prueba_carga_visual_b462.py` **9/9**, `prueba_smoke.py` OK. `python -m py_compile` OK.
`git diff --check` OK.

---

**Commit anterior — Mensaje:** Diferir la carga de previews para acelerar la interfaz

**Etapa:** B4.6 — Rendimiento de carga visual, Etapa 2 (rama `beta4`):
- `visor_videos.py` — `_crear_tarjetas`/`_agregar_tarjetas`/`_reemplazar_tarjetas` ya **no** cargan
  previews cacheadas (las tarjetas parten con textos + miniatura + placeholders); `_encolar_previews`
  encola las tarjetas no completas usando `Tarjeta._previews_completas` (estado interno, no
  persistido); `_siguiente_lote_previews` sin filtro `os.path.isdir` (reutilizar cacheadas usa solo
  la caché de miniaturas); `_aplicar_previews` valida la carpeta del video del resultado contra la
  tarjeta actual (ignora resultados tardíos de otra carpeta); `Tarjeta.actualizar_previews` marca
  `_previews_completas` y, si la tarjeta está expandida, llama `_renderizar_marcadores()`;
  `_reconstruir_previews_exploracion` con fallback a las previews cacheadas en disco (integración
  necesaria del diferido; no toca B4.3/scrub/densidad/marcadores).
- `prueba_carga_visual_b462.py` — **nueva**: 9 pruebas (no aplicación eager; placeholders;
  recuperación cacheada progresiva con 0 FFmpeg; generación de faltantes; lotes conservados;
  cambio A→B ignora resultados tardíos; reemplazo sin carga de golpe; cargar más con
  correspondencia; filtro sin romper aplicación).
- Suites adaptadas al comportamiento progresivo: `prueba_tamano_miniaturas.py`,
  `prueba_marcadores_b42.py`, `prueba_exploracion_b41.py` (esperan a que las previews se apliquen
  antes de interactuar con la tarjeta/exploración).

**Medición (PC de desarrollo, 100 tarjetas / 300 previews cacheadas):** `_crear_tarjetas(100)`
**0.69–0.85 s** (antes 1.4–4.4 s); tarjetas visibles ~0.72 s; primera preview ~1.0 s; **300
previews completas ~2.1 s**; máximo bloqueo continuo **~0.7 s**; lotes ~20–30 ms; reemplazo
~0.73 s. La interfaz queda utilizable antes de terminar las previews.

**Pruebas superadas:** `prueba_carga_visual_b462.py` **9/9**. Regresiones en verde (ejecutadas en
el cierre): `prueba_previews_progresivas.py` **16/16**, `prueba_previews_automaticas.py` **22/22**,
`prueba_previews_multicarpeta.py` **5/5**, `prueba_recarga_catalogo.py` **20/20**,
`prueba_pagina_siguiente.py` **20/20**, `prueba_tamano_miniaturas.py` **32/32**,
`prueba_interfaz_asincrona.py` **29/29**, `prueba_escaneo_interfaz.py` **36/36**,
`prueba_marcadores_b42.py` **17/17**, `prueba_exploracion_b41.py` **28/28**,
`prueba_exploracion_b432.py` **20/20**, `prueba_exploracion_b433.py` **22/22**,
`prueba_reutilizacion_metadata_b453.py` **20/20**, `prueba_optimizacion_ffprobe_b452.py` **14/14**,
`prueba_reproduccion_marcadores_b44.py` **24/24**, `prueba_smoke.py` OK. `python -m py_compile`
OK. `git diff --check` OK.

---

**Commit anterior — Mensaje:** Reutilizar metadata de videos sin cambios en reescaneos

**Etapa:** B4.5 — Rendimiento de carga inicial, Etapa 3 (rama `beta4`):
- `escanear_videos.py` — migración aditiva e idempotente **`videos.mtime_ns INTEGER NULL`**
  (`COLUMNAS_EXTRA` + helper `_asegurar_columnas_videos` reutilizado por `conectar_bd`,
  `guardar_video` y `guardar_videos`; `BEGIN` explícito en el guardado para que el `ALTER` sea
  transaccional); `obtener_tamanos_archivos` obtiene tamaño+`mtime_ns` con **un `os.stat` por
  archivo**; `combinar_registros_con_tamanos` propaga `mtime_ns`; `_upsert_video` lo persiste;
  helpers de clasificación `_normalizar_ruta_absoluta`, `_metadata_ffprobe_utilizable` y
  `_metadata_reutilizable` (criterio ruta+tamaño+`mtime_ns`); `listar_registros_por_nombres`
  (consulta por lote por `nombre`, una SELECT).
- `tareas_videos.py` — `TareaFFprobe(rutas, nombres=None, stats=None, ruta_db=None)`: consulta los
  registros previos por lote, clasifica y ejecuta FFprobe **solo** para los videos
  nuevos/cambiados/sin fingerprint/metadata inválida; el resultado devuelve metadata completa
  para todos (reutilizada o nueva) con el mismo formato.
- `visor_videos.py` — `_iniciar_ffprobe` pasa `nombres`, `stats` (`resultado_tamanos`) y `ruta_db`
  a `TareaFFprobe` (sin SQLite en la UI).
- `prueba_reutilizacion_metadata_b453.py` — **nueva**: 20 pruebas (migración antigua e
  idempotente; NULL → FFprobe; idéntico → 0 FFprobe; tamaño/mtime/ambos/ruta/nuevo/metadata
  inválida → FFprobe; metadata reutilizada exacta; persistir `mtime_ns`; video_id y marcadores
  preservados; lote mixto 10 → 3 FFprobe; lote 121 → 0 FFprobe; consulta por lote = 1 SELECT;
  un stat por archivo; normalización de ruta).
- Suites adaptadas al esquema nuevo (`mtime_ns`): `prueba_guardar.py`, `prueba_guardar_videos.py`
  (SELECT con columnas explícitas), `prueba_aplicar_incorporaciones.py`,
  `prueba_sincronizacion_asincrona.py` (`_crear_bd` con `mtime_ns`).

**Medición (PC de desarrollo, dataset temporal de 121 videos, caché caliente):** reescaneo con
**121 FFprobe → 0**; backend **~4.9 s → ~0.1–0.5 s** (referencia, no garantía universal).
Verificación empírica con 10 copias físicas independientes (10 inodos, sin hardlinks):
**10 → 0 → 1 → 0** (tercera pasada: 1 FFprobe, 9 metadata reutilizadas y 1 reprocesada;
cuarta pasada: 0). La UI de tarjetas no se optimizó en esta etapa.

**Pruebas superadas:** `prueba_reutilizacion_metadata_b453.py` **20/20**. Regresiones en verde
(ejecutadas en el cierre): `prueba_optimizacion_ffprobe_b452.py` **14/14**,
`prueba_escaneo_guardado.py` **24/24**, `prueba_guardar_videos.py` **34/34**, `prueba_guardar.py`
**19/19**, `prueba_recarga_catalogo.py` **20/20**, `prueba_escaneo_interfaz.py` **36/36**,
`prueba_plan_sincronizacion.py` **12/12**, `prueba_sincronizacion_asincrona.py` **27/27**,
`prueba_previews_progresivas.py` **16/16**, `prueba_tamano_archivo.py` **15/15**,
`prueba_detectar.py` **15/15**, `prueba_lectura.py` **15/15**, `prueba_lectura_paginada.py`
**32/32**, `prueba_interfaz_asincrona.py` **29/29**, `prueba_seleccion_carpeta.py` **26/26**,
`prueba_reproduccion_marcadores_b44.py` **24/24**, `prueba_marcadores_b42.py` **17/17**,
`prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check` OK.

---

**Commit anterior — Mensaje:** Eliminar FFprobe redundante al generar miniaturas y previews

**Etapa:** B4.5 — Rendimiento de carga inicial, Etapa 2 (rama `beta4`):
- `escanear_videos.py` — `_duracion_utilizable` (número real finito > 0; rechaza `None`, bool, no
  numérico, 0, negativos, NaN/infinito), `_duracion_de_duraciones` (busca por ruta o nombre),
  `generar_miniatura`/`generar_preview` con `duracion_segundos=None` (válida → sin FFprobe
  interno, mismo cálculo temporal y FFmpeg; inválida → fallback FFprobe anterior),
  `asegurar_miniatura`/`asegurar_miniaturas`/`generar_previews_faltantes` con propagación de
  duraciones.
- `tareas_videos.py` — `TareaMiniaturas(videos, carpeta, duraciones=None)` y
  `TareaPreviewsProgresivas(videos, carpeta, duraciones=None)`.
- `visor_videos.py` — `_iniciar_miniaturas` pasa el mapa ruta→duración construido desde
  `self.resultado_ffprobe` (`_duraciones_desde_ffprobe`); `_siguiente_lote_previews` pasa las
  duraciones de las tarjetas (`Tarjeta._duracion`) al lote.
- `prueba_optimizacion_ffprobe_b452.py` — **nueva**: 14 pruebas (miniatura/preview con duración
  conocida sin FFprobe interno; fallback sin duración; duración inválida; tiempos equivalentes;
  pipelines miniaturas y previews con 0 FFprobe internos; cache existente sin procesos; callers
  antiguos sin parámetro).
- Suites adaptadas a la firma nueva (mocks): `prueba_previews_progresivas.py`,
  `prueba_previews_multicarpeta.py`, `prueba_previews_automaticas.py`, `prueba_escaneo_guardado.py`.

**Medición (PC de desarrollo, dataset temporal de 121 videos, caché fría):** FFprobe internos
**484 → 0** (121 miniaturas + 363 previews), mismos 484 FFmpeg; total backend **~55.6 s →
~37.1 s**; miniaturas **12.3 → 7.9 s**; previews **38.6 → 24.8 s**. Verificación funcional con
la app real: carga inicial ~0.83 s, previews generadas progresivamente con **ffprobe interno = 0**
y UI fluida.

**Pruebas superadas:** `prueba_optimizacion_ffprobe_b452.py` **14/14**. Regresiones en verde
(ejecutadas en el cierre): `prueba_previews_progresivas.py` **16/16**, `prueba_tamano_miniaturas.py`
**32/32**, `prueba_recarga_catalogo.py` **20/20**, `prueba_pagina_siguiente.py` **20/20**,
`prueba_escaneo_interfaz.py` **36/36**, `prueba_escaneo_guardado.py` **24/24**,
`prueba_previews_multicarpeta.py` **5/5**, `prueba_previews_automaticas.py` **22/22**,
`prueba_reproduccion_marcadores_b44.py` **24/24**, `prueba_smoke.py` OK. `python -m py_compile`
OK. `git diff --check` OK.

---

**Commit anterior — Mensaje:** Integrar reproduccion de marcadores mediante playlists VLC

**Etapa:** B4.4 — Reproducción de marcadores en VLC (Etapa 1: validación de playlist; Etapa 2:
integración mínima) (rama `beta4`):
- `escanear_videos.py` — **`listar_marcadores_de(video_ids)`** (B4.4): lee los marcadores
  persistidos de varios `video_id` (tuplas `(id, video_id, tiempo)`), agrupados en el orden
  recibido y ordenados cronológicamente dentro de cada video; validación previa y conexión
  propia por operación, reutilizando el repositorio de B4.2.
- `tareas_videos.py` — **`TareaListarMarcadoresVarios`** (B4.4): lectura asíncrona de los
  marcadores de varios videos.
- `playlist_vlc.py` — **nuevo** (B4.4): módulo de servicio que aísla de la interfaz la
  integración con VLC: `localizar_vlc()` (ProgramFiles → ProgramFiles(x86) → `shutil.which`),
  `formatear_tiempo_vlc` (precisión decimal), `formatear_titulo_marcador` (H:MM:SS.mmm),
  `limpiar_playlists_anteriores` (solo `visor_marcadores_*.m3u`, un solo directorio, bloqueos
  ignorados), `generar_m3u` (UTF-8 explícito; limpia primero, escribe después) y
  `abrir_playlist_en_vlc` (un único `Popen`). Sin HTTP, sin libVLC, sin automatización de
  botones, sin loop automático.
- `visor_videos.py` — acción **"Reproducir marcadores en VLC"** en el menú contextual
  (habilitada con selección): recolecta los videos seleccionados en **orden visible del
  catálogo** (patrón de `_copiar_rutas_seleccionados`), obtiene sus marcadores vía
  `gestor_reproduccion` (nuevo gestor dedicado), diálogo Omitir/Desde el inicio/Cancelar para
  videos sin marcadores (sin persistir), omite archivos inexistentes con aviso (sin borrar
  marcadores/registros), genera la playlist temporal y abre VLC una única vez.
- `prueba_reproduccion_marcadores_b44.py` — **nueva**: 24 pruebas (orden visible, orden
  cronológico, generación M3U, tiempos decimales, mismo archivo múltiples entradas, mezcla de
  videos, decisiones Omitir/Desde inicio/Cancelar, todos sin marcadores, playlist vacía, VLC no
  encontrado, archivo inexistente, no modificación de marcadores, lanzamiento único, limpieza
  de playlists propias, no borrar archivos ajenos, eliminación bloqueada, rutas con espacios y
  rutas Unicode).

**Validación física (PC de desarrollo, VLC 3.0.23, videos reales de `Videos de muestra`):**
primera reproducción con A (1.5 / 17.83 / 30 s) + B (2 s): VLC abrió una sola vez, primer
marcador en ~1.5 s, Siguiente recorrió A→A→A→B, Anterior correcto, play/pause y fullscreen
normales; segunda reproducción con A + video sin marcadores (Desde el inicio): diálogo con las
3 opciones y comportamiento correcto. Playlists temporales: al final solo queda la última
(`visor_marcadores_*.m3u`); la anterior y un residuo previo fueron eliminados por la limpieza.
Se observó que la configuración actual de VLC abre una instancia por ejecución (sin impedir la
reproducción ni la limpieza; no corregido en esta etapa).

**Pruebas superadas:** `prueba_reproduccion_marcadores_b44.py` **24/24**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_b433.py` **22/22**, `prueba_marcadores_b42.py`
**17/17**, `prueba_recarga_catalogo.py` **20/20**, `prueba_pagina_siguiente.py` **20/20**,
`prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check` OK.

---

**Commit anterior — Mensaje:** Agregar densidad manual y priorizar la vista dinamica temporal

**Etapa:** B4.3.3 — Ajustes de interacción y densidad manual (rama `beta4`):
- `tareas_videos.py` — **`TareaExploracionDensa` con objetivo manual**: nuevo parámetro
  `objetivo_manual` (None = Auto). `_trabajo()` calcula el objetivo total como
  `objetivo_manual` si es positivo, o `objetivo_total_densidad(duración)` en Auto; la **fase
  rápida** siempre son los 15 prioritarios y la **fase secundaria** completa hasta ese total.
  En cada fase se construye explícitamente el **conjunto permitido**
  `tiempos_objetivo(duración, cantidad_actual)` y la emisión (`resultado_parcial`) y la cola
  final **solo decodifican/emiten ese subconjunto**: la caché en disco puede contener un
  **superset** (densidades manuales previas) y la tarea decide qué subconjunto utiliza (RAM/UI
  limitada al conjunto objetivo actual; los extras permanecen en disco sin regenerar ni
  borrar). `al_progreso` lista los existentes de la versión e intersecta con `permitidos`.
- `visor_videos.py` — **prioridad visual dinámica** (Mejora A): `_al_instante_exploracion`
  hace `raise_()` a la preview dinámica (queda por encima de las miniaturas fijas de
  marcadores durante el hover) y `eventFilter` sobre el franja baja la preview (`lower()`) al
  salir de la superficie; tiempos/ids de marcadores intactos. **Densidad manual** (Mejora B):
  constante `DENSIDADES_DISPONIBLES = (Auto, 15, 30, 60, 120, 200)`, `QComboBox` "Densidad:" en
  la tarjeta expandida, señal `densidad_cambiada`, `aplicar_densidad(valor)` filtra los densos
  de RAM al conjunto objetivo de la cantidad elegida, y `_procesar_siguiente_exploracion`
  pasa `objetivo_manual` a la tarea (solo cuando hay valor manual). El valor es por
  tarjeta/sesión.
- `prueba_exploracion_b433.py` — **nueva**: 22 pruebas (z-order 1/varios marcadores y leave;
  eliminación clic derecho; Auto/manual en videos cortos 30 s y 2 min; 56 min + 120; incremento
  15→60 y 60→120; disminución 120→30 sin borrar disco ni regenerar; volver a Auto sin borrar
  extras; máximo un FFmpeg; mouseMove solo RAM; marcadores tiempo/id intactos; caché superset
  120→30, 120→60, 120→Auto; fase rápida limitada a 15 con superset).

**Validación visual (PC de desarrollo, app real + FFmpeg real, video de 30 s, caché temporal):**
Auto → 15; marcador en 15 s: hover con dinámica arriba y al salir la fija vuelve arriba;
Auto→60 → 60 densos con scrub fluido; 60→120 → 120 densos; 120→Auto → RAM filtrada a 15 sin
errores y marcador con tiempo 15.0 intacto. B4.3 quedó validada satisfactoriamente también en
la **notebook objetivo**.

**Pruebas superadas:** `prueba_exploracion_b433.py` **22/22**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_densidad_b432.py` **12/12**,
`prueba_exploracion_b432.py` **20/20**, `prueba_exploracion_cache_b431.py` **29/29**,
`prueba_exploracion_b41.py` **28/28**, `prueba_marcadores_b42.py` **17/17**,
`prueba_previews_progresivas.py` **16/16**, `prueba_tamano_miniaturas.py` **32/32**,
`prueba_recarga_catalogo.py` **20/20**, `prueba_pagina_siguiente.py` **20/20**,
`prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check` OK.
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
- **B4.3.2 — Cobertura rápida asíncrona integrada con la UI (Etapa 1).** Cuarta etapa del ciclo
  Beta 4 (rama `beta4`), segunda subetapa de **B4.3 — Caché densa de exploración temporal**.
  La tarjeta consume el motor de B4.3.1 con una **tarea asíncrona dedicada**
  (`TareaExploracionDensa` en `tareas_videos.py`) que genera los **`FOTOGRAMAS_INICIALES = 15`**
  provisionales y emite **resultados parciales progresivos** (`QImage` decodificada en el
  worker; la conversión final a `QPixmap` ocurre en la GUI). Mientras no hay caché la superficie
  temporal conserva el **fallback a las previews normales** y la mejora es **progresiva**.
  `mouseMove` selecciona **exclusivamente en RAM** (cero FFmpeg, cero disco); la imagen mostrada
  es la **más cercana** entre la preview normal y la densa (la preview normal gana el empate).
  **Cancelación cooperativa** al cambiar de video, **aislamiento A→B** (cada tarjeta usa su
  caché), **colapso que libera las referencias densas de RAM** y **reexpansión que reutiliza la
  caché** (sin regenerar). Los **marcadores** conservan su tiempo/id y pueden mejorar
  visualmente al llegar fotogramas densos. **Validación visual manual A–G aprobada por Marcos**
  en el PC de desarrollo y validada en la **notebook objetivo** con un video real de ~56 min.
- **B4.3.2 — Etapa 2: Densidad secundaria adaptativa.** Quinta etapa del ciclo Beta 4 (rama
  `beta4`), tercera subetapa de **B4.3 — Caché densa de exploración temporal**. Tras el
  **benchmark de estrategias** sobre un video de 56 min, por **decisión de producto** se adoptó
  la **generación individual y secuencial: un FFmpeg por objetivo, sin batch, sin paralelismo**.
  `exploracion_cache.py` centraliza los parámetros **provisionales**
  (`PASO_SEGUNDOS_DENSIDAD = 30.0`, `MINIMO_FOTOGRAMAS_DENSIDAD = 15`,
  `MAXIMO_FOTOGRAMAS_DENSIDAD = 200`, `FOTOGRAMAS_INICIALES = 15`) y `objetivo_total_densidad`
  = `clamp(max(15, ceil(d/30)), 15, 200)`. `TareaExploracionDensa._trabajo()` genera en **dos
  fases secuenciales**: la **fase rápida** (los 15 prioritarios, Etapa 1 intacta) y solo después,
  sin cancelarse, la **fase secundaria** que reutiliza lo existente y completa únicamente los
  faltantes hasta el objetivo de densidad; ambas fases emiten `resultado_parcial` progresivo sin
  duplicados. **Verificado en PC de desarrollo** (app real + FFmpeg real, video ~56 min): primer
  fotograma prioritario ≈0.10 s, 15 prioritarios ≈1.13 s, primer secundario ≈1.21 s (después de
  la fase rápida), total 112 ≈8.39 s, reexpansión ≈0.08 s sin regenerar, scrub fluido desde RAM.
  Los parámetros **siguen siendo provisionales** (no congelados) y **no hay configuración
  visible**; la Etapa 2 recibió su comprobación y **B4.3 quedó validada satisfactoriamente en la
  notebook objetivo**.
- **B4.3.3 — Ajustes de interacción y densidad manual.** Sexta etapa del ciclo Beta 4 (rama
  `beta4`), cuarta subetapa de **B4.3 — Caché densa de exploración temporal**. (A) **Prioridad
  visual dinámica**: durante el hover la preview dinámica queda **por encima** de las
  miniaturas fijas de marcadores (`raise_()` en `_al_instante_exploracion`; `lower()` al salir
  de la superficie vía `eventFilter` del franja); los tiempos/ids de marcadores no cambian y la
  eliminación por clic derecho sigue funcionando. (B) **Densidad manual**: `QComboBox`
  `Auto | 15 | 30 | 60 | 120 | 200` en la tarjeta expandida; los valores manuales son el
  **total objetivo independiente de la duración** (30 s → Auto 15, manual 60 → 60, manual 120 →
  120); siempre los **15 prioritarios primero**; **aumentar** reutiliza lo existente (15→60
  reutiliza 15 y genera 45; 60→120 reutiliza 60 y genera 60); **disminuir** no borra disco ni
  regenera (la RAM se limita al conjunto objetivo `tiempos_objetivo(duración, cantidad_actual)`
  y la caché puede contener un **superset** cuyo subconjunto decide la tarea — emite/decodifica
  solo el permitido); **volver a Auto** recalcula el objetivo automático y conserva los extras
  de disco. El valor es **por tarjeta/sesión** (se conserva en colapso/reexpansión; vuelve a
  Auto si se reconstruye por recarga), **sin SQLite ni persistencia en `configuracion.json`**.
  Generación individual/secuencial, un FFmpeg activo, mouseMove solo RAM. Pruebas:
  `prueba_exploracion_b433.py` **22/22**.

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
  funciona correctamente. **Resuelta en la corrección previa al cierre de
  B4.12**: la comparación de filas preexistentes se hizo robusta al esquema
  por nombre de columna (vigente con `mtime_ns` y `tamano_bytes`); suite 15/15.
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
  archivo en el arranque. **Resuelta en la corrección previa al cierre de B4.12**:
  el contrato del test pasó a "sin carpeta guardada" (el archivo puede existir por
  el default, pero no debe contener `CLAVE_CARPETA`); suite 20/20.
- **`prueba_eliminar_candidatos.py` T02** — falla **preexistente** (verificada en el
  HEAD base limpio `507ec81` durante el cierre de B4.5): es una verificación AST de
  estructura (`eliminar_candidatos` definida solo en `escanear_videos`, sin estar
  definida ni importada en `tareas_videos`/`visor_videos`, y sin identificadores
  prohibidos) cuyo contrato no coincide con el estado actual del código. **Resuelta
  en la corrección previa al cierre de B4.12**: la regla AST quedó precisa
  excluyendo las tareas legítimas de marcadores (`TareaEliminarMarcador`, B4.2);
  suite 16/16.

## Próxima fase

**Beta 5 — planificación cerrada (B5.0, rama `beta5`, 2026-08-13).** La **Beta 4 quedó CERRADA y
aprobada** (cierre formal 2026-08-10) y se inició la **planificación y congelamiento del alcance
inicial de la Beta 5** (etapa **B5.0**, exclusivamente documental): rama `beta5` creada desde el
cierre de la Beta 4 (`v4.0-beta`, `5ed40fa1ac4d257f29878a137b5a4240e36716ac`). El alcance inicial
queda congelado con **cuatro bloques** — **A** (entrada temporal a VLC desde preview/franja),
**B** (segmentos A–B, con la decisión **marcador ≠ segmento**), **C** (reproducción de segmento
simple y en bucle) y **D** (secuencia automática de segmentos) — y un plan de etapas
**B5.1–B5.9** (ver `ROADMAP.md`, sección "Beta 5"). La investigación técnica validó en VLC 3.0.23
`start-time`, `stop-time` (CLI y M3U, con decimales), bucle `start-time + stop-time + --loop` y la
secuencia automática por playlist. **Sin implementación funcional todavía**; estos cuatro bloques
no constituyen necesariamente el alcance definitivo (tras completarlos se auditará y se decidirá
cerrar o ampliar la Beta 5).

Los pendientes técnicos conocidos quedan registrados como **deuda no bloqueante** de Beta 4 (no
como pendientes de la fase): **RAM/retención de pixmaps originales** (~+690 MB por previews
cargadas); `_construir_exploracion` crea widgets en tarjetas colapsadas; `_reemplazar_tarjetas`
reconstruye tarjetas idénticas; `miniatura_principal` hace un `os.listdir` por tarjeta; previews
normales reutilizables por existencia del archivo (sin validación por cambio del video);
flakiness intermitente de teardown de `prueba_exploracion_densidad_b432.py`; flakiness ambiental
del portapapeles bajo tooling; **riesgo obligatorio para una futura distribución pública**: el
desinstalador actual (`[UninstallDelete]`) puede eliminar datos de usuario (`biblioteca.db`,
`configuracion.json`, `miniaturas/`, marcadores y cachés) — no bloquea el cierre técnico de Beta 4,
pero debe resolverse antes de una release destinada a conservar datos reales. Líneas futuras no
iniciadas (fuera de Beta 4 y del alcance inicial de Beta 5): **selección A/B**, **loops**,
**selección de fragmentos**, **corte/unión**, **detección de archivos movidos/renombrados** con
**reasociación de marcadores huérfanos**, evoluciones de reproducción indicadas en `ROADMAP.md` y
**batch**.

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `METODOLOGIA_DESARROLLO.md` — protocolo detallado de desarrollo y auditoría
  (operación del Bridge, estado, evidencia, autorizaciones).
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
