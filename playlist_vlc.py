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
    """Escribe una playlist `.m3u` con una entrada por marcador.

    Antes de escribir elimina playlists propias anteriores del mismo
    directorio temporal, para no acumular archivos. No borra la playlist
    recién creada. Cada entrada es un diccionario con `ruta`, `nombre` y
    `tiempo`.
    """
    limpiar_playlists_anteriores(os.path.dirname(ruta_destino))
    lineas = ["#EXTM3U"]
    for entrada in entradas:
        ruta = entrada["ruta"]
        nombre = entrada["nombre"]
        tiempo = entrada["tiempo"]
        if not (isinstance(ruta, str) and ruta):
            raise ValueError("ruta debe ser un texto no vacío")
        lineas.append(f"#EXTINF:-1,{formatear_titulo_marcador(nombre, tiempo)}")
        lineas.append(f"#EXTVLCOPT:start-time={formatear_tiempo_vlc(tiempo)}")
        lineas.append(ruta)
    contenido = "\n".join(lineas) + "\n"
    with open(ruta_destino, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)
    return ruta_destino


def abrir_playlist_en_vlc(ruta_m3u, ruta_vlc):
    """Lanza VLC una única vez con la playlist completa."""
    return subprocess.Popen([ruta_vlc, ruta_m3u])


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
