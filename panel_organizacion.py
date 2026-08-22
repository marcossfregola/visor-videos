"""Panel Organización/Explorer B7.10+ — UI compacta pero genuinamente exploratoria.

Widget separado para modo Organización. No accede a SQLite, filesystem,
FFmpeg, FFprobe ni escaneo. Solo emite intenciones y recibe estado
(destino/selección/ocupado/estado navegación) desde VisorVideos. Mantiene
catálogo como área principal; panel es secundario y delimitado.

Evolución agrupada B7.10 UX + siguiente paso Explorer:
- Header claro `Destino` que diferencia visualmente origen/destino.
- Breadcrumb/ruta del destino siempre visible.
- Zona vertical que muestra simultáneamente varias subcarpetas (altura útil
  para 4-6 filas, scroll vertical cuando excede).
- Cada carpeta reconocible como carpeta (prefijo carpeta + nombre) y
  navegable por doble clic o botón Entrar/selección.
- Mantiene destino/ruta actual y control Subir.
- Acciones Mover/Copiar integradas coherentemente en el panel destino.
- Sin QSplitter global ni duplicación del catálogo origen.
- Sin acceso FS/DB/FFmpeg; reutiliza TareaListarSubcarpetasDestino del Visor.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class PanelOrganizacion(QWidget):
    """Panel Destino exploratorio (B7.10+).

    Señales emitidas (intenciones):
      - seleccionarDestinoSolicitado: usuario quiere elegir carpeta destino vía QFileDialog
      - moverSolicitado / copiarSolicitado: delegan a B7.6 con destino actual
      - entrarSubcarpetaSolicitada(str): usuario quiere navegar a subcarpeta hija
      - subirSolicitado: usuario quiere subir al padre del destino

    La UI no valida filesystem ni toca base de datos; VisorVideos resuelve
    destino y delega a TareaLoteOperaciones B7.6. El widget solo refleja
    estado recibido vía actualizar().
    """

    seleccionarDestinoSolicitado = Signal()
    moverSolicitado = Signal()
    copiarSolicitado = Signal()
    entrarSubcarpetaSolicitada = Signal(str)
    subirSolicitado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._destino_actual = None
        self._destino_valido = False
        self._cargando = False
        self._subcarpetas = []
        self._error = None
        self._puede_subir = False

        main = QVBoxLayout(self)
        main.setContentsMargins(6, 4, 6, 4)
        main.setSpacing(4)

        # ── Header claro Destino (diferencia visual origen/destino) ──
        self.etiqueta_header_destino = QLabel("Destino")
        self.etiqueta_header_destino.setObjectName("header_destino")
        self.etiqueta_header_destino.setStyleSheet(
            "color: #1a3a5c; font-weight: bold; font-size: 12px; "
            "background: #e3ecf7; border-radius: 3px; padding: 2px 6px;"
        )
        main.addWidget(self.etiqueta_header_destino)

        # ── Ruta / breadcrumb del destino ──
        self.etiqueta_destino = QLabel("Sin destino seleccionado")
        self.etiqueta_destino.setObjectName("etiqueta_destino_organizacion")
        self.etiqueta_destino.setStyleSheet("color: #333; font-size: 11px;")
        self.etiqueta_destino.setWordWrap(True)
        main.addWidget(self.etiqueta_destino)

        # ── Controles de navegación destino (Subir / Entrar + Seleccionar) ──
        fila_controles = QHBoxLayout()
        fila_controles.setSpacing(6)

        self.boton_subir_destino = QPushButton("↑ Subir")
        self.boton_subir_destino.setObjectName("boton_subir_destino")
        self.boton_subir_destino.setToolTip("Subir al padre del destino")
        self.boton_subir_destino.clicked.connect(self.subirSolicitado.emit)
        fila_controles.addWidget(self.boton_subir_destino)

        self.boton_entrar_destino = QPushButton("→ Entrar")
        self.boton_entrar_destino.setObjectName("boton_entrar_destino")
        self.boton_entrar_destino.setToolTip("Entrar en la carpeta seleccionada")
        self.boton_entrar_destino.clicked.connect(self._al_boton_entrar)
        fila_controles.addWidget(self.boton_entrar_destino)

        fila_controles.addStretch(1)

        self.boton_seleccionar_destino = QPushButton("Seleccionar destino…")
        self.boton_seleccionar_destino.setObjectName("boton_seleccionar_destino_organizacion")
        self.boton_seleccionar_destino.clicked.connect(self.seleccionarDestinoSolicitado.emit)
        fila_controles.addWidget(self.boton_seleccionar_destino)

        main.addLayout(fila_controles)

        # ── Lista vertical de carpetas del destino (varias filas + scroll) ──
        # B7.11: sin límite rígido máximo; la altura la gestiona el QSplitter vertical secundario.
        # Mantener mínimo útil y permitir expansión; catálogo sigue siendo superficie dominante.
        self.lista_subcarpetas = QListWidget()
        self.lista_subcarpetas.setObjectName("lista_subcarpetas_destino")
        self.lista_subcarpetas.setMinimumHeight(80)
        self.lista_subcarpetas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lista_subcarpetas.setStyleSheet(
            "QListWidget { background: #ffffff; border: 1px solid #b8cce0; border-radius: 3px; }"
            "QListWidget::item { padding: 3px 6px; }"
            "QListWidget::item:selected { background: #d6e4f0; color: #1a3a5c; }"
        )
        self.lista_subcarpetas.setToolTip("Doble clic o botón Entrar para navegar")
        self.lista_subcarpetas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.lista_subcarpetas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista_subcarpetas.setAlternatingRowColors(True)
        # Emisión entrar: doble clic + activación por Enter
        self.lista_subcarpetas.itemDoubleClicked.connect(self._al_doble_clic_subcarpeta)
        self.lista_subcarpetas.itemActivated.connect(self._al_doble_clic_subcarpeta)
        self.lista_subcarpetas.currentRowChanged.connect(self._al_seleccion_lista_cambia)
        main.addWidget(self.lista_subcarpetas, 1)

        self.etiqueta_estado_navegacion = QLabel("")
        self.etiqueta_estado_navegacion.setObjectName("etiqueta_estado_destino")
        self.etiqueta_estado_navegacion.setStyleSheet("color: #b00020; font-size: 11px;")
        self.etiqueta_estado_navegacion.setWordWrap(True)
        self.etiqueta_estado_navegacion.setVisible(False)
        main.addWidget(self.etiqueta_estado_navegacion)

        # ── Acciones Mover/Copiar integradas en panel destino ──
        fila_acciones = QHBoxLayout()
        fila_acciones.setSpacing(8)
        fila_acciones.addWidget(QLabel("Organizar selección → destino:"))

        self.boton_mover_seleccionados_org = QPushButton("Mover seleccionados")
        self.boton_mover_seleccionados_org.setObjectName("boton_mover_seleccionados_org")
        self.boton_mover_seleccionados_org.clicked.connect(self.moverSolicitado.emit)
        fila_acciones.addWidget(self.boton_mover_seleccionados_org)

        self.boton_copiar_seleccionados_org = QPushButton("Copiar seleccionados")
        self.boton_copiar_seleccionados_org.setObjectName("boton_copiar_seleccionados_org")
        self.boton_copiar_seleccionados_org.clicked.connect(self.copiarSolicitado.emit)
        fila_acciones.addWidget(self.boton_copiar_seleccionados_org)

        fila_acciones.addStretch(1)
        main.addLayout(fila_acciones)

        # Panel destino claramente diferenciado, sin dominar catálogo
        # B7.11: sin límite rígido máximo; el splitter gestiona la proporción. Mínimo útil + SizePolicy.
        self.setStyleSheet(
            "PanelOrganizacion { background-color: #f0f4f8; border: 1px solid #b8cce0; border-radius: 4px; }"
        )
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # estado inicial: sin destino, sin selección, no ocupado, invalido, sin subcarpetas
        self.actualizar(None, False, False)

    def _nombre_para_navegar(self, texto):
        """Normaliza texto de item a nombre de carpeta navegable o None."""
        if not isinstance(texto, str):
            try:
                texto = str(texto)
            except (ValueError, TypeError, RuntimeError) as exc:
                print(f"[B7.10+] _nombre_para_navegar conversión error: {exc}")
                return None
        try:
            texto = texto.strip()
        except (AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.10+] _nombre_para_navegar strip error: {exc}")
            return None
        if not texto or texto in ("(vacío)", "(cargando…)"):
            return None
        return texto

    def _al_doble_clic_subcarpeta(self, item):
        if item is None:
            return
        if not hasattr(item, "text"):
            return
        try:
            texto = item.text()
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.10+] _al_doble_clic_subcarpeta error: {exc}")
            return
        nombre = self._nombre_para_navegar(texto)
        if nombre:
            self.entrarSubcarpetaSolicitada.emit(nombre)

    def _al_boton_entrar(self):
        item = self.lista_subcarpetas.currentItem()
        if item is None:
            return
        try:
            texto = item.text()
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.10+] _al_boton_entrar error: {exc}")
            return
        nombre = self._nombre_para_navegar(texto)
        if nombre:
            self.entrarSubcarpetaSolicitada.emit(nombre)

    def _al_seleccion_lista_cambia(self, row):
        # B7.11: handler con comportamiento real mínimo — habilita Entrar según selección/estado.
        # Coherente con actualizar(): solo navegable si hay destino válido, sin cargando/error/bloqueo y fila navegable.
        try:
            if row < 0:
                self.boton_entrar_destino.setEnabled(False)
                return
            item = self.lista_subcarpetas.item(row)
            if item is None:
                self.boton_entrar_destino.setEnabled(False)
                return
            try:
                texto = item.text()
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] _al_seleccion_lista_cambia text error: {exc}")
                self.boton_entrar_destino.setEnabled(False)
                return
            nombre = self._nombre_para_navegar(texto)
            if nombre is None:
                self.boton_entrar_destino.setEnabled(False)
                return
            # Item navegable: habilitar solo si no bloqueado y destino válido
            if self._cargando or self._error or not self._destino_valido:
                self.boton_entrar_destino.setEnabled(False)
                return
            # No consultar ocupado directamente (visores lo gestionan), pero respetar deshabilitado por cargando/error
            self.boton_entrar_destino.setEnabled(True)
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _al_seleccion_lista_cambia error: {exc}")
            try:
                self.boton_entrar_destino.setEnabled(False)
            except (RuntimeError, AttributeError, TypeError) as exc2:
                print(f"[B7.11] setEnabled error: {exc2}")

    def actualizar(
        self,
        destino,
        tiene_seleccion,
        ocupado,
        destino_valido=None,
        subcarpetas=None,
        error=None,
        cargando=False,
        puede_subir=None,
    ):
        """Refleja estado externo sin tocar FS/DB.

        Args:
            destino: str ruta o None
            tiene_seleccion: bool
            ocupado: bool si hay tarea lote/gestor activo
            destino_valido: bool|None (None -> inferir desde destino)
            subcarpetas: list[str]|None (solo hijas inmediatas, ordenadas)
            error: str|None mensaje de destino inaccesible
            cargando: bool si navegación está cargando en background
            puede_subir: bool|None si destino tiene padre
        Mantiene compatibilidad B7.9 con llamada de 3 args.
        """
        # Destino actual
        if isinstance(destino, str) and destino.strip():
            self._destino_actual = destino.strip()
        else:
            self._destino_actual = None

        # Inferir valido si no se provee explícitamente
        if destino_valido is None:
            if error:
                self._destino_valido = False
            elif self._destino_actual is None:
                self._destino_valido = False
            else:
                self._destino_valido = True
        else:
            self._destino_valido = bool(destino_valido)

        self._cargando = bool(cargando)
        self._error = error if isinstance(error, str) and error.strip() else None
        if isinstance(subcarpetas, list):
            filtradas = []
            for s in subcarpetas:
                if isinstance(s, str) and s.strip():
                    filtradas.append(s.strip())
            self._subcarpetas = filtradas
        elif subcarpetas is None:
            self._subcarpetas = []
        else:
            self._subcarpetas = []

        if puede_subir is None:
            self._puede_subir = bool(self._destino_actual and self._destino_valido and not self._cargando)
            if not self._destino_valido:
                self._puede_subir = False
        else:
            self._puede_subir = bool(puede_subir and self._destino_valido and not self._cargando)

        # Etiqueta destino / breadcrumb / estado
        if self._error:
            if self._destino_actual:
                self.etiqueta_destino.setText(f"Destino: {self._destino_actual} — NO DISPONIBLE")
            else:
                self.etiqueta_destino.setText("Sin destino seleccionado — NO DISPONIBLE")
            self.etiqueta_destino.setStyleSheet("color: #b00020; font-weight: bold; font-size: 11px;")
            self.etiqueta_estado_navegacion.setText(self._error)
            self.etiqueta_estado_navegacion.setVisible(True)
        elif self._cargando:
            if self._destino_actual:
                self.etiqueta_destino.setText(f"Destino: {self._destino_actual}")
            else:
                self.etiqueta_destino.setText("Sin destino seleccionado")
            self.etiqueta_destino.setStyleSheet("color: #666; font-size: 11px;")
            self.etiqueta_estado_navegacion.setText("Cargando subcarpetas…")
            self.etiqueta_estado_navegacion.setVisible(True)
        elif self._destino_actual:
            self.etiqueta_destino.setText(f"Destino: {self._destino_actual}")
            self.etiqueta_destino.setStyleSheet("color: #1a3a5c; font-size: 11px;")
            if not self._subcarpetas:
                self.etiqueta_estado_navegacion.setVisible(False)
                self.etiqueta_estado_navegacion.setText("")
            else:
                self.etiqueta_estado_navegacion.setVisible(False)
                self.etiqueta_estado_navegacion.setText("")
        else:
            self.etiqueta_destino.setText("Sin destino seleccionado")
            self.etiqueta_destino.setStyleSheet("color: #666; font-size: 11px;")
            self.etiqueta_estado_navegacion.setVisible(False)
            self.etiqueta_estado_navegacion.setText("")

        # Lista subcarpetas — presentación carpeta reconocible (icono folder, texto puro para compatibilidad)
        self.lista_subcarpetas.clear()
        # Icono carpeta estándar (sin depender de tema, sin emojis en texto)
        try:
            icono_carpeta = self.style().standardIcon(QStyle.SP_DirIcon)
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.10+] icono carpeta error: {exc}")
            icono_carpeta = None
        if self._destino_actual is None:
            self.lista_subcarpetas.setEnabled(False)
        elif self._cargando:
            self.lista_subcarpetas.setEnabled(False)
            item = QListWidgetItem("(cargando…)")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.lista_subcarpetas.addItem(item)
        elif self._error:
            self.lista_subcarpetas.setEnabled(False)
        else:
            if self._subcarpetas:
                self.lista_subcarpetas.setEnabled(not bool(ocupado) and not self._cargando)
                for nombre in self._subcarpetas:
                    it = QListWidgetItem(nombre)
                    if icono_carpeta is not None and not icono_carpeta.isNull():
                        it.setIcon(icono_carpeta)
                    it.setToolTip(f"Carpeta: {nombre} — doble clic o Entrar para navegar")
                    self.lista_subcarpetas.addItem(it)
            else:
                self.lista_subcarpetas.setEnabled(False)
                it = QListWidgetItem("(vacío)")
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
                self.lista_subcarpetas.addItem(it)

        # Controles navegación
        bloqueado = bool(ocupado or self._cargando)
        self.boton_seleccionar_destino.setEnabled(not bool(ocupado))
        self.boton_subir_destino.setEnabled(bool(self._puede_subir and not bloqueado and self._destino_valido))
        # Entrar habilitado solo si hay selección navegable y no bloqueado
        tiene_item_navegable = bool(self._subcarpetas and not self._error and not self._cargando and not bloqueado)
        # Si lista tiene selección navegable, habilitar; si no, deshabilitar
        # No inspeccionar currentItem aquí para no acoplar UI a modelo; habilitar genérico si hay carpetas
        self.boton_entrar_destino.setEnabled(bool(tiene_item_navegable and self._destino_valido))
        # B7.11: habilitación fina se afina en _al_seleccion_lista_cambia según fila actual
        if bloqueado and self.lista_subcarpetas.isEnabled():
            self.lista_subcarpetas.setEnabled(False)
            self.boton_entrar_destino.setEnabled(False)

        # Mover/Copiar: habilitados solo destino válido + selección + no ocupado + no cargando/error
        habilitado = bool(self._destino_valido and tiene_seleccion and not ocupado and not self._cargando and not self._error)
        self.boton_mover_seleccionados_org.setEnabled(habilitado)
        self.boton_copiar_seleccionados_org.setEnabled(habilitado)

    def destino(self):
        return self._destino_actual
