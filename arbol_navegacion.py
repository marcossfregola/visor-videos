import os
import string

from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

TEXTO_RAIZ = "Este equipo"


def discos_disponibles():
    """Devuelve las unidades disponibles del sistema (solo Windows)."""
    if os.name != "nt":
        return []
    return [
        f"{letra}:\\"
        for letra in string.ascii_uppercase
        if os.path.exists(f"{letra}:\\")
    ]


class ArbolNavegacion(QTreeWidget):
    """Arbol visual del centro de navegacion (Etapa 2.1).

    Contiene unicamente el nodo raiz "Este equipo" y los discos
    disponibles del sistema como hijos. Es completamente pasivo:
    no conecta senales, no implementa navegacion ni seleccion
    funcional y no esta integrado con el resto de la aplicacion.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        raiz = QTreeWidgetItem(self, [TEXTO_RAIZ])
        raiz.setExpanded(True)
        for disco in discos_disponibles():
            QTreeWidgetItem(raiz, [disco])
