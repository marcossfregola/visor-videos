import escanear_videos
import exploracion_cache
import operaciones
import os
import sys
import tempfile

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from configuracion import (
    LIMITE_LONGITUD_NOMBRE_COLOR,
    MODO_ALCANCE_SELECCION,
    MODO_ALCANCE_SOLO,
    MODO_ALCANCE_SUBCARPETAS,
    NOMBRES_COLORES_POR_DEFECTO,
    TEXTO_VERSION_BUILD,
    guardar_cantidad_previews,
    guardar_modo_alcance,
    guardar_nombre_color,
    guardar_orden_catalogo,
    guardar_preferencia_escaneo_automatico,
    guardar_preferencia_subcarpetas,
    guardar_retardo_vista_ampliada,
    guardar_tamano_miniaturas,
    guardar_tamano_vista_ampliada,
    guardar_ultima_carpeta,
    obtener_cantidad_previews,
    obtener_modo_alcance,
    obtener_nombres_colores,
    obtener_orden_catalogo,
    obtener_preferencia_escaneo_automatico,
    obtener_preferencia_subcarpetas,
    obtener_retardo_vista_ampliada,
    obtener_tamano_miniaturas,
    obtener_tamano_vista_ampliada,
    obtener_ultima_carpeta,
    texto_color,
)
from escanear_videos import (
    CLAVES_COLOR_CLASIFICACION,
    COLORES_CLASIFICACION,
    _nombre_seguro,
    calcular_tiempo_preview,
    color_rgb,
    configurar_cantidad_previews,
    configurar_escaneo_recursivo,
)
from rutas import ruta_carpeta_miniaturas, ruta_configuracion, ruta_video_existente
from exploracion_temporal import (
    agregar_marcador_ordenado,
    preview_mas_cercana,
    tiempo_a_posicion,
    tiempos_objetivo,
)
from seleccion_carpetas import SeleccionCarpetas
from scrubber import BarraResumenColapsada, FranjaExploracion, MiniaturaMarcador
from tareas import Estado, GestorTareas, TareaBase
from apertura_videos import abrir_video_con_aplicacion_predeterminada
from arbol_navegacion import ArbolNavegacion
from playlist_vlc import (
    abrir_playlist_en_vlc,
    generar_m3u,
    localizar_vlc,
    reproducir_desde_instante,
    reproducir_secuencia_segmentos,
    reproducir_segmento,
    reproducir_segmento_en_bucle,
)
from tareas_videos import (
    TareaActualizarSegmento,
    TareaAsignarColorMarcador,
    TareaAsignarColorSegmento,
    TareaEscaneo,
    TareaFFprobe,
    TareaGuardarMarcador,
    TareaGuardarSegmento,
    TareaGuardarVideos,
    TareaEliminarMarcador,
    TareaEliminarSegmento,
    TareaActualizarSegmento,
    TareaExploracionDensa,
    TareaLecturaCatalogoPaginada,
    TareaListarMarcadores,
    TareaListarMarcadoresVarios,
    TareaListarSegmentos,
    TareaListarSegmentosVarios,
    TareaMiniaturas,
    TareaPreviewsProgresivas,
    TareaResumenColapsado,
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
TAMANIO_PAGINA_INICIAL = 100
TAMANIO_LOTE_PREVIEWS = 3
RETARDO_VISTA_AMPLIADA_MS = 400
LIMITE_ORIGINAL_MINIATURA = 1280
RETARDO_OCULTAR_VISTA_MS = 150
ALTO_FRANJA_EXTRAS = 44
FOTOGRAMAS_INICIALES = exploracion_cache.MINIMO_FOTOGRAMAS_DENSIDAD
DENSIDADES_DISPONIBLES = (
    ("Auto", None),
    ("15", 15),
    ("30", 30),
    ("60", 60),
    ("120", 120),
    ("200", 200),
)
FACTOR_VISTA_AMPLIADA = 1.6
FACTORES_VISTA_AMPLIADA = (1.2, 1.6, 2.0, 2.5, 3.0, 3.5)
TEXTOS_FACTOR_VISTA_AMPLIADA = (
    "1.2x",
    "1.6x",
    "2.0x",
    "2.5x",
    "3.0x",
    "3.5x",
)
FACTOR_VISTA_AMPLIADA_ACTUAL = FACTOR_VISTA_AMPLIADA


def configurar_factor_vista_ampliada(factor):
    global FACTOR_VISTA_AMPLIADA_ACTUAL
    if isinstance(factor, float) and factor in FACTORES_VISTA_AMPLIADA:
        FACTOR_VISTA_AMPLIADA_ACTUAL = factor

TAMANIOS_MINIATURAS = {
    "pequeno": (260, 146),
    "mediano": (320, 180),
    "grande": (400, 225),
    "muy_grande": (512, 288),
}
TAMANIO_MINIATURAS_ACTUAL = "mediano"
TEXTO_TAMANO_MINIATURAS = {
    "pequeno": "Pequeño",
    "mediano": "Mediano",
    "grande": "Grande",
    "muy_grande": "Muy grande",
}


def configurar_tamano_miniaturas(nombre):
    global TAMANIO_MINIATURAS_ACTUAL
    if isinstance(nombre, str) and nombre in TAMANIOS_MINIATURAS:
        TAMANIO_MINIATURAS_ACTUAL = nombre


def dimensiones_miniatura():
    return TAMANIOS_MINIATURAS[TAMANIO_MINIATURAS_ACTUAL]


def texto_tamano_miniaturas(nombre):
    return TEXTO_TAMANO_MINIATURAS.get(nombre, "Mediano")


def clave_tamano_miniaturas(texto):
    for clave, valor in TEXTO_TAMANO_MINIATURAS.items():
        if valor == texto:
            return clave
    return "mediano"

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

TEXTOS_ORDEN_CRITERIOS = {
    "nombre": "Nombre",
    "duracion": "Duración",
    "resolucion": "Resolución",
    "codec": "Codec",
    "tamano": "Tamaño",
    "fecha_importacion": "Fecha de importación",
}
TEXTOS_ORDEN_DIRECCIONES = {
    "asc": "Ascendente",
    "desc": "Descendente",
}


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


def formatear_tiempo(segundos):
    if not isinstance(segundos, (int, float)) or isinstance(segundos, bool):
        return None
    if segundos < 0:
        return None
    total = int(round(segundos))
    horas, resto = divmod(total, 3600)
    minutos, segundos_resto = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos_resto:02d}"
    return f"{minutos}:{segundos_resto:02d}"


def _ruta_contiene(padre, hija):
    if (
        not isinstance(padre, str)
        or not isinstance(hija, str)
        or not padre
        or not hija
    ):
        return False
    padre_normalizada = os.path.normcase(os.path.normpath(padre))
    hija_normalizada = os.path.normcase(os.path.normpath(hija))
    if padre_normalizada == hija_normalizada:
        return False
    try:
        return os.path.commonpath(
            [padre_normalizada, hija_normalizada]
        ) == padre_normalizada
    except ValueError:
        return False


def _alcance_efectivo(carpetas, recursivo):
    if not recursivo or len(carpetas) <= 1:
        return list(carpetas)
    efectivas = []
    for carpeta in carpetas:
        contenido = any(
            _ruta_contiene(otra, carpeta)
            for otra in carpetas
            if otra != carpeta
        )
        if not contenido:
            efectivas.append(carpeta)
    return efectivas


def _duracion_valida(duracion):
    return (
        isinstance(duracion, (int, float))
        and not isinstance(duracion, bool)
        and duracion > 0
    )


def _pixmap_acotado(pixmap):
    if pixmap is None or pixmap.isNull():
        return pixmap
    ancho = pixmap.width()
    alto = pixmap.height()
    mayor = max(ancho, alto)
    if mayor <= LIMITE_ORIGINAL_MINIATURA:
        return pixmap
    escala = LIMITE_ORIGINAL_MINIATURA / mayor
    return pixmap.scaled(
        max(1, int(ancho * escala)),
        max(1, int(alto * escala)),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


def miniatura_principal(nombre):
    prefijo = _nombre_seguro(os.path.splitext(nombre)[0])
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


class PreviewConTiempo(QLabel):
    """Etiqueta de preview que superpone el instante temporal al fotograma.

    La superposición es exclusivamente visual: mantiene un widget por slot y
    el mismo layout, sin alterar tamaños de tarjeta, de miniaturas ni el
    scroll. El pixmap almacenado es el ya escalado (mismo criterio que antes
    de la etapa), por lo que `pixmap()` conserva el contrato y el tamaño de
    la etiqueta no cambia. Si no hay tiempo (duración desconocida o
    inválida), dibuja solo el fotograma, sin valores por defecto.
    """

    ESTILO_BASE = "background-color: #f0f0f0; border: 1px solid #ccc;"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_original = None
        self._tiempo = None
        self.setFixedHeight(dimensiones_miniatura()[1])
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(self.ESTILO_BASE)

    def poner_preview(self, pixmap, tiempo=None):
        if pixmap is None or pixmap.isNull():
            return False
        self._pixmap_original = _pixmap_acotado(pixmap)
        self._tiempo = tiempo
        ancho, alto = dimensiones_miniatura()
        self.setFixedHeight(alto)
        self.setPixmap(
            self._pixmap_original.scaled(
                ancho,
                alto,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.setText("")
        self.update()
        return True

    def reajustar(self):
        ancho, alto = dimensiones_miniatura()
        self.setFixedHeight(alto)
        if self._pixmap_original is None or self._pixmap_original.isNull():
            return False
        return self.poner_preview(self._pixmap_original, self._tiempo)

    def paintEvent(self, event):
        if self.pixmap() is None or self.pixmap().isNull():
            super().paintEvent(event)
            return
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor("#f0f0f0"))
        pintor.setPen(QColor("#cccccc"))
        pintor.setBrush(Qt.NoBrush)
        pintor.drawRect(self.rect().adjusted(0, 0, -1, -1))
        escalada = self.pixmap()
        x = (self.width() - escalada.width()) // 2
        y = (self.height() - escalada.height()) // 2
        pintor.drawPixmap(x, y, escalada)
        if self._tiempo is not None:
            metrica = pintor.fontMetrics()
            ancho = metrica.horizontalAdvance(self._tiempo) + 10
            alto = metrica.height() + 4
            bx = x + escalada.width() - ancho - 4
            by = y + escalada.height() - alto - 4
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(0, 0, 0, 150))
            pintor.drawRoundedRect(bx, by, ancho, alto, 3, 3)
            pintor.setPen(QColor(255, 255, 255, 235))
            pintor.drawText(bx + 5, by + metrica.ascent() + 2, self._tiempo)
        pintor.end()


class VistaAmpliada(QFrame):
    """Popup de vista ampliada al posar el mouse sobre una miniatura (Etapa B3.4).

    Ventana de nivel superior única por `VisorVideos` (nunca se crea ni destruye
    por hover). Muestra el pixmap original ya cargado en memoria, escalado a
    ~1.6x del tamaño configurado, sin leer disco ni regenerar miniaturas.
    """

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self._pixmap = None
        self._tam_amp = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._etiqueta = QLabel()
        self._etiqueta.setStyleSheet(
            "border: 2px solid #333; background-color: #ffffff;"
        )
        self._etiqueta.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._etiqueta)
        self.hide()

    def preparar(self, pixmap):
        ancho, alto = dimensiones_miniatura()
        ancho_amp = int(ancho * FACTOR_VISTA_AMPLIADA_ACTUAL)
        alto_amp = int(alto * FACTOR_VISTA_AMPLIADA_ACTUAL)
        if (
            self._pixmap is pixmap
            and self.isVisible()
            and self._tam_amp == (ancho_amp, alto_amp)
        ):
            return True
        self._pixmap = pixmap
        self._tam_amp = (ancho_amp, alto_amp)
        self._etiqueta.setPixmap(
            pixmap.scaled(
                ancho_amp,
                alto_amp,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.adjustSize()
        return False

    def ocultar(self):
        self._pixmap = None
        self._tam_amp = None
        self.hide()


RETARDOS_VISTA_AMPLIADA = (-1, 0, 250, 400, 600)
TEXTOS_RETARDO_VISTA_AMPLIADA = (
    "Desactivado",
    "Inmediato",
    "250 ms",
    "400 ms",
    "600 ms",
)


class PreferenciasDialog(QDialog):
    """Diálogo modal de preferencias (Etapa B3.5).

    En esta primera versión contiene únicamente el retardo de la vista
    ampliada, con valores discretos. La infraestructura está preparada para
    incorporar más preferencias sin rediseñar la ventana principal.
    """

    def __init__(self, ruta_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self._ruta_config = ruta_config
        layout = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Retardo de la vista ampliada:"))
        self.combo_retardo = QComboBox()
        self.combo_retardo.addItems(list(TEXTOS_RETARDO_VISTA_AMPLIADA))
        self.combo_retardo.setCurrentIndex(
            self._indice_retardo(
                obtener_retardo_vista_ampliada(ruta_config)
            )
        )
        fila.addWidget(self.combo_retardo)
        fila.addStretch()
        layout.addLayout(fila)
        fila2 = QHBoxLayout()
        fila2.addWidget(QLabel("Tamaño de la vista ampliada:"))
        self.combo_factor_vista = QComboBox()
        self.combo_factor_vista.addItems(list(TEXTOS_FACTOR_VISTA_AMPLIADA))
        self.combo_factor_vista.setCurrentIndex(
            self._indice_factor(
                obtener_tamano_vista_ampliada(ruta_config)
            )
        )
        fila2.addWidget(self.combo_factor_vista)
        fila2.addStretch()
        layout.addLayout(fila2)
        titulo_colores = QLabel("<b>Nombres de colores de la clasificación:</b>")
        layout.addWidget(titulo_colores)
        self._cajas_color = {}
        nombres = obtener_nombres_colores(ruta_config)
        for clave, *_resto in COLORES_CLASIFICACION:
            fila_color = QHBoxLayout()
            muestra = QLabel()
            rgb = color_rgb(clave)
            pixmap_color = QPixmap(14, 14)
            pixmap_color.fill(
                QColor(rgb[0], rgb[1], rgb[2])
            )
            muestra.setPixmap(pixmap_color)
            fila_color.addWidget(muestra)
            fila_color.addWidget(
                QLabel(f"{clave.capitalize()} (nombre global):")
            )
            caja = QLineEdit()
            caja.setMaxLength(LIMITE_LONGITUD_NOMBRE_COLOR)
            caja.setPlaceholderText(
                NOMBRES_COLORES_POR_DEFECTO.get(clave, "")
            )
            caja.setText(nombres.get(clave, ""))
            fila_color.addWidget(caja, 1)
            self._cajas_color[clave] = caja
            layout.addLayout(fila_color)
        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def accept(self):
        for clave, caja in self._cajas_color.items():
            guardar_nombre_color(clave, caja.text(), self._ruta_config)
        super().accept()

    def _indice_retardo(self, ms):
        if ms in RETARDOS_VISTA_AMPLIADA:
            return RETARDOS_VISTA_AMPLIADA.index(ms)
        return RETARDOS_VISTA_AMPLIADA.index(400)

    def retardo_seleccionado(self):
        indice = self.combo_retardo.currentIndex()
        if 0 <= indice < len(RETARDOS_VISTA_AMPLIADA):
            return RETARDOS_VISTA_AMPLIADA[indice]
        return 400

    def _indice_factor(self, factor):
        if factor in FACTORES_VISTA_AMPLIADA:
            return FACTORES_VISTA_AMPLIADA.index(factor)
        return FACTORES_VISTA_AMPLIADA.index(1.6)

    def factor_vista_seleccionado(self):
        indice = self.combo_factor_vista.currentIndex()
        if 0 <= indice < len(FACTORES_VISTA_AMPLIADA):
            return FACTORES_VISTA_AMPLIADA[indice]
        return 1.6


class TareaCopiarArchivos(TareaBase):
    def __init__(self, origen, archivos, destino, parent=None):
        super().__init__(parent)
        self._origen = origen
        self._archivos = list(archivos)
        self._destino = destino

    @property
    def origen(self):
        return self._origen

    @property
    def archivos(self):
        return list(self._archivos)

    @property
    def destino(self):
        return self._destino

    def _trabajo(self):
        return operaciones.copiar_archivos(
            self._origen, self._archivos, self._destino, self.reportar_progreso
        )


class TareaPegarArchivos(TareaBase):
    def __init__(self, archivos, destino, parent=None):
        super().__init__(parent)
        self._archivos = list(archivos)
        self._destino = destino

    @property
    def archivos(self):
        return list(self._archivos)

    @property
    def destino(self):
        return self._destino

    def _trabajo(self):
        return operaciones.pegar_archivos(
            self._archivos, self._destino, self.reportar_progreso
        )


class TareaEliminarArchivos(TareaBase):
    def __init__(self, archivos, parent=None):
        super().__init__(parent)
        self._archivos = list(archivos)

    @property
    def archivos(self):
        return list(self._archivos)

    def _trabajo(self):
        return operaciones.eliminar_archivos(self._archivos, self.reportar_progreso)


class Tarjeta(QFrame):
    doble_clic = Signal(str)
    seleccionada = Signal(str, bool)
    seleccion_por_rango = Signal(str)
    menu_contextual = Signal(str)
    vista_solicitada = Signal(object)
    vista_abandonada = Signal()
    seleccion_check = Signal(str, bool)
    expansion_cambiada = Signal(str, bool)
    marcador_creado = Signal(object)
    marcador_eliminado = Signal(object)
    marcadores_solicitados = Signal()
    segmentos_solicitados = Signal()
    segmento_creado = Signal(object)
    segmento_eliminado = Signal(object)
    segmento_actualizado = Signal(object, object)
    segmento_reproduccion_solicitada = Signal(object)
    segmento_bucle_solicitado = Signal(object)
    reproduccion_temporal_solicitada = Signal(float)
    densidad_cambiada = Signal(str, object)
    marcador_color_solicitado = Signal(object, object)
    segmento_color_solicitado = Signal(object, object)

    def __init__(self, fila, parent=None, ruta_config=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self._ruta_config = ruta_config
        self._color_activo = None
        fila_principal = QHBoxLayout()

        nombre, duracion, ancho, alto, codec, miniaturas, tamano, *_resto = fila

        ruta_video_registro = _resto[0] if _resto else None
        self._video_id = _resto[1] if len(_resto) > 1 else None
        carpeta_video = None
        if (
            isinstance(ruta_video_registro, str)
            and ruta_video_registro
            and isinstance(nombre, str)
            and nombre
        ):
            base = ruta_video_registro
            if ruta_video_registro.endswith(nombre):
                base = ruta_video_registro[: -len(nombre)]
            carpeta_video = base.rstrip(os.sep) or base
        self._carpeta_video = carpeta_video

        resolucion = "No disponible"
        if ancho is not None and alto is not None:
            resolucion = f"{ancho}x{alto}"

        duracion_texto = "No disponible"
        if _duracion_valida(duracion):
            duracion_texto = formatear_tiempo(duracion)

        campos = [
            ("Nombre", nombre),
            ("Duración", duracion_texto),
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
        self._boton_expandir = QPushButton("Expandir")
        self._boton_expandir.setCheckable(True)
        self._boton_expandir.toggled.connect(self._al_toggle_expansion)
        columna_campos.insertWidget(0, self._boton_expandir)
        datos_widget = QWidget()
        datos_widget.setMaximumWidth(240)
        datos_widget.setLayout(columna_campos)
        fila_principal.addWidget(datos_widget)

        self._nombre = nombre
        self._duracion = duracion
        self._seleccionada = False
        self._etiquetas_previews = []
        self._imagen_miniatura = None
        self._miniatura_original = None
        self._recuadro_sin_miniatura = None
        self._previews_completas = False

        contenedor_imagenes = QHBoxLayout()
        contenedor_imagenes.setContentsMargins(0, 0, 0, 0)
        contenedor_imagenes.setSpacing(6)
        self._contenedor_imagenes = contenedor_imagenes

        ancho, alto = dimensiones_miniatura()
        ruta_miniatura = miniatura_principal(nombre)
        if ruta_miniatura is not None:
            imagen = QLabel()
            pixmap = _pixmap_acotado(QPixmap(ruta_miniatura))
            imagen.setPixmap(
                pixmap.scaled(
                    ancho,
                    alto,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            imagen.setFixedHeight(alto)
            imagen.setAlignment(Qt.AlignCenter)
            self._imagen_miniatura = imagen
            self._miniatura_original = pixmap
            contenedor_imagenes.addWidget(imagen)
        else:
            recuadro = QLabel("Sin miniatura")
            recuadro.setFixedSize(ancho, alto)
            recuadro.setAlignment(Qt.AlignCenter)
            recuadro.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")
            self._recuadro_sin_miniatura = recuadro
            contenedor_imagenes.addWidget(recuadro)

        for _ in range(escanear_videos.CANTIDAD_PREVIEWS):
            etiqueta = PreviewConTiempo()
            etiqueta.setText("Generando preview…")
            self._etiquetas_previews.append(etiqueta)
            contenedor_imagenes.addWidget(etiqueta)

        if self._imagen_miniatura is not None:
            self._imagen_miniatura.installEventFilter(self)
        for etiqueta in self._etiquetas_previews:
            etiqueta.installEventFilter(self)

        contenedor_imagenes.addStretch()

        contenedor_imagenes_widget = QWidget()
        contenedor_imagenes_widget.setLayout(contenedor_imagenes)
        self._area_imagenes = QScrollArea()
        self._area_imagenes.setWidgetResizable(True)
        self._area_imagenes.setFrameShape(QFrame.NoFrame)
        self._area_imagenes.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._area_imagenes.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._area_imagenes.setWidget(contenedor_imagenes_widget)
        fila_principal.addWidget(self._area_imagenes, 1)

        self._check = QCheckBox()
        self._check.setVisible(False)
        self._check.stateChanged.connect(self._al_check_cambiar)
        fila_principal.insertWidget(0, self._check)

        layout = QVBoxLayout(self)
        layout.addLayout(fila_principal)
        self._construir_exploracion()
        self._barra_colapsada = BarraResumenColapsada()
        self._barra_colapsada.set_datos(
            self._duracion, self._marcadores, self._segmentos
        )
        self._barra_colapsada.setVisible(not self._expandida)
        layout.addWidget(self._barra_colapsada)
        layout.addWidget(self._contenedor_exploracion)

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

    def _al_check_cambiar(self, _estado):
        self.seleccion_check.emit(self._nombre, self._check.isChecked())

    def mostrar_check(self, visible):
        self._check.setVisible(visible)

    def set_check(self, marcado):
        self._check.blockSignals(True)
        self._check.setChecked(bool(marcado))
        self._check.blockSignals(False)

    def _colocar_preview(self, indice, ruta):
        if not (0 <= indice < len(self._etiquetas_previews)):
            return False
        etiqueta = self._etiquetas_previews[indice]
        pixmap = QPixmap(ruta)
        if pixmap.isNull():
            return False
        tiempo = None
        duracion = self._duracion
        if _duracion_valida(duracion):
            tiempo = formatear_tiempo(calcular_tiempo_preview(duracion, indice + 1))
        return etiqueta.poner_preview(pixmap, tiempo)

    def actualizar_previews(self, rutas):
        if rutas is None:
            return False
        if isinstance(rutas, str):
            rutas = [rutas]
        actualizado = False
        for indice in range(min(len(self._etiquetas_previews), len(rutas))):
            if self._colocar_preview(indice, rutas[indice]):
                actualizado = True
        if actualizado and self._expandida:
            self._refrescar_exploracion()
            self._renderizar_marcadores()
        if self._etiquetas_previews:
            cantidad = escanear_videos.CANTIDAD_PREVIEWS
            self._previews_completas = (
                len(self._etiquetas_previews) >= cantidad
                and all(
                    not etiqueta.pixmap().isNull()
                    for etiqueta in self._etiquetas_previews[:cantidad]
                )
            )
        return actualizado

    def _asegurar_slots_previews(self, cantidad):
        while len(self._etiquetas_previews) < cantidad:
            etiqueta = PreviewConTiempo()
            etiqueta.setText("Generando preview…")
            etiqueta.installEventFilter(self)
            self._etiquetas_previews.append(etiqueta)
            self._contenedor_imagenes.insertWidget(
                self._contenedor_imagenes.count() - 1, etiqueta
            )

    def ajustar_previews(self, cantidad):
        self._asegurar_slots_previews(cantidad)
        existentes = previews_de(self._nombre) or []
        for i, etiqueta in enumerate(self._etiquetas_previews):
            etiqueta.setVisible(i < cantidad)
        self.actualizar_previews(existentes[:cantidad])

    def aplicar_tamano(self):
        ancho, alto = dimensiones_miniatura()
        if self._imagen_miniatura is not None and self._miniatura_original is not None:
            self._imagen_miniatura.setPixmap(
                self._miniatura_original.scaled(
                    ancho,
                    alto,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self._imagen_miniatura.setFixedHeight(alto)
        if self._recuadro_sin_miniatura is not None:
            self._recuadro_sin_miniatura.setFixedSize(ancho, alto)
        for etiqueta in self._etiquetas_previews:
            etiqueta.reajustar()
        if self._expandida:
            self._franja.setFixedHeight(alto + ALTO_FRANJA_EXTRAS)
            self._imagen_exploracion.setFixedSize(ancho, alto)
            for entrada in self._previews_densos:
                pixmap = entrada.get("pixmap")
                if pixmap is not None and not pixmap.isNull():
                    entrada["pixmap_escalado"] = pixmap.scaled(
                        ancho,
                        alto,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
            self._refrescar_exploracion()
            self._renderizar_marcadores()

    def _pixmap_ampliada(self, objeto):
        if objeto is self._imagen_miniatura:
            return self._miniatura_original
        if isinstance(objeto, PreviewConTiempo):
            return objeto._pixmap_original
        return None

    def _construir_exploracion(self):
        self._expandida = False
        self._previews_exploracion = []
        self._previews_densos = []
        self._marcadores = []
        self._marcadores_cargados = False
        self._marcadores_eliminados_carga = set()
        self._marcador_creado_prensa = None
        self._segmentos = []
        self._segmentos_cargados = False
        self._segmentos_eliminados_carga = set()
        # B6.4 collapsed resumen: versión/generación para carrera batch vs mutación local
        self._resumen_version = 0
        self._resumen_cargado = False
        self._resumen_eliminados_marcadores = set()
        self._resumen_eliminados_segmentos = set()
        self._extremo_segmento = None
        self._modo_crear_segmento = False
        self._menu_segmento_actual = None
        self._submenu_segmento_color_actual = None
        self._menu_marcador_actual = None
        self._submenu_marcador_color_actual = None
        self._franja = FranjaExploracion()
        self._franja.instante_seleccionado.connect(self._al_instante_exploracion)
        self._franja.marcador_solicitado.connect(self._al_marcador_solicitado)
        self._franja.marcador_eliminar_solicitado.connect(
            self._al_marcador_eliminar_solicitado
        )
        self._franja.marcador_contextual_solicitado.connect(
            self._al_marcador_contextual_solicitado
        )
        self._franja.reproduccion_solicitada.connect(
            self._al_reproduccion_solicitada
        )
        self._franja.extremo_segmento_solicitado.connect(
            self._al_extremo_segmento_solicitado
        )
        self._franja.segmento_arrastre_confirmado.connect(
            self._al_segmento_arrastre_confirmado
        )
        self._franja.extremo_editado.connect(self._al_extremo_editado)
        self._franja.segmento_contextual_solicitado.connect(
            self._al_segmento_contextual_solicitado
        )
        self._franja.installEventFilter(self)
        ancho, alto = dimensiones_miniatura()
        self._franja.setFixedHeight(alto + ALTO_FRANJA_EXTRAS)
        self._imagen_exploracion = QLabel(self._franja)
        self._imagen_exploracion.setFixedSize(ancho, alto)
        self._imagen_exploracion.setAlignment(Qt.AlignCenter)
        self._imagen_exploracion.setStyleSheet(
            "border: 1px solid #999999; background-color: #fafafa;"
        )
        self._imagen_exploracion.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._imagen_exploracion.hide()
        self._densidad_manual = None
        self._selector_densidad = QComboBox()
        for texto, valor in DENSIDADES_DISPONIBLES:
            self._selector_densidad.addItem(texto, valor)
        self._selector_densidad.currentIndexChanged.connect(
            self._al_cambiar_densidad
        )
        self._boton_segmento = QPushButton("Segmento")
        self._boton_segmento.setCheckable(True)
        self._boton_segmento.setToolTip(
            "Modo crear segmento: primer clic fija A, segundo clic fija B"
        )
        self._boton_segmento.toggled.connect(self._al_toggle_segmento)
        fila_densidad = QHBoxLayout()
        fila_densidad.addStretch(1)
        fila_densidad.addWidget(self._boton_segmento)
        fila_densidad.addWidget(QLabel("Densidad:"))
        fila_densidad.addWidget(self._selector_densidad)
        fila_color = QHBoxLayout()
        fila_color.addStretch(1)
        fila_color.addWidget(QLabel("Color:"))
        self._selector_color = QComboBox()
        self._selector_color.addItem("Sin clasificar", None)
        for clave, *_resto in COLORES_CLASIFICACION:
            self._selector_color.addItem(
                texto_color(clave, self._ruta_config), clave
            )
        self._selector_color.currentIndexChanged.connect(
            self._al_cambiar_color_activo
        )
        self._al_cambiar_color_activo()
        fila_color.addWidget(self._selector_color)
        self._contenedor_exploracion = QWidget()
        disposicion = QVBoxLayout(self._contenedor_exploracion)
        disposicion.setContentsMargins(0, 4, 0, 0)
        disposicion.addLayout(fila_densidad)
        disposicion.addLayout(fila_color)
        disposicion.addWidget(self._franja)
        self._contenedor_exploracion.setVisible(False)

    def _al_cambiar_color_activo(self):
        self._color_activo = self._selector_color.currentData()

    def _refrescar_textos_colores(self):
        """Actualiza los textos visibles del selector de color (B6.3).

        No cambia índices, datos ni la selección actual: solo refresca el
        texto de los ítems tras guardar nombres globales en preferencias.
        Los menús contextuales se construyen por demanda y ya usan
        `texto_color`, por lo que no requieren reconstrucción.
        """
        if not hasattr(self, "_selector_color"):
            return
        self._selector_color.setItemText(0, "Sin clasificar")
        for indice in range(1, self._selector_color.count()):
            clave = self._selector_color.itemData(indice)
            if clave in CLAVES_COLOR_CLASIFICACION:
                self._selector_color.setItemText(
                    indice, texto_color(clave, self._ruta_config)
                )

    def _sincronizar_barra_colapsada(self):
        """Actualiza la barra fina colapsada con duración/marcadores/segmentos actuales (B6.4).

        Reutiliza exactamente la misma fuente de verdad que la franja
        expandida (listas locales `_marcadores`/`_segmentos` y `_duracion`),
        sin consultas SQLite ni FFmpeg. La barra es pintura ligera
        (un único QWidget con `paintEvent`), sin widgets hijos por elemento,
        y se muestra solo en estado colapsado.
        """
        barra = getattr(self, "_barra_colapsada", None)
        if barra is None:
            return
        try:
            barra.set_datos(self._duracion, self._marcadores, self._segmentos)
        except Exception:
            pass

    def _bump_resumen_version(self):
        """Incrementa la generación local para la carrera batch (B6.4)."""
        try:
            self._resumen_version = int(getattr(self, "_resumen_version", 0)) + 1
        except Exception:
            self._resumen_version = 1

    def _tiempos_y_colores_marcadores(self):
        tiempos = []
        colores = {}
        for marcador in self._marcadores:
            tiempos.append(marcador["tiempo"])
            clave = marcador.get("color")
            if clave is not None:
                colores[marcador["tiempo"]] = clave
        return tiempos, colores

    def _al_cambiar_densidad(self):
        valor = self._selector_densidad.currentData()
        self.aplicar_densidad(valor)
        self.densidad_cambiada.emit(self._nombre, valor)

    def aplicar_densidad(self, valor):
        """Aplica una densidad manual (None = Auto) y filtra los densos en RAM.

        La caché en disco nunca se borra ni se regenera: se conservan solo
        los densos cargados cuyo instante pertenece al conjunto objetivo de
        la cantidad elegida (`tiempos_objetivo(duración, cantidad)`); al
        volver a pedir una densidad mayor, la tarea reincorpora los faltantes
        reutilizando el disco.
        """
        self._densidad_manual = valor
        if not _duracion_valida(self._duracion) or not self._previews_densos:
            return
        cantidad = (
            valor
            if valor is not None
            else exploracion_cache.objetivo_total_densidad(self._duracion)
        )
        if (
            isinstance(cantidad, bool)
            or not isinstance(cantidad, int)
            or cantidad <= 0
        ):
            return
        objetivo = set(tiempos_objetivo(self._duracion, cantidad))
        self._previews_densos = [
            d
            for d in self._previews_densos
            if round(d["instante"] * 1000) in objetivo
        ]
        self._refrescar_exploracion()

    def expandir(self):
        if not self._expandida:
            self._set_expansion(True)

    def colapsar(self):
        if self._expandida:
            self._set_expansion(False)

    def _al_toggle_expansion(self, marcado):
        self._set_expansion(bool(marcado))

    def _set_expansion(self, valor):
        if self._expandida == valor:
            return
        self._expandida = valor
        self._boton_expandir.blockSignals(True)
        self._boton_expandir.setChecked(valor)
        self._boton_expandir.setText("Colapsar" if valor else "Expandir")
        self._boton_expandir.blockSignals(False)
        if valor:
            self._contenedor_exploracion.setVisible(True)
            barra = getattr(self, "_barra_colapsada", None)
            if barra is not None:
                barra.setVisible(False)
            self._preparar_exploracion()
        else:
            self._contenedor_exploracion.setVisible(False)
            self._previews_exploracion = []
            self._previews_densos = []
            self._imagen_exploracion.setPixmap(QPixmap())
            self._imagen_exploracion.hide()
            self._cancelar_extremo_segmento()
            barra = getattr(self, "_barra_colapsada", None)
            if barra is not None:
                barra.setVisible(True)
                self._sincronizar_barra_colapsada()
        self.expansion_cambiada.emit(self._nombre, valor)

    def _preparar_exploracion(self):
        self._franja.set_duracion(self._duracion)
        self._franja.set_instante(0.0)
        self._franja.set_marcadores(
            *self._tiempos_y_colores_marcadores()
        )
        self._franja.set_segmentos(self._segmentos)
        self._franja.set_inicio_segmento_pendiente(None)
        self._reconstruir_previews_exploracion()
        self._limitar_ancho_superficie()
        self._actualizar_tiempo_exploracion(0.0)
        self._mostrar_preview_para_instante(0.0)
        self._renderizar_marcadores()
        self.marcadores_solicitados.emit()
        self.segmentos_solicitados.emit()
        QTimer.singleShot(0, self._reajustar_geometria_exploracion)

    def _ancho_visible_maximo(self):
        padre = self.parentWidget()
        while padre is not None:
            if isinstance(padre, QScrollArea):
                return padre.viewport().width()
            padre = padre.parentWidget()
        return None

    def _limitar_ancho_superficie(self):
        ancho_max = self._ancho_visible_maximo()
        if ancho_max is not None and ancho_max > 0:
            self._franja.setMaximumWidth(max(1, ancho_max - 24))
        else:
            self._franja.setMaximumWidth(16777215)

    def _reajustar_geometria_exploracion(self):
        if not self._expandida:
            return
        self._limitar_ancho_superficie()
        self._reposicionar_preview()
        self._renderizar_marcadores()

    def _reconstruir_previews_exploracion(self):
        disponibles = []
        duracion = self._duracion
        ancho, alto = dimensiones_miniatura()
        for indice, etiqueta in enumerate(self._etiquetas_previews):
            original = getattr(etiqueta, "_pixmap_original", None)
            if original is None or original.isNull():
                continue
            instante = None
            if _duracion_valida(duracion):
                instante = calcular_tiempo_preview(duracion, indice + 1)
            disponibles.append(
                {
                    "instante": instante,
                    "pixmap": original,
                    "pixmap_escalado": original.scaled(
                        ancho,
                        alto,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    ),
                }
            )
        if not disponibles:
            for indice, ruta in enumerate(previews_de(self._nombre)):
                pixmap = QPixmap(ruta)
                if pixmap.isNull():
                    continue
                instante = None
                if _duracion_valida(duracion):
                    instante = calcular_tiempo_preview(duracion, indice + 1)
                original = _pixmap_acotado(pixmap)
                disponibles.append(
                    {
                        "instante": instante,
                        "pixmap": original,
                        "pixmap_escalado": original.scaled(
                            ancho,
                            alto,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        ),
                    }
                )
        self._previews_exploracion = disponibles

    def _actualizar_tiempo_exploracion(self, instante):
        texto = (
            formatear_tiempo(instante)
            if isinstance(instante, (int, float))
            and not isinstance(instante, bool)
            else None
        )
        if texto is None:
            texto = "No disponible"
        total = (
            formatear_tiempo(self._duracion)
            if _duracion_valida(self._duracion)
            else "—"
        )
        self._franja.set_texto_tiempo(f"{texto} / {total}")

    def _posicionar_preview(self, instante):
        superficie = self._franja
        ancho_sup = superficie.width()
        if ancho_sup <= 0:
            return
        x = tiempo_a_posicion(instante, ancho_sup, self._duracion)
        if x is None:
            return
        ancho_img = self._imagen_exploracion.width()
        alto_img = self._imagen_exploracion.height()
        alto_sup = superficie.height()
        maximo = max(0, ancho_sup - ancho_img)
        izquierda = max(0.0, min(x - ancho_img / 2.0, float(maximo)))
        y = max(0, alto_sup - alto_img - 4)
        self._imagen_exploracion.move(int(izquierda), y)

    def _reposicionar_preview(self):
        if not self._expandida or self._franja.width() <= 0:
            return
        instante = self._franja.instante()
        if isinstance(instante, (int, float)) and not isinstance(instante, bool):
            self._posicionar_preview(instante)

    def _pixmap_para_instante(self, instante):
        if not self._previews_densos:
            disponibles = self._previews_exploracion
            indice = preview_mas_cercana(
                [d["instante"] for d in disponibles], instante
            )
            if indice is None:
                return None
            return disponibles[indice]["pixmap_escalado"]
        if not (
            isinstance(instante, (int, float))
            and not isinstance(instante, bool)
        ):
            return None
        mejor = None
        mejor_clave = None
        for es_denso, grupo in (
            (False, self._previews_exploracion),
            (True, self._previews_densos),
        ):
            for entrada in grupo:
                tiempo = entrada.get("instante")
                if not (
                    isinstance(tiempo, (int, float))
                    and not isinstance(tiempo, bool)
                ):
                    continue
                pixmap = entrada.get("pixmap_escalado")
                if pixmap is None or pixmap.isNull():
                    continue
                clave = (abs(tiempo - instante), es_denso)
                if mejor_clave is None or clave < mejor_clave:
                    mejor_clave = clave
                    mejor = pixmap
        return mejor

    def agregar_fotogramas_densos(self, densos):
        """Incorpora fotogramas densos (instante en segundos + pixmap)."""
        if not densos:
            return False
        ancho, alto = dimensiones_miniatura()
        existentes = {
            round(d["instante"], 6) for d in self._previews_densos
        }
        nuevos = False
        for entrada in densos:
            instante = entrada.get("instante")
            if not (
                isinstance(instante, (int, float))
                and not isinstance(instante, bool)
            ):
                continue
            clave = round(instante, 6)
            if clave in existentes:
                continue
            pixmap = entrada.get("pixmap")
            if pixmap is None or pixmap.isNull():
                continue
            self._previews_densos.append(
                {
                    "instante": float(instante),
                    "pixmap": pixmap,
                    "pixmap_escalado": pixmap.scaled(
                        ancho,
                        alto,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    ),
                }
            )
            existentes.add(clave)
            nuevos = True
        if nuevos and self._expandida:
            self._refrescar_exploracion()
        return nuevos

    def _mostrar_preview_para_instante(self, instante):
        pixmap = self._pixmap_para_instante(instante)
        if pixmap is None:
            self._imagen_exploracion.setPixmap(QPixmap())
            self._imagen_exploracion.setText("")
            self._imagen_exploracion.hide()
            return
        self._imagen_exploracion.setPixmap(pixmap)
        self._imagen_exploracion.setFixedSize(pixmap.size())
        self._imagen_exploracion.setText("")
        self._imagen_exploracion.show()
        self._posicionar_preview(instante)

    def _al_instante_exploracion(self, instante):
        self._actualizar_tiempo_exploracion(instante)
        self._mostrar_preview_para_instante(instante)
        self._imagen_exploracion.raise_()

    def _tolerancia_marcadores(self):
        ancho = self._franja.width()
        if ancho > 0 and _duracion_valida(self._duracion):
            return self._duracion / ancho * 0.5
        return 0.0

    def _al_marcador_solicitado(self, instante):
        self._marcador_creado_prensa = None
        tiempos = [m["tiempo"] for m in self._marcadores]
        tolerancia = self._tolerancia_marcadores()
        _, agregado = agregar_marcador_ordenado(
            instante, tiempos, tolerancia
        )
        if not agregado:
            return
        marcador = {
            "id": None,
            "tiempo": float(instante),
            "pixmap": self._pixmap_para_instante(instante),
            "etiqueta": None,
            "color": self._color_activo,
            "eliminada": False,
        }
        posicion = 0
        while (
            posicion < len(self._marcadores)
            and self._marcadores[posicion]["tiempo"] < float(instante)
        ):
            posicion += 1
        self._marcadores.insert(posicion, marcador)
        self._franja.set_marcadores(
            *self._tiempos_y_colores_marcadores()
        )
        self._renderizar_marcadores()
        self._sincronizar_barra_colapsada()
        self._bump_resumen_version()
        self._marcador_creado_prensa = marcador
        self.marcador_creado.emit(marcador)

    def _al_reproduccion_solicitada(self, instante):
        """Doble clic sobre la franja: reproduce el video desde el instante.

        La primera pulsación del doble clic crea un marcador (comportamiento
        de clic simple) en modo normal; aquí se descarta ese marcador recién
        creado para que el doble clic no deje marcadores. En modo segmento no
        hay marcador (el extremo se difiere), pero se cancela el extremo
        pendiente. En ambos casos se notifica la reproducción temporal.
        """
        self._cancelar_extremo_segmento()
        if not self._modo_crear_segmento:
            marcador = self._marcador_creado_prensa
            self._marcador_creado_prensa = None
            if marcador is not None:
                self._al_marcador_eliminar_solicitado(marcador["tiempo"])
        self.reproduccion_temporal_solicitada.emit(float(instante))

    def _al_toggle_segmento(self, marcado):
        self._modo_crear_segmento = bool(marcado)
        self._franja.set_modo_crear_segmento(bool(marcado))
        if not marcado:
            self._cancelar_extremo_segmento()

    def _cancelar_extremo_segmento(self):
        self._extremo_segmento = None
        self._franja.set_inicio_segmento_pendiente(None)

    def _al_extremo_segmento_solicitado(self, instante):
        """Primer/segundo clic en modo segmento: fija A y luego B (normalizado).

        A vive solo en RAM; el segmento se crea únicamente cuando hay dos
        extremos con `fin > inicio`, se persiste asíncronamente y se pinta la
        banda. El modo queda activo para seguir creando segmentos.
        """
        if not self._modo_crear_segmento:
            return
        if self._extremo_segmento is None:
            self._extremo_segmento = float(instante)
            self._franja.set_inicio_segmento_pendiente(self._extremo_segmento)
            return
        a = self._extremo_segmento
        b = float(instante)
        self._extremo_segmento = None
        self._franja.set_inicio_segmento_pendiente(None)
        self._crear_segmento_normalizado(a, b)

    def _al_segmento_arrastre_confirmado(self, a, b):
        """Arrastre válido en modo segmento: crea el segmento A→B.

        Reutiliza exactamente el flujo persistente de la creación por dos
        clics. Si existía un A pendiente (de un clic anterior), se cancela:
        el arrastre reemplaza el gesto previo y crea un único segmento.
        """
        if not self._modo_crear_segmento:
            return
        self._extremo_segmento = None
        self._franja.set_inicio_segmento_pendiente(None)
        self._crear_segmento_normalizado(a, b)

    def _al_extremo_editado(self, segmento, inicio, fin):
        """Edición de un extremo de segmento existente (Pulido #4).

        Actualiza de forma optimista el registro local (conservando `id`),
        cancela cualquier A pendiente y notifica para persistir un único
        UPDATE por id. `inicio`/`fin` ya llegan normalizados (inicio < fin).
        """
        if not self._modo_crear_segmento:
            return
        previo = {
            "inicio": float(segmento["inicio"]),
            "fin": float(segmento["fin"]),
        }
        inicio = float(inicio)
        fin = float(fin)
        if fin <= inicio:
            return
        if (
            abs(previo["inicio"] - inicio) < 1e-9
            and abs(previo["fin"] - fin) < 1e-9
        ):
            return
        self._extremo_segmento = None
        self._franja.set_inicio_segmento_pendiente(None)
        segmento["inicio"] = inicio
        segmento["fin"] = fin
        self._segmentos.sort(
            key=lambda s: (
                s["inicio"],
                s["fin"],
                s["id"] if s["id"] is not None else 0,
            )
        )
        self._franja.set_segmentos(self._segmentos)
        self._sincronizar_barra_colapsada()
        self._bump_resumen_version()
        self.segmento_actualizado.emit(segmento, previo)

    def _crear_segmento_normalizado(self, a, b):
        """Crea y persiste un segmento a partir de dos extremos.

        Normaliza inicio/fin (inicio < fin), descarta duración nula o
        negativa y encola la persistencia mediante `segmento_creado`
        (mismo flujo optimista/reconcile asíncrono para los caminos de
        creación por clic A+B y por arrastre).
        """
        inicio = min(float(a), float(b))
        fin = max(float(a), float(b))
        if fin <= inicio:
            return None
        registro = {
            "id": None,
            "inicio": inicio,
            "fin": fin,
            "color": self._color_activo,
            "eliminada": False,
        }
        self._segmentos.append(registro)
        self._segmentos.sort(
            key=lambda s: (
                s["inicio"],
                s["fin"],
                s["id"] if s["id"] is not None else 0,
            )
        )
        self._franja.set_segmentos(self._segmentos)
        self._sincronizar_barra_colapsada()
        self._bump_resumen_version()
        self.segmento_creado.emit(registro)
        return registro

    def _al_segmento_eliminar_solicitado(self, segmento):
        for indice, seg in enumerate(self._segmentos):
            if seg is segmento:
                del self._segmentos[indice]
                self._franja.set_segmentos(self._segmentos)
                self._sincronizar_barra_colapsada()
                self._bump_resumen_version()
                self.segmento_eliminado.emit(seg)
                return

    def _al_segmento_contextual_solicitado(self, segmento):
        """Menú contextual del segmento bajo el cursor (B5.6/B6.3).

        La franja solo informa qué segmento está bajo el cursor; aquí se
        construye el menú (acción de UI) con Reproducir/Bucle/Asignar color/
        Eliminar y se muestra de forma no bloqueante (`popup`), dejando la
        referencia disponible para su inspección/accionado programático en
        pruebas.
        """
        menu = QMenu(self)
        accion_reproducir = menu.addAction("Reproducir segmento")
        accion_bucle = menu.addAction("Reproducir segmento en bucle")
        submenu_color = QMenu("Asignar color", menu)
        menu.addMenu(submenu_color)
        for clave, *_resto in COLORES_CLASIFICACION:
            accion = submenu_color.addAction(
                texto_color(clave, self._ruta_config)
            )
            accion.triggered.connect(
                lambda *args, s=segmento, c=clave: self._emitir_color_segmento(
                    s, c
                )
            )
        accion_quitar = submenu_color.addAction("Sin clasificar")
        accion_quitar.triggered.connect(
            lambda *args, s=segmento: self._emitir_color_segmento(s, None)
        )
        if not segmento.get("color"):
            accion_quitar.setEnabled(False)
        accion_eliminar = menu.addAction("Eliminar segmento")
        accion_reproducir.triggered.connect(
            lambda *args, s=segmento: self.segmento_reproduccion_solicitada.emit(s)
        )
        accion_bucle.triggered.connect(
            lambda *args, s=segmento: self.segmento_bucle_solicitado.emit(s)
        )
        accion_eliminar.triggered.connect(
            lambda *args, s=segmento: self._al_segmento_eliminar_solicitado(s)
        )
        self._menu_segmento_actual = menu
        self._submenu_segmento_color_actual = submenu_color
        menu.popup(QCursor.pos())

    def _emitir_color_segmento(self, segmento, clave):
        self.segmento_color_solicitado.emit(segmento, clave)

    def _al_marcador_contextual_solicitado(self, tiempo):
        """Menú contextual del marcador bajo el cursor (B6.3).

        Reemplaza la eliminación directa por clic derecho: ahora se abre un
        menú no bloqueante con «Asignar color» y «Eliminar marcador». La
        referencia del menú queda en `_menu_marcador_actual` para pruebas.
        """
        objetivo = float(tiempo)
        marcador = next(
            (
                m
                for m in self._marcadores
                if abs(m["tiempo"] - objetivo) < 1e-9
            ),
            None,
        )
        if marcador is None:
            return
        menu = QMenu(self)
        submenu_color = QMenu("Asignar color", menu)
        menu.addMenu(submenu_color)
        for clave, *_resto in COLORES_CLASIFICACION:
            accion = submenu_color.addAction(
                texto_color(clave, self._ruta_config)
            )
            accion.triggered.connect(
                lambda *args, m=marcador, c=clave: self._emitir_color_marcador(
                    m, c
                )
            )
        accion_quitar = submenu_color.addAction("Sin clasificar")
        accion_quitar.triggered.connect(
            lambda *args, m=marcador: self._emitir_color_marcador(m, None)
        )
        if not marcador.get("color"):
            accion_quitar.setEnabled(False)
        accion_eliminar = menu.addAction("Eliminar marcador")
        accion_eliminar.triggered.connect(
            lambda *args, m=marcador: self._al_marcador_eliminar_solicitado(
                m["tiempo"]
            )
        )
        self._menu_marcador_actual = menu
        self._submenu_marcador_color_actual = submenu_color
        menu.popup(QCursor.pos())

    def _emitir_color_marcador(self, marcador, clave):
        self.marcador_color_solicitado.emit(marcador, clave)

    def _posicionar_miniatura_marcada(self, marcador):
        etiqueta = marcador.get("etiqueta")
        if etiqueta is None:
            return
        superficie = self._franja
        ancho_sup = superficie.width()
        if ancho_sup <= 0:
            return
        x = tiempo_a_posicion(
            marcador["tiempo"], ancho_sup, self._duracion
        )
        if x is None:
            return
        ancho_img = etiqueta.width()
        alto_img = etiqueta.height()
        alto_sup = superficie.height()
        maximo = max(0, ancho_sup - ancho_img)
        izquierda = max(0.0, min(x - ancho_img / 2.0, float(maximo)))
        y = max(0, alto_sup - alto_img - 4)
        etiqueta.move(int(izquierda), y)
        etiqueta.show()

    def _renderizar_marcadores(self):
        for marcador in self._marcadores:
            if marcador.get("pixmap") is None:
                marcador["pixmap"] = self._pixmap_para_instante(
                    marcador["tiempo"]
                )
            etiqueta = marcador.get("etiqueta")
            if etiqueta is None:
                pixmap = marcador.get("pixmap")
                if pixmap is None:
                    continue
                etiqueta = MiniaturaMarcador(self._franja, marcador["tiempo"])
                etiqueta.setPixmap(pixmap)
                etiqueta.setFixedSize(pixmap.size())
                etiqueta.eliminar_solicitado.connect(
                    self._al_marcador_eliminar_solicitado
                )
                etiqueta.contextual_solicitado.connect(
                    self._al_marcador_contextual_solicitado
                )
                marcador["etiqueta"] = etiqueta
            else:
                pixmap = marcador.get("pixmap")
                if pixmap is not None:
                    etiqueta.setPixmap(pixmap)
            self._posicionar_miniatura_marcada(marcador)

    def _al_marcador_eliminar_solicitado(self, tiempo):
        objetivo = float(tiempo)
        for indice, marcador in enumerate(self._marcadores):
            if abs(marcador["tiempo"] - objetivo) < 1e-9:
                etiqueta = marcador.get("etiqueta")
                if etiqueta is not None:
                    etiqueta.hide()
                    etiqueta.setParent(None)
                    etiqueta.deleteLater()
                del self._marcadores[indice]
                self._franja.set_marcadores(
                    *self._tiempos_y_colores_marcadores()
                )
                self._sincronizar_barra_colapsada()
                self._bump_resumen_version()
                self.marcador_eliminado.emit(marcador)
                return

    def _refrescar_exploracion(self):
        if not self._expandida:
            return
        self._reconstruir_previews_exploracion()
        instante = self._franja.instante()
        if not (
            isinstance(instante, (int, float))
            and not isinstance(instante, bool)
        ):
            instante = 0.0
        self._actualizar_tiempo_exploracion(instante)
        self._mostrar_preview_para_instante(instante)
        self._renderizar_marcadores()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        franja = getattr(self, "_franja", None)
        if franja is not None and self._expandida:
            QTimer.singleShot(0, self._reajustar_geometria_exploracion)

    def eventFilter(self, objeto, evento):
        if getattr(self, "_franja", None) is objeto:
            if evento.type() == QEvent.Leave:
                self._imagen_exploracion.lower()
            return super().eventFilter(objeto, evento)
        if evento.type() == QEvent.Enter:
            pixmap = self._pixmap_ampliada(objeto)
            if pixmap is not None:
                self.vista_solicitada.emit(pixmap)
        elif evento.type() == QEvent.Leave:
            self.vista_abandonada.emit()
        return super().eventFilter(objeto, evento)


class PanelPrincipal(QWidget):
    """Panel derecho del QSplitter que contiene toda la interfaz principal.

    Redefine minimumSizeHint() para devolver QSize(0, 0) porque el
    minimumSizeHint calculado por defecto (~720 px) esta dominado por
    la barra de herramientas (fila_carpeta) que contiene 8 widgets.

    Si no se anula, el QSplitter usa ese valor como tamano minimo
    efectivo del panel derecho, lo que bloquea el arrastre del divisor
    hacia la derecha porque el panel ya esta en su minimo.

    Al devolver (0, 0), el QSplitter solo respeta el minimumWidth
    explicito del panel izquierdo (80 px), permitiendo que el divisor
    se arrastre libremente en ambas direcciones.
    """

    def minimumSizeHint(self):
        return QSize(0, 0)


class VisorVideos(QMainWindow):
    def __init__(self, ruta_db=None, parent=None, ruta_config=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de videos")
        self.tarjetas = []
        self.visibles = []
        self._ruta_db = ruta_db
        self._ruta_config = ruta_config
        self._modo_alcance = obtener_modo_alcance(ruta_config)
        self._sincronizando_alcance = False
        self.seleccion_carpetas = SeleccionCarpetas(ruta_config=ruta_config)
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
        self.carpetas_escaneadas = set()
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = None
        self._cola_previews = []
        self.tarea_previews = None
        self.gestor_previews = None
        self._pipeline_activo = False
        self._texto_progreso = ""
        self._progreso_detallado = False
        self._nombres_seleccionados = set()
        self._ancla_seleccion = None
        self._modo_seleccion = False
        self._portapapeles = []
        self._operacion_archivos = None
        self._carpeta_sincronizacion = None
        self._cola_carpetas_escaneo = []
        self._alcance_sincronizacion = None

        clave_orden, direccion_orden = obtener_orden_catalogo(ruta_config)
        self._orden_catalogo = (clave_orden, direccion_orden)
        self._orden_generacion = 0
        self._generacion_tarea_lectura = 0
        self._reordenamiento_pendiente = False
        self._bloqueo_orden = False

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()
        self.resumen_seleccion = QLabel()
        self.estado_carga = QLabel(MENSAJE_CARGANDO)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setFixedHeight(24)

        self.boton_seleccionar_carpeta = QPushButton("Seleccionar carpeta")
        self.boton_seleccionar_carpeta.clicked.connect(self.seleccionar_carpeta)

        self.boton_escanear = QPushButton("Escanear carpeta")
        self.boton_escanear.setEnabled(False)
        self.boton_escanear.clicked.connect(
            lambda _marcado=False: self.iniciar_escaneo()
        )

        self.combo_modo_alcance = QComboBox()
        self.combo_modo_alcance.addItem(
            "Solo carpeta actual", MODO_ALCANCE_SOLO
        )
        self.combo_modo_alcance.addItem(
            "Carpeta actual y todas las subcarpetas",
            MODO_ALCANCE_SUBCARPETAS,
        )
        self.combo_modo_alcance.addItem(
            "Selección personalizada", MODO_ALCANCE_SELECCION
        )
        self.combo_modo_alcance.currentIndexChanged.connect(
            self._al_cambiar_modo_alcance
        )
        self.incluir_subcarpetas = QCheckBox("Incluir subcarpetas", self)
        self.incluir_subcarpetas.setVisible(False)
        self.incluir_subcarpetas.stateChanged.connect(
            self._al_cambiar_subcarpetas
        )

        self.escaneo_automatico = QCheckBox("Escaneo automático")
        self.escaneo_automatico.stateChanged.connect(
            self._al_cambiar_escaneo_automatico
        )

        self.etiqueta_cantidad_previews = QLabel("Previews:")
        self.combo_cantidad_previews = QComboBox()
        self.combo_cantidad_previews.addItems(["3", "5", "7", "9"])
        self.combo_cantidad_previews.currentIndexChanged.connect(
            self._al_cambiar_cantidad_previews
        )

        self.etiqueta_tamano_miniaturas = QLabel("Tamaño:")
        self.combo_tamano_miniaturas = QComboBox()
        self.combo_tamano_miniaturas.addItems(
            ["Pequeño", "Mediano", "Grande", "Muy grande"]
        )
        self.combo_tamano_miniaturas.currentIndexChanged.connect(
            self._al_cambiar_tamano_miniaturas
        )

        self.boton_preferencias = QPushButton("Preferencias…")
        self.boton_preferencias.clicked.connect(self._abrir_preferencias)

        self.boton_modo_seleccion = QPushButton("Modo selección")
        self.boton_modo_seleccion.setCheckable(True)
        self.boton_modo_seleccion.toggled.connect(
            self._al_cambiar_modo_seleccion
        )

        self.boton_copiar = QPushButton("Copiar…")
        self.boton_copiar.setEnabled(False)
        self.boton_copiar.clicked.connect(self._iniciar_copia)

        self.boton_pegar = QPushButton("Pegar…")
        self.boton_pegar.setEnabled(False)
        self.boton_pegar.clicked.connect(self._iniciar_pegar)

        self.boton_eliminar = QPushButton("Eliminar…")
        self.boton_eliminar.setEnabled(False)
        self.boton_eliminar.clicked.connect(self._iniciar_eliminar)

        self.boton_cargar_mas = QPushButton("Cargar más")
        self.boton_cargar_mas.setEnabled(False)
        self.boton_cargar_mas.clicked.connect(self.cargar_mas)

        self.etiqueta_orden = QLabel("Ordenar por:")
        self.combo_orden_criterio = QComboBox()
        for clave, texto in TEXTOS_ORDEN_CRITERIOS.items():
            self.combo_orden_criterio.addItem(texto, clave)
        self.combo_orden_direccion = QComboBox()
        for direccion, texto in TEXTOS_ORDEN_DIRECCIONES.items():
            self.combo_orden_direccion.addItem(texto, direccion)
        self.combo_orden_criterio.currentIndexChanged.connect(
            self._al_cambiar_orden_catalogo
        )
        self.combo_orden_direccion.currentIndexChanged.connect(
            self._al_cambiar_orden_catalogo
        )

        self.etiqueta_carpeta = QLabel(MENSAJE_SIN_CARPETA)
        self.etiqueta_carpeta.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.estado_escaneo = QLabel(MENSAJE_SIN_ESCANEO)

        self.mensaje_carpeta = QLabel()
        self.mensaje_carpeta.setStyleSheet("color: #b00020;")

        fila_carpeta = QHBoxLayout()
        fila_carpeta.addWidget(self.boton_seleccionar_carpeta)
        fila_carpeta.addWidget(self.boton_escanear)
        fila_carpeta.addWidget(self.combo_modo_alcance)
        fila_carpeta.addWidget(self.escaneo_automatico)
        fila_carpeta.addWidget(self.etiqueta_cantidad_previews)
        fila_carpeta.addWidget(self.combo_cantidad_previews)
        fila_carpeta.addWidget(self.etiqueta_tamano_miniaturas)
        fila_carpeta.addWidget(self.combo_tamano_miniaturas)
        fila_carpeta.addWidget(self.boton_preferencias)
        fila_carpeta.addWidget(self.boton_modo_seleccion)
        fila_carpeta.addWidget(self.boton_copiar)
        fila_carpeta.addWidget(self.boton_pegar)
        fila_carpeta.addWidget(self.boton_eliminar)
        fila_carpeta.addWidget(self.etiqueta_carpeta, 1)
        fila_carpeta.addWidget(self.estado_escaneo)
        fila_carpeta.addWidget(self.mensaje_carpeta)

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.etiqueta_orden)
        barra.addWidget(self.combo_orden_criterio)
        barra.addWidget(self.combo_orden_direccion)
        barra.addWidget(self.contador)
        barra.addWidget(self.resumen_seleccion)
        barra.addWidget(self.boton_cargar_mas)
        barra.addWidget(self.estado_carga)

        self.contenedor = QWidget()
        self.cuadricula = QGridLayout(self.contenedor)
        self.cuadricula.setColumnStretch(0, 1)
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()

        self._atajo_ctrl_a = QShortcut(QKeySequence("Ctrl+A"), self)
        self._atajo_ctrl_a.activated.connect(self._atajo_seleccionar_todo)
        self._atajo_esc = QShortcut(QKeySequence("Esc"), self)
        self._atajo_esc.activated.connect(self._atajo_salir_modo_seleccion)

        self._atajo_copiar = QShortcut(QKeySequence("Ctrl+C"), self)
        self._atajo_copiar.activated.connect(self._atajo_operacion_copiar)
        self._atajo_pegar = QShortcut(QKeySequence("Ctrl+V"), self)
        self._atajo_pegar.activated.connect(self._atajo_operacion_pegar)
        self._atajo_eliminar = QShortcut(QKeySequence("Del"), self)
        self._atajo_eliminar.activated.connect(self._atajo_operacion_eliminar)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        raiz = PanelPrincipal()
        layout = QVBoxLayout(raiz)
        layout.addLayout(fila_carpeta)
        layout.addLayout(barra)
        layout.addWidget(self.barra_progreso)
        layout.addWidget(self.area)

        panel_izquierdo = QWidget()
        panel_izquierdo.setMinimumWidth(80)
        panel_izquierdo.setMaximumWidth(400)
        panel_izquierdo.setStyleSheet("background-color: #e8e8e8;")
        layout_izquierdo = QVBoxLayout(panel_izquierdo)
        layout_izquierdo.setContentsMargins(0, 0, 0, 0)
        self.toggle_modo_seleccion = QCheckBox("Modo selección")
        self.toggle_modo_seleccion.stateChanged.connect(
            self._al_cambiar_modo_seleccion_arbol
        )
        layout_izquierdo.addWidget(self.toggle_modo_seleccion)

        self.contenedor_acciones_seleccion = QWidget()
        fila_acciones_seleccion = QHBoxLayout(self.contenedor_acciones_seleccion)
        fila_acciones_seleccion.setContentsMargins(4, 0, 4, 4)
        self.boton_seleccionar_todas = QPushButton("Seleccionar todas")
        self.boton_deseleccionar_todas = QPushButton("Deseleccionar todas")
        self.boton_invertir_seleccion = QPushButton("Invertir")
        fila_acciones_seleccion.addWidget(self.boton_seleccionar_todas)
        fila_acciones_seleccion.addWidget(self.boton_deseleccionar_todas)
        fila_acciones_seleccion.addWidget(self.boton_invertir_seleccion)
        self.contenedor_acciones_seleccion.setVisible(False)
        layout_izquierdo.addWidget(self.contenedor_acciones_seleccion)

        self.arbol_navegacion = ArbolNavegacion(
            seleccion=self.seleccion_carpetas
        )
        self.arbol_navegacion.ruta_seleccionada.connect(
            self._al_carpeta_actual_arbol
        )
        self.boton_seleccionar_todas.clicked.connect(
            self.arbol_navegacion.seleccionar_todas_nivel
        )
        self.boton_deseleccionar_todas.clicked.connect(
            self.arbol_navegacion.deseleccionar_todas
        )
        self.boton_invertir_seleccion.clicked.connect(
            self.arbol_navegacion.invertir_nivel
        )
        layout_izquierdo.addWidget(self.arbol_navegacion)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        splitter.addWidget(panel_izquierdo)
        splitter.addWidget(raiz)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 680])
        splitter.setCollapsible(0, False)
        self.setCentralWidget(splitter)

        self.etiqueta_version = QLabel(TEXTO_VERSION_BUILD)
        self.etiqueta_version.setObjectName("etiqueta_version")
        self.etiqueta_version.setStyleSheet("color: #7a7a7a;")
        self.statusBar().addPermanentWidget(self.etiqueta_version)

        self.gestor = GestorTareas(self)
        self.gestor.tarea_resultado.connect(self._al_resultado)
        self.gestor.tarea_error.connect(self._al_error)
        self.gestor.tarea_finalizada.connect(self._al_tarea_finalizada)
        self.gestor.tarea_progreso.connect(self._al_progreso_pipeline)
        self.gestor.actividad_cambiada.connect(self._al_actividad)

        self.gestor_previews = GestorTareas(self)
        self.gestor_previews.tarea_resultado.connect(self._al_resultado_previews)
        self.gestor_previews.tarea_error.connect(self._al_error_previews)
        self.gestor_previews.tarea_finalizada.connect(self._al_previews_finalizada)

        self.gestor_operaciones = GestorTareas(self)
        self.gestor_operaciones.tarea_resultado.connect(
            self._al_resultado_operaciones
        )
        self.gestor_operaciones.tarea_error.connect(
            self._al_error_operaciones
        )
        self.gestor_operaciones.tarea_progreso.connect(
            self._al_progreso_pipeline
        )

        self.gestor_marcadores = GestorTareas(self)
        self.gestor_marcadores.tarea_resultado.connect(
            self._al_resultado_marcadores
        )
        self.gestor_marcadores.tarea_error.connect(
            self._al_error_marcadores
        )
        self.gestor_marcadores.tarea_finalizada.connect(
            self._al_marcadores_finalizada
        )
        self._cola_marcadores = []
        self._marcador_op_actual = None

        self.gestor_segmentos = GestorTareas(self)
        self.gestor_segmentos.tarea_resultado.connect(
            self._al_resultado_segmentos
        )
        self.gestor_segmentos.tarea_error.connect(
            self._al_error_segmentos
        )
        self.gestor_segmentos.tarea_finalizada.connect(
            self._al_segmentos_finalizada
        )
        self._cola_segmentos = []
        self._segmento_op_actual = None

        self.gestor_reproduccion = GestorTareas(self)
        self.gestor_reproduccion.tarea_resultado.connect(
            self._al_resultado_reproduccion
        )
        self.gestor_reproduccion.tarea_error.connect(
            self._al_error_reproduccion
        )
        self._reproduccion_pendiente = None

        self.gestor_exploracion = GestorTareas(self)
        self.gestor_exploracion.tarea_resultado.connect(
            self._al_resultado_exploracion
        )
        self.gestor_exploracion.tarea_error.connect(
            self._al_error_exploracion
        )
        self.gestor_exploracion.tarea_finalizada.connect(
            self._al_exploracion_finalizada
        )
        self._cola_exploracion = []
        self._exploracion_op_actual = None
        self._exploracion_objetivo = None
        self.tarea_exploracion = None

        # B6.4 resumen colapsado: una sola tarea batch por lote de tarjetas, sin SQLite en UI
        self.gestor_resumen = GestorTareas(self)
        self.gestor_resumen.tarea_resultado.connect(self._al_resultado_resumen)
        self.gestor_resumen.tarea_error.connect(self._al_error_resumen)
        self.gestor_resumen.tarea_finalizada.connect(self._al_resumen_finalizada)
        self._cola_resumen = []
        self._resumen_op_actual = None
        self._resumen_ids_en_vuelo = set()

        self._timer_previews = QTimer(self)
        self._timer_previews.setSingleShot(True)
        self._timer_previews.setInterval(300)
        self._timer_previews.timeout.connect(self._iniciar_previews)

        self._vista = VistaAmpliada(self)
        self._vista_pendiente = None
        self._timer_vista_mostrar = QTimer(self)
        self._timer_vista_mostrar.setSingleShot(True)
        self._retardo_vista_ampliada = obtener_retardo_vista_ampliada(
            self._ruta_config
        )
        if self._retardo_vista_ampliada != -1:
            self._timer_vista_mostrar.setInterval(
                self._retardo_vista_ampliada
            )
        configurar_factor_vista_ampliada(
            obtener_tamano_vista_ampliada(self._ruta_config)
        )
        self._timer_vista_mostrar.timeout.connect(self._mostrar_vista_diferida)
        self._timer_vista_ocultar = QTimer(self)
        self._timer_vista_ocultar.setSingleShot(True)
        self._timer_vista_ocultar.setInterval(RETARDO_OCULTAR_VISTA_MS)
        self._timer_vista_ocultar.timeout.connect(self._vista.ocultar)
        self.area.verticalScrollBar().valueChanged.connect(self._ocultar_vista)
        carpeta_guardada = obtener_ultima_carpeta(self._ruta_config)
        if carpeta_guardada is not None:
            self.carpeta_seleccionada = carpeta_guardada
            self.etiqueta_carpeta.setText(carpeta_guardada)
            if not self.arbol_navegacion.revelar_ruta(carpeta_guardada):
                self.carpeta_seleccionada = None
                self.etiqueta_carpeta.setText(MENSAJE_SIN_CARPETA)
            self._actualizar_botones_carpeta()
        self._sincronizar_alcance_desde_modo()
        self.escaneo_automatico.setChecked(
            obtener_preferencia_escaneo_automatico(self._ruta_config)
        )
        cantidad = obtener_cantidad_previews(self._ruta_config)
        idx = self.combo_cantidad_previews.findText(str(cantidad))
        if idx >= 0:
            self.combo_cantidad_previews.setCurrentIndex(idx)
        configurar_cantidad_previews(cantidad)
        tamano = obtener_tamano_miniaturas(self._ruta_config)
        idx_tamano = self.combo_tamano_miniaturas.findText(
            texto_tamano_miniaturas(tamano)
        )
        self.combo_tamano_miniaturas.blockSignals(True)
        if idx_tamano >= 0:
            self.combo_tamano_miniaturas.setCurrentIndex(idx_tamano)
        self.combo_tamano_miniaturas.blockSignals(False)
        configurar_tamano_miniaturas(tamano)
        clave_orden, direccion_orden = self._orden_catalogo
        self._bloqueo_orden = True
        indice = self.combo_orden_criterio.findData(clave_orden)
        if indice >= 0:
            self.combo_orden_criterio.setCurrentIndex(indice)
        indice_dir = self.combo_orden_direccion.findData(direccion_orden)
        if indice_dir >= 0:
            self.combo_orden_direccion.setCurrentIndex(indice_dir)
        self._bloqueo_orden = False
        self._iniciar_carga()

    def _iniciar_carga(self):
        self.tarea_lectura = self._crear_tarea_lectura()
        self.gestor.iniciar(self.tarea_lectura)
        self._generacion_tarea_lectura = self._orden_generacion

    def _sincronizar_alcance_desde_modo(self):
        self._sincronizando_alcance = True
        try:
            indice = self.combo_modo_alcance.findData(self._modo_alcance)
            if indice >= 0:
                self.combo_modo_alcance.setCurrentIndex(indice)
            self.incluir_subcarpetas.setChecked(
                self._modo_alcance == MODO_ALCANCE_SUBCARPETAS
            )
        finally:
            self._sincronizando_alcance = False

    def _al_cambiar_modo_alcance(self, _indice):
        if self._sincronizando_alcance:
            return
        modo = self.combo_modo_alcance.currentData()
        if modo is None:
            return
        self._modo_alcance = modo
        guardar_modo_alcance(modo, self._ruta_config)
        self._sincronizar_alcance_desde_modo()
        if (
            modo == MODO_ALCANCE_SELECCION
            and getattr(self, "toggle_modo_seleccion", None) is not None
        ):
            self.toggle_modo_seleccion.setChecked(True)

    def _al_cambiar_subcarpetas(self, _estado):
        if self._sincronizando_alcance:
            return
        self._modo_alcance = (
            MODO_ALCANCE_SUBCARPETAS
            if self.incluir_subcarpetas.isChecked()
            else MODO_ALCANCE_SOLO
        )
        guardar_modo_alcance(self._modo_alcance, self._ruta_config)
        self._sincronizar_alcance_desde_modo()

    def _al_cambiar_escaneo_automatico(self, _estado):
        guardar_preferencia_escaneo_automatico(
            self.escaneo_automatico.isChecked(), self._ruta_config
        )

    def _al_cambiar_cantidad_previews(self, _indice):
        texto = self.combo_cantidad_previews.currentText()
        try:
            n = int(texto)
        except (ValueError, TypeError):
            return
        guardar_cantidad_previews(n, self._ruta_config)
        configurar_cantidad_previews(n)
        for _, tarjeta in self.tarjetas:
            tarjeta.ajustar_previews(n)
        self._programar_previews()

    def _al_cambiar_tamano_miniaturas(self, _indice):
        nombre = clave_tamano_miniaturas(
            self.combo_tamano_miniaturas.currentText()
        )
        configurar_tamano_miniaturas(nombre)
        guardar_tamano_miniaturas(nombre, self._ruta_config)
        for _, tarjeta in self.tarjetas:
            tarjeta.aplicar_tamano()

    def _al_vista_solicitada(self, pixmap):
        if self._retardo_vista_ampliada == -1:
            return
        if pixmap is None or pixmap.isNull():
            return
        self._timer_vista_ocultar.stop()
        if self._vista.isVisible() and self._vista._pixmap is not pixmap:
            self._vista.ocultar()
        self._vista_pendiente = pixmap
        self._timer_vista_mostrar.start()

    def _al_vista_abandonada(self):
        self._timer_vista_mostrar.stop()
        self._vista_pendiente = None
        self._timer_vista_ocultar.start()

    def _mostrar_vista_diferida(self):
        pixmap = self._vista_pendiente
        if pixmap is None or pixmap.isNull():
            return
        reutilizada = self._vista.preparar(pixmap)
        self._vista.move(self._posicion_vista())
        if not reutilizada:
            self._vista.show()
            self._vista.raise_()

    def _posicion_vista(self):
        cursor = QCursor.pos()
        pantalla = QApplication.primaryScreen().availableGeometry()
        margen = 16
        ancho = self._vista.width()
        alto = self._vista.height()
        x = cursor.x() + margen
        y = cursor.y() + margen
        if x + ancho > pantalla.right():
            x = cursor.x() - ancho - margen
        if y + alto > pantalla.bottom():
            y = cursor.y() - alto - margen
        x = max(pantalla.left(), min(x, pantalla.right() - ancho))
        y = max(pantalla.top(), min(y, pantalla.bottom() - alto))
        return QPoint(x, y)

    def _ocultar_vista(self, _valor=None):
        self._timer_vista_mostrar.stop()
        self._timer_vista_ocultar.stop()
        self._vista_pendiente = None
        self._vista.ocultar()

    def _abrir_preferencias(self):
        dialogo = PreferenciasDialog(self._ruta_config, self)
        if dialogo.exec() == QDialog.Accepted:
            self._aplicar_retardo_vista_ampliada(dialogo.retardo_seleccionado())
            self._aplicar_tamano_vista_ampliada(
                dialogo.factor_vista_seleccionado()
            )
            for _, tarjeta in self.tarjetas:
                tarjeta._refrescar_textos_colores()

    def _aplicar_retardo_vista_ampliada(self, ms):
        self._retardo_vista_ampliada = ms
        guardar_retardo_vista_ampliada(ms, self._ruta_config)
        if ms == -1:
            self._timer_vista_mostrar.stop()
            self._ocultar_vista()
        else:
            self._timer_vista_mostrar.setInterval(ms)

    def _aplicar_tamano_vista_ampliada(self, factor):
        guardar_tamano_vista_ampliada(factor, self._ruta_config)
        configurar_factor_vista_ampliada(factor)

    def _crear_tarea_lectura(self, desplazamiento=0):
        clave_orden, direccion_orden = self._orden_catalogo
        return TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL,
            desplazamiento,
            None,
            self._ruta_db,
            orden_clave=clave_orden,
            orden_direccion=direccion_orden,
        )

    def _lectura_obsoleta(self):
        """Invalidación explícita de lecturas lanzadas con un orden previo.

        Cada tarea de lectura captura `_generacion_tarea_lectura` al iniciarse;
        cada cambio de orden incrementa `_orden_generacion`. Si al llegar el
        resultado la generación no coincide, el resultado pertenece a una
        lectura del orden anterior y no debe crear, anexar ni reemplazar el
        catálogo: el reordenamiento pendiente ya disparará una recarga nueva.
        """
        return self._generacion_tarea_lectura != self._orden_generacion

    def _al_cambiar_orden_catalogo(self, _indice):
        if self._bloqueo_orden:
            return
        clave = self.combo_orden_criterio.currentData()
        direccion = self.combo_orden_direccion.currentData()
        if not isinstance(clave, str) or not isinstance(direccion, str):
            return
        if (clave, direccion) == self._orden_catalogo:
            return
        self._orden_catalogo = (clave, direccion)
        self._orden_generacion += 1
        guardar_orden_catalogo(clave, direccion, self._ruta_config)
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        # B6.4 collapsed: limpiar cola batch obsoleta del orden anterior
        self._cola_resumen.clear()
        self._resumen_ids_en_vuelo.clear()
        self.area.verticalScrollBar().setValue(0)
        self._reordenamiento_pendiente = True
        self._actualizar_botones_carpeta()
        self._procesar_reordenamiento()

    def _procesar_reordenamiento(self):
        if not self._reordenamiento_pendiente:
            return
        if self.gestor.activo:
            return
        self._reordenamiento_pendiente = False
        self._recarga_catalogo_pendiente = True
        self._iniciar_recarga_catalogo()

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
        self.arbol_navegacion.seleccionar_ruta(ruta_absoluta)
        self._actualizar_botones_carpeta()
        self._disparar_escaneo_si_automatico()

    def _disparar_escaneo_si_automatico(self):
        if self.escaneo_automatico.isChecked():
            self.iniciar_escaneo()

    def _al_cambiar_modo_seleccion_arbol(self, activo):
        self.arbol_navegacion.set_modo_seleccion(bool(activo))
        self.contenedor_acciones_seleccion.setVisible(bool(activo))

    def _al_carpeta_actual_arbol(self, ruta):
        if not isinstance(ruta, str) or not ruta:
            return
        if not os.path.isdir(ruta):
            return
        if self.carpeta_seleccionada == ruta:
            return
        self.carpeta_seleccionada = ruta
        self.etiqueta_carpeta.setText(ruta)
        self.mensaje_carpeta.clear()
        guardar_ultima_carpeta(ruta, self._ruta_config)
        self._actualizar_botones_carpeta()
        self._disparar_escaneo_si_automatico()

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
        self._actualizar_boton_copiar()
        self._actualizar_boton_pegar()
        self._actualizar_boton_eliminar()

    def _al_actividad(self, activo):
        self._actualizar_botones_carpeta()

    def _mostrar_progreso(self, texto):
        self._pipeline_activo = True
        self._texto_progreso = texto
        self._progreso_detallado = False
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setFormat(texto)
        self.barra_progreso.setVisible(True)

    def _al_progreso_pipeline(self, procesado, total):
        if total > 0:
            self.barra_progreso.setRange(0, total)
            self.barra_progreso.setValue(procesado)
            if not self._progreso_detallado:
                self.barra_progreso.setFormat(
                    f"{self._texto_progreso} %v de %m (%p%)"
                )
                self._progreso_detallado = True

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
        self._actualizar_resumen_seleccion()

    def _marcar_tarjeta(self, nombre, valor):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                tarjeta.marcar_seleccionada(valor)
                tarjeta.set_check(valor)
                self._actualizar_resumen_seleccion()
                return

    def _al_check_tarjeta(self, nombre, marcado):
        if marcado:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        else:
            self._nombres_seleccionados.discard(nombre)
            self._marcar_tarjeta(nombre, False)

    def _al_expansion_tarjeta(self, nombre, expandida):
        if not expandida:
            if self._exploracion_objetivo == nombre:
                self._exploracion_objetivo = None
                self._cancelar_exploracion_en_curso()
            return
        for candidato, tarjeta in self.tarjetas:
            if candidato != nombre:
                tarjeta.colapsar()
        self._exploracion_objetivo = nombre
        self._encolar_exploracion(nombre)

    def _encolar_exploracion(self, nombre):
        if nombre != self._exploracion_objetivo:
            return
        if nombre in self._cola_exploracion:
            return
        self._cola_exploracion.append(nombre)
        self._cancelar_exploracion_en_curso()
        self._procesar_siguiente_exploracion()

    def _al_densidad_cambiada(self, nombre, _valor):
        tarjeta = self._tarjeta_por_nombre(nombre)
        if tarjeta is None or not tarjeta._expandida:
            return
        self._encolar_exploracion(nombre)

    def _cancelar_exploracion_en_curso(self):
        tarea = self.tarea_exploracion
        if tarea is not None:
            tarea.cancelar()

    def _procesar_siguiente_exploracion(self):
        while True:
            if self.gestor_exploracion.activo:
                return
            if not self._cola_exploracion:
                return
            nombre = self._cola_exploracion.pop(0)
            if nombre != self._exploracion_objetivo:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None or not tarjeta._expandida:
                continue
            video_id = getattr(tarjeta, "_video_id", None)
            ruta_video = self._ruta_video_de(tarjeta)
            if video_id is None or not ruta_video:
                continue
            kwargs_tarea = {
                "video_id": video_id,
                "ruta_video": ruta_video,
                "duracion": tarjeta._duracion,
                "cantidad": FOTOGRAMAS_INICIALES,
            }
            objetivo_manual = getattr(tarjeta, "_densidad_manual", None)
            if objetivo_manual is not None:
                kwargs_tarea["objetivo_manual"] = objetivo_manual
            tarea = TareaExploracionDensa(**kwargs_tarea)
            tarea.resultado_parcial.connect(
                self._al_resultado_parcial_exploracion
            )
            if not self.gestor_exploracion.iniciar(tarea):
                self._cola_exploracion.insert(0, nombre)
                return
            self.tarea_exploracion = tarea
            self._exploracion_op_actual = {
                "nombre": nombre,
                "video_id": video_id,
            }
            return

    def _ruta_video_de(self, tarjeta):
        return ruta_video_existente(
            getattr(tarjeta, "_carpeta_video", None), tarjeta.nombre
        )

    def _al_resultado_exploracion(self, resultado):
        op = self._exploracion_op_actual
        if op is None:
            return
        if op.get("nombre") != self._exploracion_objetivo:
            return
        if resultado.get("cancelado"):
            return
        tarjeta = self._tarjeta_por_nombre(op.get("nombre"))
        if tarjeta is None or not tarjeta._expandida:
            return
        self._aplicar_exploracion_densa(tarjeta, op, resultado)

    def _al_resultado_parcial_exploracion(self, parcial):
        op = self._exploracion_op_actual
        if op is None:
            return
        if op.get("nombre") != self._exploracion_objetivo:
            return
        if parcial.get("video_id") != op.get("video_id"):
            return
        tarjeta = self._tarjeta_por_nombre(op.get("nombre"))
        if tarjeta is None or not tarjeta._expandida:
            return
        fotogramas = parcial.get("fotogramas") or []
        if not fotogramas:
            return
        self._aplicar_exploracion_densa(
            tarjeta,
            op,
            {
                "version": parcial.get("version"),
                "fotogramas": [ms for ms, _ in fotogramas],
                "imagenes": fotogramas,
            },
        )

    def _al_error_exploracion(self, _mensaje):
        pass

    def _al_exploracion_finalizada(self):
        self._exploracion_op_actual = None
        self.tarea_exploracion = None
        self._procesar_siguiente_exploracion()

    def _aplicar_exploracion_densa(self, tarjeta, op, resultado):
        version = resultado.get("version")
        fotogramas = resultado.get("fotogramas") or []
        if not version or not fotogramas:
            return
        video_id = op.get("video_id")
        imagenes = {}
        for item in resultado.get("imagenes") or []:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                imagenes[item[0]] = item[1]
        existentes = {
            round(d["instante"], 6) for d in tarjeta._previews_densos
        }
        densos = []
        for ms in fotogramas:
            if round(ms / 1000.0, 6) in existentes:
                continue
            imagen = imagenes.get(ms)
            if imagen is not None:
                pixmap = QPixmap.fromImage(imagen)
            else:
                ruta = exploracion_cache.ruta_fotograma_version(
                    video_id, ms, version
                )
                pixmap = QPixmap(ruta)
            if pixmap.isNull():
                continue
            densos.append({"instante": ms / 1000.0, "pixmap": pixmap})
        if densos:
            tarjeta.agregar_fotogramas_densos(densos)

    def _encolar_marcador(self, op):
        self._cola_marcadores.append(op)
        self._procesar_siguiente_marcador()

    def _procesar_siguiente_marcador(self):
        if self.gestor_marcadores.activo:
            return
        if not self._cola_marcadores:
            return
        op = self._cola_marcadores.pop(0)
        self._marcador_op_actual = op
        tipo = op.get("tipo")
        if tipo == "cargar":
            tarea = TareaListarMarcadores(op["video_id"], self._ruta_db)
        elif tipo == "crear":
            tarea = TareaGuardarMarcador(
                op["video_id"],
                op["tiempo"],
                self._ruta_db,
                color=op.get("color"),
            )
        elif tipo == "eliminar":
            tarea = TareaEliminarMarcador(
                op["marcador_id"], self._ruta_db
            )
        elif tipo == "color":
            tarea = TareaAsignarColorMarcador(
                op["marcador_id"], op["color"], self._ruta_db
            )
        else:
            self._marcador_op_actual = None
            self._procesar_siguiente_marcador()
            return
        if not self.gestor_marcadores.iniciar(tarea):
            self._marcador_op_actual = None
            self._procesar_siguiente_marcador()

    def _al_marcadores_finalizada(self):
        self._marcador_op_actual = None
        self._procesar_siguiente_marcador()

    def _al_resultado_marcadores(self, resultado):
        op = self._marcador_op_actual
        if op is None:
            return
        tipo = op.get("tipo")
        if tipo == "cargar":
            self._aplicar_marcadores_cargados(op, resultado)
        elif tipo == "crear":
            registro = op["registro"]
            registro["id"] = resultado
            if registro.get("eliminada"):
                self._encolar_marcador(
                    {
                        "tipo": "eliminar",
                        "marcador_id": resultado,
                        "video_id": op["video_id"],
                        "nombre": op["nombre"],
                    }
                )

    def _al_error_marcadores(self, mensaje):
        op = self._marcador_op_actual
        if op is None:
            return
        tipo = op.get("tipo")
        if tipo == "crear":
            registro = op["registro"]
            registro["eliminada"] = False
            self.mensaje_carpeta.setText(
                f"No se pudo guardar el marcador: {mensaje}"
            )
        elif tipo == "eliminar":
            self.mensaje_carpeta.setText(
                f"No se pudo eliminar el marcador: {mensaje}"
            )
            self._encolar_marcador(
                {
                    "tipo": "cargar",
                    "video_id": op["video_id"],
                    "nombre": op["nombre"],
                }
            )
        elif tipo == "color":
            registro = op.get("registro")
            if registro is not None:
                registro["color"] = op.get("color_previo")
                tarjeta = self._tarjeta_por_nombre(op.get("nombre"))
                if tarjeta is not None:
                    tarjeta._franja.set_marcadores(
                        *tarjeta._tiempos_y_colores_marcadores()
                    )
                    tarjeta._sincronizar_barra_colapsada()
            self.mensaje_carpeta.setText(
                f"No se pudo asignar el color del marcador: {mensaje}"
            )
        elif tipo == "cargar":
            self.mensaje_carpeta.setText(
                f"No se pudieron cargar los marcadores: {mensaje}"
            )
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._marcadores_eliminados_carga.clear()

    def _al_marcador_creado(self, tarjeta, registro):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        self._encolar_marcador(
            {
                "tipo": "crear",
                "registro": registro,
                "video_id": video_id,
                "tiempo": registro["tiempo"],
                "color": registro.get("color"),
                "nombre": tarjeta.nombre,
            }
        )

    def _al_marcador_eliminado(self, tarjeta, registro):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        marcador_id = registro.get("id")
        if marcador_id is not None:
            self._encolar_marcador(
                {
                    "tipo": "eliminar",
                    "marcador_id": marcador_id,
                    "video_id": video_id,
                    "nombre": tarjeta.nombre,
                }
            )
        else:
            registro["eliminada"] = True
            self._cancelar_crear_pendiente(registro)
            if self._hay_carga_pendiente(tarjeta):
                tarjeta._marcadores_eliminados_carga.add(
                    registro["tiempo"]
                )

    def _al_marcador_color_solicitado(self, tarjeta, registro, clave):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        marcador_id = registro.get("id")
        color_previo = registro.get("color")
        if color_previo == clave:
            return
        if clave in CLAVES_COLOR_CLASIFICACION:
            nuevo_color = clave
        else:
            nuevo_color = None
        registro["color"] = nuevo_color
        tarjeta._franja.set_marcadores(
            *tarjeta._tiempos_y_colores_marcadores()
        )
        tarjeta._sincronizar_barra_colapsada()
        try:
            tarjeta._bump_resumen_version()
        except Exception:
            pass
        if marcador_id is None:
            return
        self._encolar_marcador(
            {
                "tipo": "color",
                "registro": registro,
                "marcador_id": marcador_id,
                "video_id": video_id,
                "color": nuevo_color,
                "color_previo": color_previo,
                "nombre": tarjeta.nombre,
            }
        )

    def _hay_carga_pendiente(self, tarjeta):
        op = self._marcador_op_actual
        if (
            op is not None
            and op.get("tipo") == "cargar"
            and op.get("nombre") == tarjeta.nombre
        ):
            return True
        return any(
            op.get("tipo") == "cargar"
            and op.get("nombre") == tarjeta.nombre
            for op in self._cola_marcadores
        )

    def _cancelar_crear_pendiente(self, registro):
        self._cola_marcadores = [
            op
            for op in self._cola_marcadores
            if not (op.get("tipo") == "crear" and op.get("registro") is registro)
        ]

    def _solicitar_carga_marcadores(self, tarjeta):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None or tarjeta._marcadores_cargados:
            return
        tarjeta._marcadores_cargados = True
        self._encolar_marcador(
            {
                "tipo": "cargar",
                "video_id": video_id,
                "nombre": tarjeta.nombre,
            }
        )

    def _tarjeta_por_nombre(self, nombre):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                return tarjeta
        return None

    def _aplicar_marcadores_cargados(self, op, filas):
        tarjeta = self._tarjeta_por_nombre(op["nombre"])
        if tarjeta is None:
            return
        tarjeta._marcadores_cargados = True
        video_id = op["video_id"]
        nombre = op["nombre"]
        tolerancia = tarjeta._tolerancia_marcadores()
        for marcador_id, video_de_fila, tiempo, color in filas:
            if video_de_fila != video_id:
                continue
            if any(
                abs(tiempo - t) <= tolerancia
                for t in tarjeta._marcadores_eliminados_carga
            ):
                self._encolar_marcador(
                    {
                        "tipo": "eliminar",
                        "marcador_id": marcador_id,
                        "video_id": video_id,
                        "nombre": nombre,
                    }
                )
                continue
            encontrado = False
            for marcador in tarjeta._marcadores:
                if abs(marcador["tiempo"] - tiempo) <= tolerancia:
                    if marcador["id"] is None:
                        marcador["id"] = marcador_id
                        self._cancelar_crear_pendiente(marcador)
                    encontrado = True
                    break
            if encontrado:
                continue
            tarjeta._marcadores.append(
                {
                    "id": marcador_id,
                    "tiempo": float(tiempo),
                    "pixmap": None,
                    "etiqueta": None,
                    "color": (
                        color
                        if color in CLAVES_COLOR_CLASIFICACION
                        else None
                    ),
                    "eliminada": False,
                }
            )
        tarjeta._marcadores_eliminados_carga.clear()
        tarjeta._marcadores.sort(key=lambda m: m["tiempo"])
        tarjeta._franja.set_marcadores(
            *tarjeta._tiempos_y_colores_marcadores()
        )
        tarjeta._renderizar_marcadores()
        tarjeta._sincronizar_barra_colapsada()

    def _encolar_segmento(self, op):
        self._cola_segmentos.append(op)
        self._procesar_siguiente_segmento()

    def _procesar_siguiente_segmento(self):
        if self.gestor_segmentos.activo:
            return
        if not self._cola_segmentos:
            return
        op = self._cola_segmentos.pop(0)
        self._segmento_op_actual = op
        tipo = op.get("tipo")
        if tipo == "cargar":
            tarea = TareaListarSegmentos(op["video_id"], self._ruta_db)
        elif tipo == "crear":
            tarea = TareaGuardarSegmento(
                op["video_id"],
                op["inicio"],
                op["fin"],
                self._ruta_db,
                color=op.get("color"),
            )
        elif tipo == "eliminar":
            tarea = TareaEliminarSegmento(
                op["segmento_id"], self._ruta_db
            )
        elif tipo == "actualizar":
            tarea = TareaActualizarSegmento(
                op["segmento_id"],
                op["inicio"],
                op["fin"],
                self._ruta_db,
            )
        elif tipo == "color":
            tarea = TareaAsignarColorSegmento(
                op["segmento_id"], op["color"], self._ruta_db
            )
        else:
            self._segmento_op_actual = None
            self._procesar_siguiente_segmento()
            return
        if not self.gestor_segmentos.iniciar(tarea):
            self._segmento_op_actual = None
            self._procesar_siguiente_segmento()

    def _al_segmentos_finalizada(self):
        self._segmento_op_actual = None
        self._procesar_siguiente_segmento()

    def _al_resultado_segmentos(self, resultado):
        op = self._segmento_op_actual
        if op is None:
            return
        tipo = op.get("tipo")
        if tipo == "cargar":
            self._aplicar_segmentos_cargados(op, resultado)
        elif tipo == "crear":
            registro = op["registro"]
            seg_id, inicio, fin = resultado
            registro["id"] = seg_id
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._segmentos.sort(
                    key=lambda s: (
                        s["inicio"],
                        s["fin"],
                        s["id"] if s["id"] is not None else 0,
                    )
                )
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
                tarjeta._sincronizar_barra_colapsada()
            if registro.get("eliminada"):
                self._encolar_segmento(
                    {
                        "tipo": "eliminar",
                        "segmento_id": seg_id,
                        "video_id": op["video_id"],
                        "nombre": op["nombre"],
                    }
                )
        elif tipo == "eliminar":
            pass
        elif tipo == "actualizar":
            # El registro local ya refleja el nuevo intervalo de forma
            # optimista; se reordena y se reaplica. Si el segmento ya no
            # existía en la base (resultado None), se restaura lo previo.
            registro = op["registro"]
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if resultado is None:
                registro["inicio"] = op["previo"]["inicio"]
                registro["fin"] = op["previo"]["fin"]
                if tarjeta is not None:
                    tarjeta._segmentos.sort(
                        key=lambda s: (
                            s["inicio"],
                            s["fin"],
                            s["id"] if s["id"] is not None else 0,
                        )
                    )
                    tarjeta._franja.set_segmentos(tarjeta._segmentos)
                    tarjeta._sincronizar_barra_colapsada()
                self.mensaje_carpeta.setText(
                    "No se pudo actualizar el segmento: ya no existe."
                )
            elif tarjeta is not None:
                tarjeta._segmentos.sort(
                    key=lambda s: (
                        s["inicio"],
                        s["fin"],
                        s["id"] if s["id"] is not None else 0,
                    )
                )
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
                tarjeta._sincronizar_barra_colapsada()

    def _al_error_segmentos(self, mensaje):
        op = self._segmento_op_actual
        if op is None:
            return
        tipo = op.get("tipo")
        if tipo == "crear":
            registro = op["registro"]
            registro["eliminada"] = False
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._segmentos = [
                    seg
                    for seg in tarjeta._segmentos
                    if seg is not registro
                ]
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
                tarjeta._sincronizar_barra_colapsada()
            self.mensaje_carpeta.setText(
                f"No se pudo guardar el segmento: {mensaje}"
            )
        elif tipo == "eliminar":
            self.mensaje_carpeta.setText(
                f"No se pudo eliminar el segmento: {mensaje}"
            )
            # La eliminación optimista quitó la banda, pero SQLite la conserva:
            # se recarga para reconciliar RAM ↔ SQLite.
            self._encolar_segmento(
                {
                    "tipo": "cargar",
                    "video_id": op["video_id"],
                    "nombre": op["nombre"],
                }
            )
        elif tipo == "color":
            registro = op.get("registro")
            if registro is not None:
                registro["color"] = op.get("color_previo")
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
                tarjeta._sincronizar_barra_colapsada()
            self.mensaje_carpeta.setText(
                f"No se pudo asignar el color del segmento: {mensaje}"
            )
        elif tipo == "cargar":
            self.mensaje_carpeta.setText(
                f"No se pudieron cargar los segmentos: {mensaje}"
            )
            # Permitir reintento en una futura expansión.
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._segmentos_cargados = False
                tarjeta._segmentos_eliminados_carga.clear()
        elif tipo == "actualizar":
            # La edición optimista se revierte al estado previo.
            registro = op["registro"]
            registro["inicio"] = op["previo"]["inicio"]
            registro["fin"] = op["previo"]["fin"]
            tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._segmentos.sort(
                    key=lambda s: (
                        s["inicio"],
                        s["fin"],
                        s["id"] if s["id"] is not None else 0,
                    )
                )
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
                tarjeta._sincronizar_barra_colapsada()
            self.mensaje_carpeta.setText(
                f"No se pudo actualizar el segmento: {mensaje}"
            )

    def _solicitar_carga_segmentos(self, tarjeta):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None or tarjeta._segmentos_cargados:
            return
        tarjeta._segmentos_cargados = True
        self._encolar_segmento(
            {
                "tipo": "cargar",
                "video_id": video_id,
                "nombre": tarjeta.nombre,
                "tarjeta": tarjeta,
            }
        )

    def _al_segmento_creado(self, tarjeta, registro):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        self._encolar_segmento(
            {
                "tipo": "crear",
                "registro": registro,
                "video_id": video_id,
                "inicio": registro["inicio"],
                "fin": registro["fin"],
                "color": registro.get("color"),
                "nombre": tarjeta.nombre,
            }
        )

    def _al_segmento_eliminado(self, tarjeta, registro):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        seg_id = registro.get("id")
        if seg_id is not None:
            self._encolar_segmento(
                {
                    "tipo": "eliminar",
                    "segmento_id": seg_id,
                    "video_id": video_id,
                    "nombre": tarjeta.nombre,
                }
            )
        else:
            registro["eliminada"] = True
            self._cancelar_crear_pendiente_segmento(registro)
            if self._hay_carga_pendiente_segmentos(tarjeta):
                tarjeta._segmentos_eliminados_carga.add(
                    (registro["inicio"], registro["fin"])
                )

    def _al_segmento_color_solicitado(self, tarjeta, registro, clave):
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        seg_id = registro.get("id")
        color_previo = registro.get("color")
        if color_previo == clave:
            return
        if clave in CLAVES_COLOR_CLASIFICACION:
            nuevo_color = clave
        else:
            nuevo_color = None
        registro["color"] = nuevo_color
        tarjeta._franja.set_segmentos(tarjeta._segmentos)
        tarjeta._sincronizar_barra_colapsada()
        try:
            tarjeta._bump_resumen_version()
        except Exception:
            pass
        if seg_id is None:
            return
        self._encolar_segmento(
            {
                "tipo": "color",
                "registro": registro,
                "segmento_id": seg_id,
                "video_id": video_id,
                "color": nuevo_color,
                "color_previo": color_previo,
                "nombre": tarjeta.nombre,
            }
        )

    def _al_segmento_actualizado(self, tarjeta, registro, previo):
        """Persiste una edición de extremos con un único UPDATE por id."""
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            return
        seg_id = registro.get("id")
        if seg_id is None:
            registro["inicio"] = previo["inicio"]
            registro["fin"] = previo["fin"]
            tarjeta._franja.set_segmentos(tarjeta._segmentos)
            return
        self._encolar_segmento(
            {
                "tipo": "actualizar",
                "registro": registro,
                "segmento_id": seg_id,
                "inicio": registro["inicio"],
                "fin": registro["fin"],
                "previo": previo,
                "video_id": video_id,
                "nombre": tarjeta.nombre,
            }
        )

    def _hay_carga_pendiente_segmentos(self, tarjeta):
        op = self._segmento_op_actual
        if (
            op is not None
            and op.get("tipo") == "cargar"
            and op.get("nombre") == tarjeta.nombre
        ):
            return True
        return any(
            op.get("tipo") == "cargar"
            and op.get("nombre") == tarjeta.nombre
            for op in self._cola_segmentos
        )

    def _cancelar_crear_pendiente_segmento(self, registro):
        self._cola_segmentos = [
            op
            for op in self._cola_segmentos
            if not (
                op.get("tipo") == "crear"
                and op.get("registro") is registro
            )
        ]

    def _aplicar_segmentos_cargados(self, op, filas):
        """Reconcilia el snapshot de SQLite con el estado optimista local.

        No reemplaza el snapshot: conserva los segmentos creados localmente
        (id `None`) y no reintroduce los eliminados durante la carga.
        """
        tarjeta = self._tarjeta_por_nombre(op["nombre"])
        if tarjeta is None:
            return
        # Un resultado de carga solo se aplica al card que la solicitó: si el
        # card fue reconstruido mientras la carga estaba en vuelo, se descarta
        # (el card nuevo cargará por sí mismo al expandirse). Los reloads de
        # reconciliación (sin `tarjeta`) se aplican por nombre.
        tarjeta_esperada = op.get("tarjeta")
        if tarjeta_esperada is not None and tarjeta is not tarjeta_esperada:
            return
        if getattr(tarjeta, "_video_id", None) != op["video_id"]:
            return
        tarjeta._segmentos_cargados = True
        tolerancia = tarjeta._tolerancia_marcadores()
        eliminados = tarjeta._segmentos_eliminados_carga
        for seg_id, inicio, fin, color in filas:
            if any(
                abs(inicio - e0) <= tolerancia
                and abs(fin - e1) <= tolerancia
                for e0, e1 in eliminados
            ):
                self._encolar_segmento(
                    {
                        "tipo": "eliminar",
                        "segmento_id": seg_id,
                        "video_id": op["video_id"],
                        "nombre": op["nombre"],
                    }
                )
                continue
            encontrado = None
            for seg in tarjeta._segmentos:
                if seg.get("id") == seg_id:
                    encontrado = seg
                    break
                if (
                    seg.get("id") is None
                    and abs(seg["inicio"] - inicio) <= tolerancia
                    and abs(seg["fin"] - fin) <= tolerancia
                ):
                    encontrado = seg
                    break
            if encontrado is not None:
                if encontrado["id"] is None:
                    encontrado["id"] = seg_id
                    self._cancelar_crear_pendiente_segmento(encontrado)
                continue
            tarjeta._segmentos.append(
                {
                    "id": seg_id,
                    "inicio": float(inicio),
                    "fin": float(fin),
                    "color": color if color in CLAVES_COLOR_CLASIFICACION else None,
                    "eliminada": False,
                }
            )
        tarjeta._segmentos_eliminados_carga.clear()
        tarjeta._segmentos.sort(
            key=lambda s: (
                s["inicio"],
                s["fin"],
                s["id"] if s["id"] is not None else 0,
            )
        )
        tarjeta._franja.set_segmentos(tarjeta._segmentos)
        tarjeta._sincronizar_barra_colapsada()

    def _al_cambiar_modo_seleccion(self, activo):
        self._modo_seleccion = bool(activo)
        for _, tarjeta in self.tarjetas:
            tarjeta.mostrar_check(self._modo_seleccion)

    def _atajo_seleccionar_todo(self):
        if self.busqueda.hasFocus():
            self.busqueda.selectAll()
            return
        self._seleccionar_todo_visible()

    def _seleccionar_todo_visible(self):
        for nombre in self.visibles:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        self._actualizar_resumen_seleccion()

    def _atajo_salir_modo_seleccion(self):
        if self._modo_seleccion:
            self.boton_modo_seleccion.setChecked(False)

    def _atajo_operacion_copiar(self):
        if self.busqueda.hasFocus():
            self.busqueda.copy()
            return
        self._iniciar_copia()

    def _atajo_operacion_pegar(self):
        if self.busqueda.hasFocus():
            self.busqueda.paste()
            return
        self._iniciar_pegar()

    def _atajo_operacion_eliminar(self):
        if self.busqueda.hasFocus():
            self.busqueda.del_()
            return
        self._iniciar_eliminar()

    def _actualizar_boton_copiar(self):
        gestor_op = getattr(self, "gestor_operaciones", None)
        habilitado = (
            bool(self._nombres_seleccionados)
            and (gestor_op is None or not gestor_op.activo)
            and not self.gestor.activo
            and self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        self.boton_copiar.setEnabled(habilitado)

    def _iniciar_copia(self):
        if self.gestor_operaciones.activo or self.gestor.activo:
            return
        seleccion = list(self._nombres_seleccionados)
        if not seleccion:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        destino = QFileDialog.getExistingDirectory(
            self, "Carpeta de destino", ""
        )
        if not destino:
            return
        tarea = TareaCopiarArchivos(carpeta, seleccion, destino)
        if not self.gestor_operaciones.iniciar(tarea):
            return
        self._operacion_archivos = "copiar"
        self._mostrar_progreso("Copiando…")
        self._actualizar_boton_copiar()

    def _al_resultado_copia(self, resumen):
        self._ocultar_progreso()
        copiados = len(resumen.get("copiados", []))
        omitidos = len(resumen.get("omitidos", []))
        errores = len(resumen.get("errores", []))
        self.estado_escaneo.setText(
            f"Copiado: {copiados} — Omitidos: {omitidos} — Errores: {errores}"
        )
        self._portapapeles = list(resumen.get("copiados", []))
        self._actualizar_boton_copiar()
        self._actualizar_boton_pegar()

    def _al_error_copia(self, mensaje):
        self._ocultar_progreso()
        self.estado_escaneo.setText(f"Error al copiar: {mensaje}")
        self._actualizar_boton_copiar()
        self._actualizar_boton_pegar()

    def _al_resultado_operaciones(self, resumen):
        if self._operacion_archivos == "pegar":
            self._al_resultado_pegar(resumen)
        elif self._operacion_archivos == "eliminar":
            self._al_resultado_eliminar(resumen)
        else:
            self._al_resultado_copia(resumen)
        self._operacion_archivos = None

    def _al_error_operaciones(self, mensaje):
        if self._operacion_archivos == "pegar":
            self._al_error_pegar(mensaje)
        elif self._operacion_archivos == "eliminar":
            self._al_error_eliminar(mensaje)
        else:
            self._al_error_copia(mensaje)
        self._operacion_archivos = None

    def _actualizar_boton_pegar(self):
        gestor_op = getattr(self, "gestor_operaciones", None)
        habilitado = (
            bool(self._portapapeles)
            and (gestor_op is None or not gestor_op.activo)
            and not self.gestor.activo
            and self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        self.boton_pegar.setEnabled(habilitado)

    def _iniciar_pegar(self):
        if self.gestor_operaciones.activo or self.gestor.activo:
            return
        if not self._portapapeles:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        colision = any(
            os.path.exists(os.path.join(carpeta, os.path.basename(ruta)))
            for ruta in self._portapapeles
        )
        if colision:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Question)
            caja.setWindowTitle("Pegar")
            caja.setText(
                "Algunos archivos ya existen en la carpeta. "
                "¿Desea omitirlos o cancelar?"
            )
            boton_omitir = caja.addButton("Omitir", QMessageBox.AcceptRole)
            boton_cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
            caja.setDefaultButton(boton_omitir)
            caja.exec()
            if caja.clickedButton() != boton_omitir:
                return
        tarea = TareaPegarArchivos(list(self._portapapeles), carpeta)
        if not self.gestor_operaciones.iniciar(tarea):
            return
        self._operacion_archivos = "pegar"
        self._mostrar_progreso("Pegando…")
        self._actualizar_boton_pegar()

    def _al_resultado_pegar(self, resumen):
        self._ocultar_progreso()
        copiados = resumen.get("copiados", [])
        omitidos = resumen.get("omitidos", [])
        errores = resumen.get("errores", [])
        self.estado_escaneo.setText(
            f"Pegado: {len(copiados)} — Omitidos: {len(omitidos)} — Errores: {len(errores)}"
        )
        if copiados:
            self._procesar_archivos_pegados(
                [os.path.basename(ruta) for ruta in copiados]
            )
        self._actualizar_boton_pegar()

    def _al_error_pegar(self, mensaje):
        self._ocultar_progreso()
        self.estado_escaneo.setText(f"Error al pegar: {mensaje}")
        self._actualizar_boton_pegar()

    def _procesar_archivos_pegados(self, nombres):
        if not nombres or self.gestor.activo:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        self._carpeta_sincronizacion = carpeta
        self._escaneo_pendiente = False
        self._tamanos_pendiente = True
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.registros_guardados = None
        self.resultado_sincronizacion = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.videos_detectados = list(nombres)
        self.tarea_escaneo = TareaEscaneo(carpeta)
        self._iniciar_tamanos()
        self._actualizar_botones_carpeta()

    def _actualizar_boton_eliminar(self):
        gestor_op = getattr(self, "gestor_operaciones", None)
        habilitado = (
            bool(self._nombres_seleccionados)
            and (gestor_op is None or not gestor_op.activo)
            and not self.gestor.activo
            and self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        self.boton_eliminar.setEnabled(habilitado)

    def _iniciar_eliminar(self):
        if self.gestor_operaciones.activo or self.gestor.activo:
            return
        seleccion = list(self._nombres_seleccionados)
        if not seleccion:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        archivos = [os.path.join(carpeta, nombre) for nombre in seleccion]
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Question)
        caja.setWindowTitle("Eliminar")
        caja.setText(
            f"¿Eliminar los {len(archivos)} archivos seleccionados?\n\n"
            "Serán enviados a la Papelera de reciclaje y podrán "
            "restaurarse desde allí."
        )
        boton_eliminar = caja.addButton("Eliminar", QMessageBox.AcceptRole)
        boton_cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.setDefaultButton(boton_cancelar)
        caja.exec()
        if caja.clickedButton() != boton_eliminar:
            return
        tarea = TareaEliminarArchivos(archivos)
        if not self.gestor_operaciones.iniciar(tarea):
            return
        self._operacion_archivos = "eliminar"
        self._mostrar_progreso("Eliminando…")
        self._actualizar_boton_eliminar()

    def _al_resultado_eliminar(self, resumen):
        self._ocultar_progreso()
        eliminados = resumen.get("eliminados", [])
        omitidos = resumen.get("omitidos", [])
        errores = resumen.get("errores", [])
        self.estado_escaneo.setText(
            f"Eliminado: {len(eliminados)} — Omitidos: {len(omitidos)} — Errores: {len(errores)}"
        )
        if eliminados:
            QTimer.singleShot(0, self._procesar_archivos_eliminados)
        self._actualizar_boton_eliminar()

    def _al_error_eliminar(self, mensaje):
        self._ocultar_progreso()
        self.estado_escaneo.setText(f"Error al eliminar: {mensaje}")
        self._actualizar_boton_eliminar()

    def _procesar_archivos_eliminados(self):
        if self.gestor.activo:
            return
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        self._carpeta_sincronizacion = carpeta
        self._escaneo_pendiente = False
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = True
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self.resultado_sincronizacion = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self._iniciar_sincronizacion()
        self._actualizar_botones_carpeta()

    def _actualizar_resumen_seleccion(self):
        visibles = self.visibles
        x = sum(
            1 for nombre in visibles if nombre in self._nombres_seleccionados
        )
        self.resumen_seleccion.setText(
            f"{x} de {len(visibles)} seleccionados"
        )
        self._actualizar_boton_copiar()
        self._actualizar_boton_pegar()
        self._actualizar_boton_eliminar()

    @property
    def nombres_seleccionados(self):
        return set(self._nombres_seleccionados)

    def _recursivo_actual(self):
        return self._modo_alcance in (
            MODO_ALCANCE_SUBCARPETAS,
            MODO_ALCANCE_SELECCION,
        )

    def iniciar_escaneo(self, carpetas=None):
        if self.gestor.activo:
            return
        if carpetas is None or isinstance(carpetas, bool):
            if self._modo_alcance == MODO_ALCANCE_SELECCION:
                carpetas = self.seleccion_carpetas.obtener_seleccion()
            else:
                carpetas = [self.carpeta_seleccionada]
        elif isinstance(carpetas, str):
            carpetas = [carpetas]
        carpetas_validas = [
            c for c in carpetas
            if isinstance(c, str) and os.path.isdir(c)
        ]
        if not carpetas_validas:
            self.mensaje_carpeta.setText(MENSAJE_RUTA_INVALIDA)
            self._actualizar_botones_carpeta()
            return
        carpetas_sin_repetir = list(dict.fromkeys(carpetas_validas))
        carpetas_efectivas = _alcance_efectivo(
            carpetas_sin_repetir,
            self._recursivo_actual(),
        )
        self._cola_carpetas_escaneo = list(carpetas_efectivas[1:])
        self._alcance_sincronizacion = (
            list(carpetas_efectivas)
            if len(carpetas_efectivas) > 1
            else None
        )
        self._iniciar_escaneo_carpeta(carpetas_efectivas[0])

    def _iniciar_escaneo_carpeta(self, carpeta):
        configurar_escaneo_recursivo(self._recursivo_actual())
        tarea = TareaEscaneo(carpeta)
        self._escaneo_pendiente = True
        self._tamanos_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self._carpeta_sincronizacion = carpeta
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
            self._cola_carpetas_escaneo = []
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
        self._carpeta_sincronizacion = None
        self._cola_carpetas_escaneo = []
        self._alcance_sincronizacion = None
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
        if self._lectura_obsoleta():
            return
        self.estado_carga.hide()
        self._total_catalogo = resultado.get("total")
        filas_iniciales = resultado.get("videos", [])
        self._crear_tarjetas(filas_iniciales)
        self._carga_completada = True
        self._encolar_resumen_para_lote(filas_iniciales)
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
        tarea = TareaFFprobe(
            rutas,
            nombres=self.videos_detectados,
            stats=self.resultado_tamanos,
            ruta_db=self._ruta_db,
        )
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
        duraciones = self._duraciones_desde_ffprobe()
        tarea = TareaMiniaturas(
            self.videos_detectados,
            self.tarea_escaneo.carpeta,
            duraciones=duraciones,
        )
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_miniaturas = tarea
        self._mostrar_progreso("Generando miniaturas…")

    def _duraciones_desde_ffprobe(self):
        """Mapa ruta -> duracion a partir del resultado de `TareaFFprobe`."""
        duraciones = {}
        resultado = self.resultado_ffprobe or {}
        for item in resultado.get("resultados", []):
            if not isinstance(item, dict):
                continue
            ruta = item.get("ruta")
            datos = item.get("datos")
            if not (isinstance(ruta, str) and ruta and isinstance(datos, dict)):
                continue
            duracion = datos.get("duracion_segundos")
            if isinstance(duracion, (int, float)) and not isinstance(duracion, bool):
                duraciones[ruta] = duracion
        return duraciones

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
            self._reordenamiento_pendiente = False
            self._iniciar_recarga_catalogo()
            return
        if self._reordenamiento_pendiente:
            self._procesar_reordenamiento()
            return
        if self._cola_carpetas_escaneo:
            siguiente = self._cola_carpetas_escaneo.pop(0)
            self._iniciar_escaneo_carpeta(siguiente)
            return
        self._alcance_sincronizacion = None

    def _iniciar_sincronizacion(self, carpeta=None):
        if carpeta is None and self._carpeta_sincronizacion is not None:
            carpeta = self._carpeta_sincronizacion
        self._carpeta_sincronizacion = None
        if carpeta is None:
            carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        protegidas = None
        if self._alcance_sincronizacion:
            protegidas = [
                c for c in self._alcance_sincronizacion if c != carpeta
            ]
        tarea = TareaSincronizacionCatalogo(
            carpeta, self._ruta_db, carpetas_protegidas=protegidas
        )
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
        carpeta = resultado.get("diferencias", {}).get("carpeta")
        if isinstance(carpeta, str) and carpeta:
            self.carpetas_escaneadas.add(carpeta)
            self.arbol_navegacion.marcar_carpeta_escaneada(carpeta)
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
        self._generacion_tarea_lectura = self._orden_generacion
        self._mostrar_progreso("Actualizando catálogo…")

    def _al_resultado_recarga(self, resultado):
        if self._lectura_obsoleta():
            self._recarga_catalogo_pendiente = False
            self.tarea_recarga_catalogo = None
            return
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        filas_recarga = resultado.get("videos", [])
        self._reemplazar_tarjetas(filas_recarga)
        self.estado_carga.hide()
        self._carga_completada = True
        self._encolar_resumen_para_lote(filas_recarga)
        self._programar_previews()
        self.area.verticalScrollBar().setValue(0)
        self._ocultar_progreso()
        self._actualizar_botones_carpeta()

    def _al_error_recarga(self, mensaje):
        if self._lectura_obsoleta():
            self._recarga_catalogo_pendiente = False
            self.tarea_recarga_catalogo = None
            return
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
        self._actualizar_botones_carpeta()

    def _reemplazar_tarjetas(self, filas):
        self._ocultar_vista()
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
        self._generacion_tarea_lectura = self._orden_generacion
        self._actualizar_botones_carpeta()

    def _al_resultado_pagina(self, resultado):
        if self._lectura_obsoleta():
            self._pagina_pendiente = False
            self.tarea_pagina = None
            return
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        filas = resultado.get("videos", [])
        existentes = {nombre for nombre, _ in self.tarjetas}
        filas_nuevas = [fila for fila in filas if fila[0] not in existentes]
        self._agregar_tarjetas(filas_nuevas)
        self._encolar_resumen_para_lote(filas_nuevas)
        self._programar_previews()
        self._actualizar_botones_carpeta()

    def _al_error_pagina(self, mensaje):
        if self._lectura_obsoleta():
            self._pagina_pendiente = False
            self.tarea_pagina = None
            return
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_PAGINA)
        self._actualizar_botones_carpeta()

    def _programar_previews(self):
        if not self._carga_completada:
            return
        self._timer_previews.start()

    def _iniciar_previews(self):
        if not self._carga_completada:
            return
        nombres = [nombre for nombre, _ in self.tarjetas]
        if not nombres:
            return
        self._encolar_previews(nombres)
        self._al_previews_finalizada()

    def _encolar_previews(self, nombres):
        pendientes = {item[0] for item in self._cola_previews}
        for nombre in nombres:
            if nombre in pendientes:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            if getattr(tarjeta, "_previews_completas", False):
                continue
            carpeta = getattr(tarjeta, "_carpeta_video", None)
            if not (isinstance(carpeta, str) and carpeta):
                continue
            self._cola_previews.append((nombre, carpeta))

    def _al_previews_finalizada(self):
        if self.gestor_previews.estado != Estado.INACTIVO:
            return
        self._siguiente_lote_previews()

    def _siguiente_lote_previews(self):
        if self.gestor_previews.activo:
            return
        carpeta_lote = None
        lote = []
        restantes = []
        for item in self._cola_previews:
            nombre, carpeta = item
            if not (isinstance(carpeta, str) and carpeta):
                continue
            if carpeta_lote is None:
                carpeta_lote = carpeta
            if carpeta == carpeta_lote and len(lote) < TAMANIO_LOTE_PREVIEWS:
                lote.append(nombre)
            else:
                restantes.append(item)
        self._cola_previews = restantes
        if not lote:
            return
        duraciones = {}
        for nombre in lote:
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            duracion = getattr(tarjeta, "_duracion", None)
            if isinstance(duracion, (int, float)) and not isinstance(duracion, bool):
                duraciones[nombre] = duracion
        tarea = TareaPreviewsProgresivas(
            lote, carpeta_lote, duraciones=duraciones
        )
        if not self.gestor_previews.iniciar(tarea):
            self._cola_previews = restantes + [
                (nombre, carpeta_lote) for nombre in lote
            ]
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
            ruta_video = item.get("ruta")
            if not rutas:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            carpeta_esperada = getattr(tarjeta, "_carpeta_video", None)
            if (
                isinstance(carpeta_esperada, str)
                and carpeta_esperada
                and isinstance(ruta_video, str)
                and ruta_video
                and escanear_videos._normalizar_ruta_absoluta(
                    os.path.dirname(ruta_video)
                )
                != escanear_videos._normalizar_ruta_absoluta(
                    carpeta_esperada
                )
            ):
                continue
            tarjeta.actualizar_previews(rutas)

    def actualizar_previews(self, nombre, rutas):
        tarjeta = self._tarjeta_por_nombre(nombre)
        if tarjeta is None:
            return False
        return tarjeta.actualizar_previews(rutas)

    def _agregar_tarjetas(self, filas):
        inicio = len(self.tarjetas)
        for indice, fila in enumerate(filas):
            posicion = inicio + indice
            tarjeta = Tarjeta(fila, ruta_config=self._ruta_config)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            tarjeta.vista_solicitada.connect(self._al_vista_solicitada)
            tarjeta.vista_abandonada.connect(self._al_vista_abandonada)
            tarjeta.seleccion_check.connect(self._al_check_tarjeta)
            tarjeta.expansion_cambiada.connect(self._al_expansion_tarjeta)
            tarjeta.marcador_creado.connect(
                lambda registro, t=tarjeta: self._al_marcador_creado(t, registro)
            )
            tarjeta.marcador_eliminado.connect(
                lambda registro, t=tarjeta: self._al_marcador_eliminado(t, registro)
            )
            tarjeta.marcadores_solicitados.connect(
                lambda t=tarjeta: self._solicitar_carga_marcadores(t)
            )
            tarjeta.segmentos_solicitados.connect(
                lambda t=tarjeta: self._solicitar_carga_segmentos(t)
            )
            tarjeta.segmento_creado.connect(
                lambda registro, t=tarjeta: self._al_segmento_creado(t, registro)
            )
            tarjeta.segmento_eliminado.connect(
                lambda registro, t=tarjeta: self._al_segmento_eliminado(t, registro)
            )
            tarjeta.segmento_actualizado.connect(
                lambda registro, previo, t=tarjeta: self._al_segmento_actualizado(
                    t, registro, previo
                )
            )
            tarjeta.segmento_reproduccion_solicitada.connect(
                lambda segmento, t=tarjeta: self._al_segmento_reproduccion_solicitada(
                    t, segmento
                )
            )
            tarjeta.segmento_bucle_solicitado.connect(
                lambda segmento, t=tarjeta: self._al_segmento_bucle_solicitado(
                    t, segmento
                )
            )
            tarjeta.reproduccion_temporal_solicitada.connect(
                lambda instante, t=tarjeta: self._al_reproduccion_temporal_solicitada(
                    t, instante
                )
            )
            tarjeta.densidad_cambiada.connect(self._al_densidad_cambiada)
            tarjeta.marcador_color_solicitado.connect(
                lambda registro, clave, t=tarjeta: self._al_marcador_color_solicitado(
                    t, registro, clave
                )
            )
            tarjeta.segmento_color_solicitado.connect(
                lambda registro, clave, t=tarjeta: self._al_segmento_color_solicitado(
                    t, registro, clave
                )
            )
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, posicion, 0)
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
        if self._lectura_obsoleta():
            return
        self.estado_carga.setText(MENSAJE_ERROR)
        self._carga_completada = True

    def _al_error_guardado(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_GUARDADO)
        self._actualizar_botones_carpeta()

    def _crear_tarjetas(self, filas):
        for indice, fila in enumerate(filas):
            tarjeta = Tarjeta(fila, ruta_config=self._ruta_config)
            tarjeta.doble_clic.connect(self._abrir_video)
            tarjeta.seleccionada.connect(self._al_seleccionar_tarjeta)
            tarjeta.seleccion_por_rango.connect(self._al_seleccion_por_rango)
            tarjeta.menu_contextual.connect(self._mostrar_menu_contextual)
            tarjeta.vista_solicitada.connect(self._al_vista_solicitada)
            tarjeta.vista_abandonada.connect(self._al_vista_abandonada)
            tarjeta.seleccion_check.connect(self._al_check_tarjeta)
            tarjeta.expansion_cambiada.connect(self._al_expansion_tarjeta)
            tarjeta.marcador_creado.connect(
                lambda registro, t=tarjeta: self._al_marcador_creado(t, registro)
            )
            tarjeta.marcador_eliminado.connect(
                lambda registro, t=tarjeta: self._al_marcador_eliminado(t, registro)
            )
            tarjeta.marcadores_solicitados.connect(
                lambda t=tarjeta: self._solicitar_carga_marcadores(t)
            )
            tarjeta.segmentos_solicitados.connect(
                lambda t=tarjeta: self._solicitar_carga_segmentos(t)
            )
            tarjeta.segmento_creado.connect(
                lambda registro, t=tarjeta: self._al_segmento_creado(t, registro)
            )
            tarjeta.segmento_eliminado.connect(
                lambda registro, t=tarjeta: self._al_segmento_eliminado(t, registro)
            )
            tarjeta.segmento_actualizado.connect(
                lambda registro, previo, t=tarjeta: self._al_segmento_actualizado(
                    t, registro, previo
                )
            )
            tarjeta.segmento_reproduccion_solicitada.connect(
                lambda segmento, t=tarjeta: self._al_segmento_reproduccion_solicitada(
                    t, segmento
                )
            )
            tarjeta.segmento_bucle_solicitado.connect(
                lambda segmento, t=tarjeta: self._al_segmento_bucle_solicitado(
                    t, segmento
                )
            )
            tarjeta.reproduccion_temporal_solicitada.connect(
                lambda instante, t=tarjeta: self._al_reproduccion_temporal_solicitada(
                    t, instante
                )
            )
            tarjeta.densidad_cambiada.connect(self._al_densidad_cambiada)
            tarjeta.marcador_color_solicitado.connect(
                lambda registro, clave, t=tarjeta: self._al_marcador_color_solicitado(
                    t, registro, clave
                )
            )
            tarjeta.segmento_color_solicitado.connect(
                lambda registro, clave, t=tarjeta: self._al_segmento_color_solicitado(
                    t, registro, clave
                )
            )
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice, 0)
        self.filtrar(self.busqueda.text())

    def _abrir_video(self, nombre):
        carpeta = self.carpeta_seleccionada
        try:
            abrir_video_con_aplicacion_predeterminada(nombre, carpeta)
        except (ValueError, FileNotFoundError, OSError):
            self.mensaje_carpeta.setText(MENSAJE_ERROR_ABRIR)
            return
        self.mensaje_carpeta.clear()

    def _al_reproduccion_temporal_solicitada(self, tarjeta, instante):
        """Doble clic sobre la franja temporal: abre VLC desde el instante.

        La UI no construye playlists, no ejecuta subprocess ni accede al
        filesystem: resuelve la ruta con el servicio de rutas y delega la
        reproducción al servicio de playlists VLC.
        """
        ruta = self._ruta_video_de(tarjeta)
        if ruta is None:
            self.mensaje_carpeta.setText(
                "El video ya no está disponible para reproducirse."
            )
            return
        ruta_vlc = localizar_vlc()
        if ruta_vlc is None:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Warning)
            caja.setWindowTitle("Reproducir desde el instante")
            caja.setText("VLC no está instalado o no pudo encontrarse.")
            caja.exec()
            return
        try:
            reproducir_desde_instante(ruta, tarjeta.nombre, instante, ruta_vlc)
        except (TypeError, ValueError, FileNotFoundError, OSError) as exc:
            self.mensaje_carpeta.setText(f"No se pudo reproducir: {exc}")
            return
        self.mensaje_carpeta.clear()

    def _al_segmento_reproduccion_solicitada(self, tarjeta, segmento):
        """Reproduce un segmento A→B en VLC una sola vez (B5.6)."""
        self._reproducir_segmento(tarjeta, segmento, en_bucle=False)

    def _al_segmento_bucle_solicitado(self, tarjeta, segmento):
        """Reproduce un segmento A→B en VLC en bucle continuo (B5.7)."""
        self._reproducir_segmento(tarjeta, segmento, en_bucle=True)

    def _reproducir_segmento(self, tarjeta, segmento, en_bucle):
        """Delega la reproducción A→B al servicio de playlists VLC.

        La UI no construye playlists, no ejecuta subprocess ni accede al
        filesystem: resuelve la ruta con el servicio de rutas y delega al
        servicio VLC (simple o en bucle según `en_bucle`).
        """
        ruta = self._ruta_video_de(tarjeta)
        if ruta is None:
            self.mensaje_carpeta.setText(
                "El video ya no está disponible para reproducirse."
            )
            return
        ruta_vlc = localizar_vlc()
        if ruta_vlc is None:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Warning)
            caja.setWindowTitle("Reproducir segmento")
            caja.setText("VLC no está instalado o no pudo encontrarse.")
            caja.exec()
            return
        try:
            if en_bucle:
                reproducir_segmento_en_bucle(
                    ruta,
                    tarjeta.nombre,
                    segmento["inicio"],
                    segmento["fin"],
                    ruta_vlc,
                )
            else:
                reproducir_segmento(
                    ruta,
                    tarjeta.nombre,
                    segmento["inicio"],
                    segmento["fin"],
                    ruta_vlc,
                )
        except (
            TypeError,
            ValueError,
            FileNotFoundError,
            OSError,
            RuntimeError,
        ) as exc:
            self.mensaje_carpeta.setText(
                f"No se pudo reproducir el segmento: {exc}"
            )
            return
        self.mensaje_carpeta.clear()

    def _mostrar_menu_contextual(self, nombre):
        menu = QMenu(self)
        accion_abrir = menu.addAction("Abrir")
        accion_abrir_carpeta = menu.addAction("Abrir carpeta")
        accion_copiar_ruta = menu.addAction("Copiar ruta")
        accion_copiar_seleccionados = menu.addAction("Copiar rutas de los seleccionados")
        accion_abrir_seleccionados = menu.addAction("Abrir carpetas de los seleccionados")
        accion_reproducir_marcadores = menu.addAction(
            "Reproducir marcadores en VLC"
        )
        accion_reproducir_segmentos = menu.addAction(
            "Reproducir segmentos en VLC"
        )
        accion_abrir.triggered.connect(lambda: self._abrir_video(nombre))
        accion_abrir_carpeta.triggered.connect(lambda: self._abrir_carpeta(nombre))
        accion_copiar_ruta.triggered.connect(lambda: self._copiar_ruta(nombre))
        accion_copiar_seleccionados.triggered.connect(self._copiar_rutas_seleccionados)
        accion_abrir_seleccionados.triggered.connect(self._abrir_carpetas_seleccionados)
        accion_reproducir_marcadores.setEnabled(bool(self._nombres_seleccionados))
        accion_reproducir_marcadores.triggered.connect(
            self._reproducir_marcadores_en_vlc
        )
        accion_reproducir_segmentos.setEnabled(bool(self._nombres_seleccionados))
        accion_reproducir_segmentos.triggered.connect(
            self._reproducir_segmentos_en_vlc
        )
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

    def _abrir_carpetas_seleccionados(self):
        carpeta = self.carpeta_seleccionada
        if not carpeta or not os.path.isdir(carpeta):
            return
        carpetas = []
        for nombre in self.tarjetas_visibles():
            if nombre in self._nombres_seleccionados:
                ruta = os.path.abspath(os.path.join(carpeta, nombre))
                carpetas.append(os.path.dirname(ruta))
        for c in dict.fromkeys(carpetas):
            os.startfile(c)

    def _reproducir_marcadores_en_vlc(self):
        seleccionados = self._seleccionados_para_reproduccion()
        if not seleccionados:
            return
        video_ids = [
            s["video_id"] for s in seleccionados if s["video_id"] is not None
        ]
        if not video_ids:
            self._procesar_reproduccion(seleccionados, {})
            return
        self._reproduccion_pendiente = seleccionados
        self._reproduccion_modo = "marcadores"
        tarea = TareaListarMarcadoresVarios(video_ids, self._ruta_db)
        if not self.gestor_reproduccion.iniciar(tarea):
            self._reproduccion_pendiente = None
            self._reproduccion_modo = None

    def _reproducir_segmentos_en_vlc(self):
        """Secuencia automática de todos los segmentos de los videos
        seleccionados (B5.8), conceptualmente paralela a la reproducción de
        marcadores pero con auto-avance entre segmentos.
        """
        seleccionados = self._seleccionados_para_reproduccion()
        if not seleccionados:
            return
        video_ids = [
            s["video_id"] for s in seleccionados if s["video_id"] is not None
        ]
        if not video_ids:
            self._procesar_secuencia_segmentos(seleccionados, [])
            return
        self._reproduccion_pendiente = seleccionados
        self._reproduccion_modo = "segmentos"
        tarea = TareaListarSegmentosVarios(video_ids, self._ruta_db)
        if not self.gestor_reproduccion.iniciar(tarea):
            self._reproduccion_pendiente = None
            self._reproduccion_modo = None

    def _seleccionados_para_reproduccion(self):
        seleccionados = []
        for nombre in self.tarjetas_visibles():
            if nombre not in self._nombres_seleccionados:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            seleccionados.append(
                {
                    "nombre": nombre,
                    "video_id": getattr(tarjeta, "_video_id", None),
                    "ruta": self._ruta_video_de(tarjeta),
                }
            )
        return seleccionados

    def _al_resultado_reproduccion(self, filas):
        seleccionados = self._reproduccion_pendiente
        modo = self._reproduccion_modo
        self._reproduccion_pendiente = None
        self._reproduccion_modo = None
        if not seleccionados:
            return
        if modo == "segmentos":
            self._procesar_secuencia_segmentos(seleccionados, filas)
            return
        marcadores_por_video = {}
        for _marcador_id, video_id, tiempo, _color in filas:
            marcadores_por_video.setdefault(video_id, []).append(tiempo)
        self._procesar_reproduccion(seleccionados, marcadores_por_video)

    def _al_error_reproduccion(self, mensaje):
        modo = self._reproduccion_modo
        self._reproduccion_pendiente = None
        self._reproduccion_modo = None
        if modo == "segmentos":
            self.mensaje_carpeta.setText(
                f"No se pudieron cargar los segmentos: {mensaje}"
            )
            return
        self.mensaje_carpeta.setText(
            f"No se pudieron cargar los marcadores: {mensaje}"
        )

    def _procesar_secuencia_segmentos(self, seleccionados, filas):
        """Construye la secuencia de segmentos y la reproduce en VLC.

        Orden: videos seleccionados (mismo criterio visible que marcadores) y,
        dentro de cada video, por `inicio, fin, id`. Los segmentos provienen
        del repositorio (una sola consulta), por lo que también participan
        videos nunca expandidos. Videos sin segmentos o con archivo inexistente
        se omiten silenciosamente; si no queda ningún segmento reproducible, no
        se abre VLC.
        """
        segmentos_por_video = {}
        for _seg_id, video_id, inicio, fin, _color in filas:
            segmentos_por_video.setdefault(video_id, []).append(
                (inicio, fin)
            )
        secuencia = []
        sin_archivo = 0
        for sel in seleccionados:
            video_id = sel["video_id"]
            segmentos = segmentos_por_video.get(video_id, [])
            if not segmentos:
                continue
            if not sel["ruta"]:
                sin_archivo += 1
                continue
            for inicio, fin in sorted(segmentos):
                secuencia.append(
                    {
                        "ruta": sel["ruta"],
                        "nombre": sel["nombre"],
                        "inicio": inicio,
                        "fin": fin,
                    }
                )
        if not secuencia:
            self.mensaje_carpeta.setText(
                "Los videos seleccionados no tienen segmentos para reproducir."
            )
            return
        ruta_vlc = localizar_vlc()
        if ruta_vlc is None:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Warning)
            caja.setWindowTitle("Reproducir segmentos en VLC")
            caja.setText("VLC no está instalado o no pudo encontrarse.")
            caja.exec()
            return
        try:
            reproducir_secuencia_segmentos(secuencia, ruta_vlc)
        except (
            TypeError,
            ValueError,
            FileNotFoundError,
            OSError,
            RuntimeError,
        ) as exc:
            self.mensaje_carpeta.setText(
                f"No se pudo reproducir la secuencia: {exc}"
            )
            return
        if sin_archivo:
            self.mensaje_carpeta.setText(
                "Algunos videos ya no están disponibles y sus segmentos "
                "fueron omitidos."
            )
        else:
            self.mensaje_carpeta.clear()

    def _procesar_reproduccion(self, seleccionados, marcadores_por_video):
        faltantes = [s for s in seleccionados if not s["ruta"]]
        disponibles = [s for s in seleccionados if s["ruta"]]
        if faltantes:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Information)
            caja.setWindowTitle("Reproducir marcadores en VLC")
            caja.setText(
                "Algunos archivos seleccionados ya no están disponibles "
                "y serán omitidos de la reproducción."
            )
            caja.exec()
        if not disponibles:
            self.mensaje_carpeta.setText(
                "No hay archivos disponibles para reproducir"
            )
            return
        sin_marcadores = [
            s
            for s in disponibles
            if not marcadores_por_video.get(s["video_id"])
        ]
        incluir_inicio = False
        if sin_marcadores:
            decision = self._preguntar_videos_sin_marcadores(len(sin_marcadores))
            if decision == "omitir":
                disponibles = [s for s in disponibles if s not in sin_marcadores]
            elif decision == "inicio":
                incluir_inicio = True
            else:
                return
        entradas = []
        for video in disponibles:
            tiempos = list(marcadores_por_video.get(video["video_id"], []))
            if not tiempos and incluir_inicio:
                tiempos = [0.0]
            for tiempo in tiempos:
                entradas.append(
                    {
                        "ruta": video["ruta"],
                        "nombre": video["nombre"],
                        "tiempo": tiempo,
                    }
                )
        if not entradas:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Information)
            caja.setWindowTitle("Reproducir marcadores en VLC")
            caja.setText("No hay marcadores para reproducir.")
            caja.exec()
            return
        self._generar_y_abrir_playlist(entradas)

    def _preguntar_videos_sin_marcadores(self, cantidad):
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Question)
        caja.setWindowTitle("Reproducir marcadores en VLC")
        palabra = "video" if cantidad == 1 else "videos"
        caja.setText(
            f"{cantidad} {palabra} seleccionado(s) no tiene(n) marcadores. "
            "¿Qué desea hacer?"
        )
        boton_omitir = caja.addButton(
            "Omitir videos sin marcadores", QMessageBox.AcceptRole
        )
        boton_inicio = caja.addButton(
            "Reproducir desde el inicio", QMessageBox.ActionRole
        )
        boton_cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.setDefaultButton(boton_omitir)
        caja.exec()
        if caja.clickedButton() == boton_omitir:
            return "omitir"
        if caja.clickedButton() == boton_inicio:
            return "inicio"
        return "cancelar"

    def _generar_y_abrir_playlist(self, entradas):
        ruta_vlc = localizar_vlc()
        if ruta_vlc is None:
            caja = QMessageBox(self)
            caja.setIcon(QMessageBox.Warning)
            caja.setWindowTitle("Reproducir marcadores en VLC")
            caja.setText("VLC no está instalado o no pudo encontrarse.")
            caja.exec()
            return
        archivo_temporal = None
        try:
            archivo_temporal = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".m3u",
                prefix="visor_marcadores_",
                delete=False,
                encoding="utf-8",
            )
            ruta_m3u = archivo_temporal.name
            archivo_temporal.close()
            generar_m3u(entradas, ruta_m3u)
        except OSError:
            if archivo_temporal is not None:
                try:
                    os.remove(archivo_temporal.name)
                except OSError:
                    pass
            self.mensaje_carpeta.setText(
                "No se pudo crear la playlist temporal"
            )
            return
        try:
            abrir_playlist_en_vlc(ruta_m3u, ruta_vlc)
        except OSError:
            self.mensaje_carpeta.setText("No se pudo abrir VLC")
            try:
                os.remove(ruta_m3u)
            except OSError:
                pass

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
        self._actualizar_resumen_seleccion()

    def tarjetas_visibles(self):
        return list(self.visibles)

    def actualizar_contador(self):
        cantidad = len(self.tarjetas_visibles())
        palabra = "video" if cantidad == 1 else "videos"
        self.contador.setText(f"{cantidad} {palabra}")

    # === B6.4 Resumen colapsado batch ===
    def _tarjeta_por_video_id(self, video_id):
        for _nombre, tarjeta in self.tarjetas:
            if getattr(tarjeta, "_video_id", None) == video_id:
                return tarjeta
        return None

    def _encolar_resumen_para_lote(self, filas):
        """Encola un lote batch para las filas recién incorporadas (B6.4).

        `filas` son las filas de `listar_videos_paginado` (nombre, duracion, ... , id).
        Solo metadata mínima, sin pixmaps, en un único worker.
        """
        if not filas:
            return
        video_ids = []
        for fila in filas:
            try:
                vid = fila[8]
            except IndexError:
                continue
            if not isinstance(vid, int) or isinstance(vid, bool):
                continue
            if vid in self._resumen_ids_en_vuelo:
                continue
            tarjeta = self._tarjeta_por_video_id(vid)
            if tarjeta is None:
                continue
            if getattr(tarjeta, "_resumen_cargado", False):
                continue
            video_ids.append(vid)
        if not video_ids:
            return
        # deduplicar preservando orden
        video_ids = list(dict.fromkeys(video_ids))
        for vid in video_ids:
            self._resumen_ids_en_vuelo.add(vid)
        self._cola_resumen.append(video_ids)
        self._procesar_siguiente_resumen()

    def _procesar_siguiente_resumen(self):
        if self.gestor_resumen.activo:
            return
        if not self._cola_resumen:
            return
        video_ids = self._cola_resumen.pop(0)
        # filtrar ids cuyas tarjetas ya no existen (orden/recarga) o ya cargadas
        vigentes = []
        versiones = {}
        for vid in video_ids:
            tarjeta = self._tarjeta_por_video_id(vid)
            if tarjeta is None:
                self._resumen_ids_en_vuelo.discard(vid)
                continue
            if getattr(tarjeta, "_resumen_cargado", False):
                self._resumen_ids_en_vuelo.discard(vid)
                continue
            vigentes.append(vid)
            versiones[vid] = int(getattr(tarjeta, "_resumen_version", 0))
        if not vigentes:
            # intentar siguiente lote
            self._procesar_siguiente_resumen()
            return
        tarea = TareaResumenColapsado(vigentes, self._ruta_db)
        self._resumen_op_actual = {"video_ids": vigentes, "versiones": versiones}
        if not self.gestor_resumen.iniciar(tarea):
            # reencolar al frente
            self._cola_resumen.insert(0, vigentes)
            self._resumen_op_actual = None

    def _al_resumen_finalizada(self):
        self._resumen_op_actual = None
        self._procesar_siguiente_resumen()

    def _al_error_resumen(self, mensaje):
        op = self._resumen_op_actual
        if op is not None:
            for vid in op.get("video_ids", []):
                self._resumen_ids_en_vuelo.discard(vid)
        self._resumen_op_actual = None
        self._procesar_siguiente_resumen()

    def _al_resultado_resumen(self, resultado):
        op = self._resumen_op_actual
        if op is None:
            return
        video_ids = op.get("video_ids", [])
        versiones = op.get("versiones", {})
        # agrupar por video_id
        marcadores = resultado.get("marcadores", []) or []
        segmentos = resultado.get("segmentos", []) or []
        marcadores_por_vid = {}
        for mid, vid, tiempo, color in marcadores:
            marcadores_por_vid.setdefault(vid, []).append((mid, vid, tiempo, color))
        segmentos_por_vid = {}
        for sid, vid, inicio, fin, color in segmentos:
            segmentos_por_vid.setdefault(vid, []).append((sid, inicio, fin, color))
        for vid in video_ids:
            tarjeta = self._tarjeta_por_video_id(vid)
            if tarjeta is None:
                self._resumen_ids_en_vuelo.discard(vid)
                continue
            # carrera: si versión cambió después del dispatch, no pisar color/mutación local
            version_despachada = versiones.get(vid, 0)
            version_actual = int(getattr(tarjeta, "_resumen_version", 0))
            es_obsoleta = version_actual != version_despachada
            filas_m = marcadores_por_vid.get(vid, [])
            filas_s = segmentos_por_vid.get(vid, [])
            self._aplicar_resumen_marcadores(tarjeta, filas_m, es_obsoleta)
            self._aplicar_resumen_segmentos(tarjeta, filas_s, es_obsoleta)
            tarjeta._resumen_cargado = True
            self._resumen_ids_en_vuelo.discard(vid)
            # sincronizar barra (datos mínimos, sin pixmaps)
            try:
                tarjeta._sincronizar_barra_colapsada()
                # también mantener franja coherente sin crear widgets pesados
                tarjeta._franja.set_marcadores(*tarjeta._tiempos_y_colores_marcadores())
                tarjeta._franja.set_segmentos(tarjeta._segmentos)
            except Exception:
                pass
        # no limpiar op aquí, lo hace _al_resumen_finalizada

    def _aplicar_resumen_marcadores(self, tarjeta, filas, es_obsoleta):
        """Merge de marcadores batch sin pisar mutaciones locales más nuevas (B6.4).

        Nunca carga pixmaps ni crea `MiniaturaMarcador`; los marcadores batch
        quedan con `pixmap=None, etiqueta=None`. Si `es_obsoleta`, preserva
        el color local de marcadores ya existentes con mismo id.
        """
        if not filas:
            return
        tolerancia = tarjeta._tolerancia_marcadores()
        # mapa id -> marcador local
        por_id = {m.get("id"): m for m in tarjeta._marcadores if m.get("id") is not None}
        for marcador_id, video_de_fila, tiempo, color in filas:
            # respetar eliminados pendientes de la carga por expansión
            if any(abs(tiempo - t) <= tolerancia for t in getattr(tarjeta, "_marcadores_eliminados_carga", set())):
                continue
            if marcador_id in por_id:
                # ya existe con ese id: en caso obsoleto, no sobrescribir color local
                if es_obsoleta:
                    continue
                # no obsoleta: actualizar color si difiere (preserva NULL)
                existente = por_id[marcador_id]
                if color in CLAVES_COLOR_CLASIFICACION or color is None:
                    if existente.get("color") != (color if color in CLAVES_COLOR_CLASIFICACION else None):
                        existente["color"] = color if color in CLAVES_COLOR_CLASIFICACION else None
                continue
            # buscar duplicado por proximidad temporal con pendiente id None
            duplicado = None
            for m in tarjeta._marcadores:
                if m.get("id") is None and abs(m["tiempo"] - tiempo) <= tolerancia:
                    duplicado = m
                    break
            if duplicado is not None:
                duplicado["id"] = marcador_id
                # si es obsoleta, mantener color local
                if not es_obsoleta:
                    duplicado["color"] = color if color in CLAVES_COLOR_CLASIFICACION else None
                # cancelar crear pendiente si existía en cola
                try:
                    self._cancelar_crear_pendiente(duplicado)
                except Exception:
                    pass
                continue
            # nuevo marcador persistido nunca visto: añadir sin pixmap
            tarjeta._marcadores.append({
                "id": marcador_id,
                "tiempo": float(tiempo),
                "pixmap": None,
                "etiqueta": None,
                "color": color if color in CLAVES_COLOR_CLASIFICACION else None,
                "eliminada": False,
            })
        tarjeta._marcadores.sort(key=lambda m: m["tiempo"])
        # no _renderizar_marcadores aquí (evita pixmaps); solo franja datos

    def _aplicar_resumen_segmentos(self, tarjeta, filas, es_obsoleta):
        """Merge de segmentos batch sin pisar mutaciones locales más nuevas (B6.4)."""
        if not filas:
            return
        tolerancia = tarjeta._tolerancia_marcadores()
        por_id = {s.get("id"): s for s in tarjeta._segmentos if s.get("id") is not None}
        for seg_id, inicio, fin, color in filas:
            if any(abs(inicio - e0) <= tolerancia and abs(fin - e1) <= tolerancia for e0, e1 in getattr(tarjeta, "_segmentos_eliminados_carga", set())):
                continue
            if seg_id in por_id:
                if es_obsoleta:
                    continue
                existente = por_id[seg_id]
                if color in CLAVES_COLOR_CLASIFICACION or color is None:
                    if existente.get("color") != (color if color in CLAVES_COLOR_CLASIFICACION else None):
                        existente["color"] = color if color in CLAVES_COLOR_CLASIFICACION else None
                continue
            duplicado = None
            for s in tarjeta._segmentos:
                if s.get("id") is None and abs(s["inicio"] - inicio) <= tolerancia and abs(s["fin"] - fin) <= tolerancia:
                    duplicado = s
                    break
            if duplicado is not None:
                duplicado["id"] = seg_id
                if not es_obsoleta:
                    duplicado["color"] = color if color in CLAVES_COLOR_CLASIFICACION else None
                try:
                    self._cancelar_crear_pendiente_segmento(duplicado)
                except Exception:
                    pass
                continue
            tarjeta._segmentos.append({
                "id": seg_id,
                "inicio": float(inicio),
                "fin": float(fin),
                "color": color if color in CLAVES_COLOR_CLASIFICACION else None,
                "eliminada": False,
            })
        tarjeta._segmentos.sort(key=lambda s: (s["inicio"], s["fin"], s["id"] if s["id"] is not None else 0))

    def closeEvent(self, event):
        self._timer_previews.stop()
        self._ocultar_vista()
        self.gestor.cerrar()
        if self.gestor_previews is not None:
            self.gestor_previews.cerrar()
        if self.gestor_operaciones is not None:
            self.gestor_operaciones.cerrar()
        if self.gestor_marcadores is not None:
            self.gestor_marcadores.cerrar()
        if self.gestor_segmentos is not None:
            self.gestor_segmentos.cerrar()
        if self.gestor_reproduccion is not None:
            self.gestor_reproduccion.cerrar()
        if getattr(self, "gestor_resumen", None) is not None:
            self.gestor_resumen.cerrar()
        if getattr(self, "gestor_exploracion", None) is not None:
            self.gestor_exploracion.cerrar()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(900, 600)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
