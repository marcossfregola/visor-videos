import os
import string
from enum import IntEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
)

TEXTO_RAIZ = "Este equipo"
ROL_RUTA = Qt.UserRole + 1
ROL_CARGADO = Qt.UserRole + 2
ROL_PLACEHOLDER = Qt.UserRole + 3
ROL_ESTADO = Qt.UserRole + 4


class EstadoNodo(IntEnum):
    """Estados visuales posibles de un nodo del arbol.

    Por ahora solo se utilizan SIN_ESCANEAR y ESCANEADA; los restantes
    quedan preparados para etapas futuras sin cambiar la API publica.
    """

    SIN_ESCANEAR = 0
    ESCANEADA = 1
    PARCIAL = 2
    CAMBIOS_PENDIENTES = 3
    ERROR = 4


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
    """Arbol del centro de navegacion (Etapa 2.9).

    Muestra "Este equipo", los discos y sus carpetas con carga diferida
    por nivel y permite la seleccion funcional de discos y carpetas. La
    carpeta actual queda almacenada en el propio arbol y se consulta
    mediante `carpeta_actual()`; la señal `ruta_seleccionada` solo
    notifica cambios de seleccion. `seleccionar_ruta()` sincroniza la
    seleccion con nodos ya cargados (sin cargar carpetas nuevas);
    `revelar_ruta()` reconstruye incrementalmente la rama necesaria para
    mostrar una carpeta persistida (expandendo nivel por nivel con la
    carga diferida existente). `marcar_carpeta_escaneada()` actualiza el
    **indicador visual** de una carpeta escaneada (estado por nodo en
    `ROL_ESTADO` mediante `EstadoNodo`), sin cambiar el comportamiento de
    navegacion. El arbol no es la fuente de verdad de la carpeta activa
    de la aplicacion: puede cambiarla y reflejarla, pero `carpeta_actual()`
    representa únicamente el estado interno del widget. El nodo raiz
    "Este equipo" y los placeholders internos nunca son selecciones
    validas.
    """

    ruta_seleccionada = Signal(str)
    nueva_carpeta_solicitada = Signal(str)

    def __init__(self, parent=None, seleccion=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self._ruta_actual = None
        self._carpetas_escaneadas = set()
        self._seleccion = seleccion
        self._modo_seleccion = False
        self._sincronizando_checks = False
        self.currentItemChanged.connect(self._al_cambiar_actual)
        self.itemExpanded.connect(self._al_expandir)
        self.itemChanged.connect(self._al_item_cambiado)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._al_menu_contextual)
        raiz = QTreeWidgetItem(self, [TEXTO_RAIZ])
        raiz.setExpanded(True)
        self._aplicar_check(raiz)
        for disco in discos_disponibles():
            self._crear_nodo_disco(raiz, disco)

    def carpeta_actual(self):
        """Devuelve la ruta absoluta seleccionada o None si no hay ninguna."""
        return self._ruta_actual

    def marcar_carpeta_escaneada(self, ruta):
        """Marca una carpeta como escaneada y actualiza su indicador visual.

        Solo afecta el estado visual del nodo; no altera la seleccion, la
        expansion ni la navegacion. Si el nodo aun no esta cargado, se
        marcara al crearse (la pertenencia se consulta en `_estado_de`).
        """
        if not isinstance(ruta, str) or not ruta:
            return
        self._carpetas_escaneadas.add(ruta)
        nodo = self._buscar_ruta(self.topLevelItem(0), ruta)
        if nodo is not None:
            self._aplicar_indicador(nodo)

    def _estado_de(self, item):
        if item.data(0, ROL_RUTA) in self._carpetas_escaneadas:
            return EstadoNodo.ESCANEADA
        return EstadoNodo.SIN_ESCANEAR

    def _aplicar_indicador(self, item):
        estado = self._estado_de(item)
        item.setData(0, ROL_ESTADO, int(estado))
        item.setIcon(0, self._icono_para(estado))

    def _icono_para(self, estado):
        if estado == EstadoNodo.ESCANEADA:
            return self.style().standardIcon(QStyle.SP_DialogApplyButton)
        return QIcon()

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

    def set_modo_seleccion(self, activo):
        """Activa o desactiva el modo de seleccion de carpetas.

        Con el modo activo, cada carpeta cargada muestra un checkbox cuyo
        estado refleja exclusivamente `SeleccionCarpetas`; marcarlo o
        desmarcarlo modifica unicamente el conjunto seleccionado, sin
        cambiar la carpeta activa, sin iniciar escaneos y sin alterar la
        navegacion. Con el modo desactivado el arbol se comporta
        exactamente como antes (sin checkboxes).
        """
        self._modo_seleccion = bool(activo)
        self._reaplicar_checks_a_todos()

    def _reaplicar_checks_a_todos(self):
        raiz = self.topLevelItem(0)
        if raiz is None:
            return
        for indice in range(raiz.childCount()):
            self._reaplicar_checks_en(raiz.child(indice))

    def _reaplicar_checks_en(self, item):
        if item is None:
            return
        self._aplicar_check(item)
        for indice in range(item.childCount()):
            self._reaplicar_checks_en(item.child(indice))

    def _aplicar_check(self, item):
        if item is None:
            return
        ruta = self._ruta_valida(item)
        self._sincronizando_checks = True
        try:
            if self._modo_seleccion and ruta is not None and self._seleccion is not None:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                marcado = ruta in self._seleccion.obtener_seleccion()
                item.setCheckState(
                    0, Qt.Checked if marcado else Qt.Unchecked
                )
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
        finally:
            self._sincronizando_checks = False

    def _al_item_cambiado(self, item, columna):
        if self._sincronizando_checks:
            return
        if columna != 0:
            return
        if not self._modo_seleccion:
            return
        if self._seleccion is None:
            return
        if not (item.flags() & Qt.ItemIsUserCheckable):
            return
        ruta = self._ruta_valida(item)
        if ruta is None:
            return
        seleccion_actual = self._seleccion.obtener_seleccion()
        esperado = Qt.Checked if ruta in seleccion_actual else Qt.Unchecked
        if item.checkState(0) == esperado:
            return
        if item.checkState(0) == Qt.Checked:
            self._seleccion.seleccionar(ruta)
        else:
            self._seleccion.deseleccionar(ruta)

    def _hijos_ordenados(self, item):
        """Devuelve los nodos de carpetas cargados de un nivel, en orden visual."""
        if item is None:
            return []
        hijos = []
        for indice in range(item.childCount()):
            hijo = item.child(indice)
            if self._ruta_valida(hijo) is not None:
                hijos.append(hijo)
        return hijos

    @staticmethod
    def _rutas_de(nodos):
        return [nodo.data(0, ROL_RUTA) for nodo in nodos]

    def _reemplazar_seleccion(self, rutas):
        self._seleccion.limpiar()
        self._seleccion.seleccionar_todas(rutas)

    def _refrescar_checks(self, nodos):
        for nodo in nodos:
            self._aplicar_check(nodo)

    def _nivel_actual(self):
        item = self.currentItem()
        if item is None or self._ruta_valida(item) is None:
            return None
        return item

    def _rango_hasta(self, nodo):
        hermanos = self._hijos_ordenados(nodo.parent())
        try:
            indice = hermanos.index(nodo)
        except ValueError:
            return []
        return hermanos[: indice + 1]

    def _rango_desde(self, nodo):
        hermanos = self._hijos_ordenados(nodo.parent())
        try:
            indice = hermanos.index(nodo)
        except ValueError:
            return []
        return hermanos[indice:]

    def seleccionar_todas_nivel(self):
        """Selecciona todas las subcarpetas cargadas del nivel actual."""
        if self._seleccion is None:
            return
        nivel = self._nivel_actual()
        if nivel is None:
            return
        nodos = self._hijos_ordenados(nivel)
        if not nodos:
            return
        self._seleccion.seleccionar_todas(self._rutas_de(nodos))
        self._refrescar_checks(nodos)

    def deseleccionar_todas(self):
        """Vacía por completo la selección de carpetas."""
        if self._seleccion is None:
            return
        self._seleccion.limpiar()
        self._reaplicar_checks_a_todos()

    def invertir_nivel(self):
        """Invierte la selección dentro del nivel actual (conserva lo externo)."""
        if self._seleccion is None:
            return
        nivel = self._nivel_actual()
        if nivel is None:
            return
        nodos = self._hijos_ordenados(nivel)
        if not nodos:
            return
        actual = self._seleccion.obtener_seleccion()
        rutas = set(self._rutas_de(nodos))
        final = (actual - rutas) | (rutas - actual)
        self._reemplazar_seleccion(final)
        self._refrescar_checks(nodos)

    def seleccionar_hasta(self, nodo):
        if self._seleccion is None or nodo is None:
            return
        nodos = self._rango_hasta(nodo)
        if not nodos:
            return
        self._seleccion.seleccionar_todas(self._rutas_de(nodos))
        self._refrescar_checks(nodos)

    def deseleccionar_hasta(self, nodo):
        if self._seleccion is None or nodo is None:
            return
        nodos = self._rango_hasta(nodo)
        if not nodos:
            return
        quitar = set(self._rutas_de(nodos))
        actual = self._seleccion.obtener_seleccion()
        self._reemplazar_seleccion(actual - quitar)
        self._refrescar_checks(nodos)

    def seleccionar_desde(self, nodo):
        if self._seleccion is None or nodo is None:
            return
        nodos = self._rango_desde(nodo)
        if not nodos:
            return
        self._seleccion.seleccionar_todas(self._rutas_de(nodos))
        self._refrescar_checks(nodos)

    def deseleccionar_desde(self, nodo):
        if self._seleccion is None or nodo is None:
            return
        nodos = self._rango_desde(nodo)
        if not nodos:
            return
        quitar = set(self._rutas_de(nodos))
        actual = self._seleccion.obtener_seleccion()
        self._reemplazar_seleccion(actual - quitar)
        self._refrescar_checks(nodos)

    def _al_menu_contextual(self, pos):
        item = self.itemAt(pos)
        ruta = self._ruta_valida(item)
        if ruta is None:
            return
        menu = QMenu(self)
        accion_nueva_carpeta = menu.addAction("Nueva carpeta…")
        # Acciones existentes solo en modo selección
        accion_seleccionar_hasta = None
        accion_seleccionar_desde = None
        accion_deseleccionar_hasta = None
        accion_deseleccionar_desde = None
        if self._modo_seleccion:
            menu.addSeparator()
            accion_seleccionar_hasta = menu.addAction("Seleccionar hasta aquí")
            accion_seleccionar_desde = menu.addAction(
                "Seleccionar desde aquí hasta el final"
            )
            accion_deseleccionar_hasta = menu.addAction(
                "Deseleccionar hasta aquí"
            )
            accion_deseleccionar_desde = menu.addAction(
                "Deseleccionar desde aquí hasta el final"
            )
        elegida = menu.exec(QCursor.pos())
        if elegida == accion_nueva_carpeta:
            self.nueva_carpeta_solicitada.emit(ruta)
            return
        if self._modo_seleccion:
            if elegida == accion_seleccionar_hasta:
                self.seleccionar_hasta(item)
            elif elegida == accion_seleccionar_desde:
                self.seleccionar_desde(item)
            elif elegida == accion_deseleccionar_hasta:
                self.deseleccionar_hasta(item)
            elif elegida == accion_deseleccionar_desde:
                self.deseleccionar_desde(item)

    def refrescar_carpeta(self, ruta_padre):
        """Refresca únicamente la rama de ruta_padre tras crear carpeta (B7.3).

        Si el nodo padre está cargado, limpia hijos y recarga desde FS
        (orden alfabético via carpetas_de). Si no está cargado, expande
        para disparar carga diferida. Retorna True si el padre fue hallado.
        No hace reescaneo de videos. No borra nada.
        """
        if not isinstance(ruta_padre, str) or not ruta_padre:
            return False
        raiz = self.topLevelItem(0)
        nodo = self._buscar_ruta(raiz, ruta_padre)
        if nodo is None:
            # Intentar revelar incrementalmente
            try:
                if not self.revelar_ruta(ruta_padre):
                    return False
                nodo = self._buscar_ruta(raiz, ruta_padre)
                if nodo is None:
                    return False
            except Exception:
                return False
        # Si no está cargado, expandir para cargar
        if not nodo.data(0, ROL_CARGADO):
            if not nodo.isExpanded():
                self.expandItem(nodo)
            else:
                # Ya expandido pero no cargado (raro): forzar carga
                self._cargar(nodo, ruta_padre)
            return True
        # Ya cargado: limpiar hijos y recargar
        self._sincronizando_checks = True
        try:
            while nodo.childCount() > 0:
                child = nodo.child(0)
                nodo.removeChild(child)
            # Recargar desde FS
            try:
                nombres = carpetas_de(ruta_padre)
            except OSError:
                nombres = []
            for nombre in nombres:
                self._crear_nodo_carpeta(nodo, os.path.join(ruta_padre, nombre))
            nodo.setData(0, ROL_CARGADO, True)
            if not nodo.isExpanded():
                nodo.setExpanded(True)
        finally:
            self._sincronizando_checks = False
        return True

    def _crear_nodo_disco(self, padre, disco):
        self._sincronizando_checks = True
        try:
            item = QTreeWidgetItem(padre, [disco])
            item.setData(0, ROL_RUTA, disco)
            self._agregar_placeholder(item)
            self._aplicar_indicador(item)
            self._aplicar_check(item)
        finally:
            self._sincronizando_checks = False
        return item

    def _crear_nodo_carpeta(self, padre, ruta):
        self._sincronizando_checks = True
        try:
            item = QTreeWidgetItem(
                padre, [os.path.basename(os.path.normpath(ruta))]
            )
            item.setData(0, ROL_RUTA, ruta)
            self._agregar_placeholder(item)
            self._aplicar_indicador(item)
            self._aplicar_check(item)
        finally:
            self._sincronizando_checks = False
        return item

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
