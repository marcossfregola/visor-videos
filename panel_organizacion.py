"""Panel Organización/Explorer B7.9 — UI compacta sin acceso a FS/DB/FFmpeg.

Widget separado para modo Organización. No accede a SQLite, filesystem,
FFmpeg, FFprobe ni escaneo. Solo emite intenciones y recibe estado
(destino/selección/ocupado) desde VisorVideos. Mantiene catálogo como
área principal; panel es compacto.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class PanelOrganizacion(QWidget):
    """Barra destino compacta para modo Organización.

    Señales emitidas (intenciones):
      - seleccionarDestinoSolicitado: usuario quiere elegir carpeta destino
      - moverSolicitado: usuario quiere mover seleccionados a destino actual
      - copiarSolicitado: usuario quiere copiar seleccionados a destino actual

    La UI no valida filesystem ni toca base de datos; VisorVideos resuelve
    destino y delega a TareaLoteOperaciones B7.6. El widget solo refleja
    estado recibido vía actualizar().
    """

    seleccionarDestinoSolicitado = Signal()
    moverSolicitado = Signal()
    copiarSolicitado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._destino_actual = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        self.etiqueta_destino = QLabel("Sin destino seleccionado")
        self.etiqueta_destino.setObjectName("etiqueta_destino_organizacion")
        self.etiqueta_destino.setStyleSheet("color: #333;")
        layout.addWidget(self.etiqueta_destino, 1)

        self.boton_seleccionar_destino = QPushButton("Seleccionar destino…")
        self.boton_seleccionar_destino.setObjectName("boton_seleccionar_destino_organizacion")
        self.boton_seleccionar_destino.clicked.connect(self.seleccionarDestinoSolicitado.emit)
        layout.addWidget(self.boton_seleccionar_destino)

        self.boton_mover_seleccionados_org = QPushButton("Mover seleccionados")
        self.boton_mover_seleccionados_org.setObjectName("boton_mover_seleccionados_org")
        self.boton_mover_seleccionados_org.clicked.connect(self.moverSolicitado.emit)
        layout.addWidget(self.boton_mover_seleccionados_org)

        self.boton_copiar_seleccionados_org = QPushButton("Copiar seleccionados")
        self.boton_copiar_seleccionados_org.setObjectName("boton_copiar_seleccionados_org")
        self.boton_copiar_seleccionados_org.clicked.connect(self.copiarSolicitado.emit)
        layout.addWidget(self.boton_copiar_seleccionados_org)

        self.setStyleSheet("PanelOrganizacion { background-color: #f7f7f7; border: 1px solid #ddd; }")
        # estado inicial: sin destino, sin selección, no ocupado
        self.actualizar(None, False, False)

    def actualizar(self, destino, tiene_seleccion, ocupado):
        """Refleja estado externo sin tocar FS/DB.

        Args:
            destino: str ruta o None
            tiene_seleccion: bool
            ocupado: bool si hay tarea lote/gestor activo
        """
        self._destino_actual = destino if isinstance(destino, str) and destino.strip() else None
        if self._destino_actual:
            self.etiqueta_destino.setText(f"Destino: {self._destino_actual}")
        else:
            self.etiqueta_destino.setText("Sin destino seleccionado")

        # seleccionar destino habilitado salvo tarea activa (coherente con bloqueo)
        self.boton_seleccionar_destino.setEnabled(not bool(ocupado))

        habilitado = bool(self._destino_actual and tiene_seleccion and not ocupado)
        self.boton_mover_seleccionados_org.setEnabled(habilitado)
        self.boton_copiar_seleccionados_org.setEnabled(habilitado)

    def destino(self):
        return self._destino_actual
