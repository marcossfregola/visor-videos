import json
import os

from escanear_videos import (
    CLAVES_COLOR_CLASIFICACION,
    ORDEN_CRITERIO_DEFAULT,
    ORDEN_CRITERIOS,
    ORDEN_DIRECCION_DEFAULT,
    ORDEN_DIRECCIONES,
)
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
FACTORES_VALIDOS_VISTA_AMPLIADA = (1.2, 1.6, 2.0, 2.5, 3.0, 3.5)
FACTOR_VISTA_AMPLIADA_DESACTIVADO = 0
CLAVE_SELECCION_CARPETAS = "carpetas_seleccionadas"
CLAVE_MODO_ALCANCE = "modo_alcance"
MODO_ALCANCE_SOLO = "solo_carpeta"
MODO_ALCANCE_SUBCARPETAS = "con_subcarpetas"
MODO_ALCANCE_SELECCION = "seleccion_personalizada"
MODOS_ALCANCE_VALIDOS = (
    MODO_ALCANCE_SOLO,
    MODO_ALCANCE_SUBCARPETAS,
    MODO_ALCANCE_SELECCION,
)
VARIABLE_ENTORNO = "VISOR_CONFIG"

VERSION_PRODUCTO = "Beta 9"
BUILD_IDENTIFICADOR = "B9.9"
TEXTO_VERSION_BUILD = f"{VERSION_PRODUCTO} - {BUILD_IDENTIFICADOR}"


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
    if not isinstance(factor, bool) and (
        factor == FACTOR_VISTA_AMPLIADA_DESACTIVADO
        or factor == float(FACTOR_VISTA_AMPLIADA_DESACTIVADO)
    ):
        datos = _leer(ruta_config) or {}
        datos[CLAVE_TAMANO_VISTA_AMPLIADA] = FACTOR_VISTA_AMPLIADA_DESACTIVADO
        _escribir(datos, ruta_config)
        return FACTOR_VISTA_AMPLIADA_DESACTIVADO
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
    if not isinstance(valor, bool) and (
        valor == FACTOR_VISTA_AMPLIADA_DESACTIVADO
        or valor == float(FACTOR_VISTA_AMPLIADA_DESACTIVADO)
    ):
        return FACTOR_VISTA_AMPLIADA_DESACTIVADO
    if (
        not isinstance(valor, float)
        or isinstance(valor, bool)
        or valor not in FACTORES_VALIDOS_VISTA_AMPLIADA
    ):
        return 1.6
    return valor


def guardar_seleccion_carpetas(rutas, ruta_config=None):
    lista = []
    vistas = set()
    if isinstance(rutas, (list, tuple, set)):
        for r in rutas:
            if not isinstance(r, str) or not r.strip():
                continue
            ruta = os.path.abspath(r)
            if ruta in vistas:
                continue
            vistas.add(ruta)
            lista.append(ruta)
    datos = _leer(ruta_config) or {}
    datos[CLAVE_SELECCION_CARPETAS] = lista
    _escribir(datos, ruta_config)


def obtener_seleccion_carpetas(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return []
    valor = datos.get(CLAVE_SELECCION_CARPETAS)
    if not isinstance(valor, list):
        return []
    rutas = []
    for r in valor:
        if not isinstance(r, str) or not r.strip():
            continue
        ruta = os.path.abspath(r)
        if ruta not in rutas and os.path.isdir(ruta):
            rutas.append(ruta)
    return rutas


def guardar_modo_alcance(modo, ruta_config=None):
    if not isinstance(modo, str) or modo not in MODOS_ALCANCE_VALIDOS:
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_MODO_ALCANCE] = modo
    datos[CLAVE_SUBCARPETAS] = modo == MODO_ALCANCE_SUBCARPETAS
    _escribir(datos, ruta_config)
    return modo


def obtener_modo_alcance(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return MODO_ALCANCE_SOLO
    valor = datos.get(CLAVE_MODO_ALCANCE)
    if isinstance(valor, str) and valor in MODOS_ALCANCE_VALIDOS:
        return valor
    subcarpetas = datos.get(CLAVE_SUBCARPETAS)
    if isinstance(subcarpetas, bool):
        return (
            MODO_ALCANCE_SUBCARPETAS
            if subcarpetas
            else MODO_ALCANCE_SOLO
        )
    return MODO_ALCANCE_SOLO


CLAVE_ORDEN_CRITERIO = "orden_catalogo_clave"
CLAVE_ORDEN_DIRECCION = "orden_catalogo_direccion"


def guardar_orden_catalogo(clave, direccion, ruta_config=None):
    if not isinstance(clave, str) or clave not in ORDEN_CRITERIOS:
        return None
    if not isinstance(direccion, str) or direccion not in ORDEN_DIRECCIONES:
        return None
    datos = _leer(ruta_config) or {}
    datos[CLAVE_ORDEN_CRITERIO] = clave
    datos[CLAVE_ORDEN_DIRECCION] = direccion
    _escribir(datos, ruta_config)
    return (clave, direccion)


def obtener_orden_catalogo(ruta_config=None):
    datos = _leer(ruta_config)
    if datos is None:
        return (ORDEN_CRITERIO_DEFAULT, ORDEN_DIRECCION_DEFAULT)
    clave = datos.get(CLAVE_ORDEN_CRITERIO)
    if not isinstance(clave, str) or clave not in ORDEN_CRITERIOS:
        clave = ORDEN_CRITERIO_DEFAULT
    direccion = datos.get(CLAVE_ORDEN_DIRECCION)
    if not isinstance(direccion, str) or direccion not in ORDEN_DIRECCIONES:
        direccion = ORDEN_DIRECCION_DEFAULT
    return (clave, direccion)


CLAVE_NOMBRES_COLORES = "nombres_colores"
LIMITE_LONGITUD_NOMBRE_COLOR = 40
NOMBRES_COLORES_POR_DEFECTO = {
    "rojo": "Rojo",
    "naranja": "Naranja",
    "amarillo": "Amarillo",
    "verde": "Verde",
    "azul": "Azul",
    "violeta": "Violeta",
}


def guardar_nombre_color(clave, nombre, ruta_config=None):
    """Guarda el nombre global opcional de un color (B6.3).

    Permite solo claves estables de la paleta. Un nombre vacío (o solo
    espacios) elimina el nombre configurado y restaura el de fábrica. Si el
    nombre (recortado) supera `LIMITE_LONGITUD_NOMBRE_COLOR`, no se guarda.
    Devuelve el texto efectivo o `None` si la clave/nombre no es válido.
    """
    if not isinstance(clave, str) or clave not in CLAVES_COLOR_CLASIFICACION:
        return None
    if not isinstance(nombre, str):
        return None
    nombre_normalizado = nombre.strip()
    if len(nombre_normalizado) > LIMITE_LONGITUD_NOMBRE_COLOR:
        return None
    datos = _leer(ruta_config) or {}
    nombres = datos.get(CLAVE_NOMBRES_COLORES)
    if not isinstance(nombres, dict):
        nombres = {}
    if nombre_normalizado:
        nombres[clave] = nombre_normalizado
    else:
        nombres.pop(clave, None)
    datos[CLAVE_NOMBRES_COLORES] = nombres
    _escribir(datos, ruta_config)
    return nombre_normalizado or NOMBRES_COLORES_POR_DEFECTO[clave]


def obtener_nombres_colores(ruta_config=None):
    """Devuelve las claves→nombres configurados (solo claves válidas,
    recortadas y dentro del límite)."""
    datos = _leer(ruta_config)
    if datos is None:
        return {}
    valor = datos.get(CLAVE_NOMBRES_COLORES)
    if not isinstance(valor, dict):
        return {}
    nombres = {}
    for clave, nombre in valor.items():
        if not isinstance(clave, str) or clave not in CLAVES_COLOR_CLASIFICACION:
            continue
        if not isinstance(nombre, str):
            continue
        nombre = nombre.strip()
        if not nombre:
            continue
        if len(nombre) > LIMITE_LONGITUD_NOMBRE_COLOR:
            continue
        nombres[clave] = nombre
    return nombres


def texto_color(clave, ruta_config=None):
    """Texto visible de una clave: el nombre global configurado o el de
    fábrica. `None` si la clave no pertenece a la paleta."""
    if not isinstance(clave, str) or clave not in CLAVES_COLOR_CLASIFICACION:
        return None
    nombres = obtener_nombres_colores(ruta_config)
    return nombres.get(clave, NOMBRES_COLORES_POR_DEFECTO[clave])
