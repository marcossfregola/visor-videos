import os
import string

from PySide6.QtCore import Qt, Signal
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
    """Arbol del centro de navegacion (Etapa 2.5).

    Muestra "Este equipo", los discos y sus carpetas con carga diferida
    por nivel y permite la seleccion funcional de discos y carpetas. La
    carpeta actual queda almacenada en el propio arbol y se consulta
    mediante `carpeta_actual()`; la señal `ruta_seleccionada` solo
    notifica cambios de seleccion. `seleccionar_ruta()` sincroniza la
    seleccion con nodos ya cargados (sin cargar carpetas nuevas);
    `revelar_ruta()` reconstruye incrementalmente la rama necesaria para
    mostrar una carpeta persistida (expandendo nivel por nivel con la
    carga diferida existente). El arbol no es la fuente de verdad de la
    carpeta activa de la aplicacion: puede cambiarla y reflejarla, pero
    `carpeta_actual()` representa únicamente el estado interno del
    widget. El nodo raiz "Este equipo" y los placeholders internos nunca
    son selecciones validas.
    """

    ruta_seleccionada = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self._ruta_actual = None
        self.currentItemChanged.connect(self._al_cambiar_actual)
        self.itemExpanded.connect(self._al_expandir)
        raiz = QTreeWidgetItem(self, [TEXTO_RAIZ])
        raiz.setExpanded(True)
        for disco in discos_disponibles():
            self._crear_nodo_disco(raiz, disco)

    def carpeta_actual(self):
        """Devuelve la ruta absoluta seleccionada o None si no hay ninguna."""
        return self._ruta_actual

    def seleccionar_ruta(self, ruta):
        """Selecciona en el arbol el nodo ya cargado cuya ruta coincide.

        Busca únicamente entre los nodos actualmente cargados (sin
        recorrer el sistema de archivos ni cargar carpetas nuevas). Si
        el nodo no esta presente, no modifica la seleccion existente.
        """
        if not isinstance(ruta, str) or not ruta:
            return
        nodo = self._buscar_ruta(self.topLevelItem(0), ruta)
        if nodo is None:
            return
        padre = nodo.parent()
        while padre is not None:
            padre.setExpanded(True)
            padre = padre.parent()
        self.setCurrentItem(nodo)

    def _buscar_ruta(self, item, ruta):
        if item is None:
            return None
        if item.data(0, ROL_RUTA) == ruta:
            return item
        for indice in range(item.childCount()):
            encontrado = self._buscar_ruta(item.child(indice), ruta)
            if encontrado is not None:
                return encontrado
        return None

    def revelar_ruta(self, ruta):
        """Expande la cadena de ancestros de ruta y selecciona la carpeta.

        Estrictamente incremental: ubica el disco que contiene la ruta,
        expande ese nivel y en cada nivel busca unicamente el siguiente
        componente de la ruta, continuando hasta la carpeta destino. No
        recorre el arbol ni el disco completos y no carga ramas ajenas al
        camino. Si la ruta no puede reconstruirse (disco ausente, carpeta
        eliminada o camino cambiado) devuelve False sin lanzar y sin
        modificar la seleccion existente.
        """
        if not isinstance(ruta, str) or not ruta:
            return False
        ruta_norm = os.path.normpath(ruta)
        if not os.path.isdir(ruta_norm):
            return False
        raiz = self.topLevelItem(0)
        disco = self._buscar_disco(raiz, ruta_norm)
        if disco is None:
            return False
        ruta_disco = disco.data(0, ROL_RUTA)
        if ruta_norm == os.path.normpath(ruta_disco):
            self.setCurrentItem(disco)
            return True
        if not disco.isExpanded():
            self.expandItem(disco)
        relativo = os.path.relpath(ruta_norm, ruta_disco)
        partes = [p for p in relativo.split(os.sep) if p]
        nodo = disco
        acumulado = ruta_disco
        for indice, parte in enumerate(partes):
            acumulado = os.path.normpath(os.path.join(acumulado, parte))
            hijo = self._buscar_hijo_por_ruta(nodo, acumulado)
            if hijo is None:
                return False
            if indice == len(partes) - 1:
                self.setCurrentItem(hijo)
                return True
            if not hijo.isExpanded():
                self.expandItem(hijo)
            nodo = hijo
        return False

    def _buscar_disco(self, raiz, ruta):
        if raiz is None:
            return None
        for indice in range(raiz.childCount()):
            hijo = raiz.child(indice)
            disco = hijo.data(0, ROL_RUTA)
            if not isinstance(disco, str):
                continue
            try:
                comun = os.path.commonpath([os.path.normpath(disco), ruta])
            except ValueError:
                continue
            if comun == os.path.normpath(disco):
                return hijo
        return None

    def _buscar_hijo_por_ruta(self, item, ruta):
        if item is None:
            return None
        ruta_norm = os.path.normcase(ruta)
        for indice in range(item.childCount()):
            hijo = item.child(indice)
            ruta_hijo = hijo.data(0, ROL_RUTA)
            if isinstance(ruta_hijo, str) and os.path.normcase(ruta_hijo) == ruta_norm:
                return hijo
        return None

    def _ruta_valida(self, item):
        if item is None:
            return None
        if item.data(0, ROL_PLACEHOLDER):
            return None
        ruta = item.data(0, ROL_RUTA)
        if isinstance(ruta, str) and ruta:
            return ruta
        return None

    def _al_cambiar_actual(self, actual, anterior):
        if (
            anterior is not None
            and anterior.data(0, ROL_RUTA) == self._ruta_actual
            and anterior.isHidden()
        ):
            return
        ruta = self._ruta_valida(actual)
        if ruta is None:
            return
        self._ruta_actual = ruta
        self.ruta_seleccionada.emit(ruta)

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
