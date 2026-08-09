import glob
import os
import shutil
import subprocess


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
