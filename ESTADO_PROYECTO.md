# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** quedó **aprobado el alcance de la Beta 3** (Etapa B3.0,
exclusivamente documental) y la **implementación de la Beta 3 está en
marcha**: el **Bloque A — Experiencia visual** quedó **completo** con las
mejoras B3.1 ("Tiempo sobre las miniaturas de preview"), B3.2 ("Duración
simplificada"), B3.3 ("Tamaño configurable de miniaturas"), B3.4 ("Vista
ampliada al posar el mouse") y B3.5 ("Preferencias relacionadas con
miniaturas"). El plan de trabajo se documenta en `ROADMAP.md` (Bloque de
trabajo 3). La Beta 2 permanece como la última versión estable publicada.

## Último commit aprobado

**Mensaje:** Agregar preferencias relacionadas con miniaturas (Etapa B3.5)

**Etapa:** Preferencias relacionadas con miniaturas (B3.5, Bloque A — Experiencia visual):
- `visor_videos.py` — `PreferenciasDialog(QDialog)` con el retardo de la vista
  ampliada (Inmediato 0 / 250 / 400 / 600 ms, default 400); botón "Preferencias…"
  en la barra junto a los controles Previews y Tamaño (que permanecen intactos);
  `_abrir_preferencias` y `_aplicar_retardo_vista_ampliada(ms)` (persiste y aplica
  de inmediato el intervalo del timer). Sin reinicio, sin reconstrucción del
  catálogo, sin tocar selección/scroll.
- `configuracion.py` — `CLAVE_RETARDO_VISTA_AMPLIADA`, `guardar_retardo_vista_ampliada`
  y `obtener_retardo_vista_ampliada` (default 400; aditivo, sin migración).
- `prueba_preferencias_miniaturas.py` — 31 verificaciones de la etapa.

**Pruebas superadas:** `prueba_preferencias_miniaturas.py` 31/31 (persistencia y
tolerancia, diálogo con valores discretos, combos Previews/Tamaño preservados,
aplicación inmediata y persistencia, flujo aceptar/cancelar, restauración al
iniciar, vista ampliada con el retardo configurado, selección y scroll conservados);
regresiones `prueba_cantidad_previews.py` 14/14, `prueba_tamano_miniaturas.py` 32/32,
`prueba_vista_ampliada.py` 24/24, `prueba_tiempo_previews.py` 35/35,
`prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
`prueba_pagina_siguiente.py` 20/20, `prueba_seleccion_visual.py` OK,
`prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
`prueba_restauracion_seleccion.py` 15/15, `prueba_persistencia_subcarpetas.py` 10/10,
`prueba_smoke.py` OK, `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15.
Ejecución real de `visor_videos.py` con `biblioteca.db`: apertura del diálogo,
cambio de retardo aplicado y persistido, cancelar conserva el valor, persistencia
tras reiniciar, Previews (5→3→5) y Tamaño (Grande 225) funcionando, selección y
scroll conservados, cierre limpio (exit 0).

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

**Revisión funcional del Bloque A (Experiencia visual).** El Bloque A quedó
**completo** con las Etapas B3.1 a B3.5. Antes de continuar con la Beta 3 se
realizará una revisión funcional completa del bloque para verificar que las
cinco mejoras funcionen de forma coherente como conjunto y decidir el siguiente
bloque de trabajo, siguiendo el plan de `ROADMAP.md` (Bloque de trabajo 3).

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
