# VISOR DE VIDEOS

> **DOCUMENTO HISTÓRICO / DE REFERENCIA.**
> La autoridad vigente del estado actual es `STATUS.md`.
> Este documento conserva el snapshot acumulado Beta 7 como referencia histórica; la identidad vigente es `PROJECT.md` y la arquitectura es `ARCHITECTURE.md`.


## Fase actual ÔÇö Beta 7 (cerrada y publicada en B7.13)

La **Beta 7 ÔÇö "Organizaci├│n y operaciones de archivos"** est├í **cerrada y publicada** en **`B7.13`** sobre la rama `beta7` (**commit oficial de cierre funcional** `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` `B7 Cerrar Beta 7 B7.13`; **B7.0ÔÇôB7.13 completas y auditadas funcionalmente**; **identidad `Beta 7 - B7.13`**; **rama `beta7` publicada en `origin/beta7` y puede contener reconciliaciones documentales posteriores al tag**, **tag anotado `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3`**; **repositorio GitHub actualmente PUBLIC**; **GitHub Release `v7.0-beta` prerelease publicada** ÔÇö `Visor de Videos Beta 7 - B7.13` ÔÇö sin instalador p├║blico Beta 7; **validaci├│n espec├¡fica del instalador Beta 7 permanece PENDIENTE**). Beta 6 permanece **cerrada y publicada** sobre la rama `beta6` (commit `7d85e94bb8b617209a155e5b1086d1d38f4784f8`; **B6.1ÔÇôB6.12 completas**; **identidad `Beta 6 - B6.12`**; **packaging reproducible y validaci├│n real del instalador aprobada**; **tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios**)
(punto de partida: cierre de la Beta 5). Objetivo de producto: **cerrar el ciclo
iniciado en Beta 5** ÔÇö localizar las partes ├║tiles de los videos, clasificarlas y
convertirlas en material definitivo, conservando calidad, trazabilidad e
integridad de datos.

> **Estado de cierre publicado:** **Beta 7 funcionalmente cerrada en B7.13; identidad Beta 7 - B7.13; commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709`; tag anotado `v7.0-beta` publicado y resolviendo permanentemente a ese commit; rama `beta7` publicada en `origin/beta7` y puede contener reconciliaciones documentales posteriores al tag; repositorio GitHub actualmente PUBLIC; GitHub Release `v7.0-beta` prerelease publicada (sin instalador p├║blico Beta 7); validaci├│n espec├¡fica del instalador Beta 7 PENDIENTE.**

> **Estado publicado previo:** **Beta 6 cerrada y publicada; B6.1ÔÇôB6.12 completas; identidad Beta 6 - B6.12; packaging reproducible y validaci├│n real del instalador aprobada; tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios.**

Estado actual:

- **Rama de cierre/desarrollo:** `beta7` (base exacta `7d85e94bb8b617209a155e5b1086d1d38f4784f8`; commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` `B7 Cerrar Beta 7 B7.13`; tag `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3`; rama `beta7` publicada en `origin/beta7` y puede contener commits documentales posteriores al tag; repositorio GitHub PUBLIC; GitHub Release `v7.0-beta` prerelease publicada sin binarios; Beta 6 cerrada y publicada en `beta6`, ver arriba).
- **Beta 7 ÔÇö cerrada y publicada en B7.13.** **Estado post-publicaci├│n:** commit oficial `f9976d3` (tag `v7.0-beta` ÔåÆ `f9976d3`) publicado; al momento de la publicaci├│n `origin/beta7` resolv├¡a a `f9976d3` y la rama puede avanzar con reconciliaciones documentales posteriores; repositorio PUBLIC, GitHub Release `v7.0-beta` prerelease publicada sin binarios; **validaci├│n espec├¡fica del instalador Beta 7 PENDIENTE** (`python prueba_instalador.py` sobre `Distribucion\Beta7\VisorVideos_Beta7_Setup.exe`).
- **B6.1 ÔÇö Preservaci├│n de datos del usuario al desinstalar.** **Completada.**
- **Infraestructura y metodolog├¡a del Bridge** ya **incorporadas** y versionadas
  (commits `dd17c72` y `7a0feae`).
- **B6.2 ÔÇö Ordenamiento configurable del cat├ílogo.** **Completada, validada y
  publicada en `beta6`** (commit t├®cnico
  `52eddb8d4633282578638ba18ec2acdb2e00bf47`; commit documental posterior
  `4fe46df7bfd7ed3d2d8b4408a8b3e410e43ed258`). **Ambos commits est├ín
  publicados en `beta6`** y la publicaci├│n fue verificada con alineaci├│n
  local/remota.
- **B6.3 ÔÇö Clasificaci├│n visual de marcadores y segmentos.** **T├®cnicamente
   completada, committeada y publicada en `beta6`** (2026-08-20; commit
   `c28ccf6942fd0b52fc1c84090f0a6df083b26488` en `origin/beta6`): paleta cerrada de 6 colores; persistencia SQLite
   aditiva e idempotente (`color TEXT NULL` en `marcadores_video` y
   `segmentos_video`, `NULL` conserva los colores hist├│ricos: marcador rojo,
   segmento azul); asignar/quitar color por men├║ contextual y selector por
   tarjeta; nombres globales personalizables sin cambiar las claves; render
   visual de marcas y bandas; suite `prueba_color_b63.py` **21/21** y
   regresiones/smoke en verde (ver `HISTORIAL_PROYECTO.md` ##107 y `ROADMAP.md`).
- **B6.4 ÔÇö Marcadores y segmentos visibles en tarjetas colapsadas.** **Completada y publicada en `beta6`** (2026-08-20; commit `74bb4590fa59c506fba2e00d070e530b0b8cf34f` en `origin/beta6`): representaci├│n resumida en tarjetas colapsadas con posici├│n proporcional y colores B6.3; suite `prueba_resumen_colapsado_b64.py` **8/8** (ver `HISTORIAL_PROYECTO.md` ##108 y `ROADMAP.md`).
- **B6.5 ÔÇö Filtros y localizaci├│n del material marcado.** **Completada y validada visualmente por Marcos; cerrada en commit previo `a837fd2`** (filtros estructurados del cat├ílogo a nivel SQLite paginado/background con whitelist cerrada ÔÇö `todos`, `con_marcadores`, `con_segmentos`, `marcador:<color>`, `segmento:<color>`, `Sin clasificar` ÔÇö combinable con b├║squeda por texto, paginaci├│n, orden B6.2 y `Cargar m├ís`; combo `Mostrar:`; suite `prueba_filtro_b65.py` **24/24** y regresiones `prueba_color_b63` **21/21**, `prueba_ordenamiento_b62` **18/18**, `prueba_resumen_colapsado_b64` **8/8** en verde; ver `HISTORIAL_PROYECTO.md` ##109 y `ROADMAP.md`).
- **B6.6 ÔÇö Investigaci├│n y contrato del motor de exportaci├│n.** **Completada (2026-08-20).** Investigaci├│n FFmpeg y contrato t├®cnico para B6.7: recodificaci├│n CPU precisa (no stream-copy) con tolerancias, mapeo expl├¡cito, temporal at├│mico y verificaci├│n FFprobe (ver `ROADMAP.md` B6.6 y `HISTORIAL_PROYECTO.md` ##110).
- **B6.7 ÔÇö Extracci├│n segura de un segmento.** **Completada, implementada, probada y validada manualmente; cerrada en commit previo `bec5e83`** (servicio `exportar_segmento.py` con operaci├│n at├│mica, doble verificaci├│n y cancelaci├│n real; `TareaExportarSegmento`; UI men├║ "Exportar segmentoÔÇª", di├ílogo de destino y bot├│n "Cancelar exportaci├│n"; suite `prueba_exportacion_b67.py` **21/21** y regresiones B6.3ÔÇôB6.5 en verde; **evidencia humana: Marcos confirm├│ que el flujo visual y funcional de exportaci├│n de un segmento funciona correctamente y que el archivo resultante se reproduce y corresponde al tramo seleccionado**; ver `HISTORIAL_PROYECTO.md` ##110 y `ROADMAP.md` B6.7).
- **B6.8 ÔÇö Motor general y reutilizable de nombres.** **Completada, implementada, probada y validada manualmente; cerrada en commit previo `f643c22`** (componente puro `nombres.py` separado de UI/SQLite/FFmpeg/PySide6 con tokens cerrados `{original}/{numero}/{fecha}/{texto}/{inicio}/{fin}`, sanitizaci├│n Windows, extensi├│n controlada aparte y resoluci├│n determinista de colisiones FS/intra-lote sin sobrescritura `_001`ÔÇª; integraci├│n B6.7 delega sugerencia/extensi├│n al motor; suite `prueba_nombres_b68.py` **25/25** y regresiones `prueba_exportacion_b67.py` **21/21**, `prueba_filtro_b65.py` **24/24** en verde; **evidencia humana: Marcos complet├│ la validaci├│n manual real ÔÇö al intentar guardar con extensi├│n `.avi` la aplicaci├│n inform├│ correctamente que la extensi├│n no era v├ílida y cancel├│ la operaci├│n**; ver `HISTORIAL_PROYECTO.md` ##111 y `ROADMAP.md` B6.8).
- **B6.9 ÔÇö Exportaci├│n m├║ltiple de segmentos separados.** **Completada, implementada, probada y validada manualmente; cerrada en commit previo `1bfeda2` (2026-08-20).** Selecci├│n expl├¡cita y por clasificaci├│n con whitelist (`todos`/por color/`Sin clasificar`), motor B6.8, progreso por lote, resultados parciales seguros; servicio `exportar_lote_segmentos` + `TareaExportarLoteSegmentos` (un FFmpeg secuencial), di├ílogo `DialogoExportarLote` con preparaci├│n async (`TareaListarSegmentosVarios`) sin SQLite/FFmpeg en UI; suite `prueba_exportacion_lote_b69.py` **30/30** y regresiones B6.7 **21/21**, B6.8 **25/25** en verde; ver `HISTORIAL_PROYECTO.md` B6.9 y `ROADMAP.md` B6.9.
- **B6.10 ÔÇö Uni├│n de varios segmentos del mismo original.** **Completada, implementada, probada y validada manualmente; cerrada en commit previo `a117611` (2026-08-21).** Servicio `exportar_secuencia.py` con **v├¡a principal recodificada CPU `trim`/`atrim`/`setpts`+`concat` (`libx264 veryfast crf18 yuv420p` + `aac 128k`, `+faststart` en MP4) para precisi├│n independiente de keyframes** y **fallback por extracci├│n precisa de cada segmento + `concat` demuxer para subt├¡tulos compatibles (`mov_text` MP4, `srt` MKV, mapeo expl├¡cito `0:v/0:a/0:s`)**; **rechazo claro de MKV/SubRip no validado**; `TareaExportarSecuencia` fuera de UI con cancelaci├│n real; UI `DialogoExportarSecuencia` reutilizando selecci├│n B6.9 con orden expl├¡cito, naming B6.8 y discriminaci├│n `_export_tipo`; suites `prueba_exportacion_secuencia_b610.py` **15/15**, `prueba_ui_export_fix_b610.py` **10/10** y regresiones B6.7 **21/21**, B6.8 **25/25**, B6.9 **30/30** en verde; **evidencia humana: Marcos valid├│ el flujo completo ÔÇö uni├│n de 2 segmentos del mismo video con archivo derivado verificado y reproducido correctamente**; ver `HISTORIAL_PROYECTO.md` ##112 y `ROADMAP.md` B6.10.
- **B6.11 ÔÇö Incorporaci├│n al cat├ílogo y trazabilidad de videos derivados.** **Completada, auditada y cerrada en commit previo `cc71224` (2026-08-21, rama `beta6`).** **Contrato demostrado:** alta incremental aun fuera de ra├¡z sin reescaneo; trazabilidad originalÔåÆderivado y segmentos ordenados (`videos_derivados` + `videos_derivados_segmentos`); snapshot hist├│rico sin `CASCADE` destructivo (persiste tras borrar original/derivado de `videos`); bloqueo derivado-de-derivado; fallo de catalogaci├│n conserva archivo; validaci├│n estricta de secuencia (longitud y correspondencia `segmentos` vs `segmentos_info_orden`/`orden`); rechazo de nombre duplicado `UNIQUE(nombre)` sin reutilizaci├│n silenciosa; tablas/APIs `incorporar_video_derivado_al_catalogo`/`obtener_derivacion_por_derivado`/`listar_derivaciones_por_original`/`es_video_derivado`; suite `prueba_derivados_b611.py` **15/15** y regresiones B6.7/B6.9/B6.10 en verde; ver `HISTORIAL_PROYECTO.md` ##113 y `ROADMAP.md` B6.11.
- **B6.12 ÔÇö Integraci├│n, robustez y cierre funcional.** **Cerrada en rama `beta6` (commit `7d85e94bb8b617209a155e5b1086d1d38f4784f8`; B6.1ÔÇôB6.12 completas; packaging reproducible y validaci├│n real del instalador aprobada ÔÇöinstalaci├│n/desinstalaci├│n/reinstalaci├│n aislada preservando `biblioteca.db`/`configuracion.json`/`miniaturas`ÔÇö; tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios).** **Validaci├│n integrada 14/14, reescaneo 3/3, B6.11 15/15 de control, FFmpeg 8.1.1/FFprobe 8.1.1 reales, `PRAGMA integrity_check=ok` y validaci├│n humana de persistencia tras reinicio+reescaneo.** Suites verificadas en esta entrega: `prueba_integracion_b612.py` **14/14** (filtro/orden/paginaci├│n + resumen + export/lote/secuencia + derivados + migraciones), `prueba_reescaneo_preserva_metadatos_b612.py` **3/3** (base/modificado/plan completo + `integrity_check=ok`) y `prueba_derivados_b611.py` **15/15** (control B6.11) en verde; `py_compile` OK; `git diff --check` limpio; artefacto humano `videos_prueba/output_video_MMH3Tools_2_chunks_prueba_00001__segmento_0.33-1.25.mp4` preservado durante la validaci├│n B6.12, no versionado y actualmente no presente en el working tree. **Observaci├│n no bloqueante:** incidente aislado anterior no reproducido (reescaneo preserva IDs/marcadores/segmentos y colores en los 3 escenarios; ver `HISTORIAL_PROYECTO.md` ##114). **Beta 6 cerrada y publicada; B6.1-B6.12 completas; identidad `Beta 6 - B6.12`; packaging reproducible y validaci├│n real del instalador aprobada; tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios.** Ver `HISTORIAL_PROYECTO.md` ##115 y `ROADMAP.md` B6.12.
- El **alcance completo** de Beta 6 (B6.1ÔÇôB6.12) y su l├¡mite expl├¡cito (no se
  elimina ni reemplaza autom├íticamente el video original) est├ín en
  `ROADMAP.md`. **Beta 7 ÔÇö "Organizaci├│n y operaciones de archivos"** queda
  **diferida** durante Beta 6 (ver `ROADMAP.md`) y su apertura t├®cnica **B7.0** se registra como rama local `beta7` exactamente desde `7d85e94bb8b617209a155e5b1086d1d38f4784f8` (identidad de desarrollo `Beta 7 - B7.0`; sin B7.1).

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase anterior (contexto hist├│rico):** la **Beta 4 est├í CERRADA y aprobada** (cierre formal
2026-08-10): build final **`Beta 4 ÔÇö B4.12`** (commit t├®cnico
`198cdf533986b88c6e25dc0087722cf2b86e5f99`; instalador
`VisorVideos_Beta4_Setup.exe`, SHA-256
`730B4DAB1CD2F1F5CFDD184D2DC6FE80CF0481B8754080F0FF10CF991F89431F`), validada en la
notebook objetivo (B4.11: validaci├│n manual amplia; B4.12: validaci├│n final
corta) y con la suite integral posterior a las correcciones en **87 suites /
1570/1570 pruebas funcionales OK / 0 FAIL funcional**. La **Beta 3** qued├│
finalizada y congelada en su momento con su instalador
(`VisorVideos_Beta3_Setup.exe`); la **Beta 2** permanece como la ├║ltima versi├│n
estable publicada. El ciclo Beta 4 se desarroll├│ sobre la **rama `beta4`**
(punto de partida: cierre de la Beta 3, commit `4408d542`). **Beta 5 CERRADA
internamente (cierre formal 2026-08-15, rama `beta5`):** commit t├®cnico principal
`969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
`VisorVideos_Beta5_ValidacionFinal_Setup.exe` (SHA-256
`F40ACF41FE7D3931FF042AC718B6D2805460AE380092E9E782A918C42A650133`), aprobado en la
notebook objetivo; identidad definitiva **`Beta 5 ÔÇö B5.0`**. Sin distribuci├│n
p├║blica, sin merge a `main`, sin GitHub Release (ver "Pr├│xima fase").
La primera etapa, **B4.1 ÔÇö Exploraci├│n
temporal interactiva y marcadores visuales**, qued├│ **aprobada e incorporada**:
cada tarjeta puede expandirse en una **superficie temporal** que representa la
duraci├│n completa del video (0ÔÇô100 %), con marcador m├│vil que acompa├▒a al
cursor, tiempo correspondiente a la posici├│n, preview existente m├ís cercana al
instante y una **preview m├│vil** que acompa├▒a horizontalmente al cursor
(funciona con previews horizontales y verticales). Adem├ís permite m├║ltiples
**marcadores temporales libres** (tiempo real + marca visual + miniatura fijada,
con solapamiento permitido) y su **eliminaci├│n individual** con clic derecho
(sobre la miniatura fijada o sobre la marca roja). La segunda etapa, **B4.2 ÔÇö
Persistencia de marcadores temporales por video**, qued├│ **aprobada e
incorporada**: los marcadores creados por el usuario se almacenan
**permanentemente en SQLite** (tabla `marcadores_video`, relacionados mediante
`videos.id`), reaparecen entre sesiones, pueden eliminarse permanentemente y
recuperan su representaci├│n visual usando las previews disponibles. El
scrubbing **no ejecuta FFmpeg ni accede a disco por movimiento**.
La tercera etapa, **B4.3.1 ÔÇö Motor de cach├® temporal versionada y
reanudable**, qued├│ **aprobada e incorporada**: es el **motor de disco** de la
cach├® densa de exploraci├│n temporal, con estructura
`miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` +
`fXXXXXXXXXX.jpg`), **versiones aisladas** derivadas de un *fingerprint* de
metadatos baratos (ruta normalizada + tama├▒o + `mtime_ns` + duraci├│n, SHA-256
reducido a 16 hex; **no** es hash de contenido), **reanudaci├│n** de
generaciones incompletas (p. ej. 8 de 20 reutiliza los 8 y genera 12),
**JPEG at├│micos** v├ílidos individualmente, **invalidaci├│n por versi├│n distinta**
sin borrado autom├ítico y escritura temporal ÔåÆ `os.replace`. Es un motor puro
(sin UI, sin SQLite). La cuarta etapa, **B4.3.2 ÔÇö Cobertura r├ípida as├¡ncrona
integrada con la UI**, qued├│ **aprobada e incorporada**: la tarjeta consume el
motor con **`FOTOGRAMAS_INICIALES = 15` provisional**, con **fallback inmediato
a las previews normales** mientras no hay cach├®, **generaci├│n as├¡ncrona**,
**resultados parciales progresivos** antes de completar los 15, **lectura y
decodificaci├│n JPEG en el worker mediante `QImage`** (emitida por se├▒al) con
**conversi├│n/aplicaci├│n final a `QPixmap` en la GUI**, `mouseMove`
exclusivamente en RAM, selecci├│n temporal por la imagen m├ís cercana entre
preview normal y densa (la preview normal gana el empate), **cancelaci├│n
cooperativa**, **aislamiento AÔåÆB**, **colapso que libera las referencias densas
de RAM** y **reexpansi├│n que reutiliza la cach├®**; los **marcadores** conservan
su tiempo/id y pueden mejorar visualmente al llegar fotogramas densos. La
validaci├│n visual manual (puntos AÔÇôG) en el PC de desarrollo fue **aprobada por
Marcos**, y la cobertura r├ípida tambi├®n qued├│ validada en la **notebook objetivo**
(expansi├│n y scrub correctos con un video real de ~56 min).
La quinta etapa, **B4.3.2 ÔÇö Etapa 2: Densidad secundaria adaptativa**, qued├│
**aprobada e incorporada**: tras el **benchmark de estrategias** sobre un video
de 56 min, por **decisi├│n de producto** se adopt├│ la **generaci├│n individual y
secuencial (un FFmpeg por objetivo, sin batch, sin paralelismo)**. Los **15
prioritarios** se mantienen exactamente como en la Etapa 1 y la **fase
secundaria** (solo despu├®s de la fase r├ípida, sin solapamiento) completa hasta
`objetivo_total_densidad(duraci├│n)` = `clamp(max(15, ceil(d/30 s)), 15, 200)` ÔÇö
valores **provisionales** (30 s / m├¡n 15 / m├íx 200) centralizados en
`exploracion_cache.py` para configurarlos despu├®s, **sin controles visibles por
ahora**. Reutiliza lo existente (nunca regenera los presentes), es
**progresiva**, **reanudable** y **cancelable**; cambiar/colapsar detiene la
continuaci├│n y lo generado queda reutilizable. Validada en el PC de desarrollo
(app real + FFmpeg real) y posteriormente en la **notebook objetivo** (B4.3 en
conjunto qued├│ validada satisfactoriamente en la notebook).
La sexta etapa, **B4.3.3 ÔÇö Ajustes de interacci├│n y densidad manual**, qued├│
**aprobada e incorporada**: (A) **prioridad visual de la preview din├ímica**
durante el hover: al mover el puntero por la tira temporal la miniatura din├ímica
queda **por encima** de las miniaturas fijas de marcadores (un marcador nunca
tapa el instante que se est├í explorando activamente); los tiempos/ids de los
marcadores no cambian y al salir del hover las fijas vuelven a su orden visual
normal. (B) **densidad manual**: control `Auto | 15 | 30 | 60 | 120 | 200` en la
tarjeta expandida; los valores manuales representan el **total objetivo
independiente de la duraci├│n** (video de 30 s: Auto ÔåÆ 15, manual 60 ÔåÆ 60, manual
120 ÔåÆ 120); siempre los **15 prioritarios primero**; **aumentar** reutiliza lo
existente (15ÔåÆ60, 60ÔåÆ120); **disminuir** no borra disco ni regenera (la RAM se
limita al conjunto objetivo `tiempos_objetivo(duraci├│n, cantidad_actual)`; la
cach├® puede contener un **superset** y la tarea emite/decodifica solo el
subconjunto permitido); **volver a Auto** recalcula el objetivo y conserva los
extras de disco. El valor de densidad es **por tarjeta/sesi├│n** (se conserva en
colapso/reexpansi├│n de la misma tarjeta; vuelve a Auto si se reconstruye por
recarga); **sin SQLite y sin persistencia en `configuracion.json`**.
La s├®ptima etapa, **B4.4 ÔÇö Reproducci├│n de marcadores en VLC**, qued├│ **aprobada e
incorporada** (Etapa 1: inspecci├│n y validaci├│n f├¡sica de la estrategia **playlist
pura** con VLC **3.0.23**; Etapa 2: integraci├│n m├¡nima). La acci├│n **"Reproducir
marcadores en VLC"** (men├║ contextual, habilitada con al menos un video seleccionado)
lee los marcadores persistentes (B4.2) y genera una playlist temporal `.m3u` con una
entrada por marcador (`#EXTVLCOPT:start-time`, precisi├│n decimal) en el **orden visible
actual del cat├ílogo** y con marcadores **cronol├│gicos ascendentes**; abre **VLC una
├║nica vez**. **Siguiente/Anterior visibles de VLC recorren la secuencia naturalmente** y
Play/Pause, volumen, fullscreen y seek manual permanecen intactos. Videos seleccionados
sin marcadores ÔåÆ **di├ílogo por ocasi├│n** (Omitir / Reproducir desde el inicio / Cancelar,
sin persistir). Archivos inexistentes ÔåÆ omitidos con aviso (sin borrar marcadores ni
registros). VLC ausente ÔåÆ mensaje claro, sin instalar. Playlists temporales
`visor_marcadores_*.m3u` en `%TEMP%` con encoding **UTF-8** (espacios/acentos/Unicode) y
**limpieza propia previa** (solo patr├│n propio; bloqueos ignorados; no se borra la reci├®n
lanzada). Sin HTTP, sin python-vlc/libVLC, sin loop autom├ítico. Se conserva como
**pendiente separado**: la demora perceptible al **cargar una carpeta de 121 videos** y
generar las miniaturas normales iniciales (no corresponde a B4.4; sin optimizar a├║n). El
**batch NO est├í implementado** (ver `ROADMAP.md`, secci├│n "Beta 4").

La octava etapa, **B4.5 ÔÇö Rendimiento de carga inicial**, qued├│ **aprobada e incorporada**
(Etapa 1: diagn├│stico del cuello de botella; Etapa 2: eliminaci├│n de FFprobe redundante; Etapa 3:
reutilizaci├│n de metadata en reescaneos). El
diagn├│stico (dataset temporal de 121 videos funcionales, base y cach├® temporales) midi├│ el
pipeline normal de cat├ílogo/miniaturas en la PC de desarrollo: escaneo, tama├▒os, SQLite y
lectura despreciables; **FFprobe de metadata ~4.5 s (121 procesos, secuenciales)**; **miniaturas
normales ~12.3 s** (121 FFmpeg + 121 FFprobe internos); **previews normales ~38.6 s** (363 FFmpeg
+ 363 FFprobe internos); reescaneo caliente con **FFprobe de metadata redundante (~4.6 s de
~4.9 s)**. El cuello dominante es el **FFmpeg+FFprobe de las previews normales (~70 % del tiempo
en fr├¡o)**. La Etapa 2 elimin├│ los **FFprobe internos redundantes**: `generar_miniatura` y
`generar_preview` aceptan `duracion_segundos=None` (v├ílida ÔåÆ usa esa duraci├│n sin FFprobe
interno y con el mismo c├ílculo temporal y FFmpeg; inv├ílida o ausente ÔåÆ fallback FFprobe
anterior); `asegurar_miniaturas`/`generar_previews_faltantes` y sus tareas
(`TareaMiniaturas`/`TareaPreviewsProgresivas`) propagan las duraciones, que la interfaz toma de
`TareaFFprobe` (miniaturas) y de la tarjeta (previews). En fr├¡o con 121 videos: **484 FFprobe
internos ÔåÆ 0**, mismos 484 FFmpeg; total backend **~55.6 s ÔåÆ ~37.1 s** (miniaturas 12.3ÔåÆ7.9 s,
previews 38.6ÔåÆ24.8 s) como medici├│n de la PC de desarrollo (no extrapolable a la notebook). Sin
cambios de cantidad, posiciones, calidad, progresividad, lotes, cach├®, paralelismo ni FFmpeg.
La **Etapa 3** reutiliza metadata en reescaneos sin cambios con el criterio barato
**`ruta normalizada + tamano_bytes + mtime_ns`** (sin hash de contenido): 0 FFprobe solo si hay
registro previo, `mtime_ns` no NULL, ruta/tama├▒o/`mtime_ns` coinciden y la metadata es v├ílida;
fuerzan FFprobe archivo nuevo, registro sin `mtime_ns`, ruta/tama├▒o/`mtime_ns` cambiados o
metadata inv├ílida. Migraci├│n aditiva e idempotente `videos.mtime_ns INTEGER NULL`; bases antiguas
hacen FFprobe en la primera pasada y se rellenan. `obtener_tamanos_archivos` obtiene
tama├▒o+`mtime_ns` con un `os.stat` por archivo; `listar_registros_por_nombres` consulta por lote
(una SELECT); `TareaFFprobe` clasifica y solo probea lo necesario; `guardar_videos` persiste
`mtime_ns`. Reescaneo caliente de 121 videos: **121 FFprobe ÔåÆ 0**, backend **~4.9 s ÔåÆ ~0.1ÔÇô0.5 s**
(referencia de PC de desarrollo). Verificaci├│n emp├¡rica con 10 archivos f├¡sicos independientes
(10 inodos): **10 ÔåÆ 0 ÔåÆ 1 ÔåÆ 0**. `video_id` y marcadores intactos; un cambio de ruta fuerza
FFprobe conservando la identidad por nombre/upsert. **Riesgo residual aceptado**: si un archivo
distinto reemplaza al original conservando ruta+tama├▒o+`mtime_ns`, la metadata puede reutilizarse
(sin hash). **Pendiente t├®cnico registrado, sin corregir**: las previews existentes se consideran
reutilizables por existencia del archivo (sin validaci├│n por cambio del video). **B4.5 queda
completada en sus Etapas 1-3; no se declara la Beta 4 completa todav├¡a.**
La novena etapa, **B4.6 ÔÇö Rendimiento de carga visual**, qued├│ **aprobada e incorporada**
(Etapa 1: diagn├│stico de construcci├│n/poblaci├│n de tarjetas; Etapa 2: carga diferida de previews
cacheadas). El diagn├│stico con 100 tarjetas/300 previews cacheadas descompuso el costo de la
carga visual: construcci├│n de widgets ~0.42 s (dominada por `_construir_exploracion`);
`miniatura_principal` ~0.05 s (un `os.listdir` por tarjeta); **`_crear_tarjetas` cargaba y
escalaba las 300 previews de golpe (0.74 s caliente / ~3.5 s fr├¡o)**; bloqueo s├¡ncrono total
1.4ÔÇô4.4 s; `_reemplazar_tarjetas` re-decodificaba las mismas previews; RAM ~+690 MB por retenci├│n
de pixmaps originales. La Etapa 2 difiere la carga de previews cacheadas: `_crear_tarjetas`/
`_agregar_tarjetas`/`_reemplazar_tarjetas` ya **no** las cargan de golpe; las tarjetas parten con
textos + miniatura principal + placeholders y las previews (existentes o faltantes) se incorporan
**progresivamente** por la tuber├¡a existente (`_programar_previews` ÔåÆ `_encolar_previews` ÔåÆ
`TareaPreviewsProgresivas` ÔåÆ `generar_previews_faltantes` ÔåÆ `_aplicar_previews`). Con cach├®
completa **0 FFmpeg**; con faltantes la generaci├│n normal. `Tarjeta._previews_completas`
(estado interno, no persistido) decide si una tarjeta entra a la cola; protecci├│n de resultados
tard├¡os en `_aplicar_previews` (cambio AÔåÆB sin im├ígenes cruzadas ni crash); ajuste de integraci├│n
en `_reconstruir_previews_exploracion` (fallback a las previews de disco si las etiquetas a├║n no
las tienen; sin modificar el motor B4.3, scrub, densidad ni marcadores). Medici├│n (PC de
desarrollo): `_crear_tarjetas(100)` **0.69ÔÇô0.85 s** (antes 1.4ÔÇô4.4 s); tarjetas visibles ~0.72 s;
primera preview ~1.0 s; **300 previews completas ~2.1 s**; m├íximo bloqueo continuo **~0.7 s**;
lotes ~20ÔÇô30 ms; reemplazo ~0.73 s sin recargar previews de golpe. **La interfaz queda utilizable
antes de terminar de cargar las previews.** Pendientes separados, sin implementar: retenci├│n de
pixmaps originales/RAM (~+690 MB), `_construir_exploracion` en tarjetas colapsadas,
reconciliaci├│n de `_reemplazar_tarjetas` y `miniatura_principal` con `os.listdir`. **B4.6
completada en sus Etapas 1-2; no se declara la Beta 4 completa todav├¡a.**
La mejora de diagn├│stico **identificaci├│n visible de versi├│n/build** qued├│ **aprobada e
incorporada**: la ventana principal muestra en la **status bar** inferior un texto discreto con la
versi├│n/build en ejecuci├│n (`Beta 4 ÔÇö B4.12`), definida por constantes centrales en
`configuracion.py` (`VERSION_PRODUCTO`, `BUILD_IDENTIFICADOR`, `TEXTO_VERSION_BUILD`). La
identificaci├│n visible es **independiente del SHA Git** (el identificador se incrementa manualmente
por autorizaci├│n; sin automatizaci├│n) y para cada build de validaci├│n se registra la asociaci├│n
**identificador visible ÔåÆ SHA Git exacto ÔåÆ SHA-256 del instalador**.
La correcci├│n t├®cnica previa al cierre qued├│ **aprobada e incorporada**: (1) la resoluci├│n de
existencia de la ruta de video se movi├│ de la UI (`visor_videos.py`) a `rutas.py`
(`ruta_video_existente`), restaurando la regla "la UI no accede al filesystem"; (2) los
contract-tests quedaron reconciliados con el contrato actual (previews progresivas de B4.6, esquema
vigente con `mtime_ns`, tareas leg├¡timas de marcadores); (3) la suite integral qued├│ en **87 suites
/ 1570 pruebas, 0 FAIL** en la corrida final, con la ├║nica flakiness residual conocida de teardown
de `prueba_exploracion_densidad_b432.py` (ocasional `0xC0000409`; 12/12 funcionales; no bloqueante).
**Transici├│n de builds:** `B4.11` = build ampliamente validada en la notebook; `B4.12` = build final
validada en la notebook (validaci├│n final corta). **La Beta 4 qued├│ CERRADA y aprobada (ver
"Pr├│xima fase").**

## Cierre interno de Beta 5

**Fecha:** 2026-08-15 ┬À **Rama:** `beta5`

**Commit t├®cnico principal:** `969efcd9d71e78c1ca538bfa238a3e27f1484d9e`
(┬½Pulir interacci├│n, edici├│n y visualizaci├│n de segmentos en Beta 5┬╗).

**Identidad definitiva:** `Beta 5 ÔÇö B5.0` (constantes en `configuracion.py`).

**Instalador interno validado en notebook:** `VisorVideos_Beta5_ValidacionFinal_Setup.exe`
(SHA-256 `F40ACF41FE7D3931FF042AC718B6D2805460AE380092E9E782A918C42A650133`), aprobado.

**Funcionalidad incorporada en Beta 5:**
- doble clic temporal ÔåÆ VLC desde instante;
- modelo persistente de segmentos AÔÇôB;
- carga lazy/as├¡ncrona de segmentos;
- creaci├│n visual A+B;
- robustez y ciclo de vida de segmentos;
- reproducci├│n individual AÔåÆB; bucle AÔåÆB; secuencia de segmentos;
- creaci├│n de segmentos por drag;
- edici├│n de extremos A/B conservando id;
- feedback visual de edici├│n (handle/cursor);
- mejora de visibilidad de segmentos;
- scroll horizontal local de previews.

**Correcciones B5.9.2:** doble clic interceptado por `MiniaturaMarcador`; creaci├│n de
marcadores cercanos bloqueada por solapamiento.

**Persistencia de edici├│n:** UPDATE por id; tarea as├¡ncrona; rollback en error.

**Validaci├│n final:** suites verdes; auditor├¡a integral aprobada; notebook objetivo aprobada.

**Estado de cierre:** cierre interno y local. **Sin distribuci├│n p├║blica; sin merge a `main`;
sin GitHub Release.** Deudas registradas: uninstaller destructivo (bloqueante futuro para
distribuci├│n p├║blica), retenci├│n de pixmaps densos (deuda de Beta 4, no empeor├│), flake
ocasional de timing en pruebas VLC/PySide6, seek VLC aproximado por keyframes.

---

## Protocolo de colaboraci├│n y materializaci├│n de persistencia

**Fecha:** 2026-08-17

El protocolo de colaboraci├│n **ChatGPT Ôåö Bridge Ôåö OpenCode** (con
Bridge/MCP/Telegram como transporte) est├í **activo**. Su autoridad detallada
ÔÇö actores, flujo, estados, auditor├¡a, persistencia y seguridad ÔÇö es
`METODOLOGIA_DESARROLLO.md`.

La **inspecci├│n de persistencia** qued├│ **cerrada y aprobada**, y la
**materializaci├│n de la autoridad documental** (documento metodol├│gico,
reglas y protecciones Git) qued├│ **completada y versionada**: `METODOLOGIA_DESARROLLO.md`
como detalle del protocolo y referencia en `REGLAS_PROYECTO.md` (commit `dd17c72`),
m├ís la **infraestructura reconstruible del Bridge** versionada en `infra/`
(commit `7a0feae`). A partir de esa base se completaron **B6.1** y **B6.2**
(ver "Fase actual ÔÇö Beta 6").
Las normas permanentes del protocolo constan en `REGLAS_PROYECTO.md`; no se
insertan aqu├¡ la matriz completa ni el detalle operativo (ver
`METODOLOGIA_DESARROLLO.md`).

---

## Registro de commits aprobados de Beta 4 (hist├│rico)

Secci├│n **hist├│rica** que registra el ├║ltimo commit aprobado del ciclo
**Beta 4** (`B4.12`, 2026-08-10) y sus commits anteriores. **No representa el
estado vigente ni el ├║ltimo commit del repositorio**: ver "Fase actual ÔÇö Beta 6"
y `HISTORIAL_PROYECTO.md`.

**Mensaje:** Cerrar regresiones y contratos de prueba de Beta 4

**Correcci├│n previa al cierre** (rama `beta4`):
- `rutas.py` ÔÇö nuevo `ruta_video_existente(carpeta, nombre)`: resuelve y valida la existencia de la
  ruta de video fuera de la UI.
- `visor_videos.py` ÔÇö `_ruta_video_de` delega en `ruta_video_existente`; **ya no usa
  `os.path.isfile`** (regla arquitect├│nica "la UI no accede al filesystem" restaurada; verificado por
  `prueba_doble_clic.py` T14 sin modificar el test).
- `configuracion.py` ÔÇö `BUILD_IDENTIFICADOR = "B4.12"` (la etapa modifica c├│digo de producci├│n, por
  lo que no conserva el identificador B4.11); texto visible `Beta 4 ÔÇö B4.12`.
- Contract-tests reconciliados con el contrato actual: 7 suites de vista ampliada/previews adaptadas
  al contrato progresivo de B4.6; `prueba_filas_horizontales.py` T15 (uso real vs docstrings);
  `prueba_eliminar_candidatos.py` T02 (regla AST precisa ante `TareaEliminarMarcador` leg├¡timo);
  `prueba_persistencia_carpeta.py` T11/T16 (config creada en el arranque por `escaneo_automatico`);
  `prueba_aplicar_incorporaciones.py` T15 (esquema vigente con `mtime_ns` y `tamano_bytes`).
- `prueba_version_build.py` ÔÇö adaptada a `Beta 4 ÔÇö B4.12` (3 pruebas).

**Suite integral:** 87 suites, **1570/1570** pruebas, **0 FAIL** en la corrida final. Flakiness
residual conocida (documentada, no bloqueante): teardown ocasional de
`prueba_exploracion_densidad_b432.py` (`0xC0000409`; 12/12 comprobaciones funcionales).

**Transici├│n:** `B4.11` = build ampliamente validada en la notebook; `B4.12` = build final validada en
la notebook. **La Beta 4 qued├│ CERRADA y aprobada (ver "Pr├│xima fase").**

**Pruebas superadas:** `prueba_version_build.py` **3/3**, `prueba_doble_clic.py` **14/14**, las 7
suites B4.6 reconciliadas (vista_ampliada **24/24**, vista_ampliada_desactivada **20/20**,
preferencias_miniaturas **31/31**, pulido_bloque_a **29/29**, tamano_muy_grande **27/27**,
tiempo_previews **35/35**, tamano_vista_ampliada **38/38**), filas_horizontales **16/16**,
persistencia_carpeta **20/20**, eliminar_candidatos **16/16**, aplicar_incorporaciones **15/15**,
regresiones B4.1ÔÇôB4.6 verdes y `prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check`
OK.

---

**Commit anterior ÔÇö Mensaje:** Mostrar identificador de version y build en la interfaz

**Mejora:** Identificaci├│n visible de versi├│n/build (`Beta 4 ÔÇö B4.11`, rama `beta4`):
- `configuracion.py` ÔÇö constantes centrales `VERSION_PRODUCTO = "Beta 4"`,
  `BUILD_IDENTIFICADOR = "B4.11"` y `TEXTO_VERSION_BUILD = "Beta 4 ÔÇö B4.11"` (fuente ├║nica de
  verdad; independientes del SHA Git; embebidas en la build congelada, sin Git en runtime).
- `visor_videos.py` ÔÇö `QLabel` discreto con `TEXTO_VERSION_BUILD` en la **status bar** inferior de
  la ventana principal; sin tocar el layout principal ni otra funcionalidad.
- `prueba_version_build.py` ÔÇö **nueva**: 3 pruebas (constantes; texto exacto `Beta 4 ÔÇö B4.11`;
  etiqueta visible en la status bar).

**Build de validaci├│n:** `B4.11` es la build usada para continuar la validaci├│n manual en la
notebook. **No es el cierre definitivo de la Beta 4.**

**Pruebas superadas:** `prueba_version_build.py` **3/3**, `prueba_exploracion_b433.py` **22/22**,
`prueba_carga_visual_b462.py` **9/9**, `prueba_smoke.py` OK. `python -m py_compile` OK.
`git diff --check` OK.

---

**Commit anterior ÔÇö Mensaje:** Diferir la carga de previews para acelerar la interfaz

**Etapa:** B4.6 ÔÇö Rendimiento de carga visual, Etapa 2 (rama `beta4`):
- `visor_videos.py` ÔÇö `_crear_tarjetas`/`_agregar_tarjetas`/`_reemplazar_tarjetas` ya **no** cargan
  previews cacheadas (las tarjetas parten con textos + miniatura + placeholders); `_encolar_previews`
  encola las tarjetas no completas usando `Tarjeta._previews_completas` (estado interno, no
  persistido); `_siguiente_lote_previews` sin filtro `os.path.isdir` (reutilizar cacheadas usa solo
  la cach├® de miniaturas); `_aplicar_previews` valida la carpeta del video del resultado contra la
  tarjeta actual (ignora resultados tard├¡os de otra carpeta); `Tarjeta.actualizar_previews` marca
  `_previews_completas` y, si la tarjeta est├í expandida, llama `_renderizar_marcadores()`;
  `_reconstruir_previews_exploracion` con fallback a las previews cacheadas en disco (integraci├│n
  necesaria del diferido; no toca B4.3/scrub/densidad/marcadores).
- `prueba_carga_visual_b462.py` ÔÇö **nueva**: 9 pruebas (no aplicaci├│n eager; placeholders;
  recuperaci├│n cacheada progresiva con 0 FFmpeg; generaci├│n de faltantes; lotes conservados;
  cambio AÔåÆB ignora resultados tard├¡os; reemplazo sin carga de golpe; cargar m├ís con
  correspondencia; filtro sin romper aplicaci├│n).
- Suites adaptadas al comportamiento progresivo: `prueba_tamano_miniaturas.py`,
  `prueba_marcadores_b42.py`, `prueba_exploracion_b41.py` (esperan a que las previews se apliquen
  antes de interactuar con la tarjeta/exploraci├│n).

**Medici├│n (PC de desarrollo, 100 tarjetas / 300 previews cacheadas):** `_crear_tarjetas(100)`
**0.69ÔÇô0.85 s** (antes 1.4ÔÇô4.4 s); tarjetas visibles ~0.72 s; primera preview ~1.0 s; **300
previews completas ~2.1 s**; m├íximo bloqueo continuo **~0.7 s**; lotes ~20ÔÇô30 ms; reemplazo
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

**Commit anterior ÔÇö Mensaje:** Reutilizar metadata de videos sin cambios en reescaneos

**Etapa:** B4.5 ÔÇö Rendimiento de carga inicial, Etapa 3 (rama `beta4`):
- `escanear_videos.py` ÔÇö migraci├│n aditiva e idempotente **`videos.mtime_ns INTEGER NULL`**
  (`COLUMNAS_EXTRA` + helper `_asegurar_columnas_videos` reutilizado por `conectar_bd`,
  `guardar_video` y `guardar_videos`; `BEGIN` expl├¡cito en el guardado para que el `ALTER` sea
  transaccional); `obtener_tamanos_archivos` obtiene tama├▒o+`mtime_ns` con **un `os.stat` por
  archivo**; `combinar_registros_con_tamanos` propaga `mtime_ns`; `_upsert_video` lo persiste;
  helpers de clasificaci├│n `_normalizar_ruta_absoluta`, `_metadata_ffprobe_utilizable` y
  `_metadata_reutilizable` (criterio ruta+tama├▒o+`mtime_ns`); `listar_registros_por_nombres`
  (consulta por lote por `nombre`, una SELECT).
- `tareas_videos.py` ÔÇö `TareaFFprobe(rutas, nombres=None, stats=None, ruta_db=None)`: consulta los
  registros previos por lote, clasifica y ejecuta FFprobe **solo** para los videos
  nuevos/cambiados/sin fingerprint/metadata inv├ílida; el resultado devuelve metadata completa
  para todos (reutilizada o nueva) con el mismo formato.
- `visor_videos.py` ÔÇö `_iniciar_ffprobe` pasa `nombres`, `stats` (`resultado_tamanos`) y `ruta_db`
  a `TareaFFprobe` (sin SQLite en la UI).
- `prueba_reutilizacion_metadata_b453.py` ÔÇö **nueva**: 20 pruebas (migraci├│n antigua e
  idempotente; NULL ÔåÆ FFprobe; id├®ntico ÔåÆ 0 FFprobe; tama├▒o/mtime/ambos/ruta/nuevo/metadata
  inv├ílida ÔåÆ FFprobe; metadata reutilizada exacta; persistir `mtime_ns`; video_id y marcadores
  preservados; lote mixto 10 ÔåÆ 3 FFprobe; lote 121 ÔåÆ 0 FFprobe; consulta por lote = 1 SELECT;
  un stat por archivo; normalizaci├│n de ruta).
- Suites adaptadas al esquema nuevo (`mtime_ns`): `prueba_guardar.py`, `prueba_guardar_videos.py`
  (SELECT con columnas expl├¡citas), `prueba_aplicar_incorporaciones.py`,
  `prueba_sincronizacion_asincrona.py` (`_crear_bd` con `mtime_ns`).

**Medici├│n (PC de desarrollo, dataset temporal de 121 videos, cach├® caliente):** reescaneo con
**121 FFprobe ÔåÆ 0**; backend **~4.9 s ÔåÆ ~0.1ÔÇô0.5 s** (referencia, no garant├¡a universal).
Verificaci├│n emp├¡rica con 10 copias f├¡sicas independientes (10 inodos, sin hardlinks):
**10 ÔåÆ 0 ÔåÆ 1 ÔåÆ 0** (tercera pasada: 1 FFprobe, 9 metadata reutilizadas y 1 reprocesada;
cuarta pasada: 0). La UI de tarjetas no se optimiz├│ en esta etapa.

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

**Commit anterior ÔÇö Mensaje:** Eliminar FFprobe redundante al generar miniaturas y previews

**Etapa:** B4.5 ÔÇö Rendimiento de carga inicial, Etapa 2 (rama `beta4`):
- `escanear_videos.py` ÔÇö `_duracion_utilizable` (n├║mero real finito > 0; rechaza `None`, bool, no
  num├®rico, 0, negativos, NaN/infinito), `_duracion_de_duraciones` (busca por ruta o nombre),
  `generar_miniatura`/`generar_preview` con `duracion_segundos=None` (v├ílida ÔåÆ sin FFprobe
  interno, mismo c├ílculo temporal y FFmpeg; inv├ílida ÔåÆ fallback FFprobe anterior),
  `asegurar_miniatura`/`asegurar_miniaturas`/`generar_previews_faltantes` con propagaci├│n de
  duraciones.
- `tareas_videos.py` ÔÇö `TareaMiniaturas(videos, carpeta, duraciones=None)` y
  `TareaPreviewsProgresivas(videos, carpeta, duraciones=None)`.
- `visor_videos.py` ÔÇö `_iniciar_miniaturas` pasa el mapa rutaÔåÆduraci├│n construido desde
  `self.resultado_ffprobe` (`_duraciones_desde_ffprobe`); `_siguiente_lote_previews` pasa las
  duraciones de las tarjetas (`Tarjeta._duracion`) al lote.
- `prueba_optimizacion_ffprobe_b452.py` ÔÇö **nueva**: 14 pruebas (miniatura/preview con duraci├│n
  conocida sin FFprobe interno; fallback sin duraci├│n; duraci├│n inv├ílida; tiempos equivalentes;
  pipelines miniaturas y previews con 0 FFprobe internos; cache existente sin procesos; callers
  antiguos sin par├ímetro).
- Suites adaptadas a la firma nueva (mocks): `prueba_previews_progresivas.py`,
  `prueba_previews_multicarpeta.py`, `prueba_previews_automaticas.py`, `prueba_escaneo_guardado.py`.

**Medici├│n (PC de desarrollo, dataset temporal de 121 videos, cach├® fr├¡a):** FFprobe internos
**484 ÔåÆ 0** (121 miniaturas + 363 previews), mismos 484 FFmpeg; total backend **~55.6 s ÔåÆ
~37.1 s**; miniaturas **12.3 ÔåÆ 7.9 s**; previews **38.6 ÔåÆ 24.8 s**. Verificaci├│n funcional con
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

**Commit anterior ÔÇö Mensaje:** Integrar reproduccion de marcadores mediante playlists VLC

**Etapa:** B4.4 ÔÇö Reproducci├│n de marcadores en VLC (Etapa 1: validaci├│n de playlist; Etapa 2:
integraci├│n m├¡nima) (rama `beta4`):
- `escanear_videos.py` ÔÇö **`listar_marcadores_de(video_ids)`** (B4.4): lee los marcadores
  persistidos de varios `video_id` (tuplas `(id, video_id, tiempo)`), agrupados en el orden
  recibido y ordenados cronol├│gicamente dentro de cada video; validaci├│n previa y conexi├│n
  propia por operaci├│n, reutilizando el repositorio de B4.2.
- `tareas_videos.py` ÔÇö **`TareaListarMarcadoresVarios`** (B4.4): lectura as├¡ncrona de los
  marcadores de varios videos.
- `playlist_vlc.py` ÔÇö **nuevo** (B4.4): m├│dulo de servicio que a├¡sla de la interfaz la
  integraci├│n con VLC: `localizar_vlc()` (ProgramFiles ÔåÆ ProgramFiles(x86) ÔåÆ `shutil.which`),
  `formatear_tiempo_vlc` (precisi├│n decimal), `formatear_titulo_marcador` (H:MM:SS.mmm),
  `limpiar_playlists_anteriores` (solo `visor_marcadores_*.m3u`, un solo directorio, bloqueos
  ignorados), `generar_m3u` (UTF-8 expl├¡cito; limpia primero, escribe despu├®s) y
  `abrir_playlist_en_vlc` (un ├║nico `Popen`). Sin HTTP, sin libVLC, sin automatizaci├│n de
  botones, sin loop autom├ítico.
- `visor_videos.py` ÔÇö acci├│n **"Reproducir marcadores en VLC"** en el men├║ contextual
  (habilitada con selecci├│n): recolecta los videos seleccionados en **orden visible del
  cat├ílogo** (patr├│n de `_copiar_rutas_seleccionados`), obtiene sus marcadores v├¡a
  `gestor_reproduccion` (nuevo gestor dedicado), di├ílogo Omitir/Desde el inicio/Cancelar para
  videos sin marcadores (sin persistir), omite archivos inexistentes con aviso (sin borrar
  marcadores/registros), genera la playlist temporal y abre VLC una ├║nica vez.
- `prueba_reproduccion_marcadores_b44.py` ÔÇö **nueva**: 24 pruebas (orden visible, orden
  cronol├│gico, generaci├│n M3U, tiempos decimales, mismo archivo m├║ltiples entradas, mezcla de
  videos, decisiones Omitir/Desde inicio/Cancelar, todos sin marcadores, playlist vac├¡a, VLC no
  encontrado, archivo inexistente, no modificaci├│n de marcadores, lanzamiento ├║nico, limpieza
  de playlists propias, no borrar archivos ajenos, eliminaci├│n bloqueada, rutas con espacios y
  rutas Unicode).

**Validaci├│n f├¡sica (PC de desarrollo, VLC 3.0.23, videos reales de `Videos de muestra`):**
primera reproducci├│n con A (1.5 / 17.83 / 30 s) + B (2 s): VLC abri├│ una sola vez, primer
marcador en ~1.5 s, Siguiente recorri├│ AÔåÆAÔåÆAÔåÆB, Anterior correcto, play/pause y fullscreen
normales; segunda reproducci├│n con A + video sin marcadores (Desde el inicio): di├ílogo con las
3 opciones y comportamiento correcto. Playlists temporales: al final solo queda la ├║ltima
(`visor_marcadores_*.m3u`); la anterior y un residuo previo fueron eliminados por la limpieza.
Se observ├│ que la configuraci├│n actual de VLC abre una instancia por ejecuci├│n (sin impedir la
reproducci├│n ni la limpieza; no corregido en esta etapa).

**Pruebas superadas:** `prueba_reproduccion_marcadores_b44.py` **24/24**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_b433.py` **22/22**, `prueba_marcadores_b42.py`
**17/17**, `prueba_recarga_catalogo.py` **20/20**, `prueba_pagina_siguiente.py` **20/20**,
`prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check` OK.

---

**Commit anterior ÔÇö Mensaje:** Agregar densidad manual y priorizar la vista dinamica temporal

**Etapa:** B4.3.3 ÔÇö Ajustes de interacci├│n y densidad manual (rama `beta4`):
- `tareas_videos.py` ÔÇö **`TareaExploracionDensa` con objetivo manual**: nuevo par├ímetro
  `objetivo_manual` (None = Auto). `_trabajo()` calcula el objetivo total como
  `objetivo_manual` si es positivo, o `objetivo_total_densidad(duraci├│n)` en Auto; la **fase
  r├ípida** siempre son los 15 prioritarios y la **fase secundaria** completa hasta ese total.
  En cada fase se construye expl├¡citamente el **conjunto permitido**
  `tiempos_objetivo(duraci├│n, cantidad_actual)` y la emisi├│n (`resultado_parcial`) y la cola
  final **solo decodifican/emiten ese subconjunto**: la cach├® en disco puede contener un
  **superset** (densidades manuales previas) y la tarea decide qu├® subconjunto utiliza (RAM/UI
  limitada al conjunto objetivo actual; los extras permanecen en disco sin regenerar ni
  borrar). `al_progreso` lista los existentes de la versi├│n e intersecta con `permitidos`.
- `visor_videos.py` ÔÇö **prioridad visual din├ímica** (Mejora A): `_al_instante_exploracion`
  hace `raise_()` a la preview din├ímica (queda por encima de las miniaturas fijas de
  marcadores durante el hover) y `eventFilter` sobre el franja baja la preview (`lower()`) al
  salir de la superficie; tiempos/ids de marcadores intactos. **Densidad manual** (Mejora B):
  constante `DENSIDADES_DISPONIBLES = (Auto, 15, 30, 60, 120, 200)`, `QComboBox` "Densidad:" en
  la tarjeta expandida, se├▒al `densidad_cambiada`, `aplicar_densidad(valor)` filtra los densos
  de RAM al conjunto objetivo de la cantidad elegida, y `_procesar_siguiente_exploracion`
  pasa `objetivo_manual` a la tarea (solo cuando hay valor manual). El valor es por
  tarjeta/sesi├│n.
- `prueba_exploracion_b433.py` ÔÇö **nueva**: 22 pruebas (z-order 1/varios marcadores y leave;
  eliminaci├│n clic derecho; Auto/manual en videos cortos 30 s y 2 min; 56 min + 120; incremento
  15ÔåÆ60 y 60ÔåÆ120; disminuci├│n 120ÔåÆ30 sin borrar disco ni regenerar; volver a Auto sin borrar
  extras; m├íximo un FFmpeg; mouseMove solo RAM; marcadores tiempo/id intactos; cach├® superset
  120ÔåÆ30, 120ÔåÆ60, 120ÔåÆAuto; fase r├ípida limitada a 15 con superset).

**Validaci├│n visual (PC de desarrollo, app real + FFmpeg real, video de 30 s, cach├® temporal):**
Auto ÔåÆ 15; marcador en 15 s: hover con din├ímica arriba y al salir la fija vuelve arriba;
AutoÔåÆ60 ÔåÆ 60 densos con scrub fluido; 60ÔåÆ120 ÔåÆ 120 densos; 120ÔåÆAuto ÔåÆ RAM filtrada a 15 sin
errores y marcador con tiempo 15.0 intacto. B4.3 qued├│ validada satisfactoriamente tambi├®n en
la **notebook objetivo**.

**Pruebas superadas:** `prueba_exploracion_b433.py` **22/22**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_densidad_b432.py` **12/12**,
`prueba_exploracion_b432.py` **20/20**, `prueba_exploracion_cache_b431.py` **29/29**,
`prueba_exploracion_b41.py` **28/28**, `prueba_marcadores_b42.py` **17/17**,
`prueba_previews_progresivas.py` **16/16**, `prueba_tamano_miniaturas.py` **32/32**,
`prueba_recarga_catalogo.py` **20/20**, `prueba_pagina_siguiente.py` **20/20**,
`prueba_smoke.py` OK. `python -m py_compile` OK. `git diff --check` OK.
- `exploracion_cache.py` ÔÇö **nuevo**: motor de cach├® densa de exploraci├│n en disco, **sin Qt,
  sin SQLite y sin acoplamiento con `escanear_videos`**. Estructura
  `miniaturas/exploracion/<video_id>/<version_fingerprint>/` con `meta.json` + `f{ms:010d}.jpg`;
  el `video_id` identifica la carpeta y no se repite en el nombre del JPG.
- **Versionado f├¡sico por fingerprint**: `fingerprint_actual` (ruta normalizada + tama├▒o +
  `mtime_ns` + duraci├│n) ÔåÆ `version_id_de_fingerprint` = **SHA-256 reducido a 16 hex**. **NO**
  es hash del contenido; **limitaci├│n aceptada**: dos archivos con la misma ruta, tama├▒o,
  mtime y duraci├│n no son distinguibles. `version_actual` cuesta Ôëê **13 ┬Ás** (un `os.stat` +
  SHA-256); impacto CPU/RAM despreciable.
- **API para consumidores** (sin gestionar versiones): `generar_fotogramas`, `listar_fotogramas`,
  `faltantes`, `cache_vigente`, `fotograma_mas_cercano_en_cache`, `ruta_carpeta_actual`,
  `version_actual`.
- **Reanudaci├│n**: un `f*.jpg` presente en la versi├│n se reutiliza aunque la versi├│n est├®
  incompleta (la escritura es at├│mica, temporal ÔåÆ `os.replace`; un JPEG presente est├í completo);
  p. ej. una generaci├│n detenida en 8/20 reutiliza los 8 y genera solo 12. El `meta.json` de la
  versi├│n **solo** se escribe si la generaci├│n termina sin cancelarse y **completa**
  (`faltantes == 0`); la completitud se deriva de `objetivos - existentes`. `.tmp`/preparados/
  fallidos quedan fuera del ├¡ndice y de la lista.
- **Invalidaci├│n no destructiva**: cualquier cambio en el fingerprint produce una **versi├│n
  distinta**; las versiones antiguas quedan en disco (no se borra nada autom├íticamente; la
  limpieza queda para una etapa futura). Una versi├│n nunca usa ni lista JPEGs de otra.
- `exploracion_temporal.py` ÔÇö **densidad y orden**: `cantidad_fotogramas(duracion)` =
  `clamp(round(duraci├│n / 2 s), 40, 200)` y `tiempos_objetivo(duracion, cantidad)` = instantes
  (ms) en **orden progresivo de cobertura** por bisecci├│n de huecos (50 %, 25/75 %, octavosÔÇª),
  pensado para la estrategia h├¡brida de B4.3.2; `fotograma_mas_cercano(ms_existentes, instante)`
  por `bisect` (empate ÔåÆ el anterior). API de B4.1 intacta.
- `rutas.py` ÔÇö `ruta_carpeta_exploracion()` = `miniaturas/exploracion`.
- `prueba_exploracion_cache_b431.py` ÔÇö **nueva**: 29 pruebas (densidad, orden progresivo,
  nearest por bisect, estructura versionada, fingerprint sin hash, invalidaci├│n no destructiva,
  reanudaci├│n 8/20, fallos parciales, aislamiento A/B/C, atomicidad, nearest solo de la versi├│n
  actual, y aislamiento de la etapa: sin UI, sin SQLite, sin tocar la cach├® real).

**Pruebas superadas:** `prueba_exploracion_cache_b431.py` **29/29**. Regresiones en verde
(ejecutadas en el cierre): `prueba_exploracion_b41.py` **28/28**, `prueba_marcadores_b42.py**
**17/17**, `prueba_previews_progresivas.py` **16/16**, `prueba_smoke.py` OK. `python -m py_compile`
OK. `git diff --check` OK.

## Hitos completados

- Arquitectura general y separaci├│n de capas.
- Control de versiones con Git.
- Resoluci├│n centralizada de rutas (independiente del CWD).
- Generaci├│n de miniaturas con preservaci├│n de archivos.
- Infraestructura de trabajos en segundo plano (QThread).
- Escaneo as├¡ncrono de videos.
- Lectura as├¡ncrona del cat├ílogo SQLite.
- Lectura paginada del cat├ílogo (`LIMIT`/`OFFSET`/`COUNT` en SQL).
- Escritura individual y de colecci├│n as├¡ncronas.
- Integraci├│n as├¡ncrona de la interfaz (carga inicial sin bloquear).
- Selecci├│n de carpeta desde la interfaz.
- Escaneo manual y as├¡ncrono de la carpeta elegida.
- Pipeline completo: escaneo ÔåÆ tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas ÔåÆ guardado ÔåÆ sincronizaci├│n ÔåÆ recarga.
- Detecci├│n de diferencias disco Ôåö BD (no destructiva).
- Plan de sincronizaci├│n y aplicaci├│n de incorporaciones.
- Eliminaci├│n controlada de registros ausentes.
- Sincronizaci├│n as├¡ncrona del cat├ílogo e integraci├│n en la interfaz.
- Recarga as├¡ncrona del cat├ílogo tras sincronizaci├│n.
- Carga manual de p├íginas adicionales (bot├│n "Cargar m├ís").
- Presentaci├│n del cat├ílogo en filas horizontales (una tarjeta por video).
- Visualizaci├│n del tama├▒o de archivos (B/KB/MB/GB).
- Previews progresivos por video (3 fotogramas al 25/50/75 %).
- Apertura del video por doble clic (m├│dulo de servicio `apertura_videos.py`).
- Persistencia de la ├║ltima carpeta seleccionada (`configuracion.json`).
- Separaci├│n del punto de entrada de producci├│n y del arn├®s de smoke tests.
- Ejecutable portable (PyInstaller `--onedir --windowed`).
- Instalador Beta funcional (Inno Setup, sin permisos de administrador).
- Feedback visual del procesamiento (barra de progreso indeterminada con texto de etapa).
- Selecci├│n visual de filas (simple y m├║ltiple con Ctrl+clic). Base preparada para futuras acciones sobre elementos seleccionados sin agregar men├║s ni botones todav├¡a.
- Men├║ contextual con clic derecho sobre filas de videos (abrir, abrir carpeta, copiar ruta).
- Restauraci├│n autom├ítica de la selecci├│n tras reconstruir la lista de tarjetas.
- Selecci├│n por rango con Shift+clic basada en un ancla de selecci├│n y el orden visible.
- Copia de rutas de los seleccionados mediante men├║ contextual (primera operaci├│n sobre selecci├│n m├║ltiple).
- Apertura de carpetas de los seleccionados mediante men├║ contextual (deduplicaci├│n de carpetas).
- Cantidad configurable de previews visibles (3/5/7/9) con persistencia y actualizaci├│n inmediata de la interfaz.
- Infraestructura de paneles con QSplitter (panel izquierdo placeholder + panel derecho con interfaz existente, PanelPrincipal con minimumSizeHint anulado).
- ├ürbol de navegaci├│n en el panel izquierdo (Etapa 2.1: nodo "Este equipo" + discos del sistema, puramente visual y sin navegaci├│n).
- Expansi├│n de discos y carpetas con carga diferida (Etapa 2.2: un solo nivel por expansi├│n, estado de carga en el nodo, ruta absoluta en cada nodo, ├írbol desacoplado del cat├ílogo).
- Selecci├│n funcional del ├írbol de navegaci├│n (Etapa 2.3: `carpeta_actual()` como interfaz oficial, se├▒al `ruta_seleccionada` notificadora, ra├¡z y placeholders excluidos, selecci├│n conservada al contraer/expandir).
- Integraci├│n de la selecci├│n del ├írbol con la carpeta activa de la aplicaci├│n (Etapa 2.4: `carpeta_seleccionada` como ├║nica fuente de verdad, handler `_al_carpeta_actual_arbol`, sincronizaci├│n ├írbol Ôåö di├ílogo con `seleccionar_ruta`, sin escaneo ni cat├ílogo).
- Persistencia y restauraci├│n del Centro de Navegaci├│n (Etapa 2.5: la carpeta seleccionada se persiste con `guardar_ultima_carpeta` y se reconstruye al iniciar con `revelar_ruta`, expandiendo solo la rama necesaria; restauraci├│n tolerante).
- Integraci├│n del ├írbol con el flujo de escaneo (Etapa 2.6: seleccionar una carpeta v├ílida en el ├írbol o por el di├ílogo inicia autom├íticamente el escaneo mediante `iniciar_escaneo()`, el mismo punto de entrada del bot├│n; un ├║nico disparo por acci├│n; restauraci├│n inicial sin escaneo).
- Verificaci├│n de la paridad de "Incluir subcarpetas" (Etapa 2.7: etapa de validaci├│n sin cambios de producci├│n; ├írbol, bot├│n y di├ílogo respetan de forma id├®ntica la casilla, confirmado por `prueba_subcarpetas_arbol.py`).
- Preferencia independiente de escaneo autom├ítico (Etapa 2.8: casilla "Escaneo autom├ítico" junto a "Incluir subcarpetas", persistida en `configuracion.json` con default `True`; decisi├│n ├║nica `_disparar_escaneo_si_automatico()`; el bot├│n "Escanear carpeta" ignora la preferencia; cuatro combinaciones soportadas).
- Indicadores visuales de carpetas escaneadas (Etapa 2.9: `EstadoNodo` + `ROL_ESTADO` + `_icono_para`, marcado por el pipeline al sincronizar; ├║nicamente visual, sin alterar selecci├│n/expansi├│n/navegaci├│n; el ├írbol no conoce SQLite).
- **Cierre del Bloque de trabajo 2 y aprobaci├│n del Centro de Navegaci├│n.** La **Beta 2 queda congelada** y entra en fase de pruebas reales: sin nuevas funcionalidades, ├║nicamente correcciones de errores detectados mediante el uso.
- **Aprobaci├│n del alcance de la Beta 3 (Etapa B3.0).** Finaliz├│ la fase de
  recopilaci├│n de mejoras del uso real de la Beta 2 y qued├│ **aprobado el
  alcance de la Beta 3**, con su plan de trabajo en `ROADMAP.md` (Bloque de
  trabajo 3). Etapa exclusivamente documental: sin cambios de c├│digo ni
  implementaci├│n de funcionalidades.
- **Tiempo sobre las miniaturas de preview (Etapa B3.1).** Primera mejora de la
  Beta 3 implementada (Bloque A): cada preview muestra el instante temporal
  derivado de la duraci├│n del cat├ílogo, con overlay exclusivamente visual y sin
  cambios de pipeline, esquema SQLite ni recursos.
- **Duraci├│n simplificada (Etapa B3.2).** El campo "Duraci├│n" de la tarjeta se
  presenta con `formatear_tiempo` (m:ss / h:mm:ss / "No disponible"), reutilizando
  la funci├│n de B3.1; cambio solo de presentaci├│n, sin tocar el valor num├®rico,
  SQLite, consultas, pipeline ni miniaturas.
- **Tama├▒o configurable de miniaturas (Etapa B3.3).** Presets Peque├▒o/Mediano/Grande
  con escalado exclusivamente en memoria (reutiliza los pixmaps cargados, sin FFmpeg,
  sin relectura de disco, sin regeneraci├│n ni reescaneo); cambio inmediato
  conservando selecci├│n, scroll y overlays; preferencia persistida con default
  "Mediano".
- **Vista ampliada al posar el mouse (Etapa B3.4).** Popup ├║nico por ventana que
  ampl├¡a (~1.6├ù) la miniatura principal o cualquier preview reutilizando el pixmap
  original en memoria (sin lecturas de disco ni procesos externos); aparece tras un
  retardo, se oculta al salir/scroll/reconstrucci├│n/cierre y se posiciona dentro de
  la pantalla.
- **Preferencias relacionadas con miniaturas (Etapa B3.5).** Bot├│n "PreferenciasÔÇª"
  con di├ílogo modal que expone el retardo de la vista ampliada (discreto, default
  400 ms), aplicado de inmediato y persistido con la infraestructura existente; los
  controles Previews y Tama├▒o permanecen con acceso directo en la barra. Con esto
  el **Bloque A ÔÇö Experiencia visual queda completo**.
- **Tama├▒o "Muy grande" (Etapa B3.6).** Cuarto tama├▒o (512├ù288) incorporado como
  ampliaci├│n de A3, solo ampliando los datos de configuraci├│n (sin refactor ni
  l├│gica espec├¡fica); confirma el desacople dise├▒ado en B3.3. Miniatura principal,
  previews, overlays, vista ampliada, persistencia y cambio inmediato funcionan
  autom├íticamente; "Mediano" sigue siendo el default.
- **Tama├▒o configurable de la vista ampliada (Etapa B3.7).** El factor de ampliaci├│n
  (1.2/1.6/2.0/2.5, default 1.6) pasa a ser configurable desde el di├ílogo
  "Preferencias", aplicado de inmediato y persistido con la infraestructura existente;
  la ampliaci├│n sigue siendo proporcional al tama├▒o de la miniatura y el
  comportamiento por defecto es id├®ntico al previo.
- **Generaci├│n autom├ítica de previews faltantes (Etapa B3.8).** Al aumentar la
  cantidad de previews, las tarjetas crecen din├ímicamente (sin reconstruirse) y la
  cola existente genera ├║nicamente los ├¡ndices faltantes en segundo plano, actualizando
  solo las tarjetas afectadas; sin escaneo ni pipeline. Al disminuir solo se ocultan.
- **Pulido t├®cnico del Bloque A (Etapa B3.9).** Mejoras internas sin funcionalidades
  nuevas: acotado de pixmaps originales en memoria (l├¡mite 1280, sin releer disco ni
  regenerar), transici├│n limpia del popup, helper `_duracion_valida` y eliminaci├│n de
  constantes realmente muertas. Con esto el **Bloque A queda finalizado funcional y
  t├®cnicamente**.
- **Planificaci├│n y congelamiento del Bloque B (Etapa B3.10).** Etapa exclusivamente
  documental: se define el orden de implementaci├│n del Bloque B (B3.11 a B3.17), sus
  dependencias, las decisiones congeladas (Copiar/Pegar/Eliminar, segundo plano, modo
  selecci├│n) y los excluidos. El alcance queda congelado en `ROADMAP.md`.
- **Resumen de selecci├│n (Etapa B3.11).** Primera mejora del Bloque B implementada
  (B6): indicador permanente "X de Y seleccionados" basado ├║nicamente en las tarjetas
  visibles, centralizado en `_actualizar_resumen_seleccion()` e integrado con
  selecci├│n, b├║squeda, carga inicial, reconstrucci├│n y paginaci├│n.
- **Modo selecci├│n + Checks por fila (Etapa B3.12).** Mejoras B1 + B2: bot├│n toggle
  "Modo selecci├│n" en la barra; `QCheckBox` por tarjeta (oculto por defecto, visible
  solo en modo activo); sincronizaci├│n bidireccional centralizada en `_marcar_tarjeta`
  con `blockSignals` (sin reentradas) y `_nombres_seleccionados` como ├║nica fuente de
  verdad. Activarlo/desactivarlo conserva la selecci├│n y el resumen.
- **Atajos b├ísicos (Etapa B3.13).** Parte de B7: Ctrl+A (selecciona solo las tarjetas
  visibles, respetando el filtro; con foco en la b├║squeda no interfiere con el
  `QLineEdit`) y Esc (sale del Modo Selecci├│n, oculta los checks y conserva la
  selecci├│n y el resumen), mediante `QShortcut` sobre la ventana.
- **Copiar (Etapa B3.14).** Mejora B3: copia de los archivos de video seleccionados a
  una carpeta destino elegida por el usuario, en segundo plano (tercer gestor
  `gestor_operaciones`), sin sobrescribir, con resumen final (copiados/omitidos/errores)
  visible en la interfaz. L├│gica pura en `operaciones.copiar_archivos`.
- **Desactivar la vista ampliada (Etapa B3.14a).** Ampliaci├│n del Bloque A: opci├│n
  "Desactivado" (`-1`) en el retardo de la vista ampliada; con ella nunca se inicia el
  timer ni aparece el popup al posar el mouse, y volver a cualquier retardo reactiva la
  funcionalidad.
- **Tama├▒os grandes de la vista ampliada (Etapa B3.14b).** Ampliaci├│n del Bloque A:
  factores 3.0x y 3.5x (m├íximo 3.5x; la vista ampliada puede ocupar pr├ícticamente toda
  la pantalla, acotada por `_posicion_vista`); integraci├│n por datos, sin tratamiento
  especial, default 1.6.
- **Pegar (Etapa B3.15).** Mejora B4: pega en la carpeta actual los archivos copiados
  internamente (portapapeles interno `_portapapeles`, alimentado al copiar), en segundo
  plano reutilizando `gestor_operaciones`, con un ├║nico di├ílogo de colisi├│n
  ("Omitir"/"Cancelar", nunca sobrescribe), resumen final en la interfaz y
  **resincronizaci├│n incremental**: la cadena existente (tama├▒os ÔåÆ FFprobe ÔåÆ miniaturas
  ÔåÆ guardado ÔåÆ sincronizaci├│n ÔåÆ recarga) se reutiliza ├║nicamente para los archivos
  pegados, sin reescaneo completo. L├│gica pura en `operaciones.pegar_archivos`.
- **Eliminar (Etapa B3.16).** Mejora B5: env├¡a los archivos seleccionados a la
  **Papelera de reciclaje de Windows mediante la API nativa `SHFileOperationW` v├¡a
  `ctypes`** (sin dependencias externas; nunca borrado permanente), con un ├║nico di├ílogo
  de confirmaci├│n ("Eliminar"/"Cancelar", default Cancelar), en segundo plano
  reutilizando `gestor_operaciones` (`TareaEliminarArchivos`), resumen final en la
  interfaz y **actualizaci├│n incremental del cat├ílogo** que reutiliza la sincronizaci├│n
  existente (detecta ausentes y los elimina) + recarga, **sin reescaneo completo**.
  L├│gica pura en `operaciones.eliminar_archivos`.
- **Atajos de operaciones (Etapa B3.17).** Mejora B7 (completada): **Ctrl+C**, **Ctrl+V**
  y **Supr** vinculados respectivamente a Copiar, Pegar y Eliminar mediante `QShortcut`
  (patr├│n B3.13). Cada atajo **reutiliza directamente** `_iniciar_copia()`,
  `_iniciar_pegar()` y `_iniciar_eliminar()`, sin l├│gica paralela ni validaciones
  duplicadas (las existentes cubren sin selecci├│n, sin portapapeles y gestor ocupado).
  Con foco en la b├║squeda se **preserva el comportamiento nativo del `QLineEdit`**
  (`copy()`/`paste()`/`del_()`), replicando el criterio de Ctrl+A.
- **Correcci├│n t├®cnica del Bloque B (Etapa B3.18).** Corrige la condici├│n de carrera
  detectada en la auditor├¡a (punto I1): `_procesar_archivos_pegados` y
  `_procesar_archivos_eliminados` **capturan la carpeta al inicio** de la operaci├│n y la
  fijan en el override temporal `_carpeta_sincronizacion`; `_iniciar_sincronizacion(carpeta=None)`
  resuelve la carpeta por **par├ímetro ÔåÆ override ÔåÆ carpeta actual** y la sincronizaci├│n usa
  exactamente la carpeta de la operaci├│n aunque el usuario cambie de carpeta durante la
  cadena. El override se limpia autom├íticamente (`_iniciar_sincronizacion`, `_limpiar_cadena`
  e `iniciar_escaneo`), evitando reutilizaciones accidentales y sin modificar el
  comportamiento normal del pipeline.
- **Infraestructura de progreso (Etapa B3.20).** Primera etapa del Bloque C: cambio
  **aditivo** en `tareas.py` ÔÇö `TareaBase.progreso = Signal(int, int)` (`(procesado, total)`,
  `total <= 0` = indeterminado), helper `reportar_progreso`, `GestorTareas.tarea_progreso`
  con reenv├¡o por `_RelayTarea` y el mismo criterio del token `_vigente` (descarta emisiones
  tard├¡as). `ejecutar()` intacto y ninguna tarea emite progreso todav├¡a: sin cambio visible.
  La se├▒al queda desacoplada de la interfaz para su uso en B3.21 y B3.22.
- **Progreso real del pipeline de escaneo (Etapa B3.21).** La cadena principal informa
  progreso real en **tama├▒os, FFprobe, miniaturas y guardado** mediante **callbacks opcionales
  de progreso** en las funciones puras de `escanear_videos` (sin Qt ni bucles movidos a las
  tareas; sin callback el comportamiento es id├®ntico). `_mostrar_progreso()` restablece
  siempre el modo indeterminado y `_al_progreso_pipeline` (conectado a `gestor.tarea_progreso`)
  fija `setRange(0, total)` + `setValue(procesado)`. Escaneo, sincronizaci├│n y recarga
  permanecen indeterminados por decisi├│n.
- **Progreso real de las operaciones de archivos (Etapa B3.22).** Copiar, Pegar y Eliminar
  informan progreso real por archivo: callbacks opcionales `on_progreso` en las tres funciones
  puras de `operaciones.py` (sin Qt; incluye omitidos y errores); las tres tareas pasan
  `self.reportar_progreso`; `gestor_operaciones.tarea_progreso` se conecta al **mismo handler**
  `_al_progreso_pipeline` (sin l├│gica paralela). Se incorpora la **exclusi├│n mutua** entre
  operaciones y pipeline principal (guard en los handlers y en la habilitaci├│n de los botones).
- **Pulido visual del sistema de progreso (Etapa B3.23).** La barra muestra simult├íneamente el
  nombre de la etapa, la cantidad "N de M" y el porcentaje mediante el formato detallado
  `"{etapa} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar`, aplicado **una
  sola vez por etapa** en `_al_progreso_pipeline`. `_mostrar_progreso` guarda `_texto_progreso`
  y reinicia `_progreso_detallado`; las etapas sin emisi├│n (escaneo, sincronizaci├│n, recarga)
  siguen indeterminadas con texto simple. Sin cambios en tareas ni infraestructura. Con esto
  el **Bloque C ÔÇö Progreso queda completo**.
- **Infraestructura de selecci├│n de carpetas (Bloque 4, Etapa 1).** Clase pura
  `SeleccionCarpetas` con el conjunto de rutas como ├║nica fuente de verdad, persistencia en
  configuraci├│n (`carpetas_seleccionadas`), restauraci├│n al iniciar con descarte autom├ítico de
  rutas inexistentes y API `seleccionar`/`deseleccionar`/`alternar`/`limpiar`/`seleccionar_todas`/
  `obtener_seleccion`. Sin ├írbol, sin UI, sin cambios en escaneo/SQLite/pipeline. Es la base de
  la "Selecci├│n personalizada" del Bloque de trabajo 4.
- **Modo de selecci├│n del ├írbol y herramientas de selecci├│n r├ípida (Bloque 4, entrega conjunta
  Etapas 2-3).** `ArbolNavegacion` se enlaza a `SeleccionCarpetas`: toggle "Modo selecci├│n" que
  muestra checks por nodo sincronizados con el conjunto (sin alterar carpeta activa, navegaci├│n
  ni escaneos; con el modo desactivado el ├írbol es id├®ntico al actual). Herramientas r├ípidas:
  "Seleccionar todas" del nivel, "Deseleccionar todas", "Invertir" y men├║ contextual
  (Seleccionar/Deseleccionar: hasta aqu├¡, desde aqu├¡ hasta el final) sobre los hermanos
  ordenados. Todas materializan **rutas** en `SeleccionCarpetas`, sin intervalos ni estructuras
  paralelas.
- **Escaneo multicarpeta (Bloque 4, Etapa 4).** `iniciar_escaneo(carpetas=None)` acepta una
  lista de carpetas y encadena el pipeline existente **una vez por carpeta** (cola secuencial),
  produciendo la uni├│n en el cat├ílogo; deduplicaci├│n de carpetas y modo tradicional id├®ntico.
- **Sincronizaci├│n multicarpeta (Bloque 4, Etapa 5).** Se elimina por completo el flag temporal
  `_omite_sincronizacion` y se implementa una **sincronizaci├│n real por cada carpeta del alcance**
  efectivo: `detectar_diferencias(..., carpetas_protegidas)` sincroniza **por ruta** en modo
  multicarpeta (una carpeta no elimina registros de otras ra├¡ces del mismo alcance; el modo
  tradicional permanece id├®ntico); `_alcance_sincronizacion` es el mismo conjunto efectivo que la
  cola de escaneo; la **normalizaci├│n del alcance efectivo** (`_alcance_efectivo`/`_ruta_contiene`)
  elimina ra├¡ces descendientes redundantes cuando "Incluir subcarpetas" est├í activado (comportamiento
  ON/OFF diferenciado), y la **transici├│n A ÔåÆ A+B ÔåÆ A** queda verificada contra SQLite. Sin cambios
  de esquema SQLite.
- **Unificaci├│n del selector de alcance (Bloque 4, Etapa 6).** El checkbox "Incluir subcarpetas" es
  reemplazado por un **selector de modo ├║nico** (`combo_modo_alcance`) con tres opciones ÔÇö "Solo
  carpeta actual", "Carpeta actual y todas las subcarpetas" y "Selecci├│n personalizada" ÔÇö como
  **├║nica fuente de verdad visible** del alcance; persistencia (`modo_alcance`) y **migraci├│n
  retrocompatible** desde el booleano antiguo; el checkbox queda como **adaptador de compatibilidad
  oculto**.
- **Auditor├¡a integral del Bloque 4 y cierre funcional de la Beta 3 (Bloque 4, Etapa 7).**
  Auditor├¡a final con la bater├¡a completa de suites: se detect├│ y **corrigi├│ la regresi├│n de
  `_duracion_valida`** (restaurado `duracion > 0`; la duraci├│n 0 vuelve a ser inv├ílida), se
  incorpor├│ la verificaci├│n integrada de transiciones de modo y se confirm├│ el resto del Bloque 4
  sin problemas. Con esto la **Beta 3 queda funcionalmente cerrada y congelada** sobre el c├│digo
  definitivo.
- **Correcci├│n de la regresi├│n de previews (cierre de la Beta 3).** El subsistema de previews
  deja de depender de `carpeta_seleccionada`: cada video usa su propia carpeta real del cat├ílogo
  (columna `ruta` incorporada a `listar_videos`/`listar_videos_paginado`); carpeta ├║nica,
  carpeta + subcarpetas y selecci├│n personalizada (una o varias carpetas) generan previews
  correctamente, verificadas por `prueba_previews_multicarpeta.py` (5/5).
- **B4.1 ÔÇö Exploraci├│n temporal interactiva y marcadores visuales.** Primera etapa del ciclo
  Beta 4 (rama `beta4`). Cada tarjeta gana un control "Expandir/Colapsar" con **una sola
  tarjeta expandida a la vez**; la segunda fila expandida es una **superficie temporal** que
  mapea horizontalmente 0ÔÇô100 % de la duraci├│n (izquierda = inicio, derecha = final), con
  marcador m├│vil que acompa├▒a al cursor, tiempo correspondiente a la posici├│n, preview
  existente m├ís cercana al instante (por tiempo real) y una **preview m├│vil** que acompa├▒a
  horizontalmente al cursor (funciona con previews horizontales y verticales; el extremo
  derecho siempre es alcanzable porque la superficie se acota al ancho visible). El clic sobre
  la superficie crea **marcadores temporales libres** que conservan tiempo real, marca visual
  y miniatura fijada (solapamiento permitido; persisten en memoria mientras vive la tarjeta
  durante la sesi├│n); el clic derecho sobre la miniatura fijada o sobre la marca roja elimina
  **├║nicamente** ese marcador. `mouseMove` = **cero FFmpeg + cero acceso a disco**. Sin
  persistencia, sin cambios de SQLite ni de `escanear_videos.py`.
- **B4.2 ÔÇö Persistencia de marcadores temporales por video.** Segunda etapa del ciclo
  Beta 4 (rama `beta4`). Los marcadores creados por el usuario se almacenan
  **permanentemente en SQLite** en la tabla `marcadores_video` (`id INTEGER PRIMARY KEY
  AUTOINCREMENT`, `video_id INTEGER NOT NULL`, `tiempo REAL NOT NULL`, ├¡ndice
  `idx_marcadores_video_video_id_tiempo`), relacionados mediante **`videos.id`** (la columna
  `id` se expone en el contrato de lectura: `listar_videos` y `listar_videos_paginado`
  devuelven ahora **9 campos**); reaparecen entre sesiones, pueden eliminarse
  permanentemente y recuperan su representaci├│n visual usando las previews disponibles.
  Sin cascade autom├ítico, sin nombre/ruta como identidad, sin imagen persistida, sin
  nota/color/tipo ni JSON. **Pol├¡tica de conservaci├│n**: reescaneo del mismo registro ÔåÆ
  conserva; cambios de metadatos ÔåÆ conserva; reemplazo silencioso manteniendo el mismo
  registro ÔåÆ conserva; si el registro de video desaparece los marcadores **no** se eliminan
  autom├íticamente (pueden quedar hu├®rfanos); no existe a├║n reasociaci├│n de
  movidos/renombrados ni por nombre/ruta. Deliberado para evitar p├®rdida autom├ítica de datos
  creados por el usuario. `visor_videos.py` **no ejecuta SQLite directamente**: mantiene la
  representaci├│n optimista en memoria, carga marcadores al expandir y persiste altas/bajas con
  un gestor dedicado (`gestor_marcadores`) usando `marcador_id` como identidad t├®cnica
  persistente. La carga desde SQLite se trata como **snapshot potencialmente antiguo** y se
  **reconcilia** conservando altas/bajas locales pendientes, IDs persistentes existentes y
  deduplicando por la misma tolerancia temporal de la interacci├│n (carreras cubiertas:
  crear+borrar antes de terminar el INSERT,   cargar+crear, carga+marcador equivalente,
  carga+baja local y recuperaci├│n tras DELETE fallido).
- **B4.3.1 ÔÇö Motor de cach├® temporal versionada y reanudable.** Tercera etapa del ciclo
  Beta 4 (rama `beta4`), primera subetapa de **B4.3 ÔÇö Cach├® densa de exploraci├│n temporal**.
  Implementa el **motor de disco** de la cach├® densa de exploraci├│n en `exploracion_cache.py`
  (nuevo): estructura `miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` +
  `f{ms:010d}.jpg`), **versiones aisladas** calculadas por *fingerprint* de metadatos baratos
  (ruta normalizada + tama├▒o + `mtime_ns` + duraci├│n; SHA-256 reducido a 16 hex, **no** es hash
  de contenido), **reanudaci├│n** de generaciones incompletas (un JPEG presente est├í completo:
  escritura at├│mica temporal ÔåÆ `os.replace`), **invalidaci├│n no destructiva** (el cambio de
  fingerprint crea una versi├│n distinta; nada se borra autom├íticamente), `meta.json` coherente
  con la versi├│n (solo se escribe al completar) y una invocaci├│n de FFmpeg por fotograma como
  **mecanismo actual de validaci├│n** (no necesariamente el final desde la UI).
  `exploracion_temporal.py` incorpora la **densidad** (`cantidad_fotogramas` =
  `clamp(duraci├│n / 2 s, 40, 200)`) y el **orden progresivo** (`tiempos_objetivo` por bisecci├│n
de huecos) con `fotograma_mas_cercano` por `bisect`. Sin UI (la integraci├│n es **B4.3.2**),
  sin SQLite (`videos`, `marcadores_video` y `biblioteca.db` intactos) y sin acoplamiento con
  `escanear_videos`. Costo de versi├│n Ôëê 13 ┬Ás.
- **B4.3.2 ÔÇö Cobertura r├ípida as├¡ncrona integrada con la UI (Etapa 1).** Cuarta etapa del ciclo
  Beta 4 (rama `beta4`), segunda subetapa de **B4.3 ÔÇö Cach├® densa de exploraci├│n temporal**.
  La tarjeta consume el motor de B4.3.1 con una **tarea as├¡ncrona dedicada**
  (`TareaExploracionDensa` en `tareas_videos.py`) que genera los **`FOTOGRAMAS_INICIALES = 15`**
  provisionales y emite **resultados parciales progresivos** (`QImage` decodificada en el
  worker; la conversi├│n final a `QPixmap` ocurre en la GUI). Mientras no hay cach├® la superficie
  temporal conserva el **fallback a las previews normales** y la mejora es **progresiva**.
  `mouseMove` selecciona **exclusivamente en RAM** (cero FFmpeg, cero disco); la imagen mostrada
  es la **m├ís cercana** entre la preview normal y la densa (la preview normal gana el empate).
  **Cancelaci├│n cooperativa** al cambiar de video, **aislamiento AÔåÆB** (cada tarjeta usa su
  cach├®), **colapso que libera las referencias densas de RAM** y **reexpansi├│n que reutiliza la
  cach├®** (sin regenerar). Los **marcadores** conservan su tiempo/id y pueden mejorar
  visualmente al llegar fotogramas densos. **Validaci├│n visual manual AÔÇôG aprobada por Marcos**
  en el PC de desarrollo y validada en la **notebook objetivo** con un video real de ~56 min.
- **B4.3.2 ÔÇö Etapa 2: Densidad secundaria adaptativa.** Quinta etapa del ciclo Beta 4 (rama
  `beta4`), tercera subetapa de **B4.3 ÔÇö Cach├® densa de exploraci├│n temporal**. Tras el
  **benchmark de estrategias** sobre un video de 56 min, por **decisi├│n de producto** se adopt├│
  la **generaci├│n individual y secuencial: un FFmpeg por objetivo, sin batch, sin paralelismo**.
  `exploracion_cache.py` centraliza los par├ímetros **provisionales**
  (`PASO_SEGUNDOS_DENSIDAD = 30.0`, `MINIMO_FOTOGRAMAS_DENSIDAD = 15`,
  `MAXIMO_FOTOGRAMAS_DENSIDAD = 200`, `FOTOGRAMAS_INICIALES = 15`) y `objetivo_total_densidad`
  = `clamp(max(15, ceil(d/30)), 15, 200)`. `TareaExploracionDensa._trabajo()` genera en **dos
  fases secuenciales**: la **fase r├ípida** (los 15 prioritarios, Etapa 1 intacta) y solo despu├®s,
  sin cancelarse, la **fase secundaria** que reutiliza lo existente y completa ├║nicamente los
  faltantes hasta el objetivo de densidad; ambas fases emiten `resultado_parcial` progresivo sin
  duplicados. **Verificado en PC de desarrollo** (app real + FFmpeg real, video ~56 min): primer
  fotograma prioritario Ôëê0.10 s, 15 prioritarios Ôëê1.13 s, primer secundario Ôëê1.21 s (despu├®s de
  la fase r├ípida), total 112 Ôëê8.39 s, reexpansi├│n Ôëê0.08 s sin regenerar, scrub fluido desde RAM.
  Los par├ímetros **siguen siendo provisionales** (no congelados) y **no hay configuraci├│n
  visible**; la Etapa 2 recibi├│ su comprobaci├│n y **B4.3 qued├│ validada satisfactoriamente en la
  notebook objetivo**.
- **B4.3.3 ÔÇö Ajustes de interacci├│n y densidad manual.** Sexta etapa del ciclo Beta 4 (rama
  `beta4`), cuarta subetapa de **B4.3 ÔÇö Cach├® densa de exploraci├│n temporal**. (A) **Prioridad
  visual din├ímica**: durante el hover la preview din├ímica queda **por encima** de las
  miniaturas fijas de marcadores (`raise_()` en `_al_instante_exploracion`; `lower()` al salir
  de la superficie v├¡a `eventFilter` del franja); los tiempos/ids de marcadores no cambian y la
  eliminaci├│n por clic derecho sigue funcionando. (B) **Densidad manual**: `QComboBox`
  `Auto | 15 | 30 | 60 | 120 | 200` en la tarjeta expandida; los valores manuales son el
  **total objetivo independiente de la duraci├│n** (30 s ÔåÆ Auto 15, manual 60 ÔåÆ 60, manual 120 ÔåÆ
  120); siempre los **15 prioritarios primero**; **aumentar** reutiliza lo existente (15ÔåÆ60
  reutiliza 15 y genera 45; 60ÔåÆ120 reutiliza 60 y genera 60); **disminuir** no borra disco ni
  regenera (la RAM se limita al conjunto objetivo `tiempos_objetivo(duraci├│n, cantidad_actual)`
  y la cach├® puede contener un **superset** cuyo subconjunto decide la tarea ÔÇö emite/decodifica
  solo el permitido); **volver a Auto** recalcula el objetivo autom├ítico y conserva los extras
  de disco. El valor es **por tarjeta/sesi├│n** (se conserva en colapso/reexpansi├│n; vuelve a
  Auto si se reconstruye por recarga), **sin SQLite ni persistencia en `configuracion.json`**.
  Generaci├│n individual/secuencial, un FFmpeg activo, mouseMove solo RAM. Pruebas:
  `prueba_exploracion_b433.py` **22/22**.

## Pendientes prioritarios

1. ~~Mejorar el feedback visual del procesamiento (barra de progreso,~~
   ~~estado visible de tareas en curso).~~ **Implementado.**
2. ~~Incorporar selecci├│n visual de filas (selecci├│n simple y m├║ltiple,~~
   ~~acciones sobre videos seleccionados).~~ **Implementado.**
3. Evaluar y optimizar el rendimiento con colecciones grandes de videos.
4. Paginaci├│n completa autom├ítica del cat├ílogo (scroll infinito,
   b├║squeda en SQL desde la interfaz, ordenamiento configurable).
5. Deduplicaci├│n de nombres repetidos en el plan de sincronizaci├│n.

Las funcionalidades futuras pendientes se detallan en `ROADMAP.md`.
Los problemas t├®cnicos vigentes se detallan en `DOCUMENTO_TECNICO.md` ┬º8.

## Deuda t├®cnica

- Crecimiento y duplicaci├│n de infraestructura entre las suites de
  prueba (helpers, conectores y patrones repetidos).
- Pendiente documental: reducir progresivamente el nivel de detalle de
  implementaci├│n en `DOCUMENTO_TECNICO.md`, conservando la informaci├│n
  arquitect├│nica pero eliminando detalles que ya refleja el c├│digo fuente.
- La selecci├│n se restaura autom├íticamente despu├®s de reconstruir
  completamente las tarjetas (`_reemplazar_tarjetas`), pero solo para
  los nombres que siguen existiendo en el nuevo conjunto.
- **Rutas Windows con nombres cortos 8.3** (p. ej. `MARCOS~1`): la
  restauraci├│n del ├írbol (`revelar_ruta`) no las empareja con los nombres
  largos que carga el ├írbol y cae en el comportamiento tolerante (la
  aplicaci├│n inicia sin carpeta seleccionada, sin inconsistencias). No
  afecta el funcionamiento normal; considerarla en una futura etapa de
  robustez del Centro de Navegaci├│n (registrada tambi├®n en
  `DOCUMENTO_TECNICO.md` ┬º8, problema 13).
- **`prueba_aplicar_incorporaciones.py` T15** ÔÇö falla preexistente y
  ambiental: opera sobre una copia de la base real `biblioteca.db` y asume
  filas preexistentes con `tamano_bytes = NULL`; la base real actual tiene
  `tamano_bytes` poblado. No atribuible a etapas recientes (verificado en la
  Etapa 2.6); la suite no modifica ese subsistema y el resto del pipeline
  funciona correctamente. **Resuelta en la correcci├│n previa al cierre de
  B4.12**: la comparaci├│n de filas preexistentes se hizo robusta al esquema
  por nombre de columna (vigente con `mtime_ns` y `tamano_bytes`); suite 15/15.
- **Estado de "escaneada" por sesi├│n** (Etapa 2.9): el indicador de carpetas
  escaneadas vive en memoria (`carpetas_escaneadas` del visor) y se pierde al
  reiniciar; no se persiste ni se deriva del cat├ílogo (requerir├¡a cambios de
  esquema o en m├│dulos restringidos). La API (`EstadoNodo` + `_icono_para`) ya
  est├í preparada para futuros estados; documentada como deuda t├®cnica para una
  etapa espec├¡fica de persistencia del estado (registrada tambi├®n en
  `DOCUMENTO_TECNICO.md` ┬º8, problema 14).
- **`prueba_persistencia_carpeta.py` T11 y T16** ÔÇö falla **preexistente** (detectada
  en la Etapa B3.3, verificada tambi├®n en HEAD limpio): los tests asumen que al
  iniciar la aplicaci├│n sin preferencias no se crea `configuracion.json`, pero la
  restauraci├│n de `escaneo_automatico` (default `True`, Etapa 2.8) escribe el
  archivo en el arranque. **Resuelta en la correcci├│n previa al cierre de B4.12**:
  el contrato del test pas├│ a "sin carpeta guardada" (el archivo puede existir por
  el default, pero no debe contener `CLAVE_CARPETA`); suite 20/20.
- **`prueba_eliminar_candidatos.py` T02** ÔÇö falla **preexistente** (verificada en el
  HEAD base limpio `507ec81` durante el cierre de B4.5): es una verificaci├│n AST de
  estructura (`eliminar_candidatos` definida solo en `escanear_videos`, sin estar
  definida ni importada en `tareas_videos`/`visor_videos`, y sin identificadores
  prohibidos) cuyo contrato no coincide con el estado actual del c├│digo. **Resuelta
  en la correcci├│n previa al cierre de B4.12**: la regla AST qued├│ precisa
  excluyendo las tareas leg├¡timas de marcadores (`TareaEliminarMarcador`, B4.2);
  suite 16/16.
- **Fallos VLC ambientales reales** ÔÇö deuda t├®cnica **preexistente y ambiental**,
  registrada para su estudio en una etapa futura, **no atribuible a B6.3** ni a
  ninguna etapa reciente de Beta 6: las suites de reproducci├│n VLC (que lanzan
  procesos VLC reales y dependen de `start-time`/`stop-time`, seek por keyframes y
  timing de procesos) mostraron fallos intermitentes en ejecuci├│n real:
  `prueba_reproduccion_segmento_b56.py` P27 (26/27), `prueba_bucle_segmento_b57.py`
  P23 (23/24) y `prueba_secuencia_segmentos_b58.py` P27/P28 (27/29). No corregidas
  en esta etapa documental (fuera de alcance) ni en B6.3; quedan como deuda
  ambiental pendiente de una etapa espec├¡fica de estabilizaci├│n de las pruebas VLC.

## Pr├│xima fase

La **Beta 6** est├í **cerrada y publicada** sobre la rama `beta6` (commit `7d85e94bb8b617209a155e5b1086d1d38f4784f8`; tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios; identidad `Beta 6 - B6.12`). La **Beta 7 ÔÇö "Organizaci├│n y operaciones de archivos"** est├í **cerrada y publicada en B7.13** sobre rama `beta7` (commit oficial de cierre funcional `f9976d3b3b68a197bf8e9d29a4ecc670f48a9709` `B7 Cerrar Beta 7 B7.13`; tag `v7.0-beta` publicado y resolviendo permanentemente a `f9976d3`; rama `beta7` publicada y puede contener reconciliaciones documentales posteriores al tag; repositorio PUBLIC, GitHub Release `v7.0-beta` prerelease publicada sin binarios; identidad `Beta 7 - B7.13`; validaci├│n del instalador Beta 7 PENDIENTE). Estado
detallado en "Fase actual ÔÇö Beta 7"; el alcance completo **B7.0ÔÇôB7.13** y la direcci├│n post-Beta 7 est├ín en
`ROADMAP.md`.

## Documentos del proyecto

- `REGLAS_PROYECTO.md` ÔÇö reglas permanentes de desarrollo.
- `METODOLOGIA_DESARROLLO.md` ÔÇö protocolo detallado de desarrollo y auditor├¡a
  (operaci├│n del Bridge, estado, evidencia, autorizaciones).
- `DOCUMENTO_TECNICO.md` ÔÇö arquitectura y referencia t├®cnica.
- `ROADMAP.md` ÔÇö funcionalidades previstas.
- `VISION_PRODUCTO.md` ÔÇö decisiones estrat├®gicas y filosof├¡a.
- `HISTORIAL_PROYECTO.md` ÔÇö registro cronol├│gico de etapas.
- `ESTADO_PROYECTO.md` ÔÇö este documento.
