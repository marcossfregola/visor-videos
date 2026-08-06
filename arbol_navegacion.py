import os
import string

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

TEXTO_RAIZ = "Este equipo"
ROL_RUTA = Qt.UserRole + 1
ROL_CARGADO = Qt.UserRole + 2
ROL_PLACEHOLDER = Qt.UserRole + 3


def discos_disponibles():
    """Devuelve las unidades disponibles del sistema (solo Windows)."""
    if os.name != "nt":
        return []
    return [
        f"{letra}:\\"
        for letra in string.ascii_uppercase
        if os.path.exists(f"{letra}:\\")
    ]


def carpetas_de(ruta):
    """Devuelve los subdirectorios inmediatos de ruta, ordenados alfabeticamente.

    Tolerante ante cualquier error de acceso al sistema de archivos
    (OSError): ante un fallo devuelve una coleccion vacia sin interrumpir
    la exploracion.
    """
    try:
        with os.scandir(ruta) as entradas:
            subdirectorios = [
                e.name for e in entradas if e.is_dir()
            ]
    except OSError:
        return []
    return sorted(subdirectorios, key=str.lower)


class ArbolNavegacion(QTreeWidget):
    """Arbol visual del centro de navegacion (Etapa 2.2).

    Muestra el nodo raiz "Este equipo", los discos y sus carpetas. Las
    carpetas se cargan de forma diferida: al expandir un nodo se
    consultan unicamente sus hijos inmediatos (un solo nivel, sin
    recorrer el arbol completo). Sigue siendo pasivo: no conecta senales
    hacia el exterior, no implementa navegacion ni seleccion funcional y
    no esta integrado con el catalogo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.itemExpanded.connect(self._al_expandir)
        raiz = QTreeWidgetItem(self, [TEXTO_RAIZ])
        raiz.setExpanded(True)
        for disco in discos_disponibles():
            self._crear_nodo_disco(raiz, disco)

    def _crear_nodo_disco(self, padre, disco):
        item = QTreeWidgetItem(padre, [disco])
        item.setData(0, ROL_RUTA, disco)
        self._agregar_placeholder(item)

    def _crear_nodo_carpeta(self, padre, ruta):
        item = QTreeWidgetItem(
            padre, [os.path.basename(os.path.normpath(ruta))]
        )
        item.setData(0, ROL_RUTA, ruta)
        self._agregar_placeholder(item)

    def _agregar_placeholder(self, item):
        placeholder = QTreeWidgetItem(item)
        placeholder.setFlags(Qt.NoItemFlags)
        placeholder.setData(0, ROL_PLACEHOLDER, True)

    def _quitar_placeholder(self, item):
        for indice in range(item.childCount() - 1, -1, -1):
            hijo = item.child(indice)
            if hijo.data(0, ROL_PLACEHOLDER):
                item.removeChild(hijo)

    def _al_expandir(self, item):
        if item is None:
            return
        if item.data(0, ROL_CARGADO):
            return
        ruta = item.data(0, ROL_RUTA)
        if not isinstance(ruta, str):
            return
        self._cargar(item, ruta)

    def _cargar(self, item, ruta):
        self._quitar_placeholder(item)
        try:
            nombres = carpetas_de(ruta)
        except OSError:
            nombres = []
        for nombre in nombres:
            self._crear_nodo_carpeta(item, os.path.join(ruta, nombre))
        item.setData(0, ROL_CARGADO, True)
