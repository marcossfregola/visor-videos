# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** Beta 1.0 estabilizada. Ejecutable portable e instalador
de Windows funcionales. Arquitectura base consolidada con pipeline
asíncrono completo (escaneo, tamaños, FFprobe, miniaturas, guardado,
sincronización, recarga), previews progresivos, apertura por doble clic
y persistencia de la última carpeta seleccionada.

## Último commit aprobado

**Mensaje:** Persistir y restaurar la carpeta seleccionada del arbol de navegacion (Etapa 2.5)

**Etapa:** Persistencia del Centro de Navegación (Etapa 2.5 del Bloque de trabajo 2):
- `visor_videos.py` — `_al_carpeta_actual_arbol` ahora **persiste** la carpeta seleccionada con
  `guardar_ultima_carpeta` (misma clave/escritura atómica que el diálogo; el guard de repetición
  evita reescrituras). La restauración de arranque usa `revelar_ruta` y, si la ruta no puede
  reconstruirse, deja el estado consistente sin carpeta seleccionada.
- `arbol_navegacion.py` — nuevo método público `revelar_ruta(ruta)`: reconstrucción **estrictamente
  incremental** de la rama necesaria (disco por prefijo, expansión nivel por nivel, búsqueda solo del
  siguiente componente, comparación insensible a mayúsculas); devuelve `False` sin lanzar ante rutas
  no reconstruibles. `seleccionar_ruta` se conserva para sincronizaciones rápidas con nodos ya cargados.
- `prueba_persistencia_arbol.py` — 15 verificaciones de la etapa.
- Suites de árbol actualizadas solo para aislamiento (config temporal): `prueba_seleccion_arbol.py`,
  `prueba_expansion_carpetas.py`, `prueba_arbol_navegacion.py`.

**Pruebas superadas:** `prueba_persistencia_arbol.py` 15/15 (persistencia, una única escritura, sin
reescritura por repetición, restauración tras reinicio con solo la rama necesaria, sin escaneo,
restauración tolerante, diálogo intacto); regresiones `prueba_seleccion_arbol.py` 24/24,
`prueba_expansion_carpetas.py` 34/34, `prueba_arbol_navegacion.py` OK, `prueba_carpeta_actual.py`
17/17, `prueba_seleccion_carpeta.py` 26/26, `prueba_smoke.py` OK, `prueba_escaneo_interfaz.py` 36/36.
Ejecución real de `visor_videos.py` con restauración real (`C:\Users\Marcos Casa`) y cierre limpio (exit 0).

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

## Próxima etapa

**Etapa 2.6 del Bloque de trabajo 2 (escaneo automático al seleccionar
carpeta).** Con la persistencia/restauración del árbol ya implementada
(Etapa 2.5), la próxima etapa es el escaneo automático al seleccionar una
carpeta (preferencia independiente de "Incluir subcarpetas"), siguiendo la
dirección definida en `VISION_PRODUCTO.md` y `ROADMAP.md`.

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
