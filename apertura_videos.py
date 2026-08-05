import os


def abrir_video_con_aplicacion_predeterminada(nombre, carpeta):
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("nombre debe ser un texto no vacío")
    if not isinstance(carpeta, str) or not carpeta.strip():
        raise ValueError("carpeta debe ser un texto no vacío")
    ruta = os.path.abspath(os.path.join(carpeta, nombre))
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"El archivo no existe: {ruta}")
    os.startfile(ruta)
    return ruta
