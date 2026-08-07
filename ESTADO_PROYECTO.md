# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** quedó **aprobado el alcance de la Beta 3** (Etapa B3.0,
exclusivamente documental) y la **implementación de la Beta 3 está en
marcha**: el **Bloque A — Experiencia visual** quedó **completo funcional y
técnicamente** (B3.1 a B3.9, más las ampliaciones **B3.14a** "Desactivado" y
**B3.14b** "tamaños 3.0x/3.5x" de la vista ampliada), el **Bloque B —
Selección y operaciones** quedó **completo** (B3.11 a B3.17 más la corrección
técnica **B3.18**) y el **Bloque C — Progreso** quedó **completo**
(**B3.20–B3.23**), con lo que la **Beta 3 queda funcionalmente cerrada**
salvo problemas en las pruebas finales. Además está en marcha el **Bloque de
trabajo 4 — Catálogo por selección de carpetas**: implementadas la **Etapa 1
— Infraestructura de selección**, la **entrega conjunta Etapas 2-3 — Modo
de selección del árbol y herramientas de selección rápida** y la **Etapa 4 —
Escaneo multicarpeta** (con la limitación temporal de omisión de
sincronización, a eliminar en la Etapa 5). El plan de trabajo se documenta
en `ROADMAP.md` (Bloques de trabajo 3 y 4). La Beta 2 permanece como la
última versión estable publicada.

## Último commit aprobado

**Mensaje:** Implementar el escaneo multicarpeta del catálogo (Etapa 4, Bloque 4)

**Etapa:** Escaneo multicarpeta (Bloque de trabajo 4, Etapa 4):
- `visor_videos.py` — `iniciar_escaneo(carpetas=None)` acepta una lista (o cadena, o `None` →
  carpeta activa), filtra carpetas inexistentes y **deduplica**; `_iniciar_escaneo_carpeta`
  ejecuta la cadena existente por carpeta; cola secuencial `_cola_carpetas_escaneo`
  (avance en `_al_tarea_finalizada`); `_omite_sincronizacion` (**limitación temporal**):
  en multicarpeta se omite la sincronización monocarpetas (que eliminaría registros de otras
  carpetas) y `_al_resultado_guardado` va directo a la recarga. `boton_escanear` reconectado
  con lambda (Qt pasa `bool`). Modo tradicional idéntico; sin auto-activación desde la interfaz.
- `prueba_escaneo_multicarpeta.py` — 12 verificaciones de la etapa (nuevo), incluida la
  transición de modos A → A+B (selección) → A solicitada por la auditoría.

**Pruebas superadas:** `prueba_escaneo_multicarpeta.py` 12/12 (escaneo tradicional sin
regresión y marcado de escaneada; multicarpeta produce la unión; repetición de carpetas sin
duplicados; carpetas inexistentes ignoradas; lista vacía/inválida no escanea; la base refleja
la unión; limpieza del flag; transición A → A+B → A); regresiones relevantes OK:
`prueba_escaneo.py` 12/12, `prueba_escaneo_guardado.py` 24/24, `prueba_escaneo_interfaz.py`
36/36, `prueba_escaneo_automatico.py` 19/19, `prueba_ffprobe.py` 12/12, `prueba_guardar.py`
19/19, `prueba_guardar_videos.py` 34/34, `prueba_lectura.py` 15/15, `prueba_lectura_paginada.py`
32/32, `prueba_progreso_pipeline.py` 11/11, `prueba_progreso_operaciones.py` 12/12,
`prueba_sincronizacion_interfaz.py` 18/18, `prueba_recarga_catalogo.py` 20/20,
`prueba_interfaz_asincrona.py` 29/29, `prueba_tamano_archivo.py` 15/15, `prueba_progreso.py`
13/13, `prueba_progreso_visual.py` OK, `prueba_progreso_visual_pulido.py` 7/7,
`prueba_modo_seleccion_arbol.py` 16/16, `prueba_herramientas_seleccion_arbol.py` 20/20,
`prueba_seleccion_carpetas.py` 22/22, `prueba_arbol_navegacion.py`, `prueba_seleccion_carpeta.py`
26/26, `prueba_carpeta_actual.py` 19/19, `prueba_persistencia_arbol.py` 15/15,
`prueba_persistencia_subcarpetas.py` 10/10, `prueba_expansion_carpetas.py` 35/35,
`prueba_atajos_operaciones.py` 16/16, `prueba_seleccion.py` 28/28,
`prueba_restauracion_seleccion.py` 15/15, `prueba_duracion_simplificada.py` 23/23,
`prueba_smoke.py` OK.

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
  **Limitación temporal:** en multicarpeta se omite la sincronización monocarpetas (eliminaría
  registros de otras carpetas); se eliminará por completo en la **Etapa 5**.

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

**Etapa 5 — Sincronización multicarpeta** (Bloque de trabajo 4). Eliminar la limitación
temporal introducida en la Etapa 4 (omisión de sincronización en el escaneo multicarpeta) y
hacer que la reconciliación del catálogo sea consistente con el conjunto seleccionado
(reconciliación por carpeta del alcance, indicadores por carpeta), según `ROADMAP.md` (Bloque
de trabajo 4). Es la etapa más importante del bloque: con ella el comportamiento multicarpeta
queda completamente consistente. Su definición detallada se realizará con la inspección técnica
previa, en bloques pequeños, verificables y acumulativos, sin adelantar funcionalidades
excluidas del alcance ni agregar funcionalidades nuevas fuera del plan aprobado.

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
