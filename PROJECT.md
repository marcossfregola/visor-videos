# PROJECT — Visor de Videos

## Identidad

Visor de Videos es una aplicacion de escritorio para Windows orientada a explorar, organizar y analizar grandes colecciones de videos mediante fotogramas representativos (miniaturas y previews) sin necesidad de abrir cada archivo.

## Proposito

El proposito central es permitir identificar rapidamente el contenido de un video: que contiene, como es, y donde esta, con inspeccion visual como mecanismo principal. La aplicacion carga un catalogo desde una o mas carpetas, lo mantiene en SQLite y lo presenta como tarjetas navegables con miniaturas, previews y metadatos.

## Filosofia

- La exploracion visual es la funcion principal del producto; la reproduccion es secundaria.
- Las previews son el elemento principal de interaccion con el contenido.
- Adobe Bridge es una referencia conceptual, no una interfaz a copiar; el espacio de trabajo evoluciona hacia paneles configurables con navegacion persistente.
- El crecimiento se realiza mediante pequenas mejoras acumulativas, evitando redisenos completos.
- Funcionalidad antes que estetica: densidad visual, velocidad de navegacion y calidad de fotogramas pesan mas que un reproductor sofisticado.

## Objetivos

- Facilitar la identificacion visual de grandes colecciones de videos.
- Mantener un catalogo de metadatos consistente y sincronizado con el disco.
- Conservar una interfaz fluida con trabajo pesado fuera del hilo principal.
- Preservar los datos del usuario como prioridad absoluta.

## Alcance

- Exploracion y navegacion visual de colecciones de videos en Windows.
- Catalogo SQLite con escaneo, metadatos (FFprobe), miniaturas/previews (FFmpeg) y sincronizacion incremental.
- Operaciones seguras de archivos: copiar, pegar y eliminar (Papelera de reciclaje).
- Configuracion persistente de preferencias del usuario.

## No-alcance

- No es un editor de video tradicional con timeline.
- No es un reproductor como centro del producto.
- No realiza borrado permanente de archivos como operacion del producto.
- No compite con Premiere, Resolve u otros editores profesionales.

## Principios de producto

- **Actualizacion parcial:** modificar solo el componente afectado; evitar reconstrucciones completas que pierdan estado, scroll o seleccion.
- **Reutilizacion de cache:** reutilizar miniaturas y previews validas; no regenerar con FFmpeg informacion ya disponible.
- **Preferencias persistentes:** persistir automaticamente las opciones estables del usuario (carpeta, escaneo automatico, cantidad de previews, tamanos, vista ampliada, modo de alcance).
- **Navegacion permanente:** el arbol de navegacion y la seleccion de carpetas forman parte del contexto central.
- **Seguridad de datos:** nunca sobrescribir silenciosamente, nunca borrar sin autorizacion; ante la duda, preservar.
- **Incrementalidad:** las operaciones no deben provocar reescaneos completos innecesarios.

## Direccion futura vigente

- Espacio de trabajo de paneles independientes y configurables (infraestructura base QSplitter ya implementada).
- Centro de navegacion permanente con estructura extensible (catalogo, sistema de archivos, favoritos, etiquetas, colecciones, recientes, ultimos escaneos).
- Herramientas de manipulacion basadas en el modelo visual de escenas/previews (recorte y union) sin adoptar una interfaz de timeline.
- Organizacion (favoritos, etiquetas, puntuaciones) y administracion avanzada (deteccion de movidos, renombrado masivo, duplicados) como direccion a planificar.
- Las ideas no comprometidas viven en `BACKLOG.md`; el trabajo decidido en `ROADMAP.md`.

## Stack conceptual

- Windows.
- Python 3.13.
- PySide6 (Qt 6).
- SQLite (catalogo).
- FFmpeg y FFprobe (fotogramas y metadatos).
- Inno Setup 6 (instalador por usuario).

## Estado operativo

El estado actual, el historial y la arquitectura vigente se documentan en `STATUS.md`, `HISTORIAL_PROYECTO.md` y `ARCHITECTURE.md` respectivamente. Este documento no mezcla estado operativo.
