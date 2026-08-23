import glob
import math
import os
import shutil
import subprocess
import tempfile


def localizar_vlc():
    """Resuelve la ruta de `vlc.exe` sin buscar en discos.

    Orden de búsqueda:
    1. `%ProgramFiles%\\VideoLAN\\VLC\\vlc.exe`;
    2. `%ProgramFiles(x86)%\\VideoLAN\\VLC\\vlc.exe`;
    3. `vlc` en el PATH.
    """
    programas = os.environ.get("ProgramFiles") or r"C:\Program Files"
    programas_x86 = (
        os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    )
    candidatos = [
        os.path.join(programas, "VideoLAN", "VLC", "vlc.exe"),
        os.path.join(programas_x86, "VideoLAN", "VLC", "vlc.exe"),
    ]
    for candidato in candidatos:
        if candidato and os.path.isfile(candidato):
            return candidato
    ruta = shutil.which("vlc")
    if ruta:
        return ruta
    return None


def formatear_tiempo_vlc(segundos):
    """Texto de `start-time` conservando precisión decimal razonable."""
    if segundos is None or not isinstance(segundos, (int, float)):
        raise TypeError("tiempo debe ser un número")
    texto = f"{segundos:.6f}".rstrip("0").rstrip(".")
    return texto or "0"


def formatear_titulo_marcador(nombre, segundos):
    """Título descriptivo tipo `video.mp4 — 00:01:12.437`."""
    if segundos is None or not isinstance(segundos, (int, float)):
        raise TypeError("tiempo debe ser un número")
    total_ms = int(round(segundos * 1000))
    horas, resto = divmod(total_ms, 3600000)
    minutos, resto = divmod(resto, 60000)
    segundos_resto, milisegundos = divmod(resto, 1000)
    titulo_tiempo = (
        f"{horas:02d}:{minutos:02d}:{segundos_resto:02d}.{milisegundos:03d}"
    )
    nombre_limpio = str(nombre).replace("\n", " ").replace("\r", " ").strip()
    return f"{nombre_limpio} — {titulo_tiempo}"


def limpiar_playlists_anteriores(directorio):
    """Elimina playlists temporales propias previas en un directorio.

    Solo toca archivos que coinciden con el patrón propio
    `visor_marcadores_*.m3u`, en un único directorio (sin recorrer
    subdirectorios). Si un archivo está bloqueado y no puede eliminarse,
    el fallo se ignora de forma controlada y la limpieza continúa.
    """
    if not directorio or not os.path.isdir(directorio):
        return 0
    patron = os.path.join(directorio, "visor_marcadores_*.m3u")
    eliminados = 0
    for ruta in glob.glob(patron):
        try:
            os.remove(ruta)
            eliminados += 1
        except OSError:
            pass
    return eliminados


def generar_m3u(entradas, ruta_destino):
    """Escribe una playlist `.m3u` con una entrada por marcador/segmento.

    Antes de escribir elimina playlists propias anteriores del mismo
    directorio temporal, para no acumular archivos. No borra la playlist
    recién creada. Cada entrada es un diccionario con `ruta`, `nombre` y
    `tiempo`; opcionalmente `fin` (B5.6) para añadir
    `#EXTVLCOPT:stop-time=<fin>`, y `titulo` (B5.8) para sobreescribir el
    título `#EXTINF`. Sin `fin`/`titulo` el comportamiento es idéntico al
    previo (B4.4/B5.3/B5.6/B5.7 intactos).
    """
    limpiar_playlists_anteriores(os.path.dirname(ruta_destino))
    lineas = ["#EXTM3U"]
    for entrada in entradas:
        ruta = entrada["ruta"]
        nombre = entrada["nombre"]
        tiempo = entrada["tiempo"]
        if not (isinstance(ruta, str) and ruta):
            raise ValueError("ruta debe ser un texto no vacío")
        titulo = entrada.get("titulo")
        if titulo is None:
            titulo = formatear_titulo_marcador(nombre, tiempo)
        lineas.append(f"#EXTINF:-1,{titulo}")
        lineas.append(f"#EXTVLCOPT:start-time={formatear_tiempo_vlc(tiempo)}")
        fin = entrada.get("fin")
        if fin is not None:
            lineas.append(f"#EXTVLCOPT:stop-time={formatear_tiempo_vlc(fin)}")
        lineas.append(ruta)
    contenido = "\n".join(lineas) + "\n"
    with open(ruta_destino, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)
    return ruta_destino


def abrir_playlist_en_vlc(ruta_m3u, ruta_vlc, bucle=False):
    """Lanza VLC con la playlist completa.

    `bucle=True` agrega exclusivamente `--loop` (B5.7). Retrocompatible:
    el comportamiento previo (sin `bucle`) es idéntico.
    """
    argumentos = [ruta_vlc]
    if bucle:
        argumentos.append("--loop")
    argumentos.append(ruta_m3u)
    return subprocess.Popen(argumentos)


def _validar_instante(instante):
    """Valida un instante de reproducción (B5.3).

    Debe ser un número real finito mayor o igual que cero. Rechaza bool,
    texto, `None`, NaN, infinito y valores negativos. La franja ya acota el
    instante a `[0, duración]`, por lo que aquí solo se defiende la API
    pública del servicio.
    """
    if isinstance(instante, bool) or not isinstance(instante, (int, float)):
        raise TypeError("instante debe ser numérico")
    if not math.isfinite(instante):
        raise ValueError("instante debe ser un número finito")
    if instante < 0:
        raise ValueError("instante no puede ser negativo")


def reproducir_desde_instante(ruta_video, nombre, instante, ruta_vlc):
    """Abre VLC reproduciendo un video desde un instante exacto (B5.3).

    Genera una playlist temporal de una sola entrada con
    `#EXTVLCOPT:start-time=<instante>` (reutilizando la infraestructura de
    `generar_m3u`) y lanza VLC una única vez con
    `abrir_playlist_en_vlc`. No usa `stop-time` ni `--loop` todavía.

    Devuelve el proceso `Popen` de VLC. En producción la instancia queda
    bajo control del usuario (no se cierra automáticamente); los harness de
    prueba deben cerrar ese PID propio.

    Lanza:
      - `TypeError` si `instante` no es numérico (o es bool).
      - `ValueError` si `instante` es NaN, infinito o negativo.
      - `FileNotFoundError` si `ruta_video` no existe.
    """
    _validar_instante(instante)
    if not isinstance(ruta_video, str) or not ruta_video:
        raise TypeError("ruta_video debe ser un texto no vacío")
    if not os.path.isfile(ruta_video):
        raise FileNotFoundError(f"El archivo no existe: {ruta_video}")
    archivo_temporal = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".m3u",
        prefix="visor_marcadores_",
        delete=False,
        encoding="utf-8",
    )
    ruta_m3u = archivo_temporal.name
    archivo_temporal.close()
    generar_m3u(
        [{"ruta": ruta_video, "nombre": nombre, "tiempo": instante}],
        ruta_m3u,
    )
    return abrir_playlist_en_vlc(ruta_m3u, ruta_vlc)


def _validar_segmento_reproduccion(inicio, fin):
    """Valida un intervalo `[inicio, fin]` para reproducir un segmento (B5.6).

    Reutiliza `_validar_instante` para `inicio` y exige `fin` numérico,
    finito y estrictamente mayor que `inicio`. Rechaza bool, texto, NaN,
    infinito y valores negativos, y `fin <= inicio`.
    """
    _validar_instante(inicio)
    if isinstance(fin, bool) or not isinstance(fin, (int, float)):
        raise TypeError("fin debe ser numérico")
    if not math.isfinite(fin):
        raise ValueError("fin debe ser un número finito")
    if not (fin > inicio):
        raise ValueError("fin debe ser mayor que inicio")


def _preparar_playlist_segmento(ruta_video, nombre, inicio, fin, ruta_vlc):
    """Valida, genera la playlist A→B temporal y resuelve VLC (B5.6/B5.7).

    Devuelve `(ruta_m3u, ruta_vlc)`. La generación de la playlist de una
    sola entrada con `start-time`/`stop-time` es compartida por la
    reproducción simple y la reproducción en bucle.
    """
    _validar_segmento_reproduccion(inicio, fin)
    if not isinstance(ruta_video, str) or not ruta_video:
        raise TypeError("ruta_video debe ser un texto no vacío")
    if not os.path.isfile(ruta_video):
        raise FileNotFoundError(f"El archivo no existe: {ruta_video}")
    if ruta_vlc is None:
        ruta_vlc = localizar_vlc()
    if not ruta_vlc:
        raise RuntimeError("VLC no está instalado o no pudo encontrarse")
    archivo_temporal = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".m3u",
        prefix="visor_marcadores_",
        delete=False,
        encoding="utf-8",
    )
    ruta_m3u = archivo_temporal.name
    archivo_temporal.close()
    generar_m3u(
        [
            {
                "ruta": ruta_video,
                "nombre": nombre,
                "tiempo": inicio,
                "fin": fin,
            }
        ],
        ruta_m3u,
    )
    return ruta_m3u, ruta_vlc


def reproducir_segmento(ruta_video, nombre, inicio, fin, ruta_vlc=None):
    """Abre VLC reproduciendo una sola vez el intervalo [inicio, fin] (B5.6).

    Genera una playlist temporal de **una sola entrada** con
    `start-time=inicio` y `stop-time=fin`; **VLC es quien detiene la
    entrada en `fin`** (sin `--loop`, sin timers de Python ni vigilancia de
    posición). Reutiliza `generar_m3u`, la localización y la apertura
    existentes.

    Si `ruta_vlc` es `None`, se resuelve con `localizar_vlc()`. Devuelve el
    proceso `Popen` de VLC (en producción queda bajo control del usuario;
    los harness de prueba deben cerrar ese PID propio).

    Lanza:
      - `TypeError`/`ValueError` si `inicio`/`fin` no son válidos.
      - `FileNotFoundError` si `ruta_video` no existe.
      - `RuntimeError` si `ruta_vlc` es `None` y VLC no se encuentra.
    """
    ruta_m3u, ruta_vlc_resuelta = _preparar_playlist_segmento(
        ruta_video, nombre, inicio, fin, ruta_vlc
    )
    return abrir_playlist_en_vlc(ruta_m3u, ruta_vlc_resuelta)


def reproducir_segmento_en_bucle(ruta_video, nombre, inicio, fin, ruta_vlc=None):
    """Abre VLC reproduciendo [inicio, fin] en bucle continuo (B5.7).

    Misma playlist de una entrada (`start-time` + `stop-time`) que
    `reproducir_segmento`, lanzada con `--loop`: VLC reinicia la entrada en
    `inicio` al llegar a `fin` y repite indefinidamente, sin que la
    aplicación controle el reloj, consulte posición ni relance VLC.

    Devuelve el proceso `Popen` de VLC (en producción queda abierto bajo
    control del usuario, que decide cuándo detenerlo; los harness de prueba
    deben cerrar ese PID propio).

    Lanza las mismas excepciones que `reproducir_segmento`.
    """
    ruta_m3u, ruta_vlc_resuelta = _preparar_playlist_segmento(
        ruta_video, nombre, inicio, fin, ruta_vlc
    )
    return abrir_playlist_en_vlc(ruta_m3u, ruta_vlc_resuelta, bucle=True)


def formatear_titulo_segmento(nombre, inicio, fin):
    """Título descriptivo de una entrada de secuencia (B5.8).

    Formato: `<nombre> — <inicio> -> <fin>` en `HH:MM:SS.mmm`, para poder
    distinguir las entradas dentro de VLC.
    """
    texto_i = formatear_titulo_marcador("", inicio).strip()
    texto_f = formatear_titulo_marcador("", fin).strip()
    nombre_limpio = str(nombre).replace("\n", " ").replace("\r", " ").strip()
    return f"{nombre_limpio} — {texto_i} -> {texto_f}"


def reproducir_secuencia_segmentos(segmentos, ruta_vlc=None):
    """Abre VLC reproduciendo una secuencia automática de segmentos (B5.8).

    `segmentos` es una lista de dicts `{ruta, nombre, inicio, fin}`. Genera
    una playlist con **una entrada M3U por segmento** (`start-time` +
    `stop-time`), de modo que VLC reproduce A→B, avanza solo al siguiente
    segmento al llegar a cada `stop-time` y termina. Sin `--loop`, sin
    timers, sin RC/HTTP/polling.

    Valida toda la secuencia **antes** de lanzar (una entrada inválida aborta
    con un error claro; no se abre una playlist parcialmente corrupta).
    Reutiliza `generar_m3u`, los temporales, la localización y la apertura.

    Devuelve el proceso `Popen` de VLC (en producción queda abierto bajo
    control del usuario; los harness de prueba deben cerrar ese PID propio).

    Lanza:
      - `TypeError`/`ValueError` si una entrada no es un segmento válido.
      - `FileNotFoundError` si una ruta de video no existe.
      - `RuntimeError` si `ruta_vlc` es `None` y VLC no se encuentra.
    """
    if isinstance(segmentos, (str, bytes, bytearray)):
        raise TypeError("segmentos debe ser una colección de entradas")
    try:
        lista = list(segmentos)
    except TypeError:
        raise TypeError("segmentos debe ser una colección iterable") from None
    if not lista:
        raise ValueError("no hay segmentos para reproducir")
    # Validar toda la secuencia antes de lanzar VLC.
    for seg in lista:
        if not isinstance(seg, dict):
            raise TypeError("cada segmento debe ser un diccionario")
        inicio = seg.get("inicio")
        fin = seg.get("fin")
        ruta = seg.get("ruta")
        nombre = seg.get("nombre")
        if not (isinstance(ruta, str) and ruta):
            raise ValueError("ruta debe ser un texto no vacío")
        _validar_segmento_reproduccion(inicio, fin)
        if not os.path.isfile(ruta):
            raise FileNotFoundError(f"El archivo no existe: {ruta}")
        if not (isinstance(nombre, str) and nombre):
            raise ValueError("nombre debe ser un texto no vacío")
    if ruta_vlc is None:
        ruta_vlc = localizar_vlc()
    if not ruta_vlc:
        raise RuntimeError("VLC no está instalado o no pudo encontrarse")
    archivo_temporal = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".m3u",
        prefix="visor_marcadores_",
        delete=False,
        encoding="utf-8",
    )
    ruta_m3u = archivo_temporal.name
    archivo_temporal.close()
    entradas = [
        {
            "ruta": seg["ruta"],
            "nombre": seg["nombre"],
            "tiempo": seg["inicio"],
            "fin": seg["fin"],
            "titulo": formatear_titulo_segmento(
                seg["nombre"], seg["inicio"], seg["fin"]
            ),
        }
        for seg in lista
    ]
    generar_m3u(entradas, ruta_m3u)
    return abrir_playlist_en_vlc(ruta_m3u, ruta_vlc)
