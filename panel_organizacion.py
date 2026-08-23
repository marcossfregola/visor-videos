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
- B7.12 prepara selección estable de carpeta objetivo para futuro soltado:
  identificación de objetivo (destino raíz o subcarpeta hija), estado visual
  claro y contrato de señales sin implementar gesto de arrastre.
- B7.13A implementa receptor mínimo drag&drop interno con MIME privado que
  transporta IDs de video y señal dropVideosSolicitado sin tocar FS/SQLite.
"""

import json

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QBrush, QColor
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


# ── B7.13A — receptor mínimo drag&drop interno ──
# MIME privado estable para transporte de IDs de video dentro de la app.
# No aceptar URLs/texto genérico.
MIME_VIDEOS_IDS = "application/x-visor-videos-ids-b713a"


def _serializar_ids_videos_para_mime(ids):
    """Serializa lista ordenada de video_id a bytes para MIME privado.

    Valida que sean enteros positivos (sin bool) y lista no vacía.
    Retorna bytes JSON UTF-8 o None si inválido.
    """
    try:
        if not isinstance(ids, list) or len(ids) == 0:
            return None
        for v in ids:
            if type(v) is not int:
                return None
            if v <= 0:
                return None
        return json.dumps(ids, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        print(f"[B7.13A] _serializar_ids_videos error: {exc}")
        return None


def _deserializar_ids_videos_desde_mime(payload_bytes):
    """Deserializa payload MIME a lista ordenada de video_id o None si inválido.

    Rechaza vacío, corrupto, no lista, tipos inválidos, IDs <=0, bool, duplicados aceptados
    pero deben ser positivos y orden preservado.
    """
    try:
        if payload_bytes is None:
            return None
        # QByteArray -> bytes
        if not isinstance(payload_bytes, (bytes, bytearray)):
            try:
                payload_bytes = bytes(payload_bytes)
            except (TypeError, ValueError, RuntimeError) as exc:
                print(f"[B7.13A] _deserializar conversión bytes error: {exc}")
                return None
        if len(payload_bytes) == 0:
            return None
        try:
            texto = payload_bytes.decode("utf-8")
        except (UnicodeDecodeError, AttributeError, ValueError) as exc:
            print(f"[B7.13A] _deserializar decode error: {exc}")
            return None
        try:
            obj = json.loads(texto)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            print(f"[B7.13A] _deserializar JSON error: {exc}")
            return None
        if not isinstance(obj, list) or len(obj) == 0:
            return None
        for v in obj:
            if type(v) is not int:
                return None
            if v <= 0:
                return None
        return obj
    except (TypeError, ValueError, RuntimeError) as exc:
        print(f"[B7.13A] _deserializar error inesperado: {exc}")
        return None


class PanelOrganizacion(QWidget):
    """Panel Destino exploratorio (B7.10+).

    Señales emitidas (intenciones):
      - seleccionarDestinoSolicitado: usuario quiere elegir carpeta destino vía QFileDialog
      - moverSolicitado / copiarSolicitado: delegan a B7.6 con destino actual
      - entrarSubcarpetaSolicitada(str): usuario quiere navegar a subcarpeta hija
      - subirSolicitado: usuario quiere subir al padre del destino
      - objetivoSeleccionado(object): B7.12 — carpeta objetivo para futuro soltado
        (str nombre de subcarpeta hija o None si objetivo es destino raíz).
      - dropVideosSolicitado(object, object): B7.13A — drop interno válido
        (list[int] video_ids ordenados, str|None objetivo).

    La UI no valida filesystem ni toca base de datos; VisorVideos resuelve
    destino y delega a TareaLoteOperaciones B7.6. El widget solo refleja
    estado recibido vía actualizar(). B7.12 añade identificación estable del
    objetivo sin gesto de arrastre. B7.13A añade receptor drop mínimo.
    """

    seleccionarDestinoSolicitado = Signal()
    moverSolicitado = Signal()
    copiarSolicitado = Signal()
    entrarSubcarpetaSolicitada = Signal(str)
    subirSolicitado = Signal()
    objetivoSeleccionado = Signal(object)
    dropVideosSolicitado = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._destino_actual = None
        self._destino_valido = False
        self._cargando = False
        self._subcarpetas = []
        self._error = None
        self._puede_subir = False
        self._objetivo_nombre = None
        self._ocupado = False
        self._drag_hover_activo = False
        # B7.13D — estado transitorio hover drag (no muta selección normal)
        self._drop_hover_objetivo_nombre = None
        self._drop_hover_row = -1
        self._estilo_base_panel = "PanelOrganizacion { background-color: #f0f4f8; border: 1px solid #b8cce0; border-radius: 4px; }"
        self._estilo_highlight_panel = "PanelOrganizacion { background-color: #e8f4ff; border: 2px solid #2196F3; border-radius: 4px; }"
        self.setAcceptDrops(True)

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
        self.lista_subcarpetas.setSelectionMode(QListWidget.SingleSelection)
        # Emisión entrar: doble clic + activación por Enter
        self.lista_subcarpetas.itemDoubleClicked.connect(self._al_doble_clic_subcarpeta)
        self.lista_subcarpetas.itemActivated.connect(self._al_doble_clic_subcarpeta)
        self.lista_subcarpetas.currentRowChanged.connect(self._al_seleccion_lista_cambia)
        self.lista_subcarpetas.itemClicked.connect(self._al_item_clic_objetivo)
        main.addWidget(self.lista_subcarpetas, 1)
        # B7.13D — forwarding drag sobre lista/viewport para hit test por posición física
        try:
            self.lista_subcarpetas.setAcceptDrops(True)
            self.lista_subcarpetas.viewport().setAcceptDrops(True)
            self.lista_subcarpetas.installEventFilter(self)
            self.lista_subcarpetas.viewport().installEventFilter(self)
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13D] installEventFilter error: {exc}")

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
        self.setStyleSheet(self._estilo_base_panel)
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

    def _al_item_clic_objetivo(self, item):
        # B7.12: clic simple selecciona objetivo estable para futuro soltado
        # sin navegar. Reutiliza _al_seleccion_lista_cambia para coherencia.
        try:
            row = self.lista_subcarpetas.row(item) if item is not None else -1
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.12] _al_item_clic_objetivo row error: {exc}")
            return
        self._al_seleccion_lista_cambia(row)

    def _emitir_objetivo(self, nombre):
        # B7.12: emite objetivo estable solo si destino válido y no bloqueado
        # nombre es str o None (None = destino raíz)
        try:
            if self._cargando or self._error or not self._destino_valido:
                # en estado no válido, objetivo siempre None (destino no disponible)
                if self._objetivo_nombre is not None:
                    self._objetivo_nombre = None
                    self.objetivoSeleccionado.emit(None)
                return
            # validar nombre contra subcarpetas conocidas si no es None
            if nombre is not None:
                if not isinstance(nombre, str) or not nombre.strip():
                    nombre = None
                elif nombre not in self._subcarpetas:
                    nombre = None
            if nombre == self._objetivo_nombre:
                return
            self._objetivo_nombre = nombre
            self.objetivoSeleccionado.emit(nombre)
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.12] _emitir_objetivo error: {exc}")

    def _al_seleccion_lista_cambia(self, row):
        # B7.11: handler con comportamiento real mínimo — habilita Entrar según selección/estado.
        # Coherente con actualizar(): solo navegable si hay destino válido, sin cargando/error/bloqueo y fila navegable.
        # B7.12: además gestiona identificación estable del objetivo para futuro soltado.
        try:
            if row < 0:
                self.boton_entrar_destino.setEnabled(False)
                self._emitir_objetivo(None)
                return
            item = self.lista_subcarpetas.item(row)
            if item is None:
                self.boton_entrar_destino.setEnabled(False)
                self._emitir_objetivo(None)
                return
            try:
                texto = item.text()
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] _al_seleccion_lista_cambia text error: {exc}")
                self.boton_entrar_destino.setEnabled(False)
                self._emitir_objetivo(None)
                return
            nombre = self._nombre_para_navegar(texto)
            if nombre is None:
                self.boton_entrar_destino.setEnabled(False)
                self._emitir_objetivo(None)
                return
            # Item navegable: habilitar solo si no bloqueado y destino válido
            if self._cargando or self._error or not self._destino_valido:
                self.boton_entrar_destino.setEnabled(False)
                self._emitir_objetivo(None)
                return
            # No consultar ocupado directamente (visores lo gestionan), pero respetar deshabilitado por cargando/error
            self.boton_entrar_destino.setEnabled(True)
            self._emitir_objetivo(nombre)
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _al_seleccion_lista_cambia error: {exc}")
            try:
                self.boton_entrar_destino.setEnabled(False)
            except (RuntimeError, AttributeError, TypeError) as exc2:
                print(f"[B7.11] setEnabled error: {exc2}")
            try:
                self._emitir_objetivo(None)
            except (RuntimeError, AttributeError, TypeError) as exc3:
                print(f"[B7.12] objetivo emit error tras fallo: {exc3}")

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
        self._ocupado = bool(ocupado)
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

        # Reset objetivo previo: emisión diferida tras reconstruir lista para evitar señales intermedias
        objetivo_previo = getattr(self, "_objetivo_nombre", None)
        # Bloquear señal currentRowChanged durante reconstrucción para emitir objetivo coherente una sola vez
        try:
            self.lista_subcarpetas.blockSignals(True)
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.12] blockSignals error: {exc}")
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
                    it.setToolTip(f"Carpeta: {nombre} — clic para seleccionar objetivo, doble clic o Entrar para navegar")
                    self.lista_subcarpetas.addItem(it)
            else:
                self.lista_subcarpetas.setEnabled(False)
                it = QListWidgetItem("(vacío)")
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
                self.lista_subcarpetas.addItem(it)
        try:
            self.lista_subcarpetas.blockSignals(False)
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"[B7.12] unblockSignals error: {exc}")
        # B7.12: reset objetivo tras reconstruir: destino raíz por defecto (None) si inválido/cargando/vacío
        # Si había objetivo previo y sigue existiendo, restaurarlo sin emitir duplicado innecesario
        if self._cargando or self._error or not self._destino_valido:
            self._objetivo_nombre = None
        elif not self._subcarpetas:
            if self._objetivo_nombre is not None:
                self._objetivo_nombre = None
                try:
                    self.objetivoSeleccionado.emit(None)
                except (RuntimeError, AttributeError, TypeError) as exc:
                    print(f"[B7.12] emitir objetivo None error: {exc}")
            else:
                self._objetivo_nombre = None
        else:
            # hay subcarpetas válidas: si objetivo previo ya no existe, reset a None
            if objetivo_previo is not None and objetivo_previo not in self._subcarpetas:
                self._objetivo_nombre = None
                try:
                    self.objetivoSeleccionado.emit(None)
                except (RuntimeError, AttributeError, TypeError) as exc:
                    print(f"[B7.12] emitir objetivo reset error: {exc}")
            # si no hay selección actual (row -1), objetivo debe ser None (destino raíz)
            try:
                cur = self.lista_subcarpetas.currentRow()
                if cur < 0 and self._objetivo_nombre is not None:
                    self._objetivo_nombre = None
                    self.objetivoSeleccionado.emit(None)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.12] currentRow check error: {exc}")

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
        # B7.13C: si estado ya no es utilizable, asegurar highlight limpio sin dejar panel resaltado
        try:
            if getattr(self, "_drag_hover_activo", False) and not self._drop_destino_utilizable():
                self._desactivar_highlight_drag()
        except (AttributeError, TypeError, RuntimeError):
            _ = None
        # B7.13D: limpiar hover de fila si estado ya no utilizable o lista cambió
        try:
            if getattr(self, "_drop_hover_row", -1) != -1 or getattr(self, "_drop_hover_objetivo_nombre", None) is not None:
                if not self._drop_destino_utilizable():
                    self._limpiar_hover_y_fila()
                else:
                    # si fila hover ya no existe en subcarpetas, limpiar
                    hover = getattr(self, "_drop_hover_objetivo_nombre", None)
                    if hover is not None and hover not in self._subcarpetas:
                        self._limpiar_hover_y_fila()
        except (AttributeError, TypeError, RuntimeError):
            _ = None

    def destino(self):
        return self._destino_actual

    def objetivo_nombre(self):
        """B7.12: nombre de subcarpeta objetivo actual o None si destino raíz/no válido."""
        return getattr(self, "_objetivo_nombre", None)

    def objetivo_es_destino_raiz(self):
        """True si objetivo es destino raíz (None) y destino válido."""
        return self._objetivo_nombre is None and bool(self._destino_valido) and not self._cargando and not self._error

    # ── B7.13C — highlight simple destino válido ──
    def _activar_highlight_drag(self):
        """Activa highlight visual simple (stylesheet). Sin overlay ni contador."""
        try:
            if getattr(self, "_drag_hover_activo", False):
                return
            self._drag_hover_activo = True
            self.setStyleSheet(self._estilo_highlight_panel)
            try:
                self.update()
            except (AttributeError, TypeError, RuntimeError):
                _ = None
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] _activar_highlight error: {exc}")

    def _desactivar_highlight_drag(self):
        """Limpia highlight simple siempre (dragLeave, drop, inválido, cancelación)."""
        try:
            was = bool(getattr(self, "_drag_hover_activo", False))
            self._drag_hover_activo = False
            try:
                cur = self.styleSheet()
                if was or "2196F3" in cur:
                    self.setStyleSheet(self._estilo_base_panel)
                    try:
                        self.update()
                    except (AttributeError, TypeError, RuntimeError):
                        _ = None
            except (AttributeError, TypeError, RuntimeError) as exc2:
                print(f"[B7.13C] styleSheet check error: {exc2}")
                try:
                    self.setStyleSheet(self._estilo_base_panel)
                except (AttributeError, TypeError, RuntimeError):
                    _ = None
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] _desactivar_highlight error: {exc}")
            try:
                self._drag_hover_activo = False
                self.setStyleSheet(self._estilo_base_panel)
            except (AttributeError, TypeError, RuntimeError):
                _ = None

    def is_drag_highlight_activo(self):
        """Helper para tests: True si highlight visual activo."""
        return bool(getattr(self, "_drag_hover_activo", False))

    # ── B7.13D — hover transitorio y highlight de fila por posición física ──
    def drop_hover_objetivo_nombre(self):
        """B7.13D: objetivo hover transitorio (str hija o None raíz). No muta selección."""
        return getattr(self, "_drop_hover_objetivo_nombre", None)

    def drop_hover_row(self):
        """B7.13D: row hover transitorio (-1 si ninguno)."""
        try:
            return int(getattr(self, "_drop_hover_row", -1))
        except (TypeError, ValueError, AttributeError):
            return -1

    def is_row_highlight_activo(self, row=None):
        """B7.13D helper tests: True si fila hover highlight activo (row específico o cualquiera)."""
        try:
            cur = int(getattr(self, "_drop_hover_row", -1))
            if row is None:
                return cur >= 0
            return cur == int(row)
        except (TypeError, ValueError, AttributeError):
            return False

    def _pos_a_viewport(self, event, source_obj=None):
        """Convierte posición del evento a coordenadas del viewport de lista_subcarpetas.

        source_obj es el widget que recibió el evento (Panel, QListWidget o viewport).
        Usa event.position() (Qt6) o event.pos() como fallback.
        Retorna QPoint en coords viewport o None si no mapeable / sin posición (mock).
        """
        try:
            # extraer posición en coords del source
            pos = None
            try:
                if hasattr(event, "position"):
                    # Qt6 QPointF
                    pf = event.position()
                    if pf is not None:
                        try:
                            pos = pf.toPoint()
                        except (AttributeError, TypeError):
                            pos = None
                if pos is None and hasattr(event, "pos"):
                    try:
                        pos = event.pos()
                    except (AttributeError, TypeError, RuntimeError):
                        pos = None
            except (AttributeError, TypeError, RuntimeError):
                pos = None
            if pos is None:
                # mock sin posición
                return None
            # si source es viewport, pos ya es viewport
            try:
                vp = self.lista_subcarpetas.viewport()
            except (AttributeError, TypeError, RuntimeError):
                return None
            if source_obj is vp:
                return pos
            elif source_obj is self.lista_subcarpetas:
                try:
                    return vp.mapFrom(self.lista_subcarpetas, pos)
                except (AttributeError, TypeError, RuntimeError):
                    return pos
            else:
                # panel u otro hijo (header, botones, fondo) -> mapear panel->viewport
                try:
                    return vp.mapFrom(self, pos)
                except (AttributeError, TypeError, RuntimeError):
                    try:
                        # fallback panel->lista->viewport
                        lp = self.lista_subcarpetas.mapFrom(self, pos)
                        return vp.mapFrom(self.lista_subcarpetas, lp)
                    except (AttributeError, TypeError, RuntimeError):
                        return None
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] _pos_a_viewport error: {exc}")
            return None

    def _hit_test_fila_bajo_cursor(self, event, source_obj=None):
        """Detecta fila válida bajo cursor por posición física.

        Usa itemAt en coords viewport. Valida por _nombre_para_navegar y contra
        _subcarpetas conocidas si lista no vacía. Retorna (nombre, row) o (None, -1).
        No usa currentItem ni selección previa.
        """
        try:
            pos_vp = self._pos_a_viewport(event, source_obj)
            if pos_vp is None:
                # sin posición determinable (mock) -> tratar como sin hit distinguible
                return None, -1
            # verificar dentro del rect viewport; si fuera, es fondo
            try:
                vp = self.lista_subcarpetas.viewport()
                if not vp.rect().contains(pos_vp):
                    return None, -1
            except (AttributeError, TypeError, RuntimeError):
                _ = None
            try:
                item = self.lista_subcarpetas.itemAt(pos_vp)
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13D] itemAt error: {exc}")
                return None, -1
            if item is None:
                return None, -1
            try:
                texto = item.text()
            except (AttributeError, TypeError, RuntimeError):
                return None, -1
            nombre = self._nombre_para_navegar(texto)
            if nombre is None:
                return None, -1
            # validar contra subcarpetas conocidas si hay lista
            try:
                if self._subcarpetas and nombre not in self._subcarpetas:
                    return None, -1
            except (AttributeError, TypeError):
                _ = None
            try:
                row = self.lista_subcarpetas.row(item)
            except (AttributeError, TypeError, RuntimeError):
                row = -1
            return nombre, row
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] _hit_test error: {exc}")
            return None, -1

    def _limpiar_highlight_fila_especifica(self, row):
        try:
            if row is None or int(row) < 0:
                return
            item = self.lista_subcarpetas.item(int(row))
            if item is None:
                return
            try:
                item.setBackground(QBrush())
                try:
                    item.setData(Qt.BackgroundRole, None)
                except (AttributeError, TypeError, RuntimeError):
                    _ = None
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13D] limpiar highlight fila error: {exc}")
        except (AttributeError, TypeError, RuntimeError, ValueError):
            _ = None
            _ = None

    def _aplicar_highlight_fila(self, row):
        try:
            if row is None or int(row) < 0:
                return
            item = self.lista_subcarpetas.item(int(row))
            if item is None:
                return
            try:
                brush = QBrush(QColor("#b3d9ff"))
                item.setBackground(brush)
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13D] aplicar highlight fila error: {exc}")
        except (AttributeError, TypeError, RuntimeError, ValueError):
            _ = None
            _ = None

    def _set_hover_objetivo(self, nombre, row):
        """Actualiza hover transitorio y highlight de fila. Retorna True si cambió."""
        try:
            old_nombre = getattr(self, "_drop_hover_objetivo_nombre", None)
            old_row = int(getattr(self, "_drop_hover_row", -1))
        except (AttributeError, TypeError, ValueError):
            old_nombre = None
            old_row = -1
        # normalizar row
        try:
            row_int = int(row) if row is not None else -1
        except (TypeError, ValueError):
            row_int = -1
        if nombre == old_nombre and row_int == old_row:
            return False
        # limpiar highlight anterior si cambia de fila
        if old_row != -1 and old_row != row_int:
            self._limpiar_highlight_fila_especifica(old_row)
        # si nuevo es None, ya limpiado
        self._drop_hover_objetivo_nombre = nombre
        self._drop_hover_row = row_int if nombre is not None else -1
        if nombre is not None and row_int >= 0:
            self._aplicar_highlight_fila(row_int)
        return True
    def _limpiar_hover_y_fila(self):
        """Limpia hover transitorio y highlight de fila (no panel highlight)."""
        try:
            old_row = int(getattr(self, "_drop_hover_row", -1))
            if old_row != -1:
                self._limpiar_highlight_fila_especifica(old_row)
        except (AttributeError, TypeError, ValueError):
            _ = None
        self._drop_hover_objetivo_nombre = None
        self._drop_hover_row = -1

    def _actualizar_hover_por_evento(self, event, source_obj=None):
        """Actualiza hover según posición física del cursor durante drag. Retorna nombre hover."""
        try:
            if not self._drop_destino_utilizable():
                self._limpiar_hover_y_fila()
                return None
            # validar MIME antes de mostrar hover
            try:
                mime = event.mimeData()
            except (AttributeError, TypeError, RuntimeError):
                self._limpiar_hover_y_fila()
                return None
            ids = self._validar_mime_y_payload(mime)
            if ids is None:
                self._limpiar_hover_y_fila()
                return None
            nombre, row = self._hit_test_fila_bajo_cursor(event, source_obj)
            # nombre es str válido o None
            self._set_hover_objetivo(nombre, row)
            return nombre
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] _actualizar_hover error: {exc}")
            try:
                self._limpiar_hover_y_fila()
            except (AttributeError, TypeError, RuntimeError):
                _ = None
            return None

    def eventFilter(self, obj, event):
        """B7.13D forwarding de drag sobre lista_subcarpetas/viewport para hit test correcto."""
        try:
            # solo interceptar lista y viewport
            if obj is self.lista_subcarpetas or obj is self.lista_subcarpetas.viewport():
                et = event.type()
                if et == QEvent.DragEnter:
                    # procesar con source_obj para mapeo correcto
                    try:
                        if not self._drop_destino_utilizable():
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        ids = self._validar_mime_y_payload(event.mimeData())
                        if ids is None:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        self._activar_highlight_drag()
                        self._actualizar_hover_por_evento(event, obj)
                        event.acceptProposedAction()
                        return True
                    except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
                        print(f"[B7.13D] eventFilter DragEnter error: {exc}")
                        try:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                        except (AttributeError, TypeError, RuntimeError):
                            _ = None
                        return True
                elif et == QEvent.DragMove:
                    try:
                        if not self._drop_destino_utilizable():
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        ids = self._validar_mime_y_payload(event.mimeData())
                        if ids is None:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        self._activar_highlight_drag()
                        self._actualizar_hover_por_evento(event, obj)
                        event.acceptProposedAction()
                        return True
                    except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
                        print(f"[B7.13D] eventFilter DragMove error: {exc}")
                        try:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                        except (AttributeError, TypeError, RuntimeError):
                            _ = None
                        return True
                elif et == QEvent.DragLeave:
                    try:
                        self._limpiar_hover_y_fila()
                        self._desactivar_highlight_drag()
                        try:
                            event.accept()
                        except (AttributeError, TypeError, RuntimeError):
                            _ = None
                    except (AttributeError, TypeError, RuntimeError) as exc:
                        print(f"[B7.13D] eventFilter DragLeave error: {exc}")
                    return True
                elif et == QEvent.Drop:
                    try:
                        if not self._drop_destino_utilizable():
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        ids = self._validar_mime_y_payload(event.mimeData())
                        if ids is None:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        # hit test físico en el instante del drop
                        nombre_hit, row_hit = self._hit_test_fila_bajo_cursor(event, obj)
                        # Detección de mock sin posición: fallback a hover previo o selección estable
                        has_pos = self._pos_a_viewport(event, obj) is not None
                        objetivo = None
                        if nombre_hit is not None:
                            objetivo = nombre_hit
                        else:
                            if not has_pos:
                                # mock sin coords: fallback a hover si existe, sino selección estable para regresión
                                hover = getattr(self, "_drop_hover_objetivo_nombre", None)
                                if hover is not None:
                                    objetivo = hover
                                else:
                                    try:
                                        objetivo = self.objetivo_nombre()
                                    except (AttributeError, TypeError, RuntimeError):
                                        objetivo = None
                            else:
                                # pos válida pero fondo -> raíz
                                objetivo = None
                        try:
                            self.dropVideosSolicitado.emit(list(ids), objetivo)
                        except (AttributeError, TypeError, RuntimeError) as exc:
                            print(f"[B7.13D] emit drop via filter error: {exc}")
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                            return True
                        event.acceptProposedAction()
                        self._limpiar_hover_y_fila()
                        self._desactivar_highlight_drag()
                        return True
                    except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
                        print(f"[B7.13D] eventFilter Drop error: {exc}")
                        try:
                            self._limpiar_hover_y_fila()
                            self._desactivar_highlight_drag()
                            event.ignore()
                        except (AttributeError, TypeError, RuntimeError):
                            _ = None
                        return True
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] eventFilter general error: {exc}")
        return super().eventFilter(obj, event)

    # ── B7.13A — receptor drop mínimo ──
    def _drop_destino_utilizable(self):
        """True si estado actual permite aceptar drop (válido, sin cargar/error/bloqueo)."""
        try:
            if self._cargando:
                return False
            if self._error:
                return False
            if not self._destino_valido:
                return False
            if getattr(self, "_ocupado", False):
                return False
            if self._destino_actual is None:
                return False
            return True
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13A] _drop_destino_utilizable error: {exc}")
            return False

    def _validar_mime_y_payload(self, mime_data):
        """Valida MIME privado y payload. Retorna lista ids o None si inválido."""
        try:
            if mime_data is None:
                return None
            try:
                has = mime_data.hasFormat(MIME_VIDEOS_IDS)
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13A] hasFormat error: {exc}")
                return None
            if not has:
                return None
            # Rechazar URLs/texto genérico no es necesario si no tiene MIME privado,
            # pero si lo tiene, validar payload y no aceptar si corrupto.
            try:
                qbytes = mime_data.data(MIME_VIDEOS_IDS)
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13A] mime data error: {exc}")
                return None
            try:
                payload = bytes(qbytes)
            except (TypeError, ValueError, RuntimeError) as exc:
                print(f"[B7.13A] bytes conversion error: {exc}")
                return None
            return _deserializar_ids_videos_desde_mime(payload)
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13A] _validar_mime_y_payload error: {exc}")
            return None

    def dragEnterEvent(self, event):
        """B7.13D: acepta drag válido y actualiza hover por posición física."""
        try:
            if not self._drop_destino_utilizable():
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            mime = event.mimeData()
            ids = self._validar_mime_y_payload(mime)
            if ids is None:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            self._activar_highlight_drag()
            self._actualizar_hover_por_evento(event, self)
            event.acceptProposedAction()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] dragEnterEvent error: {exc}")
            try:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
            except (AttributeError, TypeError, RuntimeError):
                _ = None
            try:
                event.ignore()
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13D] dragEnterEvent ignore error: {exc2}")

    def dragMoveEvent(self, event):
        """B7.13D: mantiene aceptación y actualiza hover por posición física."""
        try:
            if not self._drop_destino_utilizable():
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            mime = event.mimeData()
            ids = self._validar_mime_y_payload(mime)
            if ids is None:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            self._activar_highlight_drag()
            self._actualizar_hover_por_evento(event, self)
            event.acceptProposedAction()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] dragMoveEvent error: {exc}")
            try:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
            except (AttributeError, TypeError, RuntimeError):
                _ = None
            try:
                event.ignore()
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13D] dragMoveEvent ignore error: {exc2}")

    def dragLeaveEvent(self, event):
        """B7.13D: limpia hover de fila y highlight panel siempre al salir/cancelar."""
        try:
            self._limpiar_hover_y_fila()
            self._desactivar_highlight_drag()
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13D] dragLeaveEvent error: {exc}")
        try:
            event.accept()
        except (AttributeError, TypeError, RuntimeError) as exc2:
            print(f"[B7.13D] dragLeave accept error: {exc2}")

    def dropEvent(self, event):
        """B7.13D: valida y emite drop por posición física (fila vs fondo). No toca FS/SQLite."""
        try:
            if not self._drop_destino_utilizable():
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            mime = event.mimeData()
            ids = self._validar_mime_y_payload(mime)
            if ids is None:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            # Hit test físico en el instante del drop (no inferir por currentItem/selección)
            nombre_hit, row_hit = self._hit_test_fila_bajo_cursor(event, self)
            has_pos = self._pos_a_viewport(event, self) is not None
            objetivo = None
            if nombre_hit is not None:
                objetivo = nombre_hit
            else:
                if not has_pos:
                    # mock sin coords: fallback a hover previo o selección estable para regresión
                    hover = getattr(self, "_drop_hover_objetivo_nombre", None)
                    if hover is not None:
                        objetivo = hover
                    else:
                        try:
                            objetivo = self.objetivo_nombre()
                        except (AttributeError, TypeError, RuntimeError) as exc:
                            print(f"[B7.13D] objetivo_nombre fallback error: {exc}")
                            objetivo = None
                else:
                    objetivo = None
            try:
                self.dropVideosSolicitado.emit(list(ids), objetivo)
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13D] emit dropVideosSolicitado error: {exc}")
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
                event.ignore()
                return
            event.acceptProposedAction()
            self._limpiar_hover_y_fila()
            self._desactivar_highlight_drag()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13D] dropEvent error: {exc}")
            try:
                self._limpiar_hover_y_fila()
                self._desactivar_highlight_drag()
            except (AttributeError, TypeError, RuntimeError):
                _ = None
            try:
                event.ignore()
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13D] dropEvent ignore error: {exc2}")
