import os

from configuracion import (
    guardar_seleccion_carpetas,
    obtener_seleccion_carpetas,
)


class SeleccionCarpetas:
    def __init__(self, ruta_config=None):
        self._seleccion = set()
        self._ruta_config = ruta_config
        self._restaurar()

    def _normalizar(self, ruta):
        if not isinstance(ruta, str) or not ruta.strip():
            return None
        ruta_absoluta = os.path.abspath(ruta)
        if not os.path.isdir(ruta_absoluta):
            return None
        return ruta_absoluta

    def _persistir(self):
        guardar_seleccion_carpetas(sorted(self._seleccion), self._ruta_config)

    def _restaurar(self):
        for ruta in obtener_seleccion_carpetas(self._ruta_config):
            ruta_normalizada = self._normalizar(ruta)
            if ruta_normalizada is not None:
                self._seleccion.add(ruta_normalizada)

    def seleccionar(self, ruta):
        ruta_normalizada = self._normalizar(ruta)
        if ruta_normalizada is None:
            return False
        if ruta_normalizada not in self._seleccion:
            self._seleccion.add(ruta_normalizada)
            self._persistir()
        return True

    def deseleccionar(self, ruta):
        if not isinstance(ruta, str) or not ruta.strip():
            return False
        ruta_normalizada = os.path.abspath(ruta)
        if ruta_normalizada in self._seleccion:
            self._seleccion.discard(ruta_normalizada)
            self._persistir()
        return ruta_normalizada not in self._seleccion

    def alternar(self, ruta):
        ruta_normalizada = self._normalizar(ruta)
        if ruta_normalizada is None:
            return False
        if ruta_normalizada in self._seleccion:
            self._seleccion.discard(ruta_normalizada)
            self._persistir()
            return False
        self._seleccion.add(ruta_normalizada)
        self._persistir()
        return True

    def limpiar(self):
        if self._seleccion:
            self._seleccion.clear()
            self._persistir()

    def seleccionar_todas(self, lista):
        agregadas = 0
        for ruta in lista:
            ruta_normalizada = self._normalizar(ruta)
            if ruta_normalizada is None:
                continue
            if ruta_normalizada not in self._seleccion:
                self._seleccion.add(ruta_normalizada)
                agregadas += 1
        if agregadas:
            self._persistir()
        return agregadas

    def obtener_seleccion(self):
        return set(self._seleccion)
