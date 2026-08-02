# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), **lectura paginada del catálogo SQLite**
(`TareaLecturaCatalogoPaginada` con `LIMIT`/`OFFSET`/`COUNT` en SQL),
escritura individual asíncrona (`TareaGuardarVideo`), escritura de
colección asíncrona (`TareaGuardarVideos`) aprobados e **integración
asíncrona de la primera carga del catálogo en la interfaz**
(`visor_videos.py` consume `TareaLecturaCatalogoPaginada` mediante
`GestorTareas` para la primera página, con estado de carga y manejo de
errores sin bloquear la ventana) aprobada; pendiente la integración
funcional del pipeline asíncrono del catálogo (sincronización completa
SQLite con detección de archivos y eliminación de registros ausentes;
el pipeline Escaneo → SQLite aún no está encadenado ni existe el
escaneo real de carpetas seleccionadas; la carga inicial asíncrona de
la primera página ya está integrada).

## Último commit aprobado

**Mensaje:** Incorporar escritura asíncrona de colecciones

**Etapa aprobada:** Escritura de colección transaccional asíncrona
(`guardar_videos` / `TareaGuardarVideos`), que reutiliza la capa de
escritura transaccional con un upsert compartido en una **única
transacción atómica** (un solo `connect` y un solo `commit` por
colección, `rollback` total ante cualquier fallo, `close` siempre en
`finally`), con instantánea de la colección y de cada registro y pruebas
automatizadas. Aprobada con observaciones resueltas: contrato de
`TareaGuardarVideos` ante entradas inválidas (el constructor **nunca
lanza**; todos los errores de contrato, incluido un generador que falla
al materializarse, se comunican por la señal `error` durante la
ejecución, sin abrir SQLite ni modificar la base) y suite ampliada de 31
a 34 pruebas.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Integración asíncrona de la primera carga del catálogo en la interfaz:
`visor_videos.py` dejó de leer SQLite en el hilo principal y ahora
consume `TareaLecturaCatalogoPaginada` mediante `GestorTareas` para
cargar la primera página en segundo plano (constante
`TAMANIO_PAGINA_INICIAL = 100`), con estado de carga ("Cargando
catálogo…"), manejo de errores visible sin cerrar la ventana ("No se
pudo cargar el catálogo"), filtrado sobre las tarjetas ya cargadas y
apagado ordenado en `closeEvent` (`gestor.cerrar()`). Aprobada tras
evidencia adicional que confirmó que no existen tarjetas antes de
recibir el resultado (la aseveración se verifica durante la carga; el
detalle `tarjetas=1` refleja el conteo posterior al resultado). La
ventana se construye sin consultas SQL, no almacena conexiones y no usa
`check_same_thread=False`. El escaneo real de carpetas y la
sincronización completa del catálogo quedan para la próxima etapa.

## Estado de la arquitectura

### Completado

-   Arquitectura general.
-   Git.
-   Documentación técnica.
-   Resolución centralizada de rutas.
-   Preservación de archivos.
-   Generación inicial de miniaturas.
-   Infraestructura reutilizable de trabajos.
-   Procesamiento asíncrono de FFprobe.
-   Escaneo asíncrono de videos.
-   Lectura asíncrona del catálogo.
-   Lectura paginada asíncrona del catálogo.
-   Escritura individual asíncrona.
-   Escritura de colección asíncrona.
-   Integración asíncrona de la primera carga del catálogo en la
    interfaz.
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo: el escaneo
real de carpetas seleccionadas y la sincronización completa del
catálogo —detección de archivos, FFprobe y eliminación de registros
ausentes— siguen pendientes; el pipeline Escaneo → SQLite aún no está
encadenado. La carga inicial asíncrona de la primera página del
catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización SQLite asíncrona (solo existe escritura de
    colecciones preparadas con upsert; falta la escritura masiva con
    detección de archivos, FFprobe y eliminación de registros ausentes).
2.  Escaneo real de carpetas seleccionadas por el usuario (la carga
    inicial asíncrona ya está integrada; falta el escaneo de la carpeta
    elegida).
3.  Integración SQLite asíncrona en el pipeline (encadenado).
4.  Actualización asíncrona de la interfaz (tarjetas dinámicas).
5.  FFmpeg asíncrono.
6.  Varias miniaturas por video.
7.  Selección inteligente de miniaturas.
8.  Barra de progreso.
9.  Caché avanzada.
10. Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana (la carga inicial
asíncrona ya usa `GestorTareas` y cierra de forma ordenada en
`closeEvent`); - el escaneo real de carpetas y la sincronización
completa del catálogo siguen pendientes; - decisión pendiente sobre si
`%` y `_` como comodines `LIKE` en la búsqueda de
`listar_videos_paginado` se aceptan como contrato; - FFmpeg continúa
siendo síncrono; - siguen pendientes progreso y cancelación; - limpieza
controlada de miniaturas antiguas.

## Deuda técnica

-   Crecimiento y duplicación de infraestructura entre las suites de
    prueba: cada suite (`prueba_escaneo.py`, `prueba_lectura.py`,
    `prueba_guardar.py`, `prueba_guardar_videos.py`, etc.) define sus
    propios helpers y versiones de conectores/falsificaciones
    (`ConectorConHilo`, `ConectorConFallo`, `Captura`, `correr`, bases
    temporales) en lugar de reutilizar una infraestructura común.
-   El patrón repetido de construir una base temporal + ejecutar con
    `GestorTareas`/`QThread` + verificar eventos/`error`/hilos se
    duplica en cada nueva suite.

## Próxima etapa

Integración del escaneo real de carpetas utilizando la infraestructura
asíncrona existente: seleccionar una carpeta de videos desde la interfaz
y encadenar el escaneo (detección de archivos y sincronización SQLite
completa —FFprobe y actualización/eliminación de registros ausentes—)
sobre la base de `TareaEscaneo`/`TareaGuardarVideos` y `GestorTareas`,
dentro del criterio de etapas limitadas del proyecto. Después de esa
integración, una etapa posterior de infraestructura común de pruebas
consolidará los helpers y falsificaciones que las suites repiten
(`Captura`/`correr`, bases SQLite temporales, conectores de conteo de
conexiones/hilos y de fallo controlado), sin cambiar el comportamiento
ni el contrato de los módulos probados y manteniendo
`escanear_videos.py` como única capa de datos. Solo se diseñará; no se
implementará todavía.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
