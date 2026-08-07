import json
import os

from rutas import ruta_configuracion

CLAVE_CARPETA = "ultima_carpeta"
CLAVE_SUBCARPETAS = "incluir_subcarpetas"
CLAVE_CANTIDAD_PREVIEWS = "cantidad_previews"
CLAVE_ESCANEO_AUTOMATICO = "escaneo_automatico"
CLAVE_TAMANIO_MINIATURAS = "tamano_miniaturas"
TAMANIOS_VALIDOS_MINIATURAS = {"pequeno", "mediano", "grande", "muy_grande"}
CLAVE_RETARDO_VISTA_AMPLIADA = "retardo_vista_ampliada_ms"
RETARDOS_VALIDOS_VISTA_AMPLIADA = (-1, 0, 250, 400, 600)
CLAVE_TAMANO_VISTA_AMPLIADA = "tamano_vista_ampliada"
FACTORES_VALIDOS_VISTA_AMPLIADA = (1.2, 1.6, 2.0, 2.5)
VARIABLE_ENTORNO = "VISOR_CONFIG"


def _resolver_ruta_config(ruta_config):
    if ruta_config is not None:
        return ruta_config
    ruta_env = os.environ.get(VARIABLE_ENTORNO)
    if ruta_env:
        return os.path.abspath(ruta_env)
    return ruta_configuracion()


def _ruta_archivo(ruta_config):
    return _resolver_ruta_config(ruta_config)


def _leer(ruta_config):
    ruta = _ruta_archivo(ruta_config)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    return datos


def _escribir(datos, ruta_config):
    ruta = _ruta_archivo(ruta_config)
    directorio = os.path.dirname(ruta)
    os.makedirs(directorio, exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


def guardar_ultima_carpeta(carpeta, ruta_config=None):
    if not isinstance(carpeta, str) or not carpeta.strip():
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    ruta = os.path.abspath(carpeta)
    if not os.path.isdir(ruta):
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_CARPETA] = ruta
    _escribir(datos, ruta_config)
    return ruta


def obtener_ultima_carpeta(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return None
    ruta = datos.get(CLAVE_CARPETA)
    if not isinstance(ruta, str) or not ruta.strip():
        return None
    ruta_absoluta = os.path.abspath(ruta)
    if not os.path.isdir(ruta_absoluta):
        return None
    return ruta_absoluta


def guardar_preferencia_subcarpetas(activado, ruta_config=None):
    datos = _leer(ruta_config) or {}
    datos[CLAVE_SUBCARPETAS] = bool(activado)
    _escribir(datos, ruta_config)


def obtener_preferencia_subcarpetas(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return False
    valor = datos.get(CLAVE_SUBCARPETAS)
    if not isinstance(valor, bool):
        return False
    return valor


def guardar_preferencia_escaneo_automatico(activado, ruta_config=None):
    datos = _leer(ruta_config) or {}
    datos[CLAVE_ESCANEO_AUTOMATICO] = bool(activado)
    _escribir(datos, ruta_config)


def obtener_preferencia_escaneo_automatico(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return True
    valor = datos.get(CLAVE_ESCANEO_AUTOMATICO)
    if not isinstance(valor, bool):
        return True
    return valor


def guardar_cantidad_previews(n, ruta_config=None):
    datos = _leer(ruta_config) or {}
    if isinstance(n, int) and n > 0:
        datos[CLAVE_CANTIDAD_PREVIEWS] = n
    else:
        datos.pop(CLAVE_CANTIDAD_PREVIEWS, None)
    _escribir(datos, ruta_config)


def obtener_cantidad_previews(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return 3
    valor = datos.get(CLAVE_CANTIDAD_PREVIEWS)
    if isinstance(valor, int) and valor > 0:
        return valor
    return 3


def guardar_tamano_miniaturas(nombre, ruta_config=None):
    if not isinstance(nombre, str) or nombre not in TAMANIOS_VALIDOS_MINIATURAS:
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_TAMANIO_MINIATURAS] = nombre
    _escribir(datos, ruta_config)
    return nombre


def obtener_tamano_miniaturas(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return "mediano"
    valor = datos.get(CLAVE_TAMANIO_MINIATURAS)
    if not isinstance(valor, str) or valor not in TAMANIOS_VALIDOS_MINIATURAS:
        return "mediano"
    return valor


def guardar_retardo_vista_ampliada(ms, ruta_config=None):
    if (
        not isinstance(ms, int)
        or isinstance(ms, bool)
        or ms not in RETARDOS_VALIDOS_VISTA_AMPLIADA
    ):
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_RETARDO_VISTA_AMPLIADA] = ms
    _escribir(datos, ruta_config)
    return ms


def obtener_retardo_vista_ampliada(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return 400
    valor = datos.get(CLAVE_RETARDO_VISTA_AMPLIADA)
    if (
        not isinstance(valor, int)
        or isinstance(valor, bool)
        or valor not in RETARDOS_VALIDOS_VISTA_AMPLIADA
    ):
        return 400
    return valor


def guardar_tamano_vista_ampliada(factor, ruta_config=None):
    if (
        not isinstance(factor, float)
        or isinstance(factor, bool)
        or factor not in FACTORES_VALIDOS_VISTA_AMPLIADA
    ):
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_TAMANO_VISTA_AMPLIADA] = factor
    _escribir(datos, ruta_config)
    return factor


def obtener_tamano_vista_ampliada(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return 1.6
    valor = datos.get(CLAVE_TAMANO_VISTA_AMPLIADA)
    if (
        not isinstance(valor, float)
        or isinstance(valor, bool)
        or valor not in FACTORES_VALIDOS_VISTA_AMPLIADA
    ):
        return 1.6
    return valor
