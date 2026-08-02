# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), **lectura paginada del catálogo SQLite**
(`TareaLecturaCatalogoPaginada` con `LIMIT`/`OFFSET`/`COUNT` en SQL),
escritura individual asíncrona (`TareaGuardarVideo`) y escritura de
colección asíncrona (`TareaGuardarVideos`) aprobados; pendiente la
integración funcional del pipeline asíncrono del catálogo
(sincronización completa SQLite con detección de archivos y eliminación
de registros ausentes; el pipeline Escaneo → SQLite aún no está
encadenado y la interfaz no consume las tareas asíncronas; la lectura
paginada está implementada pero aún no se integra con la ventana).

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

Implementación de la lectura paginada asíncrona del catálogo
(`listar_videos_paginado` en `escanear_videos.py` +
`TareaLecturaCatalogoPaginada` en `tareas_videos.py`): consulta paginada
(`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro, ambos en SQL, orden
determinista por `nombre` y búsqueda parcial por `LIKE` parametrizada
(sin interpolación del texto), preparada para catálogos de decenas de
miles de registros sin cargar toda la tabla en memoria. Aprobada con
observaciones resueltas. La operación **no se conecta todavía con la
interfaz**; la integración de la primera carga asíncrona paginada en
`visor_videos.py` queda para la próxima etapa.

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
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo (la
sincronización completa del catálogo —detección de archivos, FFprobe y
eliminación de registros ausentes— sigue pendiente; el pipeline
Escaneo → SQLite aún no está encadenado y la interfaz no consume las
tareas asíncronas; la lectura paginada está implementada pero aún no se
integra con la ventana).

## Pendientes prioritarios

1.  Sincronización SQLite asíncrona (solo existe escritura de
    colecciones preparadas con upsert; falta la escritura masiva con
    detección de archivos, FFprobe y eliminación de registros ausentes).
2.  Integración de la primera carga asíncrona paginada en la interfaz
    (`visor_videos.py` consume `TareaLecturaCatalogoPaginada`).
3.  Integración SQLite asíncrona en el pipeline (encadenado).
4.  Actualización asíncrona de la interfaz.
5.  FFmpeg asíncrono.
6.  Varias miniaturas por video.
7.  Selección inteligente de miniaturas.
8.  Barra de progreso.
9.  Caché avanzada.
10. Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana; - la interfaz
todavía no consume las tareas asíncronas (usa la lectura síncrona); la
lectura paginada implementada aún no se integra con la ventana; -
decisión pendiente sobre si `%` y `_` como comodines `LIKE` en la
búsqueda de `listar_videos_paginado` se aceptan como contrato; - FFmpeg
continúa siendo síncrono; - siguen pendientes progreso y cancelación; -
limpieza controlada de miniaturas antiguas.

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

Integración de la primera carga asíncrona paginada en la interfaz
(`visor_videos.py`): consumir `TareaLecturaCatalogoPaginada` para cargar
la primera página del catálogo en segundo plano y mostrarla, dentro del
criterio de etapas limitadas del proyecto. Después de esa integración,
una etapa posterior de infraestructura común de pruebas consolidará los
helpers y falsificaciones que las suites repiten (`Captura`/`correr`,
bases SQLite temporales, conectores de conteo de conexiones/hilos y de
fallo controlado), sin cambiar el comportamiento ni el contrato de los
módulos probados y manteniendo `escanear_videos.py` como única capa de
datos. Solo se diseñará; no se implementará todavía.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
