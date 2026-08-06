import os
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from configuracion import guardar_ultima_carpeta, obtener_ultima_carpeta
from rutas import ruta_carpeta_miniaturas, ruta_configuracion
from tareas import Estado, GestorTareas
from apertura_videos import abrir_video_con_aplicacion_predeterminada
from tareas_videos import (
    CANTIDAD_PREVIEWS,
    TareaEscaneo,
    TareaFFprobe,
    TareaGuardarVideos,
    TareaLecturaCatalogoPaginada,
    TareaMiniaturas,
    TareaPreviewsProgresivas,
    TareaSincronizacionCatalogo,
    TareaTamanosArchivos,
    _es_archivo_preview,
    combinar_registros_con_ffprobe,
    combinar_registros_con_miniaturas,
    combinar_registros_con_tamanos,
    conectar_bd,
    guardar_videos,
    previews_existentes,
)

ANCHO_TARJETA = 320
ALTO_TARJETA = 180
ANCHO_PREVIEW = ANCHO_TARJETA // 3
ALTO_PREVIEW = ALTO_TARJETA // 3
TAMANIO_PAGINA_INICIAL = 100
TAMANIO_LOTE_PREVIEWS = 3

MENSAJE_CARGANDO = "Cargando catálogo…"
MENSAJE_ERROR = "No se pudo cargar el catálogo"
MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"
MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"
MENSAJE_ESCANEANDO = "Escaneando carpeta…"
MENSAJE_ERROR_ESCANEO = "No se pudo escanear la carpeta"
MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"
MENSAJE_ERROR_TAMANOS = "No se pudieron obtener los tamaños de los archivos"
MENSAJE_ERROR_MINIATURAS = "No se pudieron generar las miniaturas"
MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"
MENSAJE_SINCRONIZANDO = "Sincronizando catálogo…"
MENSAJE_ERROR_SINCRONIZACION = "No se pudo sincronizar el catálogo"
MENSAJE_ERROR_RECARGA = "No se pudo actualizar el catálogo"
MENSAJE_ERROR_PAGINA = "No se pudo cargar la página"
MENSAJE_SIN_ESCANEO = "Sin escanear"
MENSAJE_ERROR_ABRIR = "No se pudo abrir el video"


def texto_resumen_sincronizacion(resumen):
    if resumen is None:
        resumen = {}
    incorporados = resumen.get("incorporados", 0)
    eliminados = resumen.get("eliminados", 0)
    restantes = resumen.get("candidatos_restantes", 0)
    return (
        f"Sincronización completa: {incorporados} incorporados, "
        f"{eliminados} eliminados, {restantes} candidatos restantes"
    )


def formatear_valor(valor):
    if valor is None:
        return "No disponible"
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def formatear_tamano(valor):
    if not isinstance(valor, int) or isinstance(valor, bool):
        return "Desconocido"
    if valor < 0:
        return "Desconocido"
    if valor < 1024:
        return f"{valor} B"
    if valor < 1024 * 1024:
        return f"{valor / 1024:.1f} KB"
    if valor < 1024 * 1024 * 1024:
        return f"{valor / (1024 * 1024):.1f} MB"
    return f"{valor / (1024 * 1024 * 1024):.1f} GB"


def miniatura_principal(nombre):
    prefijo = os.path.splitext(nombre)[0]
    carpeta = ruta_carpeta_miniaturas()
    if os.path.isdir(carpeta):
        for archivo in sorted(os.listdir(carpeta)):
            if (
                os.path.splitext(archivo)[0].startswith(prefijo)
                and not _es_archivo_preview(archivo, nombre)
            ):
                ruta = os.path.join(carpeta, archivo)
                return ruta
    return None


def previews_de(nombre):
    return previews_existentes(nombre)


ESTILO_SELECCIONADA = "Tarjeta { border: 3px solid #2196F3; }"


class Tarjeta(QFrame):
    doble_clic = Signal(str)
    seleccionada = Signal(str, bool)
    seleccion_por_rango = Signal(str)
    menu_contextual = Signal(str)

    def __init__(self, fila, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QHBoxLayout(self)

        nombre, duracion, ancho, alto, codec, miniaturas, tamano = fila

        resolucion = "No disponible"
        if ancho is not None and alto is not None:
            resolucion = f"{ancho}x{alto}"

        campos = [
            ("Nombre", nombre),
            ("Duración", formatear_valor(duracion)),
            ("Resolución", resolucion),
            ("Codec", formatear_valor(codec)),
            ("Miniaturas", formatear_valor(miniaturas)),
            ("Tamaño", formatear_tamano(tamano)),
        ]
        columna_campos = QVBoxLayout()
        for etiqueta, valor in campos:
            campo = QLabel(f"<b>{etiqueta}:</b> {valor}")
            campo.setWordWrap(True)
            columna_campos.addWidget(campo)
        columna_campos.addStretch()
        datos_widget = QWidget()
        datos_widget.setMaximumWidth(240)
        datos_widget.setLayout(columna_campos)
        layout.addWidget(datos_widget)

        self._nombre = nombre
        self._seleccionada = False
        self._etiquetas_previews = []

        contenedor_imagenes = QHBoxLayout()
        contenedor_imagenes.setContentsMargins(0, 0, 0, 0)
        contenedor_imagenes.setSpacing(6)

        ruta_miniatura = miniatura_principal(nombre)
        if ruta_miniatura is not None:
            imagen = QLabel()
            pixmap = QPixmap(ruta_miniatura)
            imagen.setPixmap(
                pixmap.scaled(
                    ANCHO_TARJETA,
                    ALTO_TARJETA,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            imagen.setFixedHeight(ALTO_TARJETA)
            imagen.setAlignment(Qt.AlignCenter)
            contenedor_imagenes.addWidget(imagen)
        else:
            recuadro = QLabel("Sin miniatura")
            recuadro.setFixedSize(ANCHO_TARJETA, ALTO_TARJETA)
            recuadro.setAlignment(Qt.AlignCenter)
            recuadro.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")
            contenedor_imagenes.addWidget(recuadro)

        for _ in range(CANTIDAD_PREVIEWS):
            etiqueta = QLabel("Generando preview…")
            etiqueta.setFixedHeight(ALTO_TARJETA)
            etiqueta.setAlignment(Qt.AlignCenter)
            etiqueta.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
            self._etiquetas_previews.append(etiqueta)
            contenedor_imagenes.addWidget(etiqueta)

        contenedor_imagenes.addStretch()
        layout.addLayout(contenedor_imagenes, 1)

    @property
    def nombre(self):
        return self._nombre

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            if shift:
                self.seleccion_por_rango.emit(self._nombre)
            else:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                self.seleccionada.emit(self._nombre, ctrl)
        elif event.button() == Qt.RightButton:
            if not self._seleccionada:
                self.seleccionada.emit(self._nombre, False)
            self.menu_contextual.emit(self._nombre)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.doble_clic.emit(self._nombre)

    def marcar_seleccionada(self, valor):
        self._seleccionada = valor
        if valor:
            self.setStyleSheet(ESTILO_SELECCIONADA)
        else:
            self.setStyleSheet("")

    def _colocar_preview(self, indice, ruta):
        if not (0 <= indice < len(self._etiquetas_previews)):
            return False
        etiqueta = self._etiquetas_previews[indice]
        ruta_a_usar = ruta
        pixmap = QPixmap(ruta_a_usar)
        if pixmap.isNull():
            return False
        etiqueta.setPixmap(
            pixmap.scaled(
                ANCHO_TARJETA,
                ALTO_TARJETA,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        etiqueta.setText("")
        return True

    def actualizar_previews(self, rutas):
        if rutas is None:
            return False
        if isinstance(rutas, str):
            rutas = [rutas]
        actualizado = False
        for indice in range(min(len(self._etiquetas_previews), len(rutas))):
            if self._colocar_preview(indice, rutas[indice]):
                actualizado = True
        return actualizado


class VisorVideos(QMainWindow):
    def __init__(self, ruta_db=None, parent=None, ruta_config=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de videos")
        self.tarjetas = []
        self.visibles = []
        self._ruta_db = ruta_db
        self._ruta_config = ruta_config
        self._carga_completada = False
        self.tarea_lectura = None
        self.carpeta_seleccionada = None
        self._escaneo_pendiente = False
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.videos_detectados = None
        self.registros_guardados = None
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = None
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = None
        self._cola_previews = []
        self.tarea_previews = None
        self.gestor_previews = None
        self._pipeline_activo = False
        self._nombres_seleccionados = set()
        self._ancla_seleccion = None

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()
        self.estado_carga = QLabel(MENSAJE_CARGANDO)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setFixedHeight(24)

        self.boton_seleccionar_carpeta = QPushButton("Seleccionar carpeta")
        self.boton_seleccionar_carpeta.clicked.connect(self.seleccionar_carpeta)

        self.boton_escanear = QPushButton("Escanear carpeta")
        self.boton_escanear.setEnabled(False)
        self.boton_escanear.clicked.connect(self.iniciar_escaneo)

        self.boton_cargar_mas = QPushButton("Cargar más")
        self.boton_cargar_mas.setEnabled(False)
        self.boton_cargar_mas.clicked.connect(self.cargar_mas)

        self.etiqueta_carpeta = QLabel(MENSAJE_SIN_CARPETA)
        self.etiqueta_carpeta.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.estado_escaneo = QLabel(MENSAJE_SIN_ESCANEO)

        self.mensaje_carpeta = QLabel()
        self.mensaje_carpeta.setStyleSheet("color: #b00020;")

        fila_carpeta = QHBoxLayout()
        fila_carpeta.addWidget(self.boton_seleccionar_carpeta)
        fila_carpeta.addWidget(self.boton_escanear)
        fila_carpeta.addWidget(self.etiqueta_carpeta, 1)
        fila_carpeta.addWidget(self.estado_escaneo)
        fila_carpeta.addWidget(self.mensaje_carpeta)

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.contador)
        barra.addWidget(self.boton_cargar_mas)
        barra.addWidget(self.estado_carga)

        self.contenedor = QWidget()
        self.cuadricula = QGridLayout(self.contenedor)
        self.cuadricula.setColumnStretch(0, 1)
        self.actualizar_contador()

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        raiz = QWidget()
        layout = QVBoxLayout(raiz)
        layout.addLayout(fila_carpeta)
        layout.addLayout(barra)
        layout.addWidget(self.barra_progreso)
        layout.addWidget(self.area)
        self.setCentralWidget(raiz)

        self.gestor = GestorTareas(self)
        self.gestor.tarea_resultado.connect(self._al_resultado)
        self.gestor.tarea_error.connect(self._al_error)
        self.gestor.tarea_finalizada.connect(self._al_tarea_finalizada)
        self.gestor.actividad_cambiada.connect(self._al_actividad)

        self.gestor_previews = GestorTareas(self)
        self.gestor_previews.tarea_resultado.connect(self._al_resultado_previews)
        self.gestor_previews.tarea_error.connect(self._al_error_previews)
        self.gestor_previews.tarea_finalizada.connect(self._al_previews_finalizada)

        self._timer_previews = QTimer(self)
        self._timer_previews.setSingleShot(True)
        self._timer_previews.setInterval(300)
        self._timer_previews.timeout.connect(self._iniciar_previews)
        carpeta_guardada = obtener_ultima_carpeta(self._ruta_config)
        if carpeta_guardada is not None:
            self.carpeta_seleccionada = carpeta_guardada
            self.etiqueta_carpeta.setText(carpeta_guardada)
            self._actualizar_botones_carpeta()
        self._iniciar_carga()

    def _iniciar_carga(self):
        self.tarea_lectura = self._crear_tarea_lectura()
        self.gestor.iniciar(self.tarea_lectura)

    def _crear_tarea_lectura(self, desplazamiento=0):
        return TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL, desplazamiento, None, self._ruta_db
        )

    def seleccionar_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de videos", ""
        )
        if not ruta:
            self._actualizar_botones_carpeta()
            return
        ruta_absoluta = os.path.abspath(ruta)
        if not os.path.isdir(ruta_absoluta):
            self.mensaje_carpeta.setText(MENSAJE_RUTA_INVALIDA)
            self._actualizar_botones_carpeta()
            return
        self.carpeta_seleccionada = ruta_absoluta
        self.etiqueta_carpeta.setText(ruta_absoluta)
        self.mensaje_carpeta.clear()
        guardar_ultima_carpeta(ruta_absoluta, self._ruta_config)
        self._actualizar_botones_carpeta()

    def _actualizar_botones_carpeta(self):
        carpeta_valida = (
            self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        cadena_activa = (
            self._escaneo_pendiente
            or self._tamanos_pendiente
            or self._ffprobe_pendiente
            or self._miniaturas_pendiente
            or self._guardado_pendiente
            or self._sincronizacion_pendiente
            or self._recarga_catalogo_pendiente
            or self._pagina_pendiente
        )
        self.boton_seleccionar_carpeta.setEnabled(not cadena_activa)
        self.boton_escanear.setEnabled(
            carpeta_valida and not self.gestor.activo and not cadena_activa
        )
        hay_mas = (
            self._carga_completada
            and self._total_catalogo is not None
            and len(self.tarjetas) < self._total_catalogo
            and not self.gestor.activo
            and not cadena_activa
        )
        self.boton_cargar_mas.setEnabled(hay_mas)

    def _al_actividad(self, activo):
        self._actualizar_botones_carpeta()

    def _mostrar_progreso(self, texto):
        self._pipeline_activo = True
        self.barra_progreso.setFormat(texto)
        self.barra_progreso.setVisible(True)

    def _ocultar_progreso(self):
        self._pipeline_activo = False
        self.barra_progreso.setVisible(False)

    def _al_seleccionar_tarjeta(self, nombre, ctrl):
        if not ctrl:
            self._limpiar_seleccion()
        if nombre in self._nombres_seleccionados:
            self._nombres_seleccionados.discard(nombre)
            self._marcar_tarjeta(nombre, False)
        else:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        self._ancla_seleccion = nombre if self._nombres_seleccionados else None

    def _al_seleccion_por_rango(self, nombre):
        visibles = self.tarjetas_visibles()
        if self._ancla_seleccion is None or self._ancla_seleccion not in visibles:
            self._limpiar_seleccion()
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
            self._ancla_seleccion = nombre
            return
        idx_ancla = visibles.index(self._ancla_seleccion)
        idx_objetivo = visibles.index(nombre)
        inicio = min(idx_ancla, idx_objetivo)
        fin = max(idx_ancla, idx_objetivo)
        self._limpiar_seleccion()
        for idx in range(inicio, fin + 1):
            n = visibles[idx]
            self._nombres_seleccionados.add(n)
            self._marcar_tarjeta(n, True)

    def _limpiar_seleccion(self):
        for nombre in list(self._nombres_seleccionados):
            self._marcar_tarjeta(nombre, False)
        self._nombres_seleccionados.clear()

    def _marcar_tarjeta(self, nombre, valor):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                tarjeta.marcar_seleccionada(valor)
                return

    @property
    def nombres_seleccionados(self):
        return set(self._nombres_seleccionados)

    def iniciar_escaneo(self):
        if self.gestor.activo:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self.mensaje_carpeta.setText(MENSAJE_RUTA_INVALIDA)
            self._actualizar_botones_carpeta()
            return
        tarea = TareaEscaneo(carpeta)
        self._escaneo_pendiente = True
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.registros_guardados = None
        self.resultado_sincronizacion = None
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        if not self.gestor.iniciar(tarea):
            self._escaneo_pendiente = False
            self._actualizar_botones_carpeta()
            return
        self.tarea_escaneo = tarea
        self.estado_escaneo.setText(MENSAJE_ESCANEANDO)
        self._mostrar_progreso("Escaneando…")
        self._actualizar_botones_carpeta()

    def _limpiar_cadena(self):
        self._escaneo_pendiente = False
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self._ocultar_progreso()

    def _al_resultado_escaneo(self, videos):
        self._escaneo_pendiente = False
        self._tamanos_pendiente = True
        self.videos_detectados = list(videos)
        self._mostrar_estado_escaneo()
        self._actualizar_botones_carpeta()

    def _al_error_escaneo(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_ESCANEO)
        self._actualizar_botones_carpeta()

    def _mostrar_estado_escaneo(self):
        if self.videos_detectados is None:
            self.estado_escaneo.setText(MENSAJE_SIN_ESCANEO)
            return
        cantidad = len(self.videos_detectados)
        if cantidad == 1:
            self.estado_escaneo.setText("1 video detectado")
        else:
            self.estado_escaneo.setText(f"{cantidad} videos detectados")

    def _al_resultado(self, resultado):
        if self._escaneo_pendiente:
            self._al_resultado_escaneo(resultado)
            return
        if self._tamanos_pendiente:
            self._al_resultado_tamanos(resultado)
            return
        if self._ffprobe_pendiente:
            self._al_resultado_ffprobe(resultado)
            return
        if self._miniaturas_pendiente:
            self._al_resultado_miniaturas(resultado)
            return
        if self._guardado_pendiente:
            self._al_resultado_guardado(resultado)
            return
        if self._sincronizacion_pendiente:
            self._al_resultado_sincronizacion(resultado)
            return
        if self._recarga_catalogo_pendiente:
            self._al_resultado_recarga(resultado)
            return
        if self._pagina_pendiente:
            self._al_resultado_pagina(resultado)
            return
        if self._carga_completada:
            return
        self.estado_carga.hide()
        self._total_catalogo = resultado.get("total")
        self._crear_tarjetas(resultado.get("videos", []))
        self._carga_completada = True
        self._programar_previews()

    def _iniciar_tamanos(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaTamanosArchivos(
            self.videos_detectados, self.tarea_escaneo.carpeta
        )
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_tamanos = tarea
        self._mostrar_progreso("Obteniendo tamaños…")

    def _al_resultado_tamanos(self, resultado):
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = True
        self.tarea_tamanos = None
        self.resultado_tamanos = resultado
        self._actualizar_botones_carpeta()

    def _al_error_tamanos(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_TAMANOS)
        self._actualizar_botones_carpeta()

    def _iniciar_ffprobe(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        carpeta = self.tarea_escaneo.carpeta
        rutas = [os.path.join(carpeta, nombre) for nombre in self.videos_detectados]
        tarea = TareaFFprobe(rutas)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_ffprobe = tarea
        self._mostrar_progreso("Leyendo metadatos…")

    def _al_resultado_ffprobe(self, resultado):
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = True
        self.tarea_ffprobe = None
        self.resultado_ffprobe = resultado
        self._actualizar_botones_carpeta()

    def _al_error_ffprobe(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_FFPROBE)
        self._actualizar_botones_carpeta()

    def _iniciar_miniaturas(self):
        if self.tarea_escaneo is None or self.videos_detectados is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaMiniaturas(self.videos_detectados, self.tarea_escaneo.carpeta)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_miniaturas = tarea
        self._mostrar_progreso("Generando miniaturas…")

    def _al_resultado_miniaturas(self, resultado):
        self._miniaturas_pendiente = False
        self._guardado_pendiente = True
        self.tarea_miniaturas = None
        self.resultado_miniaturas = resultado
        self._actualizar_botones_carpeta()

    def _al_error_miniaturas(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_MINIATURAS)
        self._actualizar_botones_carpeta()

    def _iniciar_guardado(self):
        if (
            self.tarea_escaneo is None
            or self.videos_detectados is None
            or self.resultado_tamanos is None
            or self.resultado_ffprobe is None
            or self.resultado_miniaturas is None
        ):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        registros = combinar_registros_con_ffprobe(
            self.videos_detectados, self.tarea_escaneo.carpeta, self.resultado_ffprobe
        )
        registros = combinar_registros_con_miniaturas(
            registros, self.resultado_miniaturas
        )
        registros = combinar_registros_con_tamanos(
            registros, self.resultado_tamanos
        )
        tarea = TareaGuardarVideos(registros, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_guardado = tarea
        self._mostrar_progreso("Guardando…")

    def _al_tarea_finalizada(self):
        if self.gestor.estado != Estado.INACTIVO:
            self._limpiar_cadena()
            return
        if self._escaneo_pendiente:
            return
        if self._tamanos_pendiente:
            self._iniciar_tamanos()
            return
        if self._ffprobe_pendiente:
            self._iniciar_ffprobe()
            return
        if self._miniaturas_pendiente:
            self._iniciar_miniaturas()
            return
        if self._guardado_pendiente:
            self._iniciar_guardado()
            return
        if self._sincronizacion_pendiente:
            self._iniciar_sincronizacion()
            return
        if self._recarga_catalogo_pendiente:
            self._iniciar_recarga_catalogo()
            return

    def _iniciar_sincronizacion(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        tarea = TareaSincronizacionCatalogo(carpeta, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_sincronizacion = tarea
        self.estado_escaneo.setText(MENSAJE_SINCRONIZANDO)
        self._mostrar_progreso("Sincronizando…")
        self._actualizar_botones_carpeta()

    def _al_resultado_sincronizacion(self, resultado):
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = resultado
        self.estado_escaneo.setText(
            texto_resumen_sincronizacion(resultado.get("resumen"))
        )
        self._recarga_catalogo_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error_sincronizacion(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_SINCRONIZACION)
        self._actualizar_botones_carpeta()

    def _iniciar_recarga_catalogo(self):
        tarea = self._crear_tarea_lectura()
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
            self._actualizar_botones_carpeta()
            return
        self.tarea_recarga_catalogo = tarea
        self._mostrar_progreso("Actualizando catálogo…")

    def _al_resultado_recarga(self, resultado):
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        self._reemplazar_tarjetas(resultado.get("videos", []))
        self._programar_previews()
        self._ocultar_progreso()
        self._actualizar_botones_carpeta()

    def _al_error_recarga(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
        self._actualizar_botones_carpeta()

    def _reemplazar_tarjetas(self, filas):
        seleccion_previa = set(self._nombres_seleccionados)
        self._limpiar_seleccion()
        self._ancla_seleccion = None
        for nombre, tarjeta in self.tarjetas:
            self.cuadricula.removeWidget(tarjeta)
            tarjeta.deleteLater()
        self.tarjetas = []
        self.visibles = []
        self._crear_tarjetas(filas)
        nombres_nuevos = {nombre for nombre, _ in self.tarjetas}
        for nombre in seleccion_previa:
            if nombre in nombres_nuevos:
                self._nombres_seleccionados.add(nombre)
                self._marcar_tarjeta(nombre, True)

    def cargar_mas(self):
        if self.gestor.activo:
            return
        if not self._carga_completada:
            return
        tarea = self._crear_tarea_lectura(len(self.tarjetas))
        self._pagina_pendiente = True
        self.tarea_pagina = tarea
        if not self.gestor.iniciar(tarea):
            self._pagina_pendiente = False
            self.tarea_pagina = None
            self._actualizar_botones_carpeta()
            return
        self._actualizar_botones_carpeta()

    def _al_resultado_pagina(self, resultado):
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        filas = resultado.get("videos", [])
        existentes = {nombre for nombre, _ in self.tarjetas}
        filas_nuevas = [fila for fila in filas if fila[0] not in existentes]
        self._agregar_tarjetas(filas_nuevas)
        self._programar_previews()
        self._actualizar_botones_carpeta()

    def _al_error_pagina(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_PAGINA)
        self._actualizar_botones_carpeta()

    def _programar_previews(self):
        if not self._carga_completada:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        self._timer_previews.start()

    def _iniciar_previews(self):
        if not self._carga_completada:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        nombres = [nombre for nombre, _ in self.tarjetas]
        if not nombres:
            return
        self._encolar_previews(nombres)
        self._al_previews_finalizada()

    def _encolar_previews(self, nombres):
        con_previews = set()
        for nombre, _ in self.tarjetas:
            if previews_de(nombre):
                con_previews.add(nombre)
        pendientes = set(self._cola_previews)
        for nombre in nombres:
            if nombre in con_previews or nombre in pendientes:
                continue
            self._cola_previews.append(nombre)

    def _al_previews_finalizada(self):
        if self.gestor_previews.estado != Estado.INACTIVO:
            return
        self._siguiente_lote_previews()

    def _siguiente_lote_previews(self):
        if self.gestor_previews.activo:
            return
        lote = []
        while self._cola_previews and len(lote) < TAMANIO_LOTE_PREVIEWS:
            lote.append(self._cola_previews.pop(0))
        if not lote:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self._cola_previews = []
            return
        tarea = TareaPreviewsProgresivas(lote, carpeta)
        if not self.gestor_previews.iniciar(tarea):
            return
        self.tarea_previews = tarea

    def _al_resultado_previews(self, resultado):
        self._aplicar_previews(resultado)

    def _al_error_previews(self, mensaje):
        self._siguiente_lote_previews()

    def _aplicar_previews(self, resultado):
        for item in resultado.get("resultados", []):
            nombre = item.get("nombre")
            rutas = item.get("previews")
            if rutas:
                self.actualizar_previews(nombre, rutas)

    def actualizar_previews(self, nombre, rutas):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                return tarjeta.actualizar_previews(rutas)
        return False

    def _agregar_tarjetas(self, filas):
        inicio = len(self.tarjetas)
        for indice, fila in enumerate(filas):
            posicion = inicio + indice
            tarjeta = Tarjeta(fila)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, posicion, 0)
            rutas_existentes = previews_de(fila[0])
            if rutas_existentes:
                tarjeta.actualizar_previews(rutas_existentes)
        self.filtrar(self.busqueda.text())

    def _al_resultado_guardado(self, resultado):
        self._guardado_pendiente = False
        self.tarea_guardado = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.registros_guardados = resultado.get("guardados")
        self._sincronizacion_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error(self, mensaje):
        if self._escaneo_pendiente:
            self._al_error_escaneo(mensaje)
            return
        if self._tamanos_pendiente:
            self._al_error_tamanos(mensaje)
            return
        if self._ffprobe_pendiente:
            self._al_error_ffprobe(mensaje)
            return
        if self._miniaturas_pendiente:
            self._al_error_miniaturas(mensaje)
            return
        if self._guardado_pendiente:
            self._al_error_guardado(mensaje)
            return
        if self._sincronizacion_pendiente:
            self._al_error_sincronizacion(mensaje)
            return
        if self._recarga_catalogo_pendiente:
            self._al_error_recarga(mensaje)
            return
        if self._pagina_pendiente:
            self._al_error_pagina(mensaje)
            return
        if self._carga_completada:
            return
        self.estado_carga.setText(MENSAJE_ERROR)
        self._carga_completada = True

    def _al_error_guardado(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_GUARDADO)
        self._actualizar_botones_carpeta()

    def _crear_tarjetas(self, filas):
        for indice, fila in enumerate(filas):
            tarjeta = Tarjeta(fila)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice, 0)
            rutas_existentes = previews_de(fila[0])
            if rutas_existentes:
                tarjeta.actualizar_previews(rutas_existentes)
        self.filtrar(self.busqueda.text())

    def _abrir_video(self, nombre):
        carpeta = self.carpeta_seleccionada
        try:
            abrir_video_con_aplicacion_predeterminada(nombre, carpeta)
        except (ValueError, FileNotFoundError, OSError):
            self.mensaje_carpeta.setText(MENSAJE_ERROR_ABRIR)
            return
        self.mensaje_carpeta.clear()

    def _mostrar_menu_contextual(self, nombre):
        menu = QMenu(self)
        accion_abrir = menu.addAction("Abrir")
        accion_abrir_carpeta = menu.addAction("Abrir carpeta")
        accion_copiar_ruta = menu.addAction("Copiar ruta")
        accion_copiar_seleccionados = menu.addAction("Copiar rutas de los seleccionados")
        accion_abrir.triggered.connect(lambda: self._abrir_video(nombre))
        accion_abrir_carpeta.triggered.connect(lambda: self._abrir_carpeta(nombre))
        accion_copiar_ruta.triggered.connect(lambda: self._copiar_ruta(nombre))
        accion_copiar_seleccionados.triggered.connect(self._copiar_rutas_seleccionados)
        menu.exec(QCursor.pos())

    def _abrir_carpeta(self, nombre):
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            os.startfile(carpeta)

    def _copiar_ruta(self, nombre):
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            ruta = os.path.abspath(os.path.join(carpeta, nombre))
            QApplication.clipboard().setText(ruta)

    def _copiar_rutas_seleccionados(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        rutas = []
        for nombre in self.tarjetas_visibles():
            if nombre in self._nombres_seleccionados:
                rutas.append(os.path.abspath(os.path.join(carpeta, nombre)))
        if rutas:
            QApplication.clipboard().setText("\n".join(rutas))

    def filtrar(self, texto):
        texto = texto.lower()
        visibles = []
        for nombre, tarjeta in self.tarjetas:
            coincide = texto in nombre.lower()
            tarjeta.setVisible(coincide)
            if coincide:
                visibles.append(nombre)
        self.visibles = visibles
        self.actualizar_contador()

    def tarjetas_visibles(self):
        return list(self.visibles)

    def actualizar_contador(self):
        cantidad = len(self.tarjetas_visibles())
        palabra = "video" if cantidad == 1 else "videos"
        self.contador.setText(f"{cantidad} {palabra}")

    def closeEvent(self, event):
        self._timer_previews.stop()
        self.gestor.cerrar()
        if self.gestor_previews is not None:
            self.gestor_previews.cerrar()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(900, 600)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
