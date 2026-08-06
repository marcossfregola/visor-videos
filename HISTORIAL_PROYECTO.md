# HISTORIAL DEL PROYECTO — Visor de Videos

Registro cronológico inmutable de cada etapa aprobada del proyecto.
Orden cronológico inverso (más reciente primero).

---

## 47. Árbol de navegación en el panel izquierdo (Etapa 2.1)

- **Fecha:** 2026-08-06
- **Objetivo:** Reemplazar el placeholder del panel izquierdo por un árbol real que constituya la
  infraestructura inicial del futuro Centro de Navegación. Mostrar únicamente el nodo raíz "Este
  equipo" y los discos disponibles del sistema. Sin navegación, sin escaneo, sin selección
  funcional y sin integración con lógica existente.
- **Archivos creados:**
  - `arbol_navegacion.py` — módulo de interfaz con `discos_disponibles()` (enumeración por
    `os.path.exists` sobre A–Z, solo Windows, sin dependencias externas ni lógica de UI) y
    `ArbolNavegacion(QTreeWidget)` (header oculto, `NoSelection`, raíz "Este equipo" expandida y un
    hijo por disco). Árbol completamente pasivo: sin señales, sin slots y sin navegación.
  - `prueba_arbol_navegacion.py` — verificación de la etapa: raíz "Este equipo", discos
    coincidentes con el sistema, placeholder eliminado, panel derecho funcional, splitter
    redimensionable, clic sobre disco sin ninguna acción y captura de pantalla.
- **Archivos modificados:**
  - `visor_videos.py` — import de `ArbolNavegacion` y reemplazo del `QLabel` placeholder por
    `ArbolNavegacion()` en el panel izquierdo del QSplitter. Sin cambios en el panel derecho ni en
    el pipeline.
  - `DOCUMENTO_TECNICO.md` — nuevo módulo documentado; infraestructura de paneles y constructor
    actualizados con el árbol; sección de dirección futura actualizada; árbol de directorios
    actualizado.
  - `ESTADO_PROYECTO.md` — etapa registrada como completada, actualizadas última etapa aprobada y
    próxima etapa.
  - `ROADMAP.md` — Etapa 2.1 marcada como implementada.
- **Pruebas:** `prueba_arbol_navegacion.py` OK. Regresiones: `prueba_smoke.py` OK,
  `prueba_escaneo_interfaz.py` 36/36, `prueba_persistencia_carpeta.py` 20/20,
  `prueba_cantidad_previews.py` 14/14, `prueba_seleccion_visual.py` OK. Ejecución real de
  `visor_videos.py` con cierre limpio (`exit 0`) y captura programática.
- **Resultado:** El placeholder desapareció y el panel izquierdo muestra el árbol real ("Este
  equipo" → `C:\`) sin ninguna acción al hacer clic. El panel derecho funciona igual y el splitter
  se redimensiona normalmente. Sin carpetas, sin navegación, sin escaneo ni integración (etapas
  siguientes).
- **Commit:** "Implementar arbol de navegacion en el panel izquierdo (Etapa 2.1: Este equipo y discos)"
- **Decisiones importantes:**
  1. **Módulo propio `arbol_navegacion.py`** — infraestructura nueva, no refactorización:
     encapsula la enumeración de discos (lógica pura, sin Qt) y el widget, respetando la
     separación interfaz/lógica (Regla 7) y dejando la base extensible del Centro de Navegación.
  2. **Enumeración por `os.path.exists` sobre A–Z** (no `GetLogicalDrives`): mecanismo stdlib,
     sin dependencias externas, separado de la interfaz.
  3. **Árbol pasivo con `NoSelection`**: el clic no produce ninguna acción funcional; el
     `currentItem` interno de Qt puede cambiar pero no hay highlight ni señales conectadas.

---

## 46. Infraestructura de paneles (QSplitter)

- **Fecha:** 2026-08-06
- **Objetivo:** Implementar la infraestructura de la nueva interfaz mediante un QSplitter
  horizontal que divida la ventana en panel izquierdo de navegación (placeholder) y panel
  derecho con la interfaz actual completa. Etapa exclusivamente estructural, sin
  funcionalidades nuevas.
- **Archivos modificados:**
  - `visor_videos.py` — agregado `QSplitter` y `QSize` a los imports; nueva clase
    `PanelPrincipal(QWidget)` con `minimumSizeHint()` anulado a `QSize(0, 0)` (ver decisión
    arquitectónica abajo); constructor de `VisorVideos` modificado para crear el QSplitter
    con panel izquierdo placeholder (`QWidget`, minWidth=80, maxWidth=400, `QLabel` "Panel
    de navegacion") y panel derecho `PanelPrincipal`; `setHandleWidth(8)` para usabilidad;
    `splitter.handle(1).setCursor(Qt.SplitHCursor)` exclusivamente sobre el handle.
  - `DOCUMENTO_TECNICO.md` — documentada la infraestructura de paneles, `PanelPrincipal` y
    la decisión de anular `minimumSizeHint`.
  - `ESTADO_PROYECTO.md` — etapa registrada como completada, actualizada última etapa
    aprobada y próxima etapa.
- **Pruebas:** `prueba_smoke.py` OK (7 secciones sin regresiones). Verificación manual:
  splitter arrastrable con el mouse, cursor cambia solo sobre el handle, estilo visual
  nativo de Windows, sin scroll horizontal innecesario, catálogo funcionando exactamente
  igual.
- **Resultado:** QSplitter funcional integrado como infraestructura permanente. Panel
  izquierdo placeholder sin lógica. Panel derecho conserva el 100% del comportamiento
  existente. Barra divisoria cómoda de agarrar (8 px) con cursor de redimensionamiento.
  Sin colores ni estilos personalizados.
- **Commit:** "Incorporar infraestructura de paneles con QSplitter (panel izquierdo placeholder + PanelPrincipal)"
- **Decisiones importantes:**
  1. **`PanelPrincipal.minimumSizeHint()` → `QSize(0, 0)`:** El `minimumSizeHint` por
     defecto del panel derecho (~720 px) está dominado por la barra de herramientas
     `fila_carpeta` (8 widgets: botones, checkbox, combo, labels) cuyo `minimumSizeHint`
     combinado fuerza un mínimo de ~703 px + márgenes. Sin la anulación, el QSplitter usa
     ese valor como tamaño mínimo efectivo, bloqueando el arrastre del divisor hacia la
     derecha porque el panel ya está en su mínimo. La anulación a `(0, 0)` permite que el
     splitter solo respete el `minimumWidth` del panel izquierdo (80 px), habilitando el
     arrastre libre en ambas direcciones. Se evaluaron y descartaron dos alternativas:
     `setMinimumWidth(0)` (no funciona porque Qt usa `max(minimumSizeHint, minimumWidth)`)
     y `QSizePolicy.Ignored` (tiene efectos laterales sobre cualquier layout padre, no
     solo el splitter).
  2. **`handleWidth=8` (no 5):** El ancho predeterminado de 5 px resultó demasiado
     delgado para tomar con el mouse en Windows 11/PySide6 6.11.1. Ocho píxeles conserva
     el estilo nativo y es cómodo de agarrar.
  3. **Cursor exclusivo sobre el handle:** `splitter.handle(1).setCursor(Qt.SplitHCursor)`
     asigna el cursor de redimensionamiento únicamente al `QSplitterHandle`, no al splitter
     completo, evitando que el cursor ↔ aparezca sobre toda la aplicación.

---

## 45. Redefinición de la dirección futura de la interfaz

- **Fecha:** 2026-08-05
- **Tipo:** Decisión de producto (no implica cambios de código).
- **Descripción:** Durante el cierre del ciclo de desarrollo de la Beta
  1.0 se redefinió la dirección futura de la interfaz de usuario. Se
  acordó evolucionar hacia una **interfaz modular basada en paneles
  independientes** (QSplitter), con un árbol de carpetas como mecanismo
  principal de navegación y la posibilidad de incorporar progresivamente
  paneles de propiedades, favoritos, etiquetas e IA.
- **Próximas líneas de trabajo:** infraestructura de paneles, árbol de
  carpetas, navegación desde el árbol, tarjetas expandibles,
  ordenamientos y organización.
- **Documentos actualizados:**
  - `VISION_PRODUCTO.md` — ampliada la sección de filosofía del
    producto y agregados los principios de diseño.
  - `ROADMAP.md` — agregadas las secciones «Próximas líneas de trabajo
    previstas» e «Infraestructura futura»; ampliada «Experiencia de
    usuario» con tarjetas expandibles y scroll horizontal.
  - `DOCUMENTO_TECNICO.md` — agregada la sección «Dirección
    arquitectónica futura» con la infraestructura prevista de paneles.
- **Resultado:** La documentación del proyecto refleja ahora la visión
  de largo plazo y permite que cualquier persona, al leer
  `VISION_PRODUCTO.md`, `ROADMAP.md` y `DOCUMENTO_TECNICO.md`,
  comprenda hacia dónde evoluciona el producto y cuál será la primera
  etapa del próximo ciclo de desarrollo.
- **Decisiones importantes:** El proyecto deja de concebirse únicamente
  como un visor de tarjetas y pasa a proyectarse como un entorno de
  trabajo. La exploración visual sigue siendo el objetivo principal;
  la reproducción permanece como función secundaria.

---

## 44. Cantidad configurable de previews visibles (3/5/7/9)

- **Fecha:** 2026-08-05
- **Objetivo:** Permitir al usuario elegir cuántas previews mostrar por video (3, 5, 7 o 9), con persistencia y actualización inmediata de la interfaz sin requerir reescaneo.
- **Archivos modificados:**
  - `escanear_videos.py` — `CANTIDAD_PREVIEWS` de constante `3` a mutable con valor por defecto `CANTIDAD_PREVIEWS_POR_DEFECTO`; setter `configurar_cantidad_previews(n)`; `_nombre_seguro` aplicado en `_es_archivo_preview`, `contar_miniaturas` y `miniatura_reutilizable` (corrección de bug colateral de la etapa de subcarpetas).
  - `configuracion.py` — clave `CLAVE_CANTIDAD_PREVIEWS`; `guardar_cantidad_previews(n, ruta_config)` y `obtener_cantidad_previews(ruta_config)` (default 3, mismo patrón atómico que las demás preferencias).
  - `visor_videos.py` — `QComboBox` con opciones 3/5/7/9; restauración al iniciar mediante `obtener_cantidad_previews` y configuración de `CANTIDAD_PREVIEWS`; handler `_al_cambiar_cantidad_previews` que persiste y actualiza la interfaz; método `Tarjeta.ajustar_previews(cantidad)` que muestra/oculta etiquetas y recarga previews desde caché instantáneamente; `_encolar_previews` corregido para usar `len(existentes) >= CANTIDAD_PREVIEWS` como criterio de completitud; `Tarjeta.__init__` usa `escanear_videos.CANTIDAD_PREVIEWS` dinámicamente.
  - `DOCUMENTO_TECNICO.md` — `CANTIDAD_PREVIEWS` documentado como configurable; `configuracion.py` documentado con `cantidad_previews`.
- **Archivos creados:**
  - `prueba_cantidad_previews.py` — 14 pruebas: mutable, `previews_existentes` con nueva cantidad, persistencia, default, UI con combo, restauración, escenarios 9→3, 3→7, 9→5→9, 9→9 (sin reescaneo en todos los casos).
- **Pruebas:** `prueba_cantidad_previews.py` 14/14, `prueba_previews_progresivas.py` 16/16, `prueba_smoke.py` OK.
- **Correcciones durante la etapa:**
  1. `_encolar_previews` usaba «tiene algún preview» como criterio → cambiado a «tiene todos los previews configurados», evitando que labels sobrantes quedaran en «Generando preview…» indefinidamente.
  2. `_es_archivo_preview`, `contar_miniaturas` y `miniatura_reutilizable` no usaban `_nombre_seguro`, causando mismatch con nombres de archivo sanitizados para videos en subcarpetas.
  3. La interfaz requería reescaneo para reflejar el cambio de cantidad → `Tarjeta.ajustar_previews` aplica el cambio inmediatamente mostrando/ocultando etiquetas y recargando desde caché.
- **Resultado:** Cantidad configurable con cambio visual inmediato. Separación clara entre cantidad visible (controlada por el usuario) y cantidad generada (controlada por el pipeline). Sin regeneración automática en segundo plano. Sin límites artificiales.
- **Commit:** "Agregar cantidad configurable de previews visibles (3/5/7/9) con persistencia"
- **Decisiones importantes:** `CANTIDAD_PREVIEWS` como variable de módulo mutable permite que `previews_existentes` y `previews_faltantes` se adapten automáticamente. `ajustar_previews` usa `setVisible(i < cantidad)` para ocultar/mostrar etiquetas sin reconstruir la tarjeta.

## 43. Persistencia de la preferencia "Incluir subcarpetas"

- **Fecha:** 2026-08-05
- **Objetivo:** Persistir la preferencia de la casilla "Incluir subcarpetas" entre ejecuciones de la aplicación, reutilizando el sistema de configuración existente.
- **Archivos modificados:**
  - `configuracion.py` — nueva clave `CLAVE_SUBCARPETAS = "incluir_subcarpetas"`; `guardar_preferencia_subcarpetas(activado, ruta_config)` persiste el booleano en el JSON compartido (misma escritura atómica `.tmp` + `os.replace`); `obtener_preferencia_subcarpetas(ruta_config)` restaura el valor (devuelve `False` por defecto si el archivo no existe, la clave falta o el valor no es booleano).
  - `visor_videos.py` — importa `guardar_preferencia_subcarpetas` y `obtener_preferencia_subcarpetas`; conecta `stateChanged` del checkbox a `_al_cambiar_subcarpetas`; restaura el estado del checkbox al iniciar con `obtener_preferencia_subcarpetas(self._ruta_config)`; método `_al_cambiar_subcarpetas` persiste inmediatamente el nuevo estado.
  - `DOCUMENTO_TECNICO.md` — `configuracion.py` documentado con `incluir_subcarpetas`; checkbox documentado con persistencia y restauración; `prueba_persistencia_subcarpetas.py` agregado al árbol.
- **Archivos creados:**
  - `prueba_persistencia_subcarpetas.py` — 10 pruebas: guardar True/False en JSON, obtener sin archivo, obtener sin clave, round-trip, restauración al iniciar True/False, persistencia al cambiar checkbox.
- **Pruebas:** `prueba_persistencia_subcarpetas.py` 10/10, `prueba_escaneo_subcarpetas.py` 12/12, `prueba_escaneo_interfaz.py` 36/36, `prueba_persistencia_carpeta.py` 20/20, `prueba_smoke.py` OK.
- **Resultado:** Preferencia persistida y restaurada correctamente. La casilla conserva su estado entre ejecuciones. Integración limpia con el sistema JSON existente (misma escritura atómica, misma clave). Sin perfiles de usuario, múltiples configuraciones ni otras preferencias en esta etapa.
- **Commit:** "Persistir preferencia 'Incluir subcarpetas' entre ejecuciones"
- **Decisiones importantes:** Mismo patrón que `ultima_carpeta`: clave en el mismo JSON compartido, escritura atómica con `.tmp` + `os.replace`, restauración tolerante (devuelve `False` ante cualquier anomalía). La conexión `stateChanged` persiste inmediatamente sin esperar al escaneo.

## 42. Escaneo opcional de subcarpetas

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar la opción de incluir o excluir subcarpetas durante el escaneo de videos, una funcionalidad prevista en el ROADMAP original.
- **Archivos modificados:**
  - `escanear_videos.py` — flag `_ESCANEO_RECURSIVO` a nivel módulo, setter `configurar_escaneo_recursivo(activado)`, función `_nombre_seguro(nombre)` que reemplaza `os.sep` y `/` por `_`, `escanear_videos(carpeta)` ampliado con `os.walk` cuando el flag está activo (devuelve rutas relativas), `ruta_miniatura` y `ruta_preview` usan `_nombre_seguro` para mantener planos los nombres de archivo con nombres de video que incluyen subcarpetas.
  - `visor_videos.py` — importa `QCheckBox`, `_nombre_seguro` y `configurar_escaneo_recursivo` desde `escanear_videos`; casilla `incluir_subcarpetas` (`QCheckBox` "Incluir subcarpetas") junto a los botones de carpeta y escaneo; `iniciar_escaneo()` llama a `configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())` antes de crear la tarea; `miniatura_principal` usa `_nombre_seguro`.
  - `prueba_escaneo_interfaz.py` — test 31 actualizado: verifica `configurar_escaneo_recursivo` y `_nombre_seguro` en lugar de prohibir el módulo `escanear_videos`.
  - `DOCUMENTO_TECNICO.md` — `escanear_videos` documentado con modo recursivo y `_nombre_seguro`; `boton_escanear` actualizado con la casilla.
- **Archivos creados:**
  - `prueba_escaneo_subcarpetas.py` — 12 pruebas: flag, escaneo flat, recursivo con rutas relativas, restauración a flat, `_nombre_seguro` con slash/backslash/plano, `ruta_miniatura` y `ruta_preview` seguras, checkbox en UI.
- **Pruebas:** `prueba_escaneo_subcarpetas.py` 12/12, `prueba_escaneo.py` 12/12, `prueba_escaneo_interfaz.py` 36/36, `prueba_smoke.py` OK.
- **Resultado:** Escaneo recursivo funcional con rutas relativas. Miniaturas y previews con nombres seguros (separadores reemplazados por `_`). Sin persistencia de la preferencia, filtros por profundidad ni exclusiones de carpetas en esta etapa.
- **Commit:** "Agregar escaneo recursivo opcional de subcarpetas"
- **Decisiones importantes:** Flag global `_ESCANEO_RECURSIVO` como solución más simple dado que solo hay un escaneo a la vez (garantizado por el `GestorTareas`). `_nombre_seguro` permite mantener el sistema de archivos de miniaturas plano sin necesidad de crear subdirectorios. La importación directa desde `escanear_videos` en `visor_videos.py` fue necesaria porque no se podía modificar `tareas_videos.py` para reexportar las nuevas funciones.

## 41. Abrir carpetas de los seleccionados

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar al menú contextual una quinta acción que abra las carpetas contenedoras de todos los videos seleccionados, con deduplicación para no abrir la misma carpeta más de una vez.
- **Archivos modificados:**
  - `visor_videos.py` — quinta acción "Abrir carpetas de los seleccionados" en `_mostrar_menu_contextual`; nuevo método `_abrir_carpetas_seleccionados` que itera `self.tarjetas_visibles()`, filtra por `_nombres_seleccionados`, calcula `os.path.dirname` de cada ruta, deduplica con `dict.fromkeys` (preserva orden de primera aparición) y abre cada carpeta única con `os.startfile`.
  - `DOCUMENTO_TECNICO.md` — menú contextual documentado con 5 acciones; agregado `prueba_abrir_carpetas_seleccionados.py` al árbol.
- **Archivos creados:**
  - `prueba_abrir_carpetas_seleccionados.py` — 10 pruebas: existencia del método, único seleccionado, múltiples misma carpeta (1 sola apertura), sin carpeta, sin selección, "Abrir carpeta" original intacta, 5 seleccionados deduplicados a 1.
- **Pruebas:** `prueba_abrir_carpetas_seleccionados.py` 10/10, `prueba_menu_contextual.py` 18/18, `prueba_copiar_rutas_seleccionados.py` 8/8, `prueba_shift_clic.py` 28/28, `prueba_smoke.py` OK.
- **Resultado:** Quinta acción en el menú contextual funcional. Carpetas abiertas una sola vez cada una mediante `dict.fromkeys`. La acción original "Abrir carpeta" permanece intacta. Sin confirmaciones ni límites artificiales.
- **Commit:** "Agregar accion: abrir carpetas de los seleccionados al menu contextual"
- **Decisiones importantes:** `dict.fromkeys` preserva el orden visible (primera aparición) y elimina duplicados de forma natural. La deduplicación opera sobre `os.path.dirname` de las rutas absolutas.

## 40. Copiar rutas de los seleccionados al portapapeles

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar al menú contextual una cuarta acción que copie al portapapeles las rutas completas de todos los videos seleccionados, constituyendo la primera operación real sobre una selección múltiple.
- **Archivos modificados:**
  - `visor_videos.py` — cuarta acción "Copiar rutas de los seleccionados" en `_mostrar_menu_contextual`; nuevo método `_copiar_rutas_seleccionados` que itera `self.tarjetas_visibles()`, filtra por `self._nombres_seleccionados`, construye las rutas absolutas y las copia al portapapeles separadas por `\n`; el método existente `_copiar_ruta` permanece sin cambios.
  - `DOCUMENTO_TECNICO.md` — menú contextual documentado con 4 acciones; agregado `prueba_copiar_rutas_seleccionados.py` al árbol.
- **Archivos creados:**
  - `prueba_copiar_rutas_seleccionados.py` — 8 pruebas: elemento único, múltiples con orden visible, sin carpeta, sin selección, "Copiar ruta" original intacto, todos seleccionados, existencia del método.
- **Pruebas:** `prueba_copiar_rutas_seleccionados.py` 8/8, `prueba_menu_contextual.py` 18/18, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Cuarta acción en el menú contextual funcional. Las rutas se copian en orden visible, una por línea. La acción original "Copiar ruta" sigue copiando únicamente la ruta del video sobre el que se abrió el menú. Sin exportación a archivos, copiar nombres ni metadatos.
- **Commit:** "Agregar acción "Copiar rutas de los seleccionados" al menú contextual"
- **Decisiones importantes:** Separación clara entre "Copiar ruta" (individual, la del video cliqueado) y "Copiar rutas de los seleccionados" (colectiva, por selección). La nueva acción es la primera operación real sobre selección múltiple en el proyecto.

## 39. Selección por rango con Shift+clic

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar selección por rango mediante Shift+clic, con comportamiento estándar de Windows, reutilizando el sistema de selección ya existente.
- **Archivos modificados:**
  - `visor_videos.py` — nueva señal `seleccion_por_rango = Signal(str)` en `Tarjeta`; `mousePressEvent` detecta `Qt.ShiftModifier` y enruta a `seleccion_por_rango` o `seleccionada` según corresponda; atributo `_ancla_seleccion` en `VisorVideos` (rastrea la última tarjeta seleccionada sin Shift); método `_al_seleccion_por_rango(nombre)` que calcula el rango sobre `self.visibles` (orden visible) entre el ancla y la tarjeta clickeada; sin ancla o ancla fuera de visibles → equivale a clic normal; el ancla no se actualiza durante el rango; `_reemplazar_tarjetas` limpia el ancla; conexión de la nueva señal en `_crear_tarjetas` y `_agregar_tarjetas`.
  - `DOCUMENTO_TECNICO.md` — sección de selección ampliada con Shift+clic, ancla, rango por orden visible y limpieza en reconstrucción.
- **Archivos creados:**
  - `prueba_shift_clic.py` — 28 pruebas: señal, atributo, método, Shift+clic sin ancla, rango hacia abajo, rango hacia arriba, ancla no se modifica, Ctrl+clic compatible, doble clic, emisión de señal, ancla fuera de visibles, limpieza en `_reemplazar_tarjetas`.
- **Pruebas:** `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_menu_contextual.py` 18/18, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Shift+clic funcional en ambas direcciones (hacia arriba y hacia abajo). Ancla inmutable durante el rango. Compatibilidad total con selección simple, Ctrl+clic, menú contextual y doble clic. Sin Ctrl+Shift+clic, selección con teclado ni atajos adicionales.
- **Commit:** "Agregar selección por rango con Shift+clic"
- **Decisiones importantes:** Señal independiente `seleccion_por_rango` para no modificar el contrato de `seleccionada`. El rango opera sobre el orden visible (`self.visibles`), no sobre el orden de creación. El ancla se descarta en `_reemplazar_tarjetas` porque las referencias a las tarjetas antiguas se pierden.

## 38. Restauración automática de la selección tras reconstruir la lista de tarjetas

- **Fecha:** 2026-08-05
- **Objetivo:** Restaurar la selección visual después de `_reemplazar_tarjetas` (recarga tras sincronización) sin perder el estado de selección del usuario.
- **Archivos modificados:**
  - `visor_videos.py` — `_reemplazar_tarjetas` ahora preserva `_nombres_seleccionados` antes de limpiar y, tras crear las nuevas tarjetas, restaura solo los nombres que siguen existiendo (filtrados contra `nombres_nuevos`). Los nombres que desaparecieron del catálogo se descartan silenciosamente.
  - `prueba_seleccion.py` — antiguo test "`_reemplazar_tarjetas` limpia la selección" reemplazado por 3 verificaciones de restauración (28 pruebas totales).
  - `DOCUMENTO_TECNICO.md` — actualizada la descripción de persistencia de selección y agregado `prueba_restauracion_seleccion.py` al árbol.
  - `ESTADO_PROYECTO.md` — deuda técnica actualizada.
- **Archivos creados:**
  - `prueba_restauracion_seleccion.py` — 15 pruebas: restauración simple, múltiple, sin selección previa, nombre ausente, verificación de estilo visual.
- **Pruebas:** `prueba_restauracion_seleccion.py` 15/15, `prueba_seleccion.py` 28/28, `prueba_menu_contextual.py` 18/18, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** La selección se conserva automáticamente al reconstruir la lista de tarjetas. Sin persistencia en disco ni entre ejecuciones. Sin modificar el comportamiento de clic simple, Ctrl+clic, doble clic ni menú contextual.
- **Commit:** "Restaurar automáticamente la selección tras reconstruir la lista de tarjetas"
- **Decisiones importantes:** Se reutiliza `_nombres_seleccionados` y `_marcar_tarjeta` sin nuevas estructuras de datos. El filtrado contra `nombres_nuevos` evita marcas huérfanas. Los nombres desaparecidos se descartan sin error.

## 37. Menú contextual con acciones básicas (abrir, abrir carpeta, copiar ruta)

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar un menú contextual mediante clic derecho sobre las filas de videos, con tres acciones básicas.
- **Archivos modificados:**
  - `visor_videos.py` — nueva señal `menu_contextual = Signal(str)` en `Tarjeta`, manejo de `Qt.RightButton` en `mousePressEvent` (selecciona la tarjeta si no lo estaba, conserva multi-selección), conexión en `_crear_tarjetas` y `_agregar_tarjetas`, método `_mostrar_menu_contextual(nombre)` con `QMenu` de tres acciones, `_abrir_carpeta(nombre)` (`os.startfile` sobre la carpeta seleccionada) y `_copiar_ruta(nombre)` (`QApplication.clipboard().setText` con ruta absoluta).
  - `prueba_doble_clic.py` — test 14 relajado: solo verifica que `os.isfile` no se use directamente (ya no prohíbe `os.startfile`, que ahora se usa legítimamente para abrir carpeta).
  - `DOCUMENTO_TECNICO.md` — actualizada la descripción de `Tarjeta.seleccionada` / `_nombres_seleccionados` con el menú contextual.
  - `ESTADO_PROYECTO.md` — nuevo hito completado, actualización de última etapa aprobada.
  - `ROADMAP.md` — acciones sobre elementos seleccionados marcadas como implementadas.
- **Archivos creados:**
  - `prueba_menu_contextual.py` — 18 pruebas del menú contextual (señal, selección por clic derecho, señal emitida, `_abrir_carpeta`, `_copiar_ruta`, compatibilidad con doble clic y clic izquierdo).
- **Pruebas:** `prueba_menu_contextual.py` 18/18, `prueba_seleccion.py` 26/26, `prueba_seleccion_visual.py` OK, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Menú contextual funcional con tres acciones. "Abrir" reutiliza exactamente el mecanismo existente de doble clic. "Abrir carpeta" abre el Explorador de Windows. "Copiar ruta" copia la ruta completa al portapapeles. Selección inteligente: clic derecho sobre fila no seleccionada la selecciona; sobre selección múltiple la conserva. Sin eliminar, renombrar, favoritos, etiquetas, acciones masivas ni submenús.
- **Commit:** "Incorporar menú contextual con acciones básicas (abrir, abrir carpeta, copiar ruta)"
- **Decisiones importantes:** `os.startfile` ahora se usa en dos lugares: `apertura_videos.py` (abrir video) y `visor_videos.py._abrir_carpeta` (abrir carpeta). Verificación AST de `visor_videos.py` relajada para permitir este uso legítimo.

## 36. Selección visual de filas (simple y múltiple con Ctrl+clic)

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar selección visual de filas en la lista de videos, con selección simple y múltiple mediante Ctrl+clic, preparando la base para futuras operaciones sobre elementos seleccionados.
- **Archivos modificados:**
  - `visor_videos.py` — señal `seleccionada(nombre, ctrl)` en `Tarjeta`, `mousePressEvent` con detección de `Qt.ControlModifier`, método `marcar_seleccionada(True/False)` con estilo de borde azul 3px (`ESTILO_SELECCIONADA`), tracking de selección en `VisorVideos` mediante `_nombres_seleccionados` (expuesto como `@property nombres_seleccionados`), métodos `_al_seleccionar_tarjeta` / `_limpiar_seleccion` / `_marcar_tarjeta`, conexión de señal en `_crear_tarjetas` y `_agregar_tarjetas`, limpieza en `_reemplazar_tarjetas`.
  - `DOCUMENTO_TECNICO.md` — nueva entrada documental `Tarjeta.seleccionada` / `_nombres_seleccionados`.
- **Archivos creados:**
  - `prueba_seleccion.py` — 26 pruebas unitarias de selección.
  - `prueba_seleccion_visual.py` — verificación automatizada del comportamiento de selección.
- **Pruebas:** `prueba_seleccion.py` 26/26, verificación visual OK. Regresiones: `prueba_escaneo_interfaz.py` 36/36, `prueba_escaneo_guardado.py` 24/24, `prueba_sincronizacion_interfaz.py` 18/18, `prueba_smoke.py` OK, `prueba_progreso.py` 13/13, `prueba_pagina_siguiente.py` 20/20.
- **Commit:** Aprobado y commiteado (junto con etapa 37).
- **Resultado:** Selección simple (clic reemplaza) y múltiple (Ctrl+clic agrega/quita) con diferencia visual clara (borde azul). La selección persiste al filtrar pero se pierde al reconstruir tarjetas. El doble clic no interfiere con la selección. Sin menús, botones, Shift+clic ni acciones masivas en esta etapa.
- **Decisiones importantes:** `Tarjeta.seleccionada` es señal de clase, no propiedad (la propiedad se eliminó para evitar conflicto con el descriptor del Signal). Base preparada para futuras operaciones sobre `_nombres_seleccionados`.

## 35. Estabilización de la Beta 1.0

- **Fecha:** 2026-08-05
- **Objetivo:** Corregir tres defectos de la Beta 1.0 validados por el usuario con 23 videos reales.
- **Archivos modificados:**
  - `escanear_videos.py` — definición de `_ARGS_SIN_CONSOLA` con `creationflags=subprocess.CREATE_NO_WINDOW` aplicado a todos los `subprocess.run` de FFprobe/FFmpeg.
  - `visor_videos.py` — carga inmediata de previews existentes en `_crear_tarjetas` y `_agregar_tarjetas`; nuevo layout definitivo de `Tarjeta` con datos a la izquierda (maxWidth=240) y 4 imágenes horizontales consecutivas (miniatura + 3 previews) con ancho automático por aspect ratio.
- **Pruebas:** `prueba_filas_horizontales.py` 16/16, `prueba_previews_progresivas.py` 16/16, `prueba_escaneo_interfaz.py` 36/36, `prueba_interfaz_asincrona.py` 29/29, `prueba_pagina_siguiente.py` 20/20, `prueba_recarga_catalogo.py` 19/20 (T13 preexistente), `prueba_sincronizacion_interfaz.py` 18/18, `prueba_doble_clic.py` 14/14.
- **Commit:** "Estabilizar la Beta 1.0 (consola, reescaneo de previews y layout definitivo)"
- **Resultado:** Beta lista para distribución de pruebas. Sin ventanas de consola, previews conservadas tras reescaneo, layout definitivo aprobado.
- **Decisiones importantes:** Estructura del contenedor de imágenes independiente de `CANTIDAD_PREVIEWS` para soportar cualquier número sin rediseñar.

## 34. Empaquetado de la Beta 1.0

- **Fecha:** 2026-08-04
- **Objetivo:** Empaquetar la aplicación como ejecutable portable e instalador de Windows para distribución de pruebas.
- **Archivos creados:**
  - `VisorVideos.exe` + `_internal/` — portable PyInstaller `--onedir --windowed`.
  - `instalador_beta1.0.iss` — script Inno Setup 6.7.3.
  - `VisorVideos_Beta1.0_Setup.exe` — instalador funcional.
- **Archivos modificados:**
  - `rutas.py` — `_directorio_base()` con soporte para `sys.frozen` (resolución de raíz junto al ejecutable en modo portable).
- **Pruebas:** Instalación limpia, primer inicio desde acceso directo, catálogo poblado por la app instalada, desinstalación total, sin regresiones contra el portable.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Ejecutable portable validado con driver funcional completo. Instalador con `biblioteca.db` vacía de esquema vigente, instalación por usuario sin permisos de administrador.
- **Decisiones importantes:** `biblioteca.db` vacía en el instalador (sin datos de desarrollo). FFmpeg/FFprobe no empaquetados: se resuelven por PATH. Instalación en `{localappdata}\Programs`.

## 33. Separación del punto de entrada de producción y del arnés de smoke tests

- **Fecha:** 2026-08-04
- **Objetivo:** Independizar el smoke test del arranque normal para preparar el empaquetado de la Beta.
- **Archivos creados:**
  - `prueba_smoke.py` — arnés de ejecución explícita con `python prueba_smoke.py`, base SQLite temporal, fases: paginación, escaneo + carpeta + sincronización, previews, doble clic y persistencia.
- **Archivos modificados:**
  - `visor_videos.py` — `main()` reducido a bootstrap puro (`QApplication`, `VisorVideos()`, `resize`, `show`, `exec`).
  - Cinco suites de interfaz (`prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py`, `prueba_recarga_catalogo.py`) — pasan a invocar `prueba_smoke.py` por subprocess.
- **Pruebas:** Arranque normal sin smoke automático (proceso vivo tras 8 s sin stdout/stderr). Smoke explícito con exit 0.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Aplicación preparada para empaquetado sin ejecutar pruebas al iniciar.
- **Decisiones importantes:** Separación definitiva entre punto de entrada de producción y arnés de verificación.

## 32. Persistencia de la última carpeta seleccionada

- **Fecha:** 2026-08-03
- **Objetivo:** Recordar entre sesiones la carpeta seleccionada por el usuario.
- **Archivos creados:**
  - `configuracion.py` — servicio de persistencia de configuración: `guardar_ultima_carpeta()` (escritura atómica con `.tmp` + `os.replace`), `obtener_ultima_carpeta()` (tolerante: `None` ante ausencia/corrupción/carpeta inexistente), `VARIABLE_ENTORNO = "VISOR_CONFIG"` para aislamiento de pruebas.
  - `prueba_persistencia_carpeta.py` — 20 pruebas.
- **Archivos modificados:**
  - `rutas.py` — añade `ruta_configuracion()` → `configuracion.json`.
  - `visor_videos.py` — constructor ampliado con `ruta_config`, restauración al arranque y persistencia al seleccionar.
  - `.gitignore` — añade `configuracion.json`.
  - 11 módulos de prueba — añaden `_CONFIG_TEMPORAL` + `VISOR_CONFIG` para aislamiento.
- **Pruebas:** 20/20 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Carpeta elegida persistida y restaurada automáticamente. Pruebas aisladas sin tocar archivo real del usuario.
- **Decisiones importantes:** `VISOR_CONFIG` es redirección de ubicación, no bandera de depuración. Persistencia de preferencias generales queda pendiente.

## 31. Apertura del video por doble clic

- **Fecha:** 2026-08-03
- **Objetivo:** Abrir el video con la aplicación predeterminada del sistema mediante doble clic sobre su tarjeta.
- **Archivos creados:**
  - `apertura_videos.py` — módulo de servicio: `abrir_video_con_aplicacion_predeterminada(nombre, carpeta)`, único punto del proyecto que ejecuta `os.startfile`.
  - `prueba_doble_clic.py` — 14 pruebas, incluido AST de `visor_videos.py` con cero referencias a `os.path.isfile`/`os.startfile`.
- **Archivos modificados:**
  - `visor_videos.py` — señal `Tarjeta.doble_clic = Signal(str)`, sobrescritura de `mouseDoubleClickEvent`, handler `_abrir_video(nombre)`, constante `MENSAJE_ERROR_ABRIR`, conexión en `_crear_tarjetas` y `_agregar_tarjetas`.
- **Pruebas:** 14/14 OK. Regresiones 72/72 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Doble clic funcional en tarjetas de carga inicial y páginas adicionales. Apertura aislada del resto de la arquitectura.
- **Decisiones importantes:** `os.startfile` en un único módulo de servicio, verificado por AST.

## 30. Previews progresivas para la Beta 1.0

- **Fecha:** 2026-08-03
- **Objetivo:** Generar tres previews por video (fotogramas al 25/50/75 %) de forma progresiva en segundo plano.
- **Archivos creados:**
  - `prueba_previews_progresivas.py` — 16 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `CANTIDAD_PREVIEWS = 3`, `ruta_preview`, `_es_archivo_preview`, `previews_existentes`, `previews_faltantes`, `calcular_tiempo_preview`, `generar_preview`, `generar_previews_faltantes`.
  - `tareas_videos.py` — `TareaPreviewsProgresivas(TareaBase)`.
  - `visor_videos.py` — segundo `GestorTareas` (`gestor_previews`), cola `_cola_previews`, lotes de `TAMANIO_LOTE_PREVIEWS = 3`, temporizador `_timer_previews` (300 ms), actualización incremental `Tarjeta.actualizar_previews`.
- **Pruebas:** 16/16 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Previews generados incrementalmente sin bloquear la carga del catálogo. Reutilización de miniatura base si FFmpeg falla. Nunca sobrescribe ni elimina archivos.
- **Decisiones importantes:** Segundo `GestorTareas` independiente para no interferir con el pipeline principal. Convención `miniaturas/<prefijo>_preview_NN.jpg`.

## 29. Incorporación y visualización del tamaño de los archivos de video

- **Fecha:** 2026-08-02
- **Objetivo:** Mostrar el tamaño de cada archivo de video en el catálogo.
- **Archivos creados:**
  - `prueba_tamano_archivo.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — añade `tamano_bytes INTEGER` a `COLUMNAS_EXTRA` (migración idempotente), `obtener_tamanos_archivos`, `combinar_registros_con_tamanos`.
  - `tareas_videos.py` — `TareaTamanosArchivos(TareaBase)`.
  - `visor_videos.py` — pipeline a 7 tareas (tamaños entre escaneo y FFprobe), campo "Tamaño" con `formatear_tamano` (B/KB/MB/GB).
- **Pruebas:** 15/15 OK. Regresiones en 5 suites OK. Correcciones de aislamiento T15/T27.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Tamaño de archivo visible en cada fila del catálogo con formato legible.
- **Decisiones importantes:** `tamano_bytes` como columna opcional (NULL si archivo no legible). Migración idempotente sin tocar registros existentes.

## 28. Presentación del catálogo en filas horizontales

- **Fecha:** 2026-08-02
- **Objetivo:** Cambiar la presentación del catálogo a una tarjeta horizontal por video, una fila por video en una única columna.
- **Archivos creados:**
  - `prueba_filas_horizontales.py` — 16 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — `Tarjeta` con `QHBoxLayout` (miniatura izquierda + columna de campos derecha), eliminación de `COLUMNAS = 2` y `setColumnStretch`.
- **Pruebas:** 16/16 OK. Regresiones `prueba_pagina_siguiente.py` 20/20 y `prueba_recarga_catalogo.py` 20/20 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Layout horizontal definitivo. Solo primera miniatura por video (previews y doble clic incorporados en etapas posteriores).
- **Decisiones importantes:** Sin cambios en datos reales.

## 27. Carga manual de una página adicional del catálogo

- **Fecha:** 2026-08-02
- **Objetivo:** Permitir al usuario cargar manualmente páginas adicionales del catálogo con el botón "Cargar más".
- **Archivos creados:**
  - `prueba_pagina_siguiente.py` — 20 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — factoría `_crear_tarea_lectura(desplazamiento=0)`, botón `boton_cargar_mas`, `cargar_mas()`, `_agregar_tarjetas(filas)`, estados `_pagina_pendiente`/`tarea_pagina`/`_total_catalogo`, handlers y constante `MENSAJE_ERROR_PAGINA`.
- **Pruebas:** 20/20 OK. Regresiones 98/98 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Páginas adicionales agregadas sin reemplazar existentes y sin duplicados. Sin scroll infinito ni búsqueda en SQL (pendientes).
- **Decisiones importantes:** El reemplazo de tarjetas sigue siendo exclusivo de la recarga tras sincronización.

## 26. Recarga asíncrona del catálogo tras la sincronización

- **Fecha:** 2026-08-02
- **Objetivo:** Recargar automáticamente el catálogo después de una sincronización exitosa.
- **Archivos creados:**
  - `prueba_recarga_catalogo.py` — 20 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — pipeline a 6 tareas, `_recarga_catalogo_pendiente`/`tarea_recarga_catalogo`, `_reemplazar_tarjetas(filas)`, `_iniciar_recarga_catalogo()`, handlers y constante `MENSAJE_ERROR_RECARGA`.
- **Pruebas:** 20/20 OK. Regresiones 82/82 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Tras sincronización exitosa, las tarjetas se reemplazan con la primera página actualizada. Tarjetas viejas conservadas hasta resultado válido.
- **Decisiones importantes:** La recarga fallida no revierte la sincronización ya confirmada. Sin FFprobe/FFmpeg/miniaturas en la recarga.

## 25. Integración de la sincronización completa en la interfaz

- **Fecha:** 2026-08-02
- **Objetivo:** Lanzar `TareaSincronizacionCatalogo` desde la interfaz tras el guardado exitoso del pipeline.
- **Archivos creados:**
  - `prueba_sincronizacion_interfaz.py` — 18 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — pipeline a 5 tareas, estados `_sincronizacion_pendiente`/`tarea_sincronizacion`/`resultado_sincronizacion`, handlers, constantes `MENSAJE_SINCRONIZANDO`/`MENSAJE_ERROR_SINCRONIZACION`, `texto_resumen_sincronizacion()`.
  - `prueba_escaneo_guardado.py` — actualizada a cadena de 5 tareas (24 pruebas).
  - `prueba_escaneo_interfaz.py` — actualizada a cadena de 5 tareas (36 pruebas).
- **Pruebas:** 18/18 OK. Regresiones 355/355 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Sincronización completa integrada en la interfaz. Registros ausentes eliminados de SQLite, presentes conservados. Sin recarga de tarjetas en esta etapa.
- **Decisiones importantes:** GUI sin SQLite ni SQL (AST verificado). Sincronización solo tras guardado exitoso.

## 24. Sincronización asíncrona del catálogo (TareaSincronizacionCatalogo)

- **Fecha:** 2026-08-02
- **Objetivo:** Orquestar en segundo plano la secuencia completa de sincronización disco ↔ BD.
- **Archivos creados:**
  - `prueba_sincronizacion_asincrona.py` — 27 pruebas.
- **Archivos modificados:**
  - `tareas_videos.py` — `import escanear_videos as escanear_mod`, clase `TareaSincronizacionCatalogo(TareaBase)`.
  - `prueba_plan_sincronizacion.py` — adaptación con allowlist exacta para `TareaSincronizacionCatalogo`.
- **Pruebas:** 27/27 OK. Regresiones 310/310 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Secuencia `detectar_diferencias` → `preparar_plan_sincronizacion` → `aplicar_incorporaciones` → `eliminar_candidatos` ejecutada en QThread. Sin integración con la interfaz en esta etapa.
- **Decisiones importantes:** Incorporación y eliminación como transacciones independientes. Tarea sin SQL propio: delega en funciones de `escanear_videos`.

## 23. Eliminación controlada de candidatos ausentes del catálogo

- **Fecha:** 2026-08-01
- **Objetivo:** Eliminar de forma controlada los registros ausentes del disco según el plan de sincronización.
- **Archivos creados:**
  - `prueba_eliminar_candidatos.py` — 16 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `eliminar_candidatos(plan, ruta_db=None)`, helper `_validar_plan_sincronizacion` (compartido con `aplicar_incorporaciones`).
- **Pruebas:** 16/16 OK. Regresiones 294/294 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Eliminación atómica (`DELETE` por nombre con `rowcount`, un solo `commit`, rollback total). Sin eliminación de archivos físicos ni miniaturas.
- **Decisiones importantes:** `_coleccion_nombres` devuelve orden determinista. Validación compartida con `aplicar_incorporaciones`.

## 22. Aplicación de incorporaciones del plan de sincronización

- **Fecha:** 2026-08-01
- **Objetivo:** Aplicar de forma no destructiva las incorporaciones del plan de sincronización.
- **Archivos creados:**
  - `prueba_aplicar_incorporaciones.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `aplicar_incorporaciones(plan, ruta_db=None)`.
- **Pruebas:** 15/15 OK. Regresiones 279/279 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Persiste únicamente `a_incorporar` delegando en `guardar_videos`. No elimina candidatos ni modifica `ya_sincronizados`.
- **Decisiones importantes:** Validación completa previa antes de abrir SQLite.

## 21. Preparación del plan de sincronización

- **Fecha:** 2026-08-01
- **Objetivo:** Preparar un plan puro de sincronización a partir del resultado de `detectar_diferencias`.
- **Archivos creados:**
  - `prueba_plan_sincronizacion.py` — 12 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `preparar_plan_sincronizacion(diferencias)`, helper `_coleccion_nombres`.
- **Pruebas:** 12/12 OK. Regresiones 267/267 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` con registros básicos y candidatos informativos. Operación pura: sin SQLite, sin FFprobe/FFmpeg.
- **Decisiones importantes:** `fecha_importacion` generada en la preparación, no en la detección. Deduplicación de nombres repetidos queda pendiente.

## 20. Detección no destructiva de diferencias disco ↔ BD

- **Fecha:** 2026-08-01
- **Objetivo:** Detectar diferencias entre la carpeta de videos y el catálogo SQLite sin modificar datos.
- **Archivos creados:**
  - `prueba_detectar.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `detectar_diferencias(carpeta, ruta_db=None)`.
- **Pruebas:** 15/15 OK. Regresiones 252/252 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Comparación por nombre, solo lectura. Sin integración al pipeline ni a la interfaz.
- **Decisiones importantes:** No detecta movimientos ni renombrados. No recorre subcarpetas.

## 19. Generación asíncrona de miniaturas en el pipeline

- **Fecha:** 2026-07-31
- **Objetivo:** Integrar la generación de miniaturas en el pipeline escaneo → FFprobe → miniaturas → guardado.
- **Archivos modificados:**
  - `escanear_videos.py` — `asegurar_miniaturas(videos, carpeta)`, `combinar_registros_con_miniaturas(registros, resultado_miniaturas)`.
  - `tareas_videos.py` — `TareaMiniaturas(TareaBase)`, re-exporta `asegurar_miniaturas` y `combinar_registros_con_miniaturas`.
  - `visor_videos.py` — pipeline a 4 tareas con paso de miniaturas, estados `_miniaturas_pendiente`/`tarea_miniaturas`/`resultado_miniaturas`.
  - `prueba_escaneo_guardado.py` — ampliada a 24 pruebas.
  - `prueba_escaneo_interfaz.py` — actualizada a secuencia de 4 tareas (36 pruebas).
- **Pruebas:** 24/24 OK. Regresiones 252/252 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Una miniatura básica por video integrada en el pipeline. FFmpeg ejecutado solo en segundo plano. Sin selección inteligente ni limpieza de miniaturas antiguas.
- **Decisiones importantes:** Reutilización por `mtime`. Escritura en siguiente ranura libre. Nunca sobrescribe ni elimina.

## 18. Integración de FFprobe en el pipeline

- **Fecha:** 2026-07-31
- **Objetivo:** Extender el pipeline para que los registros se guarden con metadatos FFprobe.
- **Archivos modificados:**
  - `escanear_videos.py` — `CLAVES_METADATOS_FFPROBE`, `_normalizar_ruta(ruta)`, `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)`.
  - `tareas_videos.py` — re-exporta `combinar_registros_con_ffprobe`.
  - `visor_videos.py` — pipeline a 3 tareas (escaneo → FFprobe → guardado), estados `_ffprobe_pendiente`/`tarea_ffprobe`/`resultado_ffprobe`.
  - `prueba_escaneo_guardado.py` — ampliada a 19 pruebas.
- **Pruebas:** 19/19 OK. Regresiones 247/247 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Registros guardados con duración, resolución y codec. NULL ante fallos individuales.
- **Decisiones importantes:** Combinación pura de registros por ruta normalizada. Sin FFmpeg/miniaturas en esta etapa.

## 17. Integración del pipeline limitado (escaneo → registros básicos → guardado)

- **Fecha:** 2026-07-31
- **Objetivo:** Implementar el encadenamiento escaneo → preparación → guardado y corregir la desviación arquitectónica (preparación de registros debe estar en la capa de catálogo).
- **Archivos modificados:**
  - `escanear_videos.py` — `preparar_registros_basicos(videos, carpeta)`.
  - `tareas_videos.py` — eliminada definición local, re-exporta desde `escanear_videos`.
  - `visor_videos.py` — encadenamiento escaneo → guardado con mismo `GestorTareas`, estados `_guardado_pendiente`/`tarea_guardado`/`registros_guardados`.
- **Archivos creados:**
  - `prueba_escaneo_guardado.py` — 16 pruebas.
- **Pruebas:** 16/16 OK. Regresiones 244/244 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Pipeline funcional con escritura real en SQLite. Sin FFprobe/FFmpeg/miniaturas. Sin eliminación de registros ni recarga.
- **Decisiones importantes:** La preparación de registros es lógica de catálogo, no de tareas. Corrección de arquitectura.

## 16. Escaneo manual y asíncrono de la carpeta seleccionada desde la interfaz

- **Fecha:** 2026-07-30
- **Objetivo:** Permitir al usuario escanear la carpeta elegida desde la interfaz.
- **Archivos creados:**
  - `prueba_escaneo_interfaz.py` — 36 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — botón "Escanear carpeta", `iniciar_escaneo()`, `videos_detectados`, enrutado por `_escaneo_pendiente`, constantes `MENSAJE_ESCANEANDO`/`MENSAJE_ERROR_ESCANEO`/`MENSAJE_SIN_ESCANEO`.
- **Pruebas:** 36/36 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escaneo asíncrono de la carpeta seleccionada. Conteo de videos detectados visible. Sin escritura en SQLite ni FFprobe/FFmpeg.
- **Decisiones importantes:** Mismo `GestorTareas` reutilizado. Enrutado por flag `_escaneo_pendiente`.

## 15. Selección de carpeta en la interfaz

- **Fecha:** 2026-07-30
- **Objetivo:** Permitir al usuario seleccionar la carpeta de videos desde la interfaz.
- **Archivos creados:**
  - `prueba_seleccion_carpeta.py` — 26 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — botón "Seleccionar carpeta", `carpeta_seleccionada`, `seleccionar_carpeta()`, constantes `MENSAJE_SIN_CARPETA`/`MENSAJE_RUTA_INVALIDA`.
- **Pruebas:** 26/26 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Selección de carpeta con normalización y validación. Sin escaneo automático.
- **Decisiones importantes:** Seleccionar carpeta no escanea su contenido. La persistencia queda para etapa futura.

## 14. Integración de la lectura paginada con la interfaz (carga inicial asíncrona)

- **Fecha:** 2026-07-30
- **Objetivo:** Cargar la primera página del catálogo en segundo plano sin bloquear la interfaz.
- **Archivos creados:**
  - `prueba_interfaz_asincrona.py` — 29 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — eliminado `import sqlite3` y `listar_videos`. `GestorTareas` + `TareaLecturaCatalogoPaginada` para carga inicial. Constantes `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO`, `MENSAJE_ERROR`.
- **Pruebas:** 29/29 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Interfaz sin SQLite. Carga inicial asíncrona con estado de carga y manejo de errores.
- **Decisiones importantes:** Sin `check_same_thread=False`. Apagado ordenado con `gestor.cerrar()`.

## 13. Lectura paginada del catálogo

- **Fecha:** 2026-07-29
- **Objetivo:** Implementar lectura paginada con LIMIT/OFFSET/COUNT en SQL para catálogos grandes.
- **Archivos creados:**
  - `prueba_lectura_paginada.py` — 32 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)`.
  - `tareas_videos.py` — `TareaLecturaCatalogoPaginada(TareaBase)`.
- **Pruebas:** 32/32 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Consulta paginada con búsqueda parcial por LIKE parametrizada. Sin integración con la interfaz en esta etapa.
- **Decisiones importantes:** `%` y `_` actúan como comodines LIKE (documentado como limitación conocida).

## 12. Contrato definitivo de TareaGuardarVideos ante entradas inválidas (observación)

- **Fecha:** 2026-07-29
- **Objetivo:** Garantizar que el constructor de `TareaGuardarVideos` nunca lance ante entradas inválidas.
- **Archivos modificados:**
  - `tareas_videos.py` — ampliada la captura de `(TypeError, ValueError)` a `Exception` al materializar la colección.
  - `prueba_guardar_videos.py` — ampliada de 31 a 34 pruebas (generador fallido, entradas inválidas, error diferido).
- **Pruebas:** 34/34 OK. Regresiones OK.
- **Commit:** Sin commit independiente (corrección incluida en el commit de la etapa de colección).
- **Resultado:** Constructor nunca lanza. Todos los errores por señal `error`.
- **Decisiones importantes:** Contrato definitivo documentado y cubierto por pruebas.

## 11. Escritura de colección transaccional asíncrona

- **Fecha:** 2026-07-29
- **Objetivo:** Implementar escritura de múltiples registros en una única transacción atómica.
- **Archivos creados:**
  - `prueba_guardar_videos.py` — 31 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — internos compartidos `_validar_registro_video(datos)` y `_upsert_video(conn, datos)`. `guardar_videos(datos_videos, ruta_db=None)`.
  - `tareas_videos.py` — `TareaGuardarVideos(TareaBase)`.
- **Pruebas:** 31/31 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escritura de colección con un solo commit y rollback total. Sin eliminación de registros.
- **Decisiones importantes:** `guardar_video` y `guardar_videos` comparten validación y upsert sin duplicar código.

## 10. Aislamiento del registro y validación previa a SQL (observación de la etapa 9)

- **Fecha:** 2026-07-28
- **Objetivo:** Resolver observación: aislar el diccionario de entrada en `TareaGuardarVideo` y validar contrato antes de abrir SQLite.
- **Archivos modificados:**
  - `tareas_videos.py` — `TareaGuardarVideo` toma instantánea `self._datos = dict(datos)`.
  - `prueba_guardar.py` — ampliada a 19 pruebas.
- **Pruebas:** 19/19 OK. Regresiones OK.
- **Commit:** Sin commit independiente (resuelto antes del commit de la etapa 9).
- **Resultado:** Constructor inmune a mutaciones posteriores del llamador. Validación previa a SQL sin abrir conexión.

## 9. Escritura individual asíncrona de video

- **Fecha:** 2026-07-28
- **Objetivo:** Implementar escritura individual asíncrona de registros de video en SQLite.
- **Archivos creados:**
  - `prueba_guardar.py` — 19 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `guardar_video(datos, ruta_db=None)`.
  - `tareas_videos.py` — `TareaGuardarVideo(TareaBase)`.
- **Pruebas:** 19/19 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Upsert transaccional de un único registro. `commit`/`rollback`/`close` propios.
- **Decisiones importantes:** Conexión abierta y cerrada dentro del hilo de trabajo.

## 8. Lectura asíncrona del catálogo

- **Fecha:** 2026-07-28
- **Objetivo:** Leer el catálogo SQLite en segundo plano.
- **Archivos creados:**
  - `prueba_lectura.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `listar_videos(ruta_db=None)` con validación `os.path.isfile` antes de conectar.
  - `tareas_videos.py` — `TareaLecturaCatalogo(TareaBase)`.
- **Pruebas:** 15/15 OK. Regresiones 37/37 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Lectura asíncrona con conexión por hilo. Base inexistente → `FileNotFoundError` sin crear archivos.
- **Decisiones importantes:** La lectura nunca crea la base.

## 7. Escaneo asíncrono

- **Fecha:** 2026-07-27
- **Objetivo:** Ejecutar el escaneo de archivos de video en segundo plano.
- **Archivos creados:**
  - `prueba_escaneo.py` — 12 pruebas.
- **Archivos modificados:**
  - `tareas_videos.py` — `TareaEscaneo(TareaBase)`.
- **Pruebas:** 12/12 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escaneo asíncrono con errores propagados por señal `error`.
- **Decisiones importantes:** Reutiliza `escanear_videos(carpeta)` sin cambios.

## 6. Procesamiento asíncrono de metadatos FFprobe

- **Fecha:** 2026-07-27
- **Objetivo:** Ejecutar FFprobe en segundo plano para no bloquear la interfaz.
- **Archivos creados:**
  - `tareas_videos.py` — `rutas_videos()` y `TareaFFprobe(TareaBase)`.
  - `prueba_ffprobe.py` — 12 pruebas.
- **Pruebas:** 12/12 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Metadatos FFprobe en segundo plano con resultado y error por ruta. Timeout 30 s.
- **Decisiones importantes:** FFprobe en hilo de trabajo. `creationflags=subprocess.CREATE_NO_WINDOW` en Windows.

## 5. Infraestructura reutilizable de trabajos en segundo plano

- **Fecha:** 2026-07-27
- **Objetivo:** Crear infraestructura genérica para ejecutar tareas asíncronas con QThread.
- **Archivos creados:**
  - `tareas.py` — `Estado`, `TareaBase(QObject)`, `GestorTareas(QObject)`.
  - `prueba_tareas.py` — 13 pruebas.
- **Pruebas:** 13/13 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Infraestructura con señales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada`. Un QThread por ejecución. Apagado ordenado con `cerrar(timeout_ms)`.
- **Decisiones importantes:** Ciclo de vida `inactivo` → `ocupado` → `inactivo`.

## 4. Rutas independientes del directorio de trabajo

- **Fecha:** 2026-07-26
- **Objetivo:** Resolver rutas del proyecto sin depender del CWD.
- **Archivos creados:**
  - `rutas.py` — `ruta_raiz()`, `ruta_biblioteca()`, `ruta_carpeta_miniaturas()`, `ruta_carpeta_videos()`.
- **Archivos modificados:**
  - `escanear_videos.py` — eliminadas constantes relativas, usa `rutas.py`.
  - `visor_videos.py` — `miniatura_principal()` resuelve a través de `rutas.py`.
- **Pruebas:** Regresiones completas OK. Smoke test desde CWD ajeno al proyecto OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Proyecto funciona desde cualquier ubicación.
- **Decisiones importantes:** Resolución anclada en `os.path.dirname(os.path.abspath(__file__))`.

## 3. Primera generación de miniaturas con preservación de archivos

- **Fecha:** 2026-07-26
- **Objetivo:** Implementar generación automática de miniaturas con reutilización y preservación.
- **Archivos modificados:**
  - `escanear_videos.py` — constantes `CARPETA_MINIATURAS`/`EXTENSION_MINIATURA`, funciones `ffmpeg_disponible`, `ruta_miniatura`, `calcular_tiempo_miniatura`, `miniatura_vigente`, `generar_miniatura`, `siguiente_indice_libre`, `miniatura_reutilizable`, `asegurar_miniatura`. `sincronizar_bd()` invoca `asegurar_miniatura`.
- **Pruebas:** Smoke test OK. Miniatura generada sin sobrescribir existentes.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Como máximo una miniatura nueva por video por escaneo. Reutilización por `mtime`. Escritura en siguiente ranura libre.
- **Decisiones importantes:** Nunca sobrescribir ni eliminar archivos. Videos vacíos (0 bytes) no generan miniatura.

## 2. Incorporación de Git

- **Fecha:** 2026-07-26
- **Objetivo:** Añadir control de versiones al proyecto.
- **Archivos creados:** `.gitignore` con `biblioteca.db`, `datos.txt`, `miniaturas/`, `__pycache__/`, `*.pyc`.
- **Pruebas:** N/A.
- **Commit:** Inicial.
- **Resultado:** Proyecto bajo control de versiones Git.

## 1. Arquitectura congelada — línea base

- **Fecha:** 2026-08-02 (fecha de congelamiento documental)
- **Objetivo:** Establecer la arquitectura base del proyecto y documentarla como referencia.
- **Archivos existentes en la línea base:**
  - `escanear_videos.py` — backend: escaneo, SQLite, FFprobe, FFmpeg, miniaturas, sincronización.
  - `visor_videos.py` — interfaz gráfica PySide6.
  - `biblioteca.db` — base de datos SQLite del catálogo.
  - `miniaturas/` — caché de miniaturas generadas.
  - `videos_prueba/` — dataset de prueba.
  - `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` — artefactos ajenos al visor (preservados).
- **Pruebas:** Verificación de compilación, sincronización de catálogo, metadatos FFprobe, smoke test GUI (4 videos, filtro "real" → 1 video).
- **Commit:** Arquitectura base documentada.
- **Resultado:** Arquitectura congelada como referencia para desarrollo posterior.
- **Decisiones importantes:** Separación interfaz/lógica/catálogo. Interfaz nunca accede directamente a SQLite, FFprobe, FFmpeg ni archivos. Documentación en 4 documentos (REGLAS, DOCUMENTO_TECNICO, ESTADO, ROADMAP).
