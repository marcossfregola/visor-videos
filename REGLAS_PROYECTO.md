# REGLAS DEL PROYECTO

## Objetivo

Este documento contiene las reglas permanentes de desarrollo del
proyecto.

Todas las etapas futuras deberán respetarlas salvo autorización expresa
de ChatGPT.

## 1. Metodología

-   El proyecto avanza mediante etapas pequeñas, verificables y
    acumulativas.
-   Cada etapa debe tener un único objetivo claramente definido.
-   No mezclar funcionalidades grandes en una misma implementación.
-   No avanzar a una nueva etapa antes de aprobar la anterior.

## 2. Inspección previa

Antes de modificar cualquier archivo se debe: - inspeccionar el estado
actual del proyecto; - identificar los archivos a modificar; -
justificar por qué son necesarios; - indicar qué archivos no serán
modificados.

## 3. Cambios

-   Modificar únicamente los archivos estrictamente necesarios.
-   No realizar refactorizaciones innecesarias.
-   No introducir cambios ajenos al alcance de la etapa.

## 4. Auditoría

Al finalizar cada etapa se debe entregar: - archivos creados; - archivos
modificados; - archivos eliminados; - explicación técnica; - pruebas
realmente ejecutadas; - limitaciones restantes; - salida de
`git status`.

Nunca afirmar pruebas no ejecutadas ni verificaciones visuales no
realizadas.

## 5. Commits

Flujo obligatorio:

Implementación → Pruebas → Auditoría → Aprobación → Commit

-   Nunca crear commits por iniciativa propia.
-   Un commit por etapa aprobada.
-   No mezclar cambios.
-   Árbol limpio tras cada commit.

## 6. Preservación de archivos

Nunca eliminar, sobrescribir, reemplazar, mover ni renombrar archivos
existentes sin autorización expresa.

Incluye bases de datos, miniaturas, cachés, archivos temporales,
ignorados por Git y datos de prueba.

Ante la duda: preservar.

## 7. Arquitectura

Mantener separación entre: - interfaz; - lógica de catálogo; - SQLite; -
escaneo; - FFprobe; - FFmpeg; - caché; - trabajos en segundo plano; -
configuración.

La interfaz nunca debe acceder directamente a SQLite, FFprobe, FFmpeg,
archivos ni lógica pesada.

## 8. Evidencia

Diferenciar siempre: - código modificado; - archivos generados durante
pruebas; - cambios reales en SQLite; - cambios reales en miniaturas; -
archivos ignorados por Git.

## 9. Documentación

Cuando cambie la arquitectura o el comportamiento técnico: - verificar
si `DOCUMENTO_TECNICO.md` requiere actualización; - informarlo aunque no
forme parte de la etapa.

## 10. Calidad

Prioridades: 1. Seguridad de los datos. 2. Arquitectura. 3.
Mantenibilidad. 4. Estabilidad. 5. Rendimiento. 6. Nuevas
funcionalidades.
