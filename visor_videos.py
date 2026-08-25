import math
import escanear_videos
import exploracion_cache
import nombres
import operaciones
import os
import sys
import tempfile

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDrag,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QRadioButton,
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
    FILTRO_MARCADOR_SIN_CLASIFICAR,
    FILTRO_SEGMENTO_SIN_CLASIFICAR,
    _nombre_seguro,
    actualizar_cantidad_miniaturas_batch,
    calcular_tiempo_preview,
    color_rgb,
    configurar_cantidad_previews,
    configurar_escaneo_recursivo,
    ruta_miniatura_id,
    ruta_preview_id,
)
from rutas import (
    carpeta_padre,
    carpetas_iguales,
    normalizar_ruta_clave,
    resolver_destino_drop,
    ruta_carpeta_miniaturas,
    ruta_configuracion,
    ruta_video_existente,
    validar_destino_drop_completo,
)
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
from panel_organizacion import (
    MIME_VIDEOS_IDS,
    PanelOrganizacion,
    _serializar_ids_videos_para_mime,
)
from tareas_videos import (
    TareaActualizarCantidadMiniaturas,
    TareaActualizarSegmento,
    TareaAsignarColorMarcador,
    TareaAsignarColorSegmento,
    TareaCopiarVideo,
    TareaCrearCarpeta,
    TareaEliminarVideo,
    TareaEscaneo,
    TareaExportarSecuencia,
    TareaExportarSegmento,
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
    TareaLoteOperaciones,
    TareaMigrarCacheLegacy,
    TareaMiniaturas,
    TareaMiniaturasPorId,
    TareaMoverVideo,
    TareaPrevalidarDrop,
    TareaPreviewsPorId,
    TareaPreviewsProgresivas,
    TareaRenombrarMasivo,
    TareaRenombrarVideo,
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
    previews_existentes_por_id,
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
# B9.3 — tira virtualizada: autoridad única Densidad, Vista solo define cómo se muestran
TIRA_B93_ALTURA_EXTRA = 18
TIRA_B93_SPACING = 2
TIRA_B93_MARGIN = 2
MODO_TIRA_DINAMICA = "dinamica"
MODO_TIRA = "tira"

def _densidad_cantidad_objetivo(duracion, densidad_manual):
    """Cantidad objetivo vigente según Densidad (Auto->objetivo_total_densidad, int->manual)."""
    if isinstance(densidad_manual, int) and not isinstance(densidad_manual, bool) and densidad_manual > 0:
        return densidad_manual
    return exploracion_cache.objetivo_total_densidad(duracion)

def _tiempos_densidad_actual(duracion, densidad_manual):
    """Tiempos ms del conjunto densidad vigente (orden progresivo bisección)."""
    cant = _densidad_cantidad_objetivo(duracion, densidad_manual)
    if cant <= 0:
        return []
    return tiempos_objetivo(duracion, cant)

def _ms_tira_densidad_ordenada(duracion, densidad_manual):
    """Tiempos ms ordenados cronológicamente para tira virtual (autoridad densidad)."""
    t = _tiempos_densidad_actual(duracion, densidad_manual)
    return sorted(t)
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

# ── B7.13B — helper origen drag (reutiliza contrato MIME B7.13A sin duplicar) ──
def _crear_mime_data_drag_b713b(ids):
    """Construye QMimeData con MIME_VIDEOS_IDS para origen drag B7.13B.

    Usa exactamente la serialización B7.13A. Retorna QMimeData real o None si
    ids inválidos. No agrega URLs/texto genérico. Sin FS/SQLite/FFmpeg.
    """
    try:
        payload = _serializar_ids_videos_para_mime(ids)
        if payload is None:
            return None
        mime = QMimeData()
        mime.setData(MIME_VIDEOS_IDS, QByteArray(payload))
        return mime
    except (TypeError, ValueError, RuntimeError) as exc:
        print(f"[B7.13B] _crear_mime_data_drag_b713b error: {exc}")
        return None


def crear_mime_data_drag(ids):
    """Alias público para pruebas B7.13B (reutiliza mismo helper)."""
    return _crear_mime_data_drag_b713b(ids)


# ── B8.3B — helper identidad estricta por video_id (única autoridad) ──
def _es_video_id_valido(vid):
    """Retorna True solo si vid es int positivo no-bool (ID válido B8.3B)."""
    return isinstance(vid, int) and not isinstance(vid, bool) and vid > 0


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
    """Legacy B8.1: por nombre (conservado solo para migración, no usar en flujo normal)."""
    prefijo = _nombre_seguro(os.path.splitext(nombre)[0])
    carpeta = ruta_carpeta_miniaturas()
    if os.path.isdir(carpeta):
        for archivo in sorted(os.listdir(carpeta)):
            base = os.path.splitext(archivo)[0]
            if not base.startswith(prefijo + "_"):
                continue
            if _es_archivo_preview(archivo, nombre):
                continue
            suffix = base[len(prefijo):]
            if not suffix.startswith("_"):
                continue
            if not suffix[1:].isdigit():
                continue
            ruta = os.path.join(carpeta, archivo)
            return ruta
    return None

def miniatura_principal_por_id(video_id):
    """B8.2: ruta determinista por video_id sin I/O pesado en UI.

    Devuelve la ruta canónica v<id>_01.jpg sin recorrer filesystem ni copiar.
    La migración legacy y la verificación de vigencia ocurren en backend/tareas.
    La UI solo intenta cargar el QPixmap; si no existe se muestra 'Sin miniatura'.
    """
    if not isinstance(video_id, int) or isinstance(video_id, bool) or video_id <= 0:
        return None
    try:
        return ruta_miniatura_id(video_id, 1)
    except (ValueError, TypeError):
        return None

def previews_de(nombre):
    return previews_existentes(nombre)

def previews_de_por_id(video_id):
    return previews_existentes_por_id(video_id)


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


class PreviewTiraTemporal(QWidget):
    """B9.3 — widget ligero para tira: una sola QPixmap fuente, escalado en paintEvent.

    No retiene pixmap_escalado duplicado ni en widget ni en tira_cache.
    Reajuste de tamaño sin I/O/FFmpeg: repintado con mismo pixmap fuente.
    B9.3/029 — integración mínima marcadores/segmentos: estado ligero de binding
    y decoraciones sin widgets extra; emite señales con _logical_ms actual.
    """

    tira_left_clicked = Signal(int)
    tira_right_clicked = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._tiempo = None
        self._logical_ms = None
        self._marcadores_tira = []
        self._segmentos_tira = []
        self._pendiente_tira = False
        self._tira_right_guard_ms = None
        self._tira_right_guard_time = 0.0
        self.setFixedHeight(dimensiones_miniatura()[1])

    def set_preview(self, pixmap, tiempo=None):
        if pixmap is None or pixmap.isNull():
            return False
        self._pixmap = _pixmap_acotado(pixmap)
        self._tiempo = tiempo
        self.setFixedHeight(dimensiones_miniatura()[1])
        self.update()
        return True

    def reajustar(self):
        self.setFixedHeight(dimensiones_miniatura()[1])
        self.update()
        return True

    def bind_tira(self, logical_ms, marcadores=None, segmentos=None, pendiente=False):
        """B9.3/029 — binding ligero; limpia estado anterior siempre."""
        try:
            self._logical_ms = int(logical_ms) if isinstance(logical_ms, int) and not isinstance(logical_ms, bool) else None
        except Exception:
            self._logical_ms = None
        try:
            self._marcadores_tira = list(marcadores) if isinstance(marcadores, (list, tuple)) else []
        except Exception:
            self._marcadores_tira = []
        try:
            self._segmentos_tira = list(segmentos) if isinstance(segmentos, (list, tuple)) else []
        except Exception:
            self._segmentos_tira = []
        self._pendiente_tira = bool(pendiente)
        self.update()

    def set_pendiente_tira(self, pendiente):
        val = bool(pendiente)
        if getattr(self, "_pendiente_tira", False) != val:
            self._pendiente_tira = val
            self.update()

    def clear_tira(self):
        self._logical_ms = None
        self._marcadores_tira = []
        self._segmentos_tira = []
        self._pendiente_tira = False
        self._pixmap = None
        self._tiempo = None
        self.update()

    def _color_marcador_tira(self, marcador):
        try:
            clave = marcador.get("color") if isinstance(marcador, dict) else None
            rgb = color_rgb(clave)
            if rgb is not None:
                return QColor(rgb[0], rgb[1], rgb[2])
        except Exception:
            pass
        return QColor(158, 158, 158)

    def _color_segmento_tira(self, segmento):
        try:
            clave = segmento.get("color") if isinstance(segmento, dict) else None
            rgb = color_rgb(clave)
            if rgb is not None:
                return QColor(rgb[0], rgb[1], rgb[2])
        except Exception:
            pass
        return QColor(158, 158, 158)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton and self._logical_ms is not None:
                self.tira_left_clicked.emit(int(self._logical_ms))
                event.accept()
                return
            if event.button() == Qt.RightButton and self._logical_ms is not None:
                try:
                    gp = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                except Exception:
                    gp = QCursor.pos()
                self.tira_right_clicked.emit(int(self._logical_ms), gp)
                try:
                    import time as _t
                    self._tira_right_guard_ms = int(self._logical_ms)
                    self._tira_right_guard_time = _t.monotonic()
                except Exception:
                    pass
                event.accept()
                return
        except Exception:
            pass
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        try:
            if self._logical_ms is not None:
                # guardia robusta: si mousePress ya emitio para este ms hace <0.6s, no duplicar
                try:
                    import time as _t
                    if self._tira_right_guard_ms is not None and int(self._logical_ms) == self._tira_right_guard_ms and (_t.monotonic() - self._tira_right_guard_time) < 0.6:
                        event.accept()
                        return
                except Exception:
                    pass
                try:
                    gp = event.globalPos() if hasattr(event, "globalPos") else QCursor.pos()
                except Exception:
                    gp = QCursor.pos()
                self.tira_right_clicked.emit(int(self._logical_ms), gp)
                event.accept()
                return
        except Exception:
            pass
        super().contextMenuEvent(event)

    def paintEvent(self, event):
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor("#f0f0f0"))
        pintor.setPen(QColor("#cccccc"))
        pintor.setBrush(Qt.NoBrush)
        pintor.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._pixmap is None or self._pixmap.isNull():
            # pintar decoraciones incluso sin pixmap? mantener borde base pero intentar decorar
            # no pixmap aun: aun mostrar decoración si hay marcador/segmento asociado
            if self._marcadores_tira:
                try:
                    c = self._color_marcador_tira(self._marcadores_tira[0])
                    pintor.setPen(Qt.NoPen)
                    pintor.setBrush(c)
                    pintor.drawRect(2, 2, self.width() - 4, 4)
                except Exception:
                    pass
            if self._segmentos_tira:
                try:
                    c2 = self._color_segmento_tira(self._segmentos_tira[0])
                    pintor.setPen(Qt.NoPen)
                    pintor.setBrush(c2)
                    pintor.drawRect(2, self.height() - 6, self.width() - 4, 4)
                except Exception:
                    pass
            if getattr(self, "_pendiente_tira", False):
                try:
                    # pendiente: borde 3px teal sin tapar marker/segment ni timestamp; badge A debajo de marcador (y=7) geometría mínima
                    col_pend = QColor(0, 150, 136)
                    pintor.setPen(QPen(col_pend, 3))
                    pintor.setBrush(Qt.NoBrush)
                    pintor.drawRect(self.rect().adjusted(2, 2, -3, -3))
                    pintor.setPen(Qt.NoPen)
                    pintor.setBrush(col_pend)
                    pintor.drawEllipse(4, 7, 14, 14)
                    pintor.setPen(QColor(255, 255, 255))
                    # centrar "A" usando fuente pequeña
                    try:
                        fm = pintor.fontMetrics()
                        txt = "A"
                        tw = fm.horizontalAdvance(txt)
                        th = fm.ascent()
                        pintor.drawText(4 + (14 - tw)//2, 7 + (14 + th)//2 - 2, txt)
                    except Exception:
                        pintor.drawText(8, 17, "A")
                except Exception:
                    pass
            pintor.end()
            return
        ancho, alto = dimensiones_miniatura()
        escalada = self._pixmap.scaled(ancho, alto, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - escalada.width()) // 2
        y = (self.height() - escalada.height()) // 2
        pintor.drawPixmap(x, y, escalada)
        # decoración marcadores: borde superior 4px con color real
        if self._marcadores_tira:
            try:
                c = self._color_marcador_tira(self._marcadores_tira[0])
                pintor.setPen(Qt.NoPen)
                pintor.setBrush(c)
                pintor.drawRect(1, 1, self.width() - 2, 4)
                # pequeña marca esquina si múltiples
                if len(self._marcadores_tira) > 1:
                    pintor.setBrush(QColor(255, 255, 255))
                    pintor.drawEllipse(self.width() - 10, 3, 6, 6)
            except Exception:
                pass
        # decoración segmentos: banda inferior 5px con color real
        if self._segmentos_tira:
            try:
                c2 = self._color_segmento_tira(self._segmentos_tira[0])
                pintor.setPen(Qt.NoPen)
                pintor.setBrush(c2)
                pintor.drawRect(1, self.height() - 6, self.width() - 2, 5)
                if len(self._segmentos_tira) > 1:
                    pintor.setBrush(QColor(255, 255, 255, 180))
                    pintor.drawEllipse(3, self.height() - 9, 6, 6)
            except Exception:
                pass
        if getattr(self, "_pendiente_tira", False):
            try:
                col_pend = QColor(0, 150, 136)
                pintor.setPen(QPen(col_pend, 3))
                pintor.setBrush(Qt.NoBrush)
                pintor.drawRect(self.rect().adjusted(1, 1, -2, -2))
                pintor.setPen(Qt.NoPen)
                pintor.setBrush(col_pend)
                pintor.drawEllipse(4, 7, 14, 14)
                pintor.setPen(QColor(255, 255, 255))
                try:
                    fm = pintor.fontMetrics()
                    txt = "A"
                    tw = fm.horizontalAdvance(txt)
                    th = fm.ascent()
                    pintor.drawText(4 + (14 - tw)//2, 7 + (14 + th)//2 - 2, txt)
                except Exception:
                    pintor.drawText(8, 17, "A")
            except Exception:
                pass
        if self._tiempo is not None:
            metrica = pintor.fontMetrics()
            ancho_t = metrica.horizontalAdvance(self._tiempo) + 10
            alto_t = metrica.height() + 4
            bx = x + escalada.width() - ancho_t - 4
            by = y + escalada.height() - alto_t - 4
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(0, 0, 0, 150))
            pintor.drawRoundedRect(bx, by, ancho_t, alto_t, 3, 3)
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


class DialogoExportarLote(QDialog):
    """Diálogo mínimo de alcance para B6.9.

    Ofrece:
      1) Todos los segmentos de los videos visibles
      2) Segmentos por color (6 colores + Sin clasificar)
      3) Segmentos seleccionados - lista ligera dentro del dialogo con
         checkboxes solo aqui. Texto por fila: video + inicio-fin + color
         si aporta claridad. Sin imagenes. Orden determinista.
         La lista se alimenta sin acceso directo a BD desde UI: el caller resuelve
         via tarea antes de construir el dialogo y pasa `segmentos`.
    """

    def __init__(self, filtro_actual, ruta_config=None, parent=None, video_ids=None, ruta_db=None, segmentos=None, nombres_por_id=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar segmentos")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Seleccione el alcance del lote:"))
        self.radio_todos = QRadioButton("Todos los segmentos de los videos visibles")
        self.radio_color = QRadioButton("Segmentos por color:")
        self.radio_seleccion = QRadioButton("Segmentos seleccionados...")
        self.combo_color = QComboBox()
        self.combo_color.addItem("Sin clasificar", None)
        for clave, *_resto in COLORES_CLASIFICACION:
            self.combo_color.addItem(texto_color(clave, ruta_config), clave)
        # Resolver segmentos para la lista explícita (puramente presentacional)
        # El caller (Visor) resuelve vía GestorTareas en background y pasa `segmentos` ya listos.
        # Si no hay datos, se deshabilita la opción explícita; nunca se consulta repositorio desde el hilo UI.
        self._segmentos = []
        self._nombres_por_id = dict(nombres_por_id) if isinstance(nombres_por_id, dict) else {}
        self._ruta_config_dialog = ruta_config
        if segmentos is not None:
            try:
                tmp = list(segmentos)
                self._segmentos = tmp
            except Exception:
                self._segmentos = []
        else:
            self._segmentos = []
        # Orden determinista para la lista (video_id ASC, inicio ASC, fin ASC, id ASC)
        try:
            self._segmentos = sorted(self._segmentos, key=lambda x: (x[1] if len(x) > 1 else 0, x[2] if len(x) > 2 else 0, x[3] if len(x) > 3 else 0, x[0] if len(x) > 0 else 0))
        except Exception:
            pass
        # Preselección coherente con filtro actual sin cambiar filtro
        filtro = filtro_actual if isinstance(filtro_actual, str) else "todos"
        is_segmento = isinstance(filtro, str) and filtro.startswith("segmento:")
        preselect = None
        if is_segmento:
            val = filtro[len("segmento:") :]
            if val == "sin_clasificar":
                preselect = None
            elif val in CLAVES_COLOR_CLASIFICACION:
                preselect = val
            else:
                is_segmento = False
        if is_segmento:
            self.radio_color.setChecked(True)
            idx = self.combo_color.findData(preselect)
            if idx >= 0:
                self.combo_color.setCurrentIndex(idx)
        else:
            self.radio_todos.setChecked(True)
        # Grupo exclusivo
        grupo = QButtonGroup(self)
        grupo.addButton(self.radio_todos)
        grupo.addButton(self.radio_color)
        grupo.addButton(self.radio_seleccion)
        grupo.setExclusive(True)
        # Lista ligera de segmentos con checkboxes (solo dentro del diálogo)
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self._lista_widget = QListWidget()
        self._lista_widget.setMaximumHeight(180)
        self._checkboxes = []  # lista de (QCheckBox, segmento)
        # Construir items sin pixmaps
        for seg in self._segmentos:
            try:
                seg_id, vid, inicio, fin, color = seg[0], seg[1], seg[2], seg[3], seg[4] if len(seg) > 4 else None
            except Exception:
                continue
            nombre_video = self._nombres_por_id.get(vid, f"video {vid}")
            # Texto identificable: video + inicio-fin + color si aporta
            t_ini = formatear_tiempo(inicio) if formatear_tiempo(inicio) is not None else f"{inicio:.2f}"
            t_fin = formatear_tiempo(fin) if formatear_tiempo(fin) is not None else f"{fin:.2f}"
            color_txt = ""
            if color in CLAVES_COLOR_CLASIFICACION:
                color_txt = f" [{texto_color(color, ruta_config)}]"
            elif color is None:
                color_txt = " [Sin clasificar]"
            texto = f"{nombre_video}  {t_ini}-{t_fin}{color_txt}"
            item = QListWidgetItem(self._lista_widget)
            # Usar checkbox nativo del item (sin pixmap)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setText(texto)
            # Guardar seg_id en data
            item.setData(Qt.UserRole, seg_id)
            self._checkboxes.append(item)
        # Controles Todos/Ninguno para la lista
        fila_sel_btns = QHBoxLayout()
        self.boton_sel_todos = QPushButton("Seleccionar todos")
        self.boton_sel_ninguno = QPushButton("Ninguno")
        fila_sel_btns.addWidget(self.boton_sel_todos)
        fila_sel_btns.addWidget(self.boton_sel_ninguno)
        fila_sel_btns.addStretch()
        self.boton_sel_todos.clicked.connect(self._seleccionar_todos_explicitos)
        self.boton_sel_ninguno.clicked.connect(self._deseleccionar_todos_explicitos)
        # Habilitación según radio
        self.combo_color.setEnabled(self.radio_color.isChecked())
        self._lista_widget.setEnabled(self.radio_seleccion.isChecked())
        self.boton_sel_todos.setEnabled(self.radio_seleccion.isChecked())
        self.boton_sel_ninguno.setEnabled(self.radio_seleccion.isChecked())
        self.radio_todos.toggled.connect(lambda checked: self.combo_color.setEnabled(self.radio_color.isChecked()))
        self.radio_color.toggled.connect(lambda checked: self.combo_color.setEnabled(checked))
        self.radio_seleccion.toggled.connect(lambda checked: self._actualizar_habilitacion_seleccion(checked))
        # Si no hay segmentos, deshabilitar opción explícita
        if not self._segmentos:
            self.radio_seleccion.setEnabled(False)
            self._lista_widget.setEnabled(False)
            self.boton_sel_todos.setEnabled(False)
            self.boton_sel_ninguno.setEnabled(False)
        layout.addWidget(self.radio_todos)
        fila_color = QHBoxLayout()
        fila_color.addWidget(self.radio_color)
        fila_color.addWidget(self.combo_color, 1)
        layout.addLayout(fila_color)
        layout.addWidget(self.radio_seleccion)
        layout.addWidget(self._lista_widget)
        layout.addLayout(fila_sel_btns)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _actualizar_habilitacion_seleccion(self, checked):
        self._lista_widget.setEnabled(checked and bool(self._segmentos))
        self.boton_sel_todos.setEnabled(checked and bool(self._segmentos))
        self.boton_sel_ninguno.setEnabled(checked and bool(self._segmentos))
        self.combo_color.setEnabled(self.radio_color.isChecked())

    def _seleccionar_todos_explicitos(self):
        for i in range(self._lista_widget.count()):
            self._lista_widget.item(i).setCheckState(Qt.Checked)

    def _deseleccionar_todos_explicitos(self):
        for i in range(self._lista_widget.count()):
            self._lista_widget.item(i).setCheckState(Qt.Unchecked)

    def alcance_seleccionado(self):
        """Devuelve (tipo, dato) donde tipo es 'todos' | 'color' | 'seleccion'.
        Para 'seleccion', dato es lista de segmento ids orden determinista.
        """
        if self.radio_seleccion.isChecked():
            ids = []
            for i in range(self._lista_widget.count()):
                item = self._lista_widget.item(i)
                if item.checkState() == Qt.Checked:
                    ids.append(item.data(Qt.UserRole))
            # Orden determinista ya es el de la lista (sorted); asegurar sin duplicados y ordenado
            # Mantener orden de aparición (que es determinista)
            return ("seleccion", ids)
        if self.radio_color.isChecked():
            return ("color", self.combo_color.currentData())
        return ("todos", None)

    def ids_seleccionados(self):
        """Compatibilidad: devuelve ids explícitos seleccionados."""
        _, dato = self.alcance_seleccionado()
        if isinstance(dato, list):
            return dato
        return []


class DialogoExportarSecuencia(QDialog):
    """Diálogo mínimo para B6.10 — unir varios segmentos del mismo original.

    Reutiliza la selección B6.9 (lista ligera con checkboxes) y añade orden explícito
    (botones Subir/Bajar). No toca base de datos ni procesos externos ni carga imágenes.
    La lista se alimenta sin BD desde el hilo UI: el caller resuelve vía GestorTareas
    en background y pasa `segmentos` y `nombres_por_id`.
    Valida N>=2 y mismo video_id; el orden es el explícito elegido por el usuario
    (el de la lista tras mover).
    """

    def __init__(self, segmentos=None, nombres_por_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unir segmentos — secuencia")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Seleccione al menos 2 segmentos del MISMO video y ordene la secuencia:"))
        self._segmentos = []
        self._nombres_por_id = dict(nombres_por_id) if isinstance(nombres_por_id, dict) else {}
        if segmentos is not None:
            try:
                self._segmentos = sorted(list(segmentos), key=lambda x: (x[1] if len(x) > 1 else 0, x[2] if len(x) > 2 else 0, x[3] if len(x) > 3 else 0, x[0] if len(x) > 0 else 0))
            except Exception:
                self._segmentos = list(segmentos) if isinstance(segmentos, list) else []
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self._lista_widget = QListWidget()
        self._lista_widget.setMaximumHeight(200)
        for seg in self._segmentos:
            try:
                seg_id, vid, inicio, fin, color = seg[0], seg[1], seg[2], seg[3], seg[4] if len(seg) > 4 else None
            except Exception:
                continue
            nombre_video = self._nombres_por_id.get(vid, f"video {vid}")
            t_ini = formatear_tiempo(inicio) if formatear_tiempo(inicio) is not None else f"{inicio:.2f}"
            t_fin = formatear_tiempo(fin) if formatear_tiempo(fin) is not None else f"{fin:.2f}"
            color_txt = ""
            if color in CLAVES_COLOR_CLASIFICACION:
                color_txt = f" [{texto_color(color, None)}]"
            elif color is None:
                color_txt = " [Sin clasificar]"
            texto = f"{nombre_video}  {t_ini}-{t_fin}{color_txt}  [#%s]" % seg_id
            item = QListWidgetItem(self._lista_widget)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setText(texto)
            item.setData(Qt.UserRole, seg_id)
            # guardar vid para validación
            item.setData(Qt.UserRole + 1, vid)
        # Botones ordenar
        fila_orden = QHBoxLayout()
        self.boton_subir = QPushButton("Subir")
        self.boton_bajar = QPushButton("Bajar")
        self.boton_sel_todos = QPushButton("Seleccionar todos")
        self.boton_sel_ninguno = QPushButton("Ninguno")
        fila_orden.addWidget(self.boton_subir)
        fila_orden.addWidget(self.boton_bajar)
        fila_orden.addWidget(self.boton_sel_todos)
        fila_orden.addWidget(self.boton_sel_ninguno)
        fila_orden.addStretch()
        self.boton_subir.clicked.connect(self._mover_arriba)
        self.boton_bajar.clicked.connect(self._mover_abajo)
        self.boton_sel_todos.clicked.connect(self._seleccionar_todos)
        self.boton_sel_ninguno.clicked.connect(self._deseleccionar_todos)
        # Info
        self.label_info = QLabel("")
        self.label_info.setStyleSheet("color: #666;")
        layout.addWidget(self._lista_widget)
        layout.addLayout(fila_orden)
        layout.addWidget(self.label_info)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._al_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        self._botones = botones
        self._update_info()
        self._lista_widget.itemChanged.connect(lambda *_: self._update_info())

    def _mover_arriba(self):
        row = self._lista_widget.currentRow()
        if row <= 0:
            return
        item = self._lista_widget.takeItem(row)
        self._lista_widget.insertItem(row - 1, item)
        self._lista_widget.setCurrentRow(row - 1)

    def _mover_abajo(self):
        row = self._lista_widget.currentRow()
        if row < 0 or row >= self._lista_widget.count() - 1:
            return
        item = self._lista_widget.takeItem(row)
        self._lista_widget.insertItem(row + 1, item)
        self._lista_widget.setCurrentRow(row + 1)

    def _seleccionar_todos(self):
        for i in range(self._lista_widget.count()):
            self._lista_widget.item(i).setCheckState(Qt.Checked)
        self._update_info()

    def _deseleccionar_todos(self):
        for i in range(self._lista_widget.count()):
            self._lista_widget.item(i).setCheckState(Qt.Unchecked)
        self._update_info()

    def _update_info(self):
        ids = []
        vids = set()
        for i in range(self._lista_widget.count()):
            item = self._lista_widget.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
                vids.add(item.data(Qt.UserRole + 1))
        if not ids:
            self.label_info.setText("Ningún segmento seleccionado")
        elif len(ids) < 2:
            self.label_info.setText(f"{len(ids)} seleccionado — se requieren al menos 2")
        elif len(vids) > 1:
            self.label_info.setText(f"{len(ids)} seleccionados de {len(vids)} videos — deben ser del mismo video")
        else:
            self.label_info.setText(f"{len(ids)} seleccionados — orden explícito {ids}")

    def _al_aceptar(self):
        ids = []
        vids = set()
        for i in range(self._lista_widget.count()):
            item = self._lista_widget.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
                vids.add(item.data(Qt.UserRole + 1))
        if len(ids) < 2:
            QMessageBox.warning(self, "Unir segmentos", "Seleccione al menos 2 segmentos.")
            return
        if len(vids) > 1:
            QMessageBox.warning(self, "Unir segmentos", "Los segmentos deben pertenecer al mismo video original.")
            return
        self.accept()

    def segmentos_ordenados(self):
        """Devuelve lista de ids en el orden explícito de la lista (solo checked, en orden visual)."""
        ids = []
        for i in range(self._lista_widget.count()):
            item = self._lista_widget.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def video_id_seleccionado(self):
        vids = set()
        for i in range(self._lista_widget.count()):
            item = self._lista_widget.item(i)
            if item.checkState() == Qt.Checked:
                vids.add(item.data(Qt.UserRole + 1))
        if len(vids) == 1:
            return next(iter(vids))
        return None


class DialogoRenombrar(QDialog):
    """Diálogo simple B7.1 — renombrado individual (preserva extensión)."""

    def __init__(self, nombre_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renombrar")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Nombre actual: {nombre_actual}"))
        layout.addWidget(QLabel("Nuevo nombre (extensión preservada):"))
        self._campo = QLineEdit()
        self._campo.setText(nombre_actual)
        self._campo.selectAll()
        layout.addWidget(self._campo)
        self._label_error = QLabel("")
        self._label_error.setStyleSheet("color: #b00020;")
        layout.addWidget(self._label_error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._al_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _al_aceptar(self):
        texto = self._campo.text()
        if not texto.strip():
            self._label_error.setText("El nombre no puede estar vacío")
            return
        # Validación rápida local (extensión se valida en servicio, aquí solo vacío)
        self.accept()

    def texto(self):
        return self._campo.text()


class DialogoCrearCarpeta(QDialog):
    """Diálogo simple B7.3 — crear carpeta hija directa."""

    def __init__(self, carpeta_padre, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva carpeta")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Carpeta padre: {carpeta_padre}"))
        layout.addWidget(QLabel("Nombre de la nueva carpeta:"))
        self._campo = QLineEdit()
        self._campo.setPlaceholderText("Nombre sin separadores, sin punto/espacio final")
        self._campo.selectAll()
        layout.addWidget(self._campo)
        self._label_error = QLabel("")
        self._label_error.setStyleSheet("color: #b00020;")
        layout.addWidget(self._label_error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._al_aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _al_aceptar(self):
        texto = self._campo.text()
        if not texto.strip():
            self._label_error.setText("El nombre no puede estar vacío")
            return
        # Validación rápida local mínima; servicio valida resto
        if "/" in texto or "\\" in texto:
            self._label_error.setText("No se permiten separadores de ruta")
            return
        if texto.strip() in (".", ".."):
            self._label_error.setText("Nombre no puede ser '.' o '..'")
            return
        if texto.endswith(" ") or texto.endswith("."):
            self._label_error.setText("No puede terminar en punto o espacio")
            return
        self.accept()

    def texto(self):
        return self._campo.text()


class DialogoRenombrarMasivo(QDialog):
    """Diálogo B7.7 — renombrado masivo con plantilla cerrada y preview exacta.

    - Plantilla reutiliza exclusivamente motores cerrados de nombres.py (sin eval).
    - Preview muestra claramente nombre actual -> nombre final para TODOS los seleccionados.
    - Preview es exactamente el plan que se ejecutará (no recalcula diferente al confirmar).
    - Sanitización visible: nombres mostrados son finales exactos (incluye _ por reservados, reemplazo de inválidos).
    - Errores no resolubles bloquean Aplicar con mensaje claro.
    - Preserva extensión original (no cambia extensiones).
    """

    def __init__(self, video_infos, ruta_db=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renombrado masivo")
        self._video_infos = list(video_infos) if isinstance(video_infos, list) else []
        self._ruta_db = ruta_db
        self._plan = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Plantilla (tokens cerrados: {original}, {numero}, {numero:03d}, {fecha}, {fecha:YYYY-MM-DD}, {texto}):"))
        self._campo_plantilla = QLineEdit()
        self._campo_plantilla.setPlaceholderText("{original}_{numero:03d}")
        self._campo_plantilla.setText("{original}_{numero:03d}")
        layout.addWidget(self._campo_plantilla)
        layout.addWidget(QLabel("Texto personalizado para {texto} (si no usa {texto}, dejar vacío):"))
        self._campo_texto = QLineEdit()
        self._campo_texto.setPlaceholderText("texto para {texto}")
        layout.addWidget(self._campo_texto)
        layout.addWidget(QLabel("Previsualización (actual -> final):"))
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self._tabla = QTableWidget()
        self._tabla.setColumnCount(2)
        self._tabla.setHorizontalHeaderLabels(["Actual", "Final"])
        header = self._tabla.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._tabla)
        self._label_error = QLabel("")
        self._label_error.setStyleSheet("color: #b00020;")
        self._label_error.setWordWrap(True)
        layout.addWidget(self._label_error)
        self._botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._botones.button(QDialogButtonBox.Ok).setText("Aplicar")
        self._botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        self._botones.accepted.connect(self._al_aceptar)
        self._botones.rejected.connect(self.reject)
        layout.addWidget(self._botones)
        # Conectar cambios para preview en vivo
        self._campo_plantilla.textChanged.connect(self._actualizar_preview)
        self._campo_texto.textChanged.connect(self._actualizar_preview)
        self._actualizar_preview()
        self.resize(700, 420)

    def _actualizar_preview(self):
        plantilla = self._campo_plantilla.text()
        texto = self._campo_texto.text()
        # texto vacío -> None (si plantilla no usa {texto}, no afecta)
        texto_val = texto if isinstance(texto, str) and texto.strip() else None
        # Si plantilla vacía, mostrar error y bloquear
        if not plantilla.strip():
            self._label_error.setText("Plantilla vacía")
            self._tabla.setRowCount(0)
            self._plan = None
            self._botones.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        try:
            import renombrar_masivo as rm
            res = rm.construir_plan(self._video_infos, plantilla, texto=texto_val, ruta_db=self._ruta_db)
        except Exception as exc:
            self._label_error.setText(f"Error al construir plan: {type(exc).__name__}: {exc}")
            self._tabla.setRowCount(0)
            self._plan = None
            self._botones.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        # Poblar tabla con plan
        plan = res.get("plan", [])
        self._tabla.setRowCount(len(plan))
        from PySide6.QtWidgets import QTableWidgetItem
        for row, item in enumerate(plan):
            actual = item.get("nombre_actual", "")
            final = item.get("nombre_final")
            error = item.get("error")
            item_actual = QTableWidgetItem(str(actual))
            if error:
                final_text = f"ERROR: {error}"
            else:
                final_text = str(final) if final is not None else ""
            item_final = QTableWidgetItem(final_text)
            if error:
                # resaltar error
                item_final.setForeground(QColor("#b00020"))
            self._tabla.setItem(row, 0, item_actual)
            self._tabla.setItem(row, 1, item_final)
        # Manejar errores globales y por item
        if not res.get("ok"):
            errores = res.get("errores") or []
            item_errs = [f"{p.get('nombre_actual')}: {p.get('error')}" for p in plan if p.get("error")]
            todos = errores + item_errs
            msg = "; ".join(todos) if todos else "Plantilla o nombres inválidos"
            # Truncar para label pero mantener completo en tooltip
            self._label_error.setText(msg[:600])
            self._label_error.setToolTip(msg)
            self._plan = None
            self._botones.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self._label_error.setText("")
            self._label_error.setToolTip("")
            self._plan = plan
            self._botones.button(QDialogButtonBox.Ok).setEnabled(True)

    def _al_aceptar(self):
        if self._plan is None:
            self._label_error.setText("Corrija la plantilla antes de aplicar")
            return
        # Verificar que plan no contiene errores
        for item in self._plan:
            if item.get("error"):
                self._label_error.setText(f"Plan contiene error en {item.get('nombre_actual')}: {item.get('error')}")
                return
        self.accept()

    def plan(self):
        return list(self._plan) if isinstance(self._plan, list) else None

    def plantilla_text(self):
        return self._campo_plantilla.text()

    def texto_personalizado(self):
        t = self._campo_texto.text()
        return t if isinstance(t, str) and t.strip() else None


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
    doble_clic = Signal(object)
    seleccionada = Signal(object, bool)
    seleccion_por_rango = Signal(object)
    menu_contextual = Signal(object)
    vista_solicitada = Signal(object)
    vista_abandonada = Signal()
    seleccion_check = Signal(object, bool)
    expansion_cambiada = Signal(object, bool)
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
    densidad_cambiada = Signal(object, object)
    modo_tira_cambiada = Signal(object, object)
    preview_visual_solicitada = Signal(object)  # B9.3 virtualización: {video_id, version, ms_list, request_id, gen}
    marcador_color_solicitado = Signal(object, object)
    segmento_color_solicitado = Signal(object, object)
    segmento_exportacion_solicitada = Signal(object)

    def __init__(self, fila, parent=None, ruta_config=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self._ruta_config = ruta_config
        self._color_activo = None
        # B7.13B — estado drag origen (umbral Qt)
        self._drag_start_pos = None
        self._drag_deferred = False
        fila_principal = QHBoxLayout()

        nombre, duracion, ancho, alto, codec, miniaturas, tamano, *_resto = fila
        # B9.3/P01 compacta: conservar dimensiones originales para aspect ratio sin FFprobe
        try:
            self._video_ancho = int(ancho) if isinstance(ancho, int) and not isinstance(ancho, bool) and ancho > 0 else None
            self._video_alto = int(alto) if isinstance(alto, int) and not isinstance(alto, bool) and alto > 0 else None
        except Exception:
            self._video_ancho = None
            self._video_alto = None
        self._tira_aspect_cache = None
        self._tira_ancho_slot_cache = None

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
        self._labels_campos = []
        for etiqueta, valor in campos:
            campo = QLabel(f"<b>{etiqueta}:</b> {valor}")
            campo.setWordWrap(True)
            campo.installEventFilter(self)
            self._labels_campos.append(campo)
            columna_campos.addWidget(campo)
        columna_campos.addStretch()
        self._boton_expandir = QPushButton("Expandir")
        self._boton_expandir.setCheckable(True)
        self._boton_expandir.toggled.connect(self._al_toggle_expansion)
        columna_campos.insertWidget(0, self._boton_expandir)
        datos_widget = QWidget()
        datos_widget.setObjectName("datos_widget_b93")
        datos_widget.setMaximumWidth(240)
        datos_widget.setLayout(columna_campos)
        fila_principal.addWidget(datos_widget)
        # B9.3/P01 corredor vertical: referencia durable para geometría global
        self._datos_widget = datos_widget

        self._nombre = nombre
        self._duracion = duracion
        self._seleccionada = False
        # B8.3B — tooltip con ruta para distinguir homónimos (display mínimo, sin rediseño)
        try:
            if isinstance(ruta_video_registro, str) and ruta_video_registro:
                self.setToolTip(ruta_video_registro)
            elif isinstance(carpeta_video, str) and carpeta_video:
                self.setToolTip(os.path.join(carpeta_video, nombre) if isinstance(nombre, str) else carpeta_video)
        except Exception:
            pass
        self._etiquetas_previews = []
        self._imagen_miniatura = None
        self._miniatura_original = None
        self._recuadro_sin_miniatura = None
        self._previews_completas = False
        self._previews_cache = []

        contenedor_imagenes = QHBoxLayout()
        contenedor_imagenes.setContentsMargins(0, 0, 0, 0)
        contenedor_imagenes.setSpacing(6)
        self._contenedor_imagenes = contenedor_imagenes

        ancho, alto = dimensiones_miniatura()
        ruta_miniatura = None
        # B8.2: resolución determinista sin I/O pesado ni migración en UI (backend/tareas)
        if isinstance(self._video_id, int) and self._video_id > 0 and not isinstance(self._video_id, bool):
            ruta_miniatura = miniatura_principal_por_id(self._video_id)
        else:
            ruta_miniatura = miniatura_principal(nombre)
        # Intentar cargar; si QPixmap es nulo (archivo no existe aún) mostrar recuadro
        pixmap_cargado = None
        if ruta_miniatura is not None:
            try:
                _pix = QPixmap(ruta_miniatura)
                if not _pix.isNull():
                    pixmap_cargado = _pixmap_acotado(_pix)
                else:
                    ruta_miniatura = None
            except (RuntimeError, ValueError, TypeError):
                ruta_miniatura = None
                pixmap_cargado = None
        if ruta_miniatura is not None and pixmap_cargado is not None and not pixmap_cargado.isNull():
            imagen = QLabel()
            pixmap = pixmap_cargado
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
        if self._recuadro_sin_miniatura is not None:
            self._recuadro_sin_miniatura.installEventFilter(self)
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

    def actualizar_nombre(self, nuevo_nombre, nueva_ruta=None):
        """Actualiza el nombre y la carpeta del video tras renombrado (B7.1).

        Sincroniza identidad del archivo usando nuevo_nombre y nueva_ruta,
        actualizando _nombre y _carpeta_video desde dirname(nueva_ruta).
        Mantiene el label. Si nueva_ruta no es válida, no altera _carpeta_video
        pero sí sincroniza _nombre (el caller valida inconsistencia).
        """
        if isinstance(nuevo_nombre, str) and nuevo_nombre:
            self._nombre = nuevo_nombre
        if isinstance(nueva_ruta, str) and nueva_ruta.strip():
            try:
                carpeta = os.path.dirname(nueva_ruta)
                if carpeta:
                    # Normalizar sin trailing sep, preservar raíz/drive
                    carpeta_norm = carpeta.rstrip(os.sep) or carpeta
                    self._carpeta_video = carpeta_norm
                else:
                    # Fallback: derivar desde abspath si dirname vacío
                    ab = os.path.abspath(nueva_ruta)
                    d = os.path.dirname(ab)
                    if d:
                        self._carpeta_video = d.rstrip(os.sep) or d
            except Exception:
                pass
        # Actualizar QLabel de Nombre si existe (primer campo)
        try:
            for lbl in self.findChildren(QLabel):
                txt = lbl.text()
                if txt.startswith("<b>Nombre:</b>"):
                    lbl.setText(f"<b>Nombre:</b> {self._nombre}")
                    break
        except Exception:
            pass
        # B8.3B: actualizar tooltip para homónimos
        try:
            if isinstance(nueva_ruta, str) and nueva_ruta:
                self.setToolTip(nueva_ruta)
            elif isinstance(self._carpeta_video, str) and self._nombre:
                self.setToolTip(os.path.join(self._carpeta_video, self._nombre))
        except Exception:
            pass

    def actualizar_ruta(self, nueva_ruta):
        """Actualiza únicamente la ruta/carpeta tras mover (B7.2).

        Contrato estricto:
        - nueva_ruta debe ser str no vacío con dirname válido.
        - basename(nueva_ruta) debe coincidir con self._nombre
          (comparación case-insensitive en Windows via normcase);
          si no coincide lanza ValueError.
        - Calcula carpeta y actualiza _carpeta_video solo después de validar.
        - No traga excepciones silenciosamente.
        Mantiene mismo nombre y video_id.
        """
        if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
            raise ValueError("nueva_ruta debe ser texto no vacío")
        if not isinstance(self._nombre, str) or not self._nombre:
            raise ValueError("nombre de tarjeta inválido para validar ruta")
        base = os.path.basename(nueva_ruta)
        if not base:
            raise ValueError("nueva_ruta sin basename")
        # Comparación apropiada Windows: case-insensitive via normcase
        if os.path.normcase(base) != os.path.normcase(self._nombre):
            raise ValueError(
                f"basename {base!r} no coincide con nombre tarjeta {self._nombre!r}"
            )
        carpeta = os.path.dirname(nueva_ruta)
        if not carpeta or not carpeta.strip():
            # Derivar desde abspath si dirname vacío (ruta relativa)
            ab = os.path.abspath(nueva_ruta)
            carpeta = os.path.dirname(ab)
        if not carpeta or not carpeta.strip():
            raise ValueError("no se pudo derivar carpeta de nueva_ruta")
        carpeta_norm = carpeta.rstrip(os.sep) or carpeta
        # Solo después de validar se actualiza el estado
        self._carpeta_video = carpeta_norm
        # B8.3B: actualizar tooltip
        try:
            self.setToolTip(nueva_ruta)
        except Exception:
            pass

    @property
    def nombre(self):
        return self._nombre

    # ── B7.13B — origen drag: estado mínimo para umbral Qt ──
    def _visor_para_drag(self):
        """Localiza VisorVideos ancestro sin FS/SQLite."""
        try:
            w = self.window()
            if w is not None and w.__class__.__name__ == "VisorVideos":
                return w
            p = self.parent()
            while p is not None:
                if p.__class__.__name__ == "VisorVideos":
                    return p
                try:
                    np = p.parent()
                    if np is p:
                        break
                    p = np
                except (AttributeError, TypeError, RuntimeError):
                    break
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13B] _visor_para_drag error: {exc}")
        return None

    def _ids_para_drag(self, visor):
        """Retorna lista ordenada de video_id para drag o None si no utilizable.

        Reutiliza exactamente _video_ids_seleccionados_ordenados del visor
        (orden estable determinista por tarjetas_visibles). Sin duplicar lógica.
        """
        try:
            if visor is None or not getattr(visor, "_modo_organizacion", False):
                return None
            vid_self = getattr(self, "_video_id", None)
            if not isinstance(vid_self, int) or isinstance(vid_self, bool) or vid_self <= 0:
                return None
            metodo = getattr(visor, "_video_ids_seleccionados_ordenados", None)
            if callable(metodo):
                try:
                    ids = metodo()
                except (AttributeError, TypeError, RuntimeError) as exc:
                    print(f"[B7.13B] _ids_para_drag metodo error: {exc}")
                    return None
                if isinstance(ids, list) and len(ids) > 0:
                    filtrados = [x for x in ids if isinstance(x, int) and not isinstance(x, bool) and x > 0]
                    if filtrados and vid_self in filtrados:
                        return filtrados
                    if filtrados:
                        # Si origen no está en selección (caso no seleccionado tras press ya es single)
                        # filtrados ya contiene el single correcto; si no, fallback single
                        if vid_self in filtrados:
                            return filtrados
                        # origen no seleccionado pero selección existe: tras press será single con vid_self
                        # devolver filtrados si ya incluye vid_self sino single
                        return [vid_self] if getattr(self, "_seleccionada", False) else None
                    return None
                # Sin selección utilizable
                if getattr(self, "_seleccionada", False):
                    return [vid_self]
                return None
            if getattr(self, "_seleccionada", False):
                return [vid_self]
            return None
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13B] _ids_para_drag error: {exc}")
            return None

    def _pixmap_drag_b713c(self, ids):
        """B7.13C — genera pixmap ghost semi-transparente reutilizando grab().

        - Reutiliza visualmente la tarjeta actual mediante grab() (sin leer disco ni procesos externos).
        - Tamaño razonable acotado (max 200x120) con escalado suave.
        - Semi-transparente (opacity 0.85) sobre fondo transparente.
        - Incluye indicación visible de cantidad: "1 video", "2 videos", etc.
        - Fallback sin grab si no disponible.
        """
        try:
            cnt = len(ids) if isinstance(ids, list) else 1
            try:
                cnt = int(cnt)
            except (TypeError, ValueError):
                cnt = 1
            if cnt < 1:
                cnt = 1
            # Intentar capturar visual de la tarjeta
            base = None
            try:
                base = self.grab()
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13C] grab error: {exc}")
                base = None
            if base is None or base.isNull():
                # Fallback: pixmap placeholder con nombre
                pix = QPixmap(180, 100)
                pix.fill(QColor(240, 240, 240, 210))
                try:
                    p = QPainter(pix)
                    p.setPen(QColor("#333333"))
                    nombre_txt = getattr(self, "_nombre", "video")
                    if not isinstance(nombre_txt, str):
                        nombre_txt = str(nombre_txt)
                    # truncar
                    if len(nombre_txt) > 28:
                        nombre_txt = nombre_txt[:28] + "…"
                    p.drawText(pix.rect(), Qt.AlignCenter, nombre_txt)
                    # badge cantidad
                    text = f"{cnt} video" if cnt == 1 else f"{cnt} videos"
                    fm = p.fontMetrics()
                    tw = fm.horizontalAdvance(text) + 16
                    th = fm.height() + 8
                    x = (pix.width() - tw) // 2
                    y = pix.height() - th - 6
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(33, 150, 243, 230))
                    p.drawRoundedRect(x, y, tw, th, 6, 6)
                    p.setPen(QColor(255, 255, 255))
                    p.drawText(x + 8, y + fm.ascent() + 4, text)
                    p.end()
                except (AttributeError, TypeError, RuntimeError) as exc2:
                    print(f"[B7.13C] fallback painter error: {exc2}")
                    try:
                        p.end()
                    except (AttributeError, TypeError, RuntimeError):
                        _ = None
                return pix
            # Acotar tamaño razonable no gigante
            MAX_W = 200
            MAX_H = 120
            w = base.width()
            h = base.height()
            if w > MAX_W or h > MAX_H:
                try:
                    base = base.scaled(MAX_W, MAX_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                except (AttributeError, TypeError, RuntimeError) as exc:
                    print(f"[B7.13C] scaled error: {exc}")
            # Crear pixmap semi-transparente con badge
            try:
                pix = QPixmap(base.size())
                pix.fill(Qt.transparent)
                painter = QPainter(pix)
                painter.setOpacity(0.85)
                painter.drawPixmap(0, 0, base)
                painter.setOpacity(1.0)
                # Indicación cantidad (siempre visible para test determinista: "1 video" / "N videos")
                text = f"{cnt} video" if cnt == 1 else f"{cnt} videos"
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(text) + 16
                th = fm.height() + 8
                # Centrar badge abajo
                x = (pix.width() - tw) // 2
                y = pix.height() - th - 6
                if y < 2:
                    y = 2
                if x < 2:
                    x = 2
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(33, 150, 243, 230))
                painter.drawRoundedRect(x, y, tw, th, 6, 6)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(x + 8, y + fm.ascent() + 4, text)
                painter.end()
                return pix
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13C] painter badge error: {exc}")
                try:
                    painter.end()
                except (AttributeError, TypeError, RuntimeError):
                    _ = None
                return base
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13C] _pixmap_drag_b713c error: {exc}")
            try:
                fallback = QPixmap(180, 100)
                fallback.fill(QColor(220, 220, 220, 200))
                return fallback
            except (AttributeError, TypeError, RuntimeError):
                return None

    def mousePressEvent(self, event):
        # B7.13B: almacenar posición inicio para umbral Qt; preservar semántica de selección
        if event.button() == Qt.LeftButton:
            try:
                if hasattr(event, "position"):
                    self._drag_start_pos = event.position().toPoint()
                else:
                    self._drag_start_pos = event.pos()
            except (AttributeError, TypeError, RuntimeError):
                try:
                    self._drag_start_pos = event.pos()
                except (AttributeError, TypeError, RuntimeError):
                    self._drag_start_pos = None
            # Preservar selección múltiple si origen ya seleccionado (evitar clear prematuro antes de drag)
            visor = self._visor_para_drag()
            defer = False
            if visor is not None and getattr(visor, "_modo_organizacion", False):
                if getattr(self, "_seleccionada", False):
                    try:
                        # B8.3B: usar ids para homónimos
                        sel_ids = getattr(visor, "_ids_seleccionados", set())
                        if isinstance(sel_ids, set) and len(sel_ids) > 1 and isinstance(self._video_id, int) and self._video_id in sel_ids:
                            shift = bool(event.modifiers() & Qt.ShiftModifier)
                            ctrl = bool(event.modifiers() & Qt.ControlModifier)
                            if not shift and not ctrl:
                                defer = True
                        else:
                            sel = getattr(visor, "_nombres_seleccionados", set())
                            if isinstance(sel, set) and len(sel) > 1 and self._nombre in sel:
                                shift = bool(event.modifiers() & Qt.ShiftModifier)
                                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                                if not shift and not ctrl:
                                    defer = True
                    except (AttributeError, TypeError, RuntimeError):
                        defer = False
            if defer:
                self._drag_deferred = True
                super().mousePressEvent(event)
                return
            self._drag_deferred = False
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            if shift:
                self.seleccion_por_rango.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre)
            else:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                self.seleccionada.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, ctrl)
        elif event.button() == Qt.RightButton:
            self._drag_start_pos = None
            self._drag_deferred = False
            if not self._seleccionada:
                self.seleccionada.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, False)
            self.menu_contextual.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre)
        else:
            self._drag_start_pos = None
            self._drag_deferred = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # B7.13B: iniciar arrastre solo en modo Organización, con umbral Qt, desde tarjeta real
        try:
            if not (event.buttons() & Qt.LeftButton):
                return super().mouseMoveEvent(event)
            if getattr(self, "_drag_start_pos", None) is None:
                return super().mouseMoveEvent(event)
            # Umbral Qt
            try:
                cur = event.position().toPoint() if hasattr(event, "position") else event.pos()
                dist = (cur - self._drag_start_pos).manhattanLength()
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13B] mouseMove distancia error: {exc}")
                return super().mouseMoveEvent(event)
            if dist < QApplication.startDragDistance():
                return super().mouseMoveEvent(event)
            visor = self._visor_para_drag()
            if visor is None:
                return super().mouseMoveEvent(event)
            if not getattr(visor, "_modo_organizacion", False):
                return super().mouseMoveEvent(event)
            ids = self._ids_para_drag(visor)
            if not ids:
                return super().mouseMoveEvent(event)
            mime = _crear_mime_data_drag_b713b(ids)
            if mime is None:
                return super().mouseMoveEvent(event)
            # No agregar URLs ni texto genérico: solo MIME privado
            drag = QDrag(self)
            drag.setMimeData(mime)
            # B7.13C — feedback visual mínimo: ghost + hotspot (reutiliza grab(), sin FS/FFmpeg)
            try:
                pix = self._pixmap_drag_b713c(ids)
                if pix is not None and not pix.isNull():
                    if hasattr(drag, "setPixmap"):
                        try:
                            drag.setPixmap(pix)
                        except (AttributeError, TypeError, RuntimeError) as exc_pm:
                            print(f"[B7.13C] setPixmap error: {exc_pm}")
                    # Hotspot desplazado para no tapar destino
                    if hasattr(drag, "setHotSpot"):
                        try:
                            w = pix.width()
                            h = pix.height()
                            hx = 12 if w > 12 else max(0, w // 3)
                            hy = 12 if h > 12 else max(0, h // 3)
                            drag.setHotSpot(QPoint(hx, hy))
                        except (AttributeError, TypeError, RuntimeError, ValueError) as exc_hs:
                            print(f"[B7.13C] setHotSpot error: {exc_hs}")
                            try:
                                drag.setHotSpot(QPoint(10, 10))
                            except (AttributeError, TypeError, RuntimeError):
                                _ = None
                else:
                    if hasattr(drag, "setHotSpot"):
                        try:
                            drag.setHotSpot(QPoint(10, 10))
                        except (AttributeError, TypeError, RuntimeError):
                            _ = None
            except (AttributeError, TypeError, RuntimeError, ValueError) as exc_pix:
                print(f"[B7.13C] pixmap drag error: {exc_pix}")
                if hasattr(drag, "setHotSpot"):
                    try:
                        drag.setHotSpot(QPoint(10, 10))
                    except (AttributeError, TypeError, RuntimeError):
                        _ = None
            # Acción Move para esta etapa (no ejecuta FS todavía)
            try:
                result = drag.exec(Qt.MoveAction)
            except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
                print(f"[B7.13B] drag exec error: {exc}")
                try:
                    result2 = drag.exec_(Qt.MoveAction)
                except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc2:
                    print(f"[B7.13B] drag exec_ fallback error: {exc2}")
            self._drag_start_pos = None
            self._drag_deferred = False
            return
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13B] mouseMoveEvent error: {exc}")
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # B7.13B: si se difirió selección y no hubo drag (distancia < umbral), ahora sí seleccionar single
        try:
            if event.button() == Qt.LeftButton and getattr(self, "_drag_deferred", False):
                # Si no se inició drag (start_pos aún existe => no hubo drag), emitir selección single
                if getattr(self, "_drag_start_pos", None) is not None:
                    # Simular click sin modificadores: limpiar y seleccionar solo este
                    self.seleccionada.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, False)
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13B] mouseRelease deferred error: {exc}")
        self._drag_start_pos = None
        self._drag_deferred = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # B7.13B: doble click no debe iniciar drag; resetear estado
        self._drag_start_pos = None
        self._drag_deferred = False
        super().mouseDoubleClickEvent(event)
        # Qt puede re-entrar a mousePressEvent via super, restablecer definitivamente
        self._drag_start_pos = None
        self._drag_deferred = False
        self.doble_clic.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre)

    def marcar_seleccionada(self, valor):
        self._seleccionada = valor
        if valor:
            self.setStyleSheet(ESTILO_SELECCIONADA)
        else:
            self.setStyleSheet("")

    def _al_check_cambiar(self, _estado):
        self.seleccion_check.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, self._check.isChecked())

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
        # B8.2: mantener caché en memoria para ajustar_previews sin I/O
        # B9.3 compacta: guardar ancho_slot previo para detectar cambio de aspecto
        prev_slot = None
        try:
            if getattr(self, "_expandida", False) and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                prev_slot = self._tira_ancho_slot()
        except Exception:
            prev_slot = None
        try:
            self._previews_cache = list(rutas) if isinstance(rutas, (list, tuple)) else [rutas]
        except (TypeError, ValueError):
            self._previews_cache = []
        actualizado = False
        for indice in range(min(len(self._etiquetas_previews), len(rutas))):
            if self._colocar_preview(indice, rutas[indice]):
                actualizado = True
        if actualizado and self._expandida:
            self._refrescar_exploracion()
            self._renderizar_marcadores()
            # B9.3/P01 compacta: si primer preview real cambia aspecto, recalcular geometría preservando scroll
            try:
                if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA and prev_slot is not None:
                    if self._tira_ancho_slot() != prev_slot:
                        self._tira_recalcular_si_cambia_aspect(prev_slot)
            except Exception:
                pass
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

    def actualizar_miniatura_por_id(self):
        """B8.2: refresca miniatura principal desde v<id>_01.jpg tras migración background.

        No realiza recorrido de carpeta ni duplicado de archivos ni acceso a base
        ni generación de miniaturas. Solo intenta cargar el QPixmap canónico
        determinado por video_id. Si no existe o es nulo, no altera la tarjeta.
        Si había 'Sin miniatura', lo reemplaza por la imagen sin recargar catálogo
        ni perder selección/scroll. Retorna True si hubo cambio visible.
        """
        if not isinstance(self._video_id, int) or isinstance(self._video_id, bool) or self._video_id <= 0:
            return False
        ruta = miniatura_principal_por_id(self._video_id)
        if not ruta:
            return False
        try:
            pix = QPixmap(ruta)
        except (RuntimeError, ValueError, TypeError):
            return False
        if pix.isNull():
            return False
        pix = _pixmap_acotado(pix)
        # B9.3/P01 compacta: guardar slot previo para detectar cambio de aspecto
        prev_slot_mini = None
        try:
            if getattr(self, "_expandida", False) and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                prev_slot_mini = self._tira_ancho_slot()
        except Exception:
            prev_slot_mini = None
        ancho, alto = dimensiones_miniatura()
        if self._imagen_miniatura is not None and self._miniatura_original is not None:
            # Ya tenía imagen: actualizar pixmap si es distinto
            try:
                if self._miniatura_original.cacheKey() == pix.cacheKey():
                    return False
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
            self._imagen_miniatura.setPixmap(pix.scaled(ancho, alto, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._imagen_miniatura.setFixedHeight(alto)
            self._miniatura_original = pix
            try:
                if prev_slot_mini is not None and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA and getattr(self, "_expandida", False):
                    if self._tira_ancho_slot() != prev_slot_mini:
                        self._tira_recalcular_si_cambia_aspect(prev_slot_mini)
            except Exception:
                pass
            return True
        if self._recuadro_sin_miniatura is not None:
            try:
                self._contenedor_imagenes.removeWidget(self._recuadro_sin_miniatura)
                self._recuadro_sin_miniatura.hide()
                self._recuadro_sin_miniatura.deleteLater()
            except (RuntimeError, AttributeError, TypeError):
                pass
            self._recuadro_sin_miniatura = None
            imagen = QLabel()
            imagen.setPixmap(pix.scaled(ancho, alto, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            imagen.setFixedHeight(alto)
            imagen.setAlignment(Qt.AlignCenter)
            imagen.installEventFilter(self)
            self._imagen_miniatura = imagen
            self._miniatura_original = pix
            # Insertar al inicio (antes de previews)
            try:
                self._contenedor_imagenes.insertWidget(0, imagen)
            except (RuntimeError, AttributeError, TypeError):
                self._contenedor_imagenes.addWidget(imagen)
            try:
                if prev_slot_mini is not None and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA and getattr(self, "_expandida", False):
                    if self._tira_ancho_slot() != prev_slot_mini:
                        self._tira_recalcular_si_cambia_aspect(prev_slot_mini)
            except Exception:
                pass
            return True
        return False

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
        # B8.2: sin I/O en UI — usa cache en memoria poblada por _aplicar_previews/migracion.
        # previews_de_por_id haria stats por indice en hilo UI; se evita para no bloquear.
        # Generacion de faltantes sigue por GestorTareas/TareaPreviewsPorId.
        existentes = []
        try:
            cache = getattr(self, "_previews_cache", None)
            if isinstance(cache, (list, tuple)) and cache:
                existentes = list(cache)
            else:
                # sin cache previa: mostrar placeholders (no FS ni DB ni proceso)
                existentes = []
        except (AttributeError, TypeError, ValueError) as exc:
            print(f"[B8.2] ajustar_previews cache error: {exc}")
            existentes = []
        for i, etiqueta in enumerate(self._etiquetas_previews):
            etiqueta.setVisible(i < cantidad)
        # Mostrar solo los ya conocidos; si faltan, quedan placeholders "Generando preview…"
        self.actualizar_previews(existentes[:cantidad] if existentes else [])

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
            self._refrescar_exploracion()
            self._renderizar_marcadores()
            try:
                self._actualizar_tira_tamano_b93()
            except Exception:
                pass

    def _pixmap_ampliada(self, objeto):
        if objeto is self._imagen_miniatura:
            return self._miniatura_original
        if isinstance(objeto, PreviewConTiempo):
            return objeto._pixmap_original
        return None

    def _construir_exploracion(self):
        self._expandida = False
        # B9.2 — estado fijado (solo sesión, sin persistencia, barato)
        self._fijada = False
        self._previews_exploracion = []
        self._previews_densos = []  # B9.3 metadata ligera: {instante, ms} sin QPixmap masivo
        self._densidad_version = None
        self._densidad_ms_set = set()  # ms ints para dedup rápido
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
        self._tira_mapa_marcadores = {}
        self._menu_segmento_actual = None
        self._submenu_segmento_color_actual = None
        self._menu_marcador_actual = None
        self._submenu_marcador_color_actual = None
        self._accion_exportar_segmento_actual = None
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
        # B9.3 — Vista Dinámica|Tira (default Dinámica, solo sesión, densidad es autoridad)
        self._modo_tira_b93 = MODO_TIRA_DINAMICA
        self._selector_modo_tira = QComboBox()
        self._selector_modo_tira.setObjectName("selector_modo_tira")
        self._selector_modo_tira.addItem("Dinámica", MODO_TIRA_DINAMICA)
        self._selector_modo_tira.addItem("Tira", MODO_TIRA)
        self._selector_modo_tira.setCurrentIndex(0)
        self._selector_modo_tira.currentIndexChanged.connect(
            self._al_cambiar_modo_tira
        )
        self._boton_segmento = QPushButton("Segmento")
        self._boton_segmento.setCheckable(True)
        self._boton_segmento.setToolTip(
            "Modo crear segmento: primer clic fija A, segundo clic fija B"
        )
        self._boton_segmento.toggled.connect(self._al_toggle_segmento)
        # B9.2 — control fijar/desfijar (visible solo expandida, texto inequívoco, sin rediseño)
        self._boton_fijar = QPushButton("Fijar")
        self._boton_fijar.setObjectName("boton_fijar")
        self._boton_fijar.setCheckable(True)
        self._boton_fijar.setToolTip("Fijar tarjeta expandida")
        self._boton_fijar.setVisible(False)
        self._boton_fijar.toggled.connect(self._al_toggle_fijar)
        fila_densidad = QHBoxLayout()
        fila_densidad.addWidget(self._boton_fijar)
        fila_densidad.addStretch(1)
        fila_densidad.addWidget(self._boton_segmento)
        fila_densidad.addWidget(QLabel("Vista:"))
        fila_densidad.addWidget(self._selector_modo_tira)
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
        # B9.3 — tira virtualizada horizontal (Densidad autoridad, virtualización por viewport)
        self._tira_scroll = QScrollArea()
        self._tira_scroll.setObjectName("tira_b93_scroll")
        self._tira_scroll.setWidgetResizable(False)
        self._tira_scroll.setFrameShape(QFrame.StyledPanel)
        self._tira_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tira_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        alto_tira = dimensiones_miniatura()[1] + TIRA_B93_ALTURA_EXTRA
        self._tira_scroll.setFixedHeight(alto_tira + 8)
        self._tira_contenedor = QWidget()
        self._tira_contenedor.setObjectName("tira_b93_contenedor")
        # Sin layout: posicionamiento absoluto virtualizado
        self._tira_contenedor.setLayout(None)
        self._tira_scroll.setWidget(self._tira_contenedor)
        self._tira_previews_widgets = []  # pool virtualizado (acotado por viewport+overscan)
        self._tira_pool_indices = {}  # widget -> logical index
        self._tira_logical_ms = []  # lista ordenada ms (autoridad densidad)
        # B9.3 virtualización REAL: metadata ligera + cache visual acotada
        self._cache_visual = {}  # ms -> QPixmap acotado
        self._cache_visual_gen = 0  # token para descartar resultados viejos
        self._cache_visual_pending = set()  # ms pendientes de carga
        self._hover_instante_actual = None
        self._tira_scroll.setVisible(False)
        # virtualización: scroll y resize refrescan viewport
        try:
            self._tira_scroll.horizontalScrollBar().valueChanged.connect(self._tira_on_scroll)
            self._tira_scroll.viewport().installEventFilter(self)
            self._tira_scroll.installEventFilter(self)
            self._tira_contenedor.installEventFilter(self)
        except (AttributeError, RuntimeError):
            pass
        self._contenedor_exploracion = QWidget()
        disposicion = QVBoxLayout(self._contenedor_exploracion)
        disposicion.setContentsMargins(0, 4, 0, 0)
        disposicion.addLayout(fila_densidad)
        disposicion.addLayout(fila_color)
        disposicion.addWidget(self._franja)
        disposicion.addWidget(self._tira_scroll)
        self._contenedor_exploracion.setVisible(False)

    def _al_cambiar_color_activo(self):
        self._color_activo = self._selector_color.currentData()

    def _al_toggle_fijar(self, marcado):
        """B9.2 — fijar/desfijar tarjeta expandida (solo sesión, sin persistencia)."""
        # Solo tiene efecto si está expandida; si se colapsa por otro motivo, _set_expansion limpia.
        if not getattr(self, "_expandida", False):
            # Evitar fijar estando colapsada: reset inmediato
            if marcado:
                try:
                    self._boton_fijar.blockSignals(True)
                    self._boton_fijar.setChecked(False)
                    self._boton_fijar.setText("Fijar")
                    self._boton_fijar.setToolTip("Fijar tarjeta expandida")
                finally:
                    self._boton_fijar.blockSignals(False)
                self._fijada = False
            return
        self._fijada = bool(marcado)
        try:
            self._boton_fijar.setText("Desfijar" if self._fijada else "Fijar")
            self._boton_fijar.setToolTip("Desfijar tarjeta" if self._fijada else "Fijar tarjeta expandida")
        except (AttributeError, RuntimeError):
            pass

    def _al_cambiar_modo_tira(self, _idx=None):
        """B9.3 — Vista Dinámica vs Tira (solo sesión, densidad es autoridad)."""
        try:
            modo = self._selector_modo_tira.currentData()
        except Exception:
            modo = MODO_TIRA_DINAMICA
        if modo not in (MODO_TIRA_DINAMICA, MODO_TIRA):
            modo = MODO_TIRA_DINAMICA
        self._modo_tira_b93 = modo
        if modo == MODO_TIRA_DINAMICA:
            # B9.3/P01 — Tira→Dinámica debe liberar TODO lo visual de tira (QPixmap/pending/gen) manteniendo metadata _previews_densos
            try:
                self._cache_visual_gen += 1
            except Exception:
                self._cache_visual_gen = 1
            try:
                self._cache_visual_pending.clear()
            except Exception:
                self._cache_visual_pending = set()
            try:
                self._cache_visual.clear()
            except Exception:
                self._cache_visual = {}
            # ocultar preview dinámico visible para que se recargue bajo demanda (no conservar cache de tira por comodidad)
            try:
                self._hover_instante_actual = None
            except Exception:
                pass
            try:
                if hasattr(self, "_imagen_exploracion") and self._imagen_exploracion is not None:
                    self._imagen_exploracion.hide()
                    self._imagen_exploracion.setPixmap(QPixmap())
            except Exception:
                pass
            try:
                self._limpiar_tira_b93()
            except Exception:
                pass
            try:
                self._tira_aplicar_visibilidad_exclusiva()
            except Exception:
                pass
        else:
            try:
                self._tira_aplicar_visibilidad_exclusiva()
            except Exception:
                pass
            try:
                self._tira_actualizar_logica()
                self._tira_refrescar_viewport()
            except Exception:
                pass
        try:
            ident = self._video_id if _es_video_id_valido(self._video_id) else self._nombre
            self.modo_tira_cambiada.emit(ident, modo)
        except Exception:
            pass

    # ── B9.3 — helpers geometría compacta (aspect ratio sin FFprobe) ──
    def _tira_altura_b93(self):
        try:
            return dimensiones_miniatura()[1]
        except Exception:
            return 180

    def _tira_aspect_ratio(self):
        """Devuelve aspect ratio real del video (w/h) sin FFprobe ni I/O pesado."""
        # cache válida si proviene de dimensiones originales
        try:
            w = getattr(self, "_video_ancho", None)
            h = getattr(self, "_video_alto", None)
            if isinstance(w, int) and isinstance(h, int) and not isinstance(w, bool) and not isinstance(h, bool) and w > 0 and h > 0:
                asp = w / h
                if 0.2 < asp < 5.0:
                    self._tira_aspect_cache = asp
                    return asp
        except Exception:
            pass
        # intentar desde miniatura original ya cargada (misma fuente que preview normales)
        try:
            pm = getattr(self, "_miniatura_original", None)
            if pm is not None and not pm.isNull() and pm.height() > 0 and pm.width() > 0:
                asp = pm.width() / pm.height()
                if 0.2 < asp < 5.0:
                    return asp
        except Exception:
            pass
        # intentar desde primer preview disponible
        try:
            for et in getattr(self, "_etiquetas_previews", []) or []:
                pm2 = getattr(et, "_pixmap_original", None)
                if pm2 is not None and not pm2.isNull() and pm2.height() > 0 and pm2.width() > 0:
                    asp = pm2.width() / pm2.height()
                    if 0.2 < asp < 5.0:
                        return asp
        except Exception:
            pass
        # fallback: ratio de dimensiones_miniatura (16:9 genérico)
        try:
            aw, ah = dimensiones_miniatura()
            if ah and ah > 0:
                return aw / ah
        except Exception:
            pass
        return 16.0 / 9.0

    def _tira_ancho_slot(self):
        """Ancho visual real de miniatura a altura H manteniendo aspecto."""
        try:
            h = self._tira_altura_b93()
            asp = self._tira_aspect_ratio()
            w = int(round(h * asp))
            # limitar a valores válidos para evitar slots absurdos
            if w < 40:
                w = 40
            if w > 800:
                w = 800
            self._tira_ancho_slot_cache = w
            return w
        except Exception:
            try:
                return dimensiones_miniatura()[0]
            except Exception:
                return 320

    def _tira_stride(self):
        try:
            return self._tira_ancho_slot() + TIRA_B93_SPACING
        except Exception:
            return 322

    def _tira_aplicar_visibilidad_exclusiva(self):
        """Hace Vista exclusiva: Dinámica muestra franja, Tira muestra tira. Nunca ambas."""
        try:
            expandida = bool(getattr(self, "_expandida", False))
            modo = getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA)
            franja = getattr(self, "_franja", None)
            tira = getattr(self, "_tira_scroll", None)
            if not expandida:
                if franja is not None:
                    franja.setVisible(False)
                if tira is not None:
                    tira.setVisible(False)
                return
            if modo == MODO_TIRA:
                if franja is not None:
                    franja.setVisible(False)
                    franja.setEnabled(False)
                if tira is not None:
                    # visibilidad real depende de tener logical >0, pero si no, también ocultable
                    # _tira_actualizar_logica controlará visible según N>0; aquí habilitamos para que pueda mostrarse
                    tira.setEnabled(True)
            else:
                if tira is not None:
                    tira.setVisible(False)
                    tira.setEnabled(False)
                if franja is not None:
                    franja.setVisible(True)
                    franja.setEnabled(True)
        except Exception:
            pass

    def _es_objeto_tira_wheel(self, objeto):
        """B9.3 — helper testeable para routing wheel por zona real de la Tira.

        True únicamente para objetos pertenecientes realmente a la Tira:
        - _tira_scroll
        - _tira_scroll.viewport()
        - _tira_contenedor
        - PreviewTiraTemporal del pool vigente
        - descendientes visuales reales de esos widgets.
        False para labels/controles/contenedor de datos y cualquier zona no-Tira.
        Usa walk parentWidget() seguro, evita considerar la Tarjeta completa como ancestro.
        """
        if objeto is None:
            return False
        try:
            tira = getattr(self, "_tira_scroll", None)
            if tira is None:
                return False
            try:
                vp = tira.viewport()
            except Exception:
                vp = None
            cont = getattr(self, "_tira_contenedor", None)
            pool = getattr(self, "_tira_previews_widgets", None)
            # Construir set rápido de pool para identidad
            pool_set = set(pool) if isinstance(pool, (list, tuple)) and pool else set()
            cur = objeto
            while cur is not None:
                if cur is tira:
                    return True
                if vp is not None and cur is vp:
                    return True
                if cont is not None and cur is cont:
                    return True
                if cur in pool_set:
                    return True
                # Si cur es un preview widget (por si pool_set no contiene cur por identidad distinta), chequear clase
                # pero la identidad ya cubre; para descendientes de preview, el walk llegará al preview en iteración siguiente
                try:
                    cur = cur.parentWidget()
                except Exception:
                    break
            # Fallback con isAncestorOf para cubrir casos donde parentWidget chain no incluye todos (seguridad)
            try:
                if cont is not None and cont.isAncestorOf(objeto):
                    return True
            except Exception:
                pass
            try:
                if vp is not None and vp.isAncestorOf(objeto):
                    # viewport ancestor solo si objeto no es datos (datos no es descendant de viewport)
                    # pero viewport contiene solo cont, así que si es descendant y no fue captado por cont, igual es tira
                    if cont is None or cont.isAncestorOf(objeto) or objeto in pool_set:
                        return True
                    # Si es descendiente directo de viewport pero no de cont (ej: margen), aún es zona tira
                    # verificar que no sea scrollbar interno extraño: limitamos a objetos cuyo ancestro inmediato es viewport y está dentro del área de tira
                    # Para simplificar, si viewport es ancestro y objeto no es scrollbar vertical padre, lo dejamos como tira solo si está bajo cont
                    # Por eso requerimos cont ancestor; si no, no es tira pura
                    pass
            except Exception:
                pass
            # Pool descendants via isAncestorOf
            if pool:
                for w in pool:
                    if w is None:
                        continue
                    try:
                        if w.isAncestorOf(objeto):
                            return True
                    except Exception:
                        continue
            # Tira isAncestorOf como último recurso (pero solo si objeto está bajo cont o preview, evita falsos positivos de datos)
            # ya cubierto
        except Exception:
            return False
        return False

    def _wheel_en_corredor_vertical_datos(self, objeto, evento):
        """B9.3/P01 — corredor vertical permanente alineado con columna de datos.

        Decide SOLO por posición GLOBAL HORIZONTAL X del cursor respecto al rango
        X global visible de self._datos_widget.rect(). Tolerancia 2 px lateral por
        bordes/layout (documentado). No importa Y: el corredor se extiende de
        arriba a abajo por toda la ventana/listado. Visible real, no hardcode.
        Si _datos_widget no está visible, fallback seguro: no aplica corredor.

        Obtiene gx vía evento.globalPosition() si disponible; fallback robusto
        mediante objeto.mapToGlobal(position()) y QCursor.pos() para eventos
        sintéticos/tests.
        """
        try:
            datos = getattr(self, "_datos_widget", None)
            if datos is None:
                return False
            try:
                if not datos.isVisible():
                    return False
            except Exception:
                return False
            # obtener global X del evento
            gx = None
            try:
                if hasattr(evento, "globalPosition"):
                    gp = evento.globalPosition()
                    # QPointF
                    try:
                        gx = float(gp.x())
                    except Exception:
                        try:
                            gx = float(gp.x)
                        except Exception:
                            gx = None
                elif hasattr(evento, "globalPos"):
                    gp = evento.globalPos()
                    gx = float(gp.x())
                elif hasattr(evento, "globalPositionF"):
                    gx = float(evento.globalPositionF().x())
            except Exception:
                gx = None
            if gx is None:
                # fallback: mapear position local del objeto a global
                try:
                    if hasattr(evento, "position"):
                        lp = evento.position()
                        if objeto is not None and hasattr(objeto, "mapToGlobal"):
                            try:
                                if hasattr(lp, "toPoint"):
                                    pt = lp.toPoint()
                                else:
                                    pt = QPoint(int(lp.x()), int(lp.y()))
                                gp2 = objeto.mapToGlobal(pt)
                                gx = float(gp2.x())
                            except Exception:
                                pass
                        if gx is None:
                            try:
                                gx = float(QCursor.pos().x())
                            except Exception:
                                pass
                    elif hasattr(evento, "pos"):
                        lp = evento.pos()
                        try:
                            gp2 = objeto.mapToGlobal(lp)
                            gx = float(gp2.x())
                        except Exception:
                            pass
                except Exception:
                    gx = None
            if gx is None:
                return False
            # rango global horizontal de datos_widget (ancho visible real)
            try:
                top_left = datos.mapToGlobal(QPoint(0, 0))
                left = float(top_left.x())
                w = float(datos.width())
                if w <= 0:
                    try:
                        w = float(datos.rect().width())
                    except Exception:
                        w = 240.0
                right = left + w
                tol = 2.0  # tolerancia lateral documentada B9.3/P01
                left -= tol
                right += tol
                return left <= gx <= right
            except Exception:
                return False
        except Exception:
            return False

    def _tira_recalcular_si_cambia_aspect(self, prev_ancho_slot=None):
        """Si el aspect cambió respecto a prev_ancho_slot, recalcular preservando posición temporal visible."""
        try:
            if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) != MODO_TIRA:
                return False
            if not getattr(self, "_expandida", False):
                return False
            nuevo = self._tira_ancho_slot()
            if prev_ancho_slot is not None and nuevo == prev_ancho_slot:
                return False
            # preservar fracción de scroll
            try:
                scroll = getattr(self, "_tira_scroll", None)
                if scroll is not None:
                    hbar = scroll.horizontalScrollBar()
                    max_old = hbar.maximum()
                    val_old = hbar.value()
                    frac = (val_old / max_old) if max_old > 0 else 0.0
                else:
                    frac = 0.0
                # recalcular geometría y viewport (usará nuevo ancho_slot)
                self._tira_actualizar_logica()
                self._tira_refrescar_viewport()
                # restaurar fracción
                if scroll is not None:
                    hbar2 = scroll.horizontalScrollBar()
                    max_new = hbar2.maximum()
                    new_val = int(round(frac * max_new))
                    hbar2.setValue(new_val)
                    self._tira_refrescar_viewport()
                return True
            except Exception:
                try:
                    self._tira_actualizar_logica()
                    self._tira_refrescar_viewport()
                except Exception:
                    pass
                return True
        except Exception:
            return False

    # ── B9.3 — tira virtualizada: autoridad Densidad, 1 conjunto temporal ──
    def _tira_actualizar_logica(self):
        """Recalcula _tira_logical_ms según densidad vigente y actualiza geometría lógica."""
        if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) != MODO_TIRA:
            try:
                sc = getattr(self, "_tira_scroll", None)
                if sc is not None:
                    sc.setVisible(False)
            except Exception:
                pass
            return
        if not getattr(self, "_expandida", False):
            return
        # densidad autoridad
        densidad = getattr(self, "_densidad_manual", None)
        dur = getattr(self, "_duracion", None)
        logical = _ms_tira_densidad_ordenada(dur, densidad)
        self._tira_logical_ms = logical
        # B9.3/029 — recalcular mapa marcador→sample al cambiar logical
        try:
            self._reconstruir_mapa_marcadores_tira()
        except Exception:
            pass
        # geometría lógica compacta: ancho_slot real según aspecto
        try:
            # preservar fracción de scroll si ya existe geometría previa (tamaño miniatura cambió)
            prev_frac = None
            prev_scroll = None
            try:
                _prev_scroll = getattr(self, "_tira_scroll", None)
                if _prev_scroll is not None:
                    _hbar_prev = _prev_scroll.horizontalScrollBar()
                    _max_prev = _hbar_prev.maximum()
                    _val_prev = _hbar_prev.value()
                    if _max_prev > 0:
                        prev_frac = _val_prev / _max_prev
                        prev_scroll = _prev_scroll
            except Exception:
                prev_frac = None
            ancho_slot = self._tira_ancho_slot()
            spacing = TIRA_B93_SPACING
            margins_total = TIRA_B93_MARGIN * 2
            n = len(logical)
            total_ancho = n * ancho_slot + max(0, n - 1) * spacing + margins_total
            cont = getattr(self, "_tira_contenedor", None)
            scroll = getattr(self, "_tira_scroll", None)
            if cont is not None:
                cont.setFixedWidth(max(total_ancho, 120))
                cont.setFixedHeight(scroll.height() - 8 if scroll and scroll.height() > 0 else dimensiones_miniatura()[1] + TIRA_B93_ALTURA_EXTRA)
            if scroll is not None:
                # respetar exclusividad: si Tira visible, mostrar; si no, ya oculto por _tira_aplicar
                if n > 0:
                    scroll.setVisible(True)
                else:
                    scroll.setVisible(False)
                # actualizar rango scrollbar preservando fracción si hubo cambio de ancho_slot/tamaño
                try:
                    hbar = scroll.horizontalScrollBar()
                    hbar.setRange(0, max(0, total_ancho - scroll.viewport().width()))
                    if prev_frac is not None and prev_scroll is scroll and hbar.maximum() > 0:
                        hbar.setValue(int(round(prev_frac * hbar.maximum())))
                except Exception:
                    pass
        except Exception:
            pass

    def _tira_pixmap_para_ms(self, ms):
        """Obtiene QPixmap para ms desde cache visual (metadata pura no retiene pixmap)."""
        try:
            pm = getattr(self, "_cache_visual", {}).get(ms)
            if pm is not None and not pm.isNull():
                return pm
        except Exception:
            pass
        return None

    def _ms_visuales_necesarios(self):
        """Calcula conjunto requerido derivado de necesidad actual (viewport+overscan y vecindario dinámico)."""
        requeridos = set()
        # Tira: índices visibles + overscan calculado por viewport
        if getattr(self, "_expandida", False) and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
            logical = getattr(self, "_tira_logical_ms", []) or []
            n = len(logical)
            if n > 0:
                try:
                    ancho_slot = self._tira_ancho_slot()
                    spacing = TIRA_B93_SPACING
                    vp_w = self._tira_scroll.viewport().width() if hasattr(self, "_tira_scroll") and self._tira_scroll.viewport() else 800
                    if vp_w <= 0:
                        vp_w = 800
                    visible = max(1, (vp_w + spacing) // (ancho_slot + spacing) + 1)
                    overscan = visible
                    # compensar margen inicial
                    scroll_val = self._tira_scroll.horizontalScrollBar().value() if hasattr(self, "_tira_scroll") else 0
                    stride = ancho_slot + spacing
                    # scroll_val incluye margen inicial TIRA_B93_MARGIN, descontarlo para índice
                    eff_scroll = max(0, scroll_val - TIRA_B93_MARGIN)
                    first_visible = max(0, eff_scroll // stride) if stride > 0 else 0
                    last_visible = min(n - 1, first_visible + visible - 1)
                    first = max(0, first_visible - overscan)
                    last = min(n - 1, last_visible + overscan)
                    for idx in range(first, last + 1):
                        requeridos.add(logical[idx])
                except Exception:
                    pass
        # Dinámica: frame actual + vecindario pequeño derivado de uso dinámico
        try:
            hover = getattr(self, "_hover_instante_actual", None)
            if isinstance(hover, (int, float)) and not isinstance(hover, bool):
                ms_hover = self._ms_mas_cercano(hover)
                if isinstance(ms_hover, int) and ms_hover > 0:
                    requeridos.add(ms_hover)
                    try:
                        logical_dyn = getattr(self, "_tira_logical_ms", []) or sorted([d.get("ms") for d in self._previews_densos if isinstance(d.get("ms"), int)])
                        if ms_hover in logical_dyn:
                            idx = logical_dyn.index(ms_hover)
                            for off in (-2, -1, 1, 2):
                                j = idx + off
                                if 0 <= j < len(logical_dyn):
                                    requeridos.add(logical_dyn[j])
                    except Exception:
                        pass
        except Exception:
            pass
        return requeridos

    def _sincronizar_cache_visual(self):
        """Expulsa todo QPixmap fuera del conjunto requerido y limpia pending no vigente."""
        requeridos = self._ms_visuales_necesarios()
        # Si no hay requeridos (colapsada o sin viewport), vaciar cache si corresponde será manejado por colapso
        # pero para estabilidad, si requeridos vacío y expandida en Tira sin geometría, no evictar agresivo
        # Solo evictar lo fuera de requeridos cuando requeridos no vacío o estamos en Dinámica con hover
        if requeridos:
            try:
                for ms in list(getattr(self, "_cache_visual", {}).keys()):
                    if ms not in requeridos:
                        del self._cache_visual[ms]
            except Exception:
                pass
            try:
                cur_pending = getattr(self, "_cache_visual_pending", set()) or set()
                self._cache_visual_pending = set(m for m in cur_pending if m in requeridos and m not in self._cache_visual)
            except Exception:
                self._cache_visual_pending = set()
        else:
            # B9.3/P01 — si Vista=Dinámica y no hay hover/requeridos, cache visual densa =0 (no dejar pass que conserve residuo)
            try:
                if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) != MODO_TIRA and getattr(self, "_hover_instante_actual", None) is None:
                    try:
                        self._cache_visual.clear()
                    except Exception:
                        self._cache_visual = {}
                    try:
                        self._cache_visual_pending.clear()
                    except Exception:
                        self._cache_visual_pending = set()
            except Exception:
                pass

    def _tira_estimar_pool(self):
        """Calcula pool_size necesario: visible + 1 pantalla extra por lado."""
        try:
            ancho_slot = self._tira_ancho_slot()
            spacing = TIRA_B93_SPACING
            vp_w = self._tira_scroll.viewport().width() if hasattr(self, "_tira_scroll") and self._tira_scroll.viewport() else 800
            if vp_w <= 0:
                vp_w = 800
            visible = max(1, (vp_w + spacing) // (ancho_slot + spacing) + 1)
            overscan = visible  # 1 pantalla extra por lado
            pool_needed = visible + 2 * overscan
            # acotar por N lógico
            n = len(getattr(self, "_tira_logical_ms", []) or [])
            pool_needed = min(pool_needed, n)
            pool_needed = max(pool_needed, min(8, n))  # mínimo razonable
            return pool_needed, visible, ancho_slot, spacing
        except Exception:
            return 12, 6, 320, 2

    def _tira_asegurar_pool(self, pool_needed):
        """Asegura que _tira_previews_widgets tenga pool_needed widgets."""
        cur = len(getattr(self, "_tira_previews_widgets", []) or [])
        if cur >= pool_needed:
            # si sobran muchos, recortar? mantener acotado
            if cur > pool_needed + 4:
                for w in list(self._tira_previews_widgets[pool_needed:]):
                    try:
                        w.hide(); w.close(); w.setParent(None); w.deleteLater()
                    except Exception:
                        pass
                self._tira_previews_widgets = self._tira_previews_widgets[:pool_needed]
            return
        for _ in range(pool_needed - cur):
            w = PreviewTiraTemporal(self._tira_contenedor)
            w.installEventFilter(self)
            # B9.3/029 — conectar señales de tira una sola vez por widget (sin lambdas index)
            try:
                w.tira_left_clicked.connect(self._on_tira_left_clicked)
                w.tira_right_clicked.connect(self._on_tira_right_clicked)
            except Exception:
                pass
            w.hide()
            self._tira_previews_widgets.append(w)

    def _tira_refrescar_viewport(self):
        """Virtualiza: asigna widgets visibles + overscan a índices lógicos."""
        if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) != MODO_TIRA:
            return
        if not getattr(self, "_expandida", False):
            return
        logical = getattr(self, "_tira_logical_ms", None)
        if logical is None:
            self._tira_actualizar_logica()
            logical = getattr(self, "_tira_logical_ms", []) or []
        n = len(logical)
        if n == 0:
            try:
                self._tira_scroll.setVisible(False)
            except Exception:
                pass
            return
        # asegurar contenedor visible
        try:
            self._tira_scroll.setVisible(True)
        except Exception:
            pass
        pool_needed, visible, ancho_slot, spacing = self._tira_estimar_pool()
        self._tira_asegurar_pool(pool_needed)
        # calcular rango visible (compensar margen inicial)
        try:
            scroll_val = self._tira_scroll.horizontalScrollBar().value() if hasattr(self, "_tira_scroll") else 0
        except Exception:
            scroll_val = 0
        stride = ancho_slot + spacing
        eff_scroll = max(0, scroll_val - TIRA_B93_MARGIN)
        first_visible = max(0, eff_scroll // stride) if stride > 0 else 0
        last_visible = min(n - 1, first_visible + visible - 1)
        overscan = visible
        first = max(0, first_visible - overscan)
        last = min(n - 1, last_visible + overscan)
        needed = last - first + 1
        # ajustar pool si needed != pool_needed (por cambio tamaño)
        if needed != len(self._tira_previews_widgets):
            # re-asegurar
            self._tira_asegurar_pool(needed)
            # recalc needed might differ
            if len(self._tira_previews_widgets) != needed:
                # si n pequeño, usar n
                needed = min(needed, len(self._tira_previews_widgets))
                last = first + needed - 1
        # B9.3 virtualización REAL: mapa ms->pixmap desde _cache_visual (acotada por necesidad)
        dens_map = {}
        try:
            for ms, pm in getattr(self, "_cache_visual", {}).items():
                if pm is not None and not pm.isNull():
                    dens_map[ms] = pm
        except Exception:
            pass
        # sincronizar cache según necesidad actual antes de detectar misses
        try:
            self._sincronizar_cache_visual()
            # reconstruir dens_map tras sincronizar
            dens_map = {ms: pm for ms, pm in getattr(self, "_cache_visual", {}).items() if pm is not None and not pm.isNull()}
        except Exception:
            pass
        # detectar misses del viewport para encolar background batch
        misses = []
        try:
            for logical_idx in range(first, last + 1):
                ms = logical[logical_idx]
                if ms not in dens_map and ms not in getattr(self, "_cache_visual_pending", set()):
                    misses.append(ms)
            if misses:
                batch = misses[:12]
                for m in batch:
                    self._cache_visual_pending.add(m)
                try:
                    self._cache_visual_gen += 1
                except Exception:
                    self._cache_visual_gen = 1
                payload = {"video_id": getattr(self, "_video_id", None), "version": getattr(self, "_densidad_version", None), "ms_lista": batch, "request_id": self._cache_visual_gen, "gen": self._cache_visual_gen}
                self.preview_visual_solicitada.emit(payload)
        except Exception:
            pass
        # asegurar mapa marcadores actualizado antes de bind (no sobre-optimizar, O(Nmark*Nsamples) pequeño)
        try:
            self._reconstruir_mapa_marcadores_tira()
        except Exception:
            pass
        try:
            pendiente_ms_global = self._tira_ms_pendiente_logico()
        except Exception:
            pendiente_ms_global = None
        # asignar widgets
        for i, w in enumerate(self._tira_previews_widgets):
            logical_idx = first + i
            if logical_idx > last or logical_idx >= n:
                try:
                    w.hide()
                    w.clear_tira()
                except Exception:
                    try:
                        w._pixmap = None
                        w.update()
                    except Exception:
                        pass
                continue
            ms = logical[logical_idx]
            instante = ms / 1000.0
            pixmap = dens_map.get(ms)
            tiempo_txt = formatear_tiempo(instante) if _duracion_valida(self._duracion) else None
            # datos ligeros de marcador/segmento para este sample (sin duplicar QPixmap)
            try:
                marcadores_ms = self._marcadores_para_sample_tira(ms)
            except Exception:
                marcadores_ms = []
            try:
                segmentos_ms = self._segmentos_para_sample_tira(ms)
            except Exception:
                segmentos_ms = []
            # posición absoluta compacta
            x = TIRA_B93_MARGIN + logical_idx * stride
            y = TIRA_B93_MARGIN
            h = dimensiones_miniatura()[1]
            try:
                w.setFixedHeight(h)
                w.setFixedWidth(ancho_slot)
                w.move(x, y)
                # set preview (si pixmap None -> mostrar placeholder sin pixmap)
                if pixmap is not None and not pixmap.isNull():
                    w.set_preview(pixmap, tiempo_txt)
                else:
                    # placeholder: sin pixmap, solo timestamp
                    w._pixmap = None
                    w._tiempo = tiempo_txt
                    w.update()
                # binding ligero SIEMPRE limpia estado anterior (reciclado) y asigna marcadores/segmentos reales
                pendiente = (pendiente_ms_global is not None and int(ms) == int(pendiente_ms_global))
                try:
                    w.bind_tira(ms, marcadores_ms, segmentos_ms, pendiente)
                except Exception:
                    # fallback directo
                    w._logical_ms = ms
                    w._marcadores_tira = list(marcadores_ms)
                    w._segmentos_tira = list(segmentos_ms)
                    w._pendiente_tira = bool(pendiente)
                    w.update()
                w.show()
                w.raise_()
            except Exception:
                pass
        # actualizar altura contenedor si cambió tamaño miniatura
        try:
            alto = dimensiones_miniatura()[1]
            cont = getattr(self, "_tira_contenedor", None)
            if cont is not None:
                cont.setFixedHeight(alto + TIRA_B93_ALTURA_EXTRA)
        except Exception:
            pass

    def _tira_on_scroll(self, _val=None):
        try:
            self._tira_refrescar_viewport()
        except Exception:
            pass

    # Compat: alias antiguo
    def _poblar_tira_b93(self):
        self._tira_actualizar_logica()
        self._tira_refrescar_viewport()

    def _limpiar_tira_b93(self):
        """Libera pool virtualizado (JPEG en disco permanece, _previews_densos intactos)."""
        try:
            for w in list(getattr(self, "_tira_previews_widgets", []) or []):
                try:
                    w.hide()
                    w.close()
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass
            self._tira_previews_widgets = []
            self._tira_pool_indices = {}
        except Exception:
            self._tira_previews_widgets = []
        try:
            self._tira_logical_ms = []
        except Exception:
            pass
        try:
            if hasattr(self, "_tira_scroll") and self._tira_scroll is not None:
                self._tira_scroll.setVisible(False)
        except Exception:
            pass
        try:
            QApplication.processEvents()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            QApplication.processEvents()
        except Exception:
            pass

    def _actualizar_tira_tamano_b93(self):
        """Reajusta tira al cambiar tamaño miniaturas sin I/O (repintado virtualizado)."""
        try:
            alto = dimensiones_miniatura()[1]
            if hasattr(self, "_tira_scroll") and self._tira_scroll is not None:
                self._tira_scroll.setFixedHeight(alto + TIRA_B93_ALTURA_EXTRA + 8)
                if hasattr(self, "_tira_contenedor") and self._tira_contenedor is not None:
                    self._tira_contenedor.setFixedHeight(alto + TIRA_B93_ALTURA_EXTRA)
            # recalcular geometría lógica y viewport
            self._tira_actualizar_logica()
            self._tira_refrescar_viewport()
            # también reajustar pixmaps en pool
            for w in getattr(self, "_tira_previews_widgets", []) or []:
                try:
                    w.reajustar()
                except Exception:
                    pass
        except Exception:
            pass

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
        self.densidad_cambiada.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, valor)

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
        # B9.3 — densidad autoridad: actualizar tira virtualizada sin reconstruir tarjeta
        try:
            if getattr(self, "_expandida", False) and getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                self._tira_actualizar_logica()
                self._tira_refrescar_viewport()
        except Exception:
            pass

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
            # B9.2 — mostrar control fijar con estado actual
            try:
                if hasattr(self, "_boton_fijar"):
                    self._boton_fijar.setVisible(True)
                    self._boton_fijar.blockSignals(True)
                    self._boton_fijar.setChecked(bool(getattr(self, "_fijada", False)))
                    self._boton_fijar.setText("Desfijar" if getattr(self, "_fijada", False) else "Fijar")
                    self._boton_fijar.setToolTip("Desfijar tarjeta" if getattr(self, "_fijada", False) else "Fijar tarjeta expandida")
                    self._boton_fijar.blockSignals(False)
            except (AttributeError, RuntimeError):
                pass
            self._preparar_exploracion()
            try:
                self._tira_aplicar_visibilidad_exclusiva()
            except Exception:
                pass
            # B9.3 — tira virtualizada se inicializa en _preparar_exploracion
            pass
        else:
            # B9.2 — colapso manual desfija automáticamente (sin persistencia)
            if getattr(self, "_fijada", False):
                self._fijada = False
                try:
                    if hasattr(self, "_boton_fijar"):
                        self._boton_fijar.blockSignals(True)
                        self._boton_fijar.setChecked(False)
                        self._boton_fijar.setText("Fijar")
                        self._boton_fijar.setToolTip("Fijar tarjeta expandida")
                        self._boton_fijar.blockSignals(False)
                except (AttributeError, RuntimeError):
                    pass
            try:
                if hasattr(self, "_boton_fijar"):
                    self._boton_fijar.setVisible(False)
            except (AttributeError, RuntimeError):
                pass
            self._contenedor_exploracion.setVisible(False)
            self._previews_exploracion = []
            self._previews_densos = []
            self._densidad_version = None
            self._densidad_ms_set = set()
            # B9.3 virtualización REAL: invalidar requests y vaciar cache visual
            try:
                self._cache_visual_gen += 1
            except Exception:
                self._cache_visual_gen = 1
            try:
                self._cache_visual.clear()
            except Exception:
                self._cache_visual = {}
            try:
                self._cache_visual_pending.clear()
            except Exception:
                self._cache_visual_pending = set()
            self._hover_instante_actual = None
            # B9.3 — liberar tira expandida al colapsar (disco permanece)
            try:
                self._limpiar_tira_b93()
            except Exception:
                pass
            self._imagen_exploracion.setPixmap(QPixmap())
            self._imagen_exploracion.hide()
            self._cancelar_extremo_segmento()
            barra = getattr(self, "_barra_colapsada", None)
            if barra is not None:
                barra.setVisible(True)
                self._sincronizar_barra_colapsada()
        self.expansion_cambiada.emit(self._video_id if _es_video_id_valido(self._video_id) else self._nombre, valor)

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
        # B9.3 — Vista exclusiva + si Vista=Tira, inicializar lógica virtualizada
        try:
            self._tira_aplicar_visibilidad_exclusiva()
            if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                self._tira_actualizar_logica()
                self._tira_refrescar_viewport()
        except Exception:
            pass
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
        """B9.3 virtualización: cache hit inmediato, considera preview vs denso con tie-break preview. Solo cache_visual para densos."""
        if not isinstance(instante, (int, float)) or isinstance(instante, bool):
            return None
        if not self._previews_densos:
            disponibles = self._previews_exploracion
            indice = preview_mas_cercana([d["instante"] for d in disponibles], instante)
            if indice is None:
                return None
            return disponibles[indice].get("pixmap_escalado")
        mejor = None
        mejor_clave = None
        for entrada in self._previews_exploracion or []:
            tiempo = entrada.get("instante")
            if not isinstance(tiempo, (int, float)) or isinstance(tiempo, bool):
                continue
            pm = entrada.get("pixmap_escalado")
            if pm is None or pm.isNull():
                continue
            clave = (abs(float(tiempo) - float(instante)), False)
            if mejor_clave is None or clave < mejor_clave:
                mejor_clave = clave
                mejor = pm
        for d in self._previews_densos or []:
            tiempo = d.get("instante")
            if not isinstance(tiempo, (int, float)) or isinstance(tiempo, bool):
                continue
            ms = d.get("ms")
            if not isinstance(ms, int):
                try:
                    ms = round(float(tiempo) * 1000)
                except Exception:
                    continue
            pm = None
            try:
                pm = self._cache_visual.get(ms)
            except Exception:
                pm = None
            if pm is None or (hasattr(pm, "isNull") and pm.isNull()):
                continue
            clave = (abs(float(tiempo) - float(instante)), True)
            if mejor_clave is None or clave < mejor_clave:
                mejor_clave = clave
                mejor = pm
        return mejor

    def _ms_mas_cercano(self, instante):
        try:
            from exploracion_temporal import fotograma_mas_cercano as _fmc
            ms_lista = [d.get("ms") for d in self._previews_densos if isinstance(d.get("ms"), int)]
            if not ms_lista:
                ms_lista = [round(float(d["instante"])*1000) for d in self._previews_densos if isinstance(d.get("instante"), (int,float)) and not isinstance(d.get("instante"), bool)]
            return _fmc(ms_lista, instante)
        except Exception:
            return None

    def _solicitar_visual_si_falta(self, ms):
        """Encola background para ms y vecinos si no está en cache ni pending (sin límite fijo)."""
        if not isinstance(ms, int) or ms <= 0:
            return
        if ms in self._cache_visual:
            return
        if ms in getattr(self, "_cache_visual_pending", set()):
            return
        try:
            self._cache_visual_gen += 1
        except Exception:
            self._cache_visual_gen = 1
        req = self._cache_visual_gen
        vecinos = []
        try:
            logical = getattr(self, "_tira_logical_ms", []) or sorted([d.get("ms") for d in self._previews_densos if isinstance(d.get("ms"), int)])
            if ms in logical:
                idx = logical.index(ms)
                for off in (-2, -1, 1, 2):
                    j = idx + off
                    if 0 <= j < len(logical):
                        vecinos.append(logical[j])
        except Exception:
            vecinos = []
        ms_list = [ms] + [v for v in vecinos if v not in self._cache_visual and v not in self._cache_visual_pending]
        ms_list = ms_list[:5]
        # pending representa requests actuales; sin pop arbitrario
        for m in ms_list:
            self._cache_visual_pending.add(m)
        try:
            payload = {"video_id": getattr(self, "_video_id", None), "version": getattr(self, "_densidad_version", None), "ms_lista": ms_list, "request_id": req, "gen": req}
            self.preview_visual_solicitada.emit(payload)
        except Exception:
            pass


    def agregar_fotogramas_densos(self, densos):
        """B9.3 virtualización REAL: _previews_densos SIEMPRE metadata ligera {instante,ms} sin QPixmap."""
        if not densos:
            return False
        existentes_inst = {round(float(d.get("instante", 0)), 6) for d in self._previews_densos if isinstance(d.get("instante"), (int, float)) and not isinstance(d.get("instante"), bool)}
        nuevos = False
        for entrada in densos:
            instante = entrada.get("instante")
            if not (isinstance(instante, (int, float)) and not isinstance(instante, bool)):
                continue
            clave = round(float(instante), 6)
            if clave in existentes_inst:
                continue
            # B9.3 metadata pura: si entrada trae pixmap, validar que sea no nulo (compat filtrado histórico) pero no retener
            if "pixmap" in entrada:
                pm = entrada.get("pixmap")
                if pm is None or (hasattr(pm, "isNull") and pm.isNull()):
                    continue
            ms = round(float(instante) * 1000)
            self._previews_densos.append({"instante": float(instante), "ms": ms})
            existentes_inst.add(clave)
            self._densidad_ms_set.add(ms)
            nuevos = True
        if nuevos and self._expandida:
            self._refrescar_exploracion()
            try:
                if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                    self._tira_refrescar_viewport()
            except Exception:
                pass
        return nuevos

    def set_metadata_densa(self, ms_lista, version=None):
        """B9.3: establece metadata ligera para N tiempos sin QPixmap. Retorna True si hubo nuevos."""
        if not ms_lista:
            return False
        if version is not None:
            self._densidad_version = version
        nuevos = False
        existentes_ms = set(getattr(self, "_densidad_ms_set", set())) | {d.get("ms") for d in self._previews_densos if isinstance(d.get("ms"), int)}
        # también reconstruir desde _previews_densos instantes si ms no está
        for d in list(self._previews_densos):
            if "ms" not in d and isinstance(d.get("instante"), (int,float)):
                try:
                    d["ms"] = round(float(d["instante"])*1000)
                except Exception:
                    pass
        for ms in ms_lista:
            if not isinstance(ms, int) or isinstance(ms, bool) or ms <0:
                continue
            if ms in existentes_ms:
                continue
            instante = ms/1000.0
            self._previews_densos.append({"instante": instante, "ms": ms})
            existentes_ms.add(ms)
            nuevos = True
        self._densidad_ms_set = existentes_ms
        # Ordenar por instante para facilitar fotograma_mas_cercano aunque metadata puede venir en orden bisección
        try:
            self._previews_densos.sort(key=lambda d: d.get("instante", 0))
        except Exception:
            pass
        # actualizar lógica tira
        try:
            if getattr(self, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                self._tira_actualizar_logica()
                self._tira_refrescar_viewport()
        except Exception:
            pass
        return nuevos

    def _mostrar_preview_para_instante(self, instante):
        # B9.3: cache hit inmediato, miss encola background sin JPEG síncrono
        # Si hay metadata densa, verificar cache visual directamente para decidir miss y encolar
        if self._previews_densos and isinstance(instante, (int,float)) and not isinstance(instante,bool):
            ms = self._ms_mas_cercano(instante)
            if ms is not None:
                pm_cache = None
                try:
                    pm_cache = self._cache_visual.get(ms)
                except Exception:
                    pm_cache = None
                if pm_cache is not None and not pm_cache.isNull():
                    self._hover_instante_actual = instante
                    self._imagen_exploracion.setPixmap(pm_cache)
                    self._imagen_exploracion.setFixedSize(pm_cache.size())
                    self._imagen_exploracion.setText("")
                    self._imagen_exploracion.show()
                    self._posicionar_preview(instante)
                    return
                # miss -> encolar background
                self._solicitar_visual_si_falta(ms)
                self._hover_instante_actual = instante
                # fallback a preview si existe, sino ocultar
                pix_preview = None
                try:
                    idx = preview_mas_cercana([d["instante"] for d in self._previews_exploracion], instante)
                    if idx is not None:
                        pix_preview = self._previews_exploracion[idx].get("pixmap_escalado")
                except Exception:
                    pix_preview = None
                if pix_preview is not None and not pix_preview.isNull():
                    self._imagen_exploracion.setPixmap(pix_preview)
                    self._imagen_exploracion.setFixedSize(pix_preview.size())
                    self._imagen_exploracion.setText("")
                    self._imagen_exploracion.show()
                    self._posicionar_preview(instante)
                else:
                    self._imagen_exploracion.setPixmap(QPixmap())
                    self._imagen_exploracion.setText("")
                    self._imagen_exploracion.hide()
                return
        # fallback sin metadata o instante inválido
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

    # ── B9.3/029 — asociación marcador/segmento → sample tira (helpers testeables) ──
    def _reconstruir_mapa_marcadores_tira(self):
        """Construye mapa sample_ms -> [marcadores reales] con criterio determinista."""
        mapa = {}
        logical = getattr(self, "_tira_logical_ms", None) or []
        if not logical or not getattr(self, "_marcadores", None):
            self._tira_mapa_marcadores = mapa
            return mapa
        # para cada marcador real encontrar sample más cercano (tie menor ms)
        for marcador in self._marcadores:
            try:
                t = float(marcador.get("tiempo", 0))
            except Exception:
                continue
            t_ms = int(round(t * 1000))
            best = None
            best_dist = None
            for sample in logical:
                try:
                    dist = abs(int(sample) - t_ms)
                except Exception:
                    continue
                if best_dist is None or dist < best_dist or (dist == best_dist and sample < best):
                    best_dist = dist
                    best = sample
            if best is not None:
                mapa.setdefault(int(best), []).append(marcador)
        # ordenar listas por tiempo real asc para determinismo
        for k in list(mapa.keys()):
            try:
                mapa[k] = sorted(mapa[k], key=lambda m: float(m.get("tiempo", 0)))
            except Exception:
                pass
        self._tira_mapa_marcadores = mapa
        return mapa

    def _marcadores_para_sample_tira(self, ms):
        """Devuelve marcadores reales asociados al sample lógico `ms` (int ms)."""
        try:
            ms = int(ms)
        except Exception:
            return []
        mapa = getattr(self, "_tira_mapa_marcadores", None)
        if mapa is None:
            mapa = self._reconstruir_mapa_marcadores_tira()
        lst = mapa.get(ms)
        if lst is None:
            # fallback: recalcular si mapa vacío pero logical cambió sin reconstruir
            # verificar si mapa fue construido con logical viejo
            logical = getattr(self, "_tira_logical_ms", None) or []
            if logical and ms in logical:
                # reconstruir y reintentar
                mapa = self._reconstruir_mapa_marcadores_tira()
                lst = mapa.get(ms, [])
            else:
                lst = []
        return list(lst) if lst else []

    def _segmentos_para_sample_tira(self, ms):
        """Devuelve segmentos reales que contienen al sample `ms` (inicio <= ms/1000 <= fin)."""
        try:
            ms_i = int(ms)
            t = ms_i / 1000.0
        except Exception:
            return []
        res = []
        for seg in getattr(self, "_segmentos", []) or []:
            try:
                inicio = float(seg.get("inicio"))
                fin = float(seg.get("fin"))
            except Exception:
                continue
            # tolerancia 1e-9 si contrato la exige; sin alterar tiempos
            if inicio - 1e-9 <= t <= fin + 1e-9:
                # clamp exacto: si fuera por tolerancia, aún devolver real con tiempos originales
                if inicio <= t <= fin or abs(t - inicio) < 1e-7 or abs(t - fin) < 1e-7:
                    res.append(seg)
                else:
                    # tolerancia leve pero devolver igual si dentro de epsilon
                    res.append(seg)
        # orden determinista: inicio asc, fin asc, id asc
        try:
            res.sort(key=lambda s: (float(s.get("inicio", 0)), float(s.get("fin", 0)), int(s.get("id") or 0)))
        except Exception:
            pass
        return res

    def _tira_actualizar_decoraciones(self):
        """Refresca decoraciones de widgets visibles tras mutación marcadores/segmentos/densidad."""
        try:
            self._reconstruir_mapa_marcadores_tira()
        except Exception:
            pass
        # actualizar cada widget visible con nuevo bind sin reconstruir pool
        logical = getattr(self, "_tira_logical_ms", None) or []
        if not logical:
            return
        pendiente_ms = self._tira_ms_pendiente_logico()
        # mapa inverso logical_idx -> ms ya conocido
        for w in getattr(self, "_tira_previews_widgets", []) or []:
            try:
                ms = getattr(w, "_logical_ms", None)
                if ms is None:
                    continue
                if ms not in logical:
                    continue
                marcadores = self._marcadores_para_sample_tira(ms)
                segmentos = self._segmentos_para_sample_tira(ms)
                pendiente = (pendiente_ms is not None and int(ms) == int(pendiente_ms))
                w.bind_tira(ms, marcadores, segmentos, pendiente)
            except Exception:
                continue

    def _tira_ms_pendiente_logico(self):
        """Devuelve el sample lógico ms que representa visualmente el extremo A pendiente, o None.

        Usa _extremo_segmento autoritativo (segundos) y busca el sample más cercano en _tira_logical_ms.
        Si el extremo coincide exactamente con un sample, lo retorna exacto; si no, el más cercano
        (tie: menor ms) solo para representación visual, sin modificar el tiempo real almacenado.
        Solo tiene efecto si _modo_crear_segmento activo y existe pendiente.
        """
        try:
            if not getattr(self, "_modo_crear_segmento", False):
                return None
            extremo = getattr(self, "_extremo_segmento", None)
            if extremo is None:
                return None
            if not isinstance(extremo, (int, float)) or isinstance(extremo, bool):
                return None
            logical = getattr(self, "_tira_logical_ms", None) or []
            if not logical:
                return None
            t_ms = int(round(float(extremo) * 1000))
            if t_ms in logical:
                return int(t_ms)
            # buscar más cercano
            best = None
            best_dist = None
            for s in logical:
                try:
                    dist = abs(int(s) - t_ms)
                except Exception:
                    continue
                if best_dist is None or dist < best_dist or (dist == best_dist and int(s) < int(best)):
                    best_dist = dist
                    best = s
            return int(best) if best is not None else None
        except Exception:
            return None

    def _tira_actualizar_pendiente(self):
        """Actualiza solo la decoración pendiente en widgets visibles sin tocar marcadores/segmentos."""
        try:
            pendiente_ms = self._tira_ms_pendiente_logico()
            for w in getattr(self, "_tira_previews_widgets", []) or []:
                try:
                    ms = getattr(w, "_logical_ms", None)
                    if ms is None:
                        continue
                    # si widget no tiene logical (clear_tira) asegurar sin pendiente
                    if pendiente_ms is not None and int(ms) == int(pendiente_ms):
                        if not getattr(w, "_pendiente_tira", False):
                            w.set_pendiente_tira(True)
                    else:
                        if getattr(w, "_pendiente_tira", False):
                            w.set_pendiente_tira(False)
                except Exception:
                    continue
        except Exception:
            pass

    def _on_tira_left_clicked(self, logical_ms):
        """Left click sobre miniatura tira: crea marcador o extremo segmento según modo."""
        try:
            t = float(int(logical_ms)) / 1000.0
        except Exception:
            return
        if getattr(self, "_modo_crear_segmento", False):
            self._al_extremo_segmento_solicitado(t)
        else:
            self._al_marcador_solicitado(t)

    def _on_tira_right_clicked(self, logical_ms, global_pos):
        """Right/context sobre tira: abre menú real de marcador/segmento asociado."""
        try:
            ms = int(logical_ms)
        except Exception:
            return
        marcadores = self._marcadores_para_sample_tira(ms)
        segmentos = self._segmentos_para_sample_tira(ms)
        # Prioridad: si hay marcadores asociados, mostrar menú de marcador (preferir marcadores)
        # Si múltiples marcadores en mismo sample -> submenu por tiempo real
        if marcadores:
            if len(marcadores) == 1:
                # reutilizar handler existente con tiempo real (busca exacto 1e-9)
                try:
                    self._al_marcador_contextual_solicitado(float(marcadores[0].get("tiempo")))
                except Exception:
                    self._mostrar_menu_marcador_tira(marcadores[0], global_pos)
            else:
                self._mostrar_menu_marcador_multiple_tira(marcadores, global_pos)
            return
        if segmentos:
            if len(segmentos) == 1:
                try:
                    self._al_segmento_contextual_solicitado(segmentos[0])
                except Exception:
                    self._mostrar_menu_segmento_tira(segmentos[0], global_pos)
            else:
                self._mostrar_menu_segmento_multiple_tira(segmentos, global_pos)
            return
        # sin marcador/segmento asociado: no-op (no menú vacío)

    def _mostrar_menu_marcador_tira(self, marcador, global_pos=None):
        """Construye menú para un marcador real desde Tira sin duplicar persistencia."""
        try:
            # reutiliza lógica de _al_marcador_contextual_solicitado pero con registro real
            menu = QMenu(self)
            submenu_color = QMenu("Asignar color", menu)
            menu.addMenu(submenu_color)
            for clave, *_resto in COLORES_CLASIFICACION:
                accion = submenu_color.addAction(texto_color(clave, self._ruta_config))
                accion.triggered.connect(lambda *args, m=marcador, c=clave: self._emitir_color_marcador(m, c))
            accion_quitar = submenu_color.addAction("Sin clasificar")
            accion_quitar.triggered.connect(lambda *args, m=marcador: self._emitir_color_marcador(m, None))
            if not marcador.get("color"):
                accion_quitar.setEnabled(False)
            accion_eliminar = menu.addAction("Eliminar marcador")
            accion_eliminar.triggered.connect(lambda *args, m=marcador: self._al_marcador_eliminar_solicitado(m["tiempo"]))
            self._menu_marcador_actual = menu
            self._submenu_marcador_color_actual = submenu_color
            # para tests, exponer referencia sin popup bloqueante
            try:
                pos = global_pos if global_pos is not None else QCursor.pos()
                menu.popup(pos)
            except Exception:
                menu.popup(QCursor.pos())
        except Exception:
            pass

    def _mostrar_menu_marcador_multiple_tira(self, marcadores, global_pos=None):
        """Submenú determinista cuando varios marcadores mapean al mismo sample."""
        try:
            menu = QMenu(self)
            # ordenar por tiempo real asc, id asc para determinismo
            ordenados = sorted(marcadores, key=lambda m: (float(m.get("tiempo", 0)), int(m.get("id") or 0)))
            for idx, marcador in enumerate(ordenados):
                t = float(marcador.get("tiempo", 0))
                txt_t = formatear_tiempo(t) if formatear_tiempo(t) else f"{t:.3f}s"
                color = marcador.get("color")
                color_txt = f" [{texto_color(color, self._ruta_config)}]" if color in CLAVES_COLOR_CLASIFICACION else (" [Sin clasificar]" if color is None else "")
                nombre = f"Marcador {txt_t}{color_txt} id={marcador.get('id')}"
                sub = menu.addMenu(nombre)
                for clave, *_resto in COLORES_CLASIFICACION:
                    acc = sub.addAction(texto_color(clave, self._ruta_config))
                    acc.triggered.connect(lambda *args, m=marcador, c=clave: self._emitir_color_marcador(m, c))
                acc_quitar = sub.addAction("Sin clasificar")
                acc_quitar.triggered.connect(lambda *args, m=marcador: self._emitir_color_marcador(m, None))
                if not marcador.get("color"):
                    acc_quitar.setEnabled(False)
                acc_elim = sub.addAction("Eliminar marcador")
                acc_elim.triggered.connect(lambda *args, m=marcador: self._al_marcador_eliminar_solicitado(m["tiempo"]))
            self._menu_marcador_actual = menu
            # crear submenu dummy para compatibilidad
            self._submenu_marcador_color_actual = None
            try:
                pos = global_pos if global_pos is not None else QCursor.pos()
                menu.popup(pos)
            except Exception:
                menu.popup(QCursor.pos())
        except Exception:
            pass

    def _mostrar_menu_segmento_tira(self, segmento, global_pos=None):
        try:
            # reutilizar handler existente (construye menú completo con reproducir/bucle/exportar)
            self._al_segmento_contextual_solicitado(segmento)
            # si handler usó popup con cursor, ya está; si pasamos global_pos distinto, repopup?
            # mantener menu creado por handler
        except Exception:
            pass

    def _mostrar_menu_segmento_multiple_tira(self, segmentos, global_pos=None):
        """Lista determinista cuando varios segmentos solapan el mismo sample."""
        try:
            menu = QMenu(self)
            ordenados = sorted(segmentos, key=lambda s: (float(s.get("inicio", 0)), float(s.get("fin", 0)), int(s.get("id") or 0)))
            for seg in ordenados:
                inicio = float(seg.get("inicio", 0))
                fin = float(seg.get("fin", 0))
                t_ini = formatear_tiempo(inicio) if formatear_tiempo(inicio) else f"{inicio:.2f}"
                t_fin = formatear_tiempo(fin) if formatear_tiempo(fin) else f"{fin:.2f}"
                color = seg.get("color")
                color_txt = f" [{texto_color(color, self._ruta_config)}]" if color in CLAVES_COLOR_CLASIFICACION else (" [Sin clasificar]" if color is None else "")
                txt = f"Segmento {t_ini}-{t_fin}{color_txt} id={seg.get('id')}"
                sub = menu.addMenu(txt)
                acc_rep = sub.addAction("Reproducir segmento")
                acc_rep.triggered.connect(lambda *args, s=seg: self.segmento_reproduccion_solicitada.emit(s))
                acc_bucle = sub.addAction("Reproducir en bucle")
                acc_bucle.triggered.connect(lambda *args, s=seg: self.segmento_bucle_solicitado.emit(s))
                sub_color = QMenu("Asignar color", sub)
                sub.addMenu(sub_color)
                for clave, *_resto in COLORES_CLASIFICACION:
                    acc_c = sub_color.addAction(texto_color(clave, self._ruta_config))
                    acc_c.triggered.connect(lambda *args, s=seg, c=clave: self._emitir_color_segmento(s, c))
                acc_quitar = sub_color.addAction("Sin clasificar")
                acc_quitar.triggered.connect(lambda *args, s=seg: self._emitir_color_segmento(s, None))
                if not seg.get("color"):
                    acc_quitar.setEnabled(False)
                acc_elim = sub.addAction("Eliminar segmento")
                acc_elim.triggered.connect(lambda *args, s=seg: self._al_segmento_eliminar_solicitado(s))
                acc_exp = sub.addAction("Exportar segmento…")
                acc_exp.triggered.connect(lambda *args, s=seg: self.segmento_exportacion_solicitada.emit(s))
            self._menu_segmento_actual = menu
            self._submenu_segmento_color_actual = None
            try:
                pos = global_pos if global_pos is not None else QCursor.pos()
                menu.popup(pos)
            except Exception:
                menu.popup(QCursor.pos())
        except Exception:
            pass

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
        try:
            self._tira_actualizar_decoraciones()
        except Exception:
            pass

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
        try:
            self._tira_actualizar_pendiente()
        except Exception:
            pass

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
            try:
                self._tira_actualizar_pendiente()
            except Exception:
                pass
            return
        a = self._extremo_segmento
        b = float(instante)
        self._extremo_segmento = None
        self._franja.set_inicio_segmento_pendiente(None)
        try:
            self._tira_actualizar_pendiente()
        except Exception:
            pass
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
        try:
            self._tira_actualizar_pendiente()
        except Exception:
            pass
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
        try:
            self._tira_actualizar_pendiente()
        except Exception:
            pass
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
        try:
            self._tira_actualizar_decoraciones()
        except Exception:
            pass

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
        try:
            self._tira_actualizar_decoraciones()
        except Exception:
            pass
        return registro

    def _al_segmento_eliminar_solicitado(self, segmento):
        for indice, seg in enumerate(self._segmentos):
            if seg is segmento:
                del self._segmentos[indice]
                self._franja.set_segmentos(self._segmentos)
                self._sincronizar_barra_colapsada()
                self._bump_resumen_version()
                self.segmento_eliminado.emit(seg)
                try:
                    self._tira_actualizar_decoraciones()
                except Exception:
                    pass
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
        accion_exportar = menu.addAction("Exportar segmento…")
        accion_reproducir.triggered.connect(
            lambda *args, s=segmento: self.segmento_reproduccion_solicitada.emit(s)
        )
        accion_bucle.triggered.connect(
            lambda *args, s=segmento: self.segmento_bucle_solicitado.emit(s)
        )
        accion_eliminar.triggered.connect(
            lambda *args, s=segmento: self._al_segmento_eliminar_solicitado(s)
        )
        accion_exportar.triggered.connect(
            lambda *args, s=segmento: self.segmento_exportacion_solicitada.emit(s)
        )
        self._menu_segmento_actual = menu
        self._submenu_segmento_color_actual = submenu_color
        self._accion_exportar_segmento_actual = accion_exportar
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
                try:
                    self._tira_actualizar_decoraciones()
                except Exception:
                    pass
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
        # B9.3/P01 — routing wheel: Tira fuera del corredor => horizontal, corredor/tira-dentro/datos => vertical nativa
        try:
            if evento.type() == QEvent.Wheel:
                es_tira = self._es_objeto_tira_wheel(objeto)
                en_corredor = self._wheel_en_corredor_vertical_datos(objeto, evento)
                if es_tira and not en_corredor:
                    try:
                        delta = evento.angleDelta().y()
                        if delta == 0:
                            delta = evento.angleDelta().x()
                    except Exception:
                        delta = 0
                    if delta != 0:
                        tira = getattr(self, "_tira_scroll", None)
                        if tira is not None:
                            try:
                                hbar = tira.horizontalScrollBar()
                                hbar.setValue(hbar.value() - int(delta / 2))
                            except Exception:
                                pass
                    return True
                else:
                    # Corredor vertical, datos o zona no-Tira: no tocar hbar, dejar propagación vertical nativa
                    return super().eventFilter(objeto, evento)
        except Exception:
            pass
        if getattr(self, "_franja", None) is objeto:
            if evento.type() == QEvent.Leave:
                self._imagen_exploracion.lower()
            return super().eventFilter(objeto, evento)
        # B7.13B — routing drag sobre hijos reales: reenvío centralizado press/move/release/dbl
        # Evita duplicar lógica, excluye controles interactivos (checkbox, botones, franja, barras)
        if evento.type() in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            # Excluir controles interactivos que necesitan su propio mouse (sin except genérico)
            _is_interactive = False
            try:
                from PySide6.QtWidgets import QCheckBox as _CB, QPushButton as _PB, QComboBox as _CO, QScrollArea as _SA
                if isinstance(objeto, (_CB, _PB, _CO, _SA)):
                    _is_interactive = True
            except (AttributeError, TypeError, RuntimeError, ImportError, ValueError):
                _is_interactive = False
            if _is_interactive:
                return super().eventFilter(objeto, evento)
            # Exclusión por identidad de widgets interactivos concretos de Tarjeta
            if objeto in (
                getattr(self, "_check", None),
                getattr(self, "_boton_expandir", None),
                getattr(self, "_franja", None),
                getattr(self, "_barra_colapsada", None),
                getattr(self, "_area_imagenes", None),
                getattr(self, "_selector_densidad", None),
                getattr(self, "_selector_color", None),
                getattr(self, "_boton_segmento", None),
            ):
                return super().eventFilter(objeto, evento)
            # Exclusión por nombre de clase de widgets de exploración/marcadores
            _clsname = ""
            try:
                _clsname = objeto.__class__.__name__
            except (AttributeError, TypeError, RuntimeError):
                _clsname = ""
            if _clsname in ("FranjaExploracion", "BarraResumenColapsada", "MiniaturaMarcador", "QScrollArea"):
                return super().eventFilter(objeto, evento)
            # Solo reenviar si el objeto es hijo drag-habilitado (labels, previews, imagen, recuadro)
            es_hijo_drag = False
            # permitir QLabel genérico y PreviewConTiempo sin try genérico
            if isinstance(objeto, QLabel):
                es_hijo_drag = True
            elif getattr(objeto.__class__, "__name__", "") == "PreviewConTiempo":
                es_hijo_drag = True
            if not es_hijo_drag:
                if objeto in getattr(self, "_labels_campos", []):
                    es_hijo_drag = True
                elif objeto is getattr(self, "_imagen_miniatura", None):
                    es_hijo_drag = True
                elif objeto is getattr(self, "_recuadro_sin_miniatura", None):
                    es_hijo_drag = True
                elif objeto in getattr(self, "_etiquetas_previews", []):
                    es_hijo_drag = True
            if es_hijo_drag:
                try:
                    # Mapear posición hijo -> Tarjeta
                    if hasattr(evento, "position"):
                        child_pos = evento.position()
                        try:
                            mapped = objeto.mapTo(self, child_pos.toPoint())
                        except (AttributeError, TypeError, RuntimeError, ValueError):
                            mapped = objeto.mapTo(self, QPoint(int(child_pos.x()), int(child_pos.y())))
                        mappedF = QPointF(mapped)
                    else:
                        child_pos = evento.pos()
                        mapped = objeto.mapTo(self, child_pos)
                        mappedF = QPointF(mapped)
                    # Crear evento sintético en coordenadas de Tarjeta
                    new_ev = QMouseEvent(evento.type(), mappedF, evento.button(), evento.buttons(), evento.modifiers())
                    if evento.type() == QEvent.MouseButtonPress:
                        self.mousePressEvent(new_ev)
                    elif evento.type() == QEvent.MouseMove:
                        self.mouseMoveEvent(new_ev)
                    elif evento.type() == QEvent.MouseButtonRelease:
                        self.mouseReleaseEvent(new_ev)
                    elif evento.type() == QEvent.MouseButtonDblClick:
                        self.mouseDoubleClickEvent(new_ev)
                    return True
                except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
                    print(f"[B7.13B] eventFilter redirect error: {exc}")
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
        self._actualizar_miniaturas_pendiente = False
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_actualizar_miniaturas = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.resultado_actualizar_miniaturas = None
        self.videos_detectados = None
        self.registros_guardados = None
        self._guardado_por_ruta_normalizada = None
        self._guardado_rutas_por_id = None
        self._guardado_nombres_por_id = None
        self._registros_para_guardar = None
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
        self._ids_seleccionados = set()
        self._ancla_seleccion = None
        self._ancla_seleccion_id = None
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

        # B6.5 filtro estructurado del catálogo (SQLite paginado)
        self._filtro_catalogo = "todos"
        self._bloqueo_filtro = False

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

        self.boton_mover_seleccionados = QPushButton("Mover seleccionados…")
        self.boton_mover_seleccionados.setEnabled(False)
        self.boton_mover_seleccionados.clicked.connect(self._iniciar_lote_mover)

        self.boton_copiar_seleccionados = QPushButton("Copiar seleccionados…")
        self.boton_copiar_seleccionados.setEnabled(False)
        self.boton_copiar_seleccionados.clicked.connect(self._iniciar_lote_copiar)

        self.boton_eliminar_seleccionados = QPushButton("Enviar seleccionados a Papelera…")
        self.boton_eliminar_seleccionados.setEnabled(False)
        self.boton_eliminar_seleccionados.clicked.connect(self._iniciar_lote_eliminar)

        self.boton_renombrar_masivo = QPushButton("Renombrar seleccionados…")
        self.boton_renombrar_masivo.setEnabled(False)
        self.boton_renombrar_masivo.clicked.connect(self._iniciar_renombrar_masivo)

        self.boton_cancelar_lote = QPushButton("Cancelar lote")
        self.boton_cancelar_lote.setVisible(False)
        self.boton_cancelar_lote.clicked.connect(self._cancelar_lote)

        self.boton_cancelar_renombrar_masivo = QPushButton("Cancelar renombrado")
        self.boton_cancelar_renombrar_masivo.setVisible(False)
        self.boton_cancelar_renombrar_masivo.clicked.connect(self._cancelar_renombrar_masivo)

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

        # B6.5 control compacto Mostrar: (Todos, Con marcadores/segmentos, por color)
        self.etiqueta_filtro = QLabel("Mostrar:")
        self.combo_filtro = QComboBox()
        self._poblar_combo_filtro()
        self.combo_filtro.currentIndexChanged.connect(
            self._al_cambiar_filtro_catalogo
        )

        self.etiqueta_carpeta = QLabel(MENSAJE_SIN_CARPETA)
        self.etiqueta_carpeta.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.estado_escaneo = QLabel(MENSAJE_SIN_ESCANEO)

        self.mensaje_carpeta = QLabel()
        self.mensaje_carpeta.setStyleSheet("color: #b00020;")

        self.boton_exportar_lote = QPushButton("Exportar segmentos…")
        self.boton_exportar_lote.clicked.connect(self._al_exportar_lote_solicitado)
        self.boton_exportar_secuencia = QPushButton("Unir segmentos…")
        self.boton_exportar_secuencia.clicked.connect(self._al_exportar_secuencia_solicitado)

        # B7.9 modo Organización/Explorer base
        self.boton_modo_organizacion = QPushButton("Modo Organización")
        self.boton_modo_organizacion.setObjectName("boton_modo_organizacion")
        self.boton_modo_organizacion.setCheckable(True)
        self.boton_modo_organizacion.setChecked(False)
        self.boton_modo_organizacion.toggled.connect(self._al_cambiar_modo_organizacion)

        fila_carpeta = QHBoxLayout()
        fila_carpeta.addWidget(self.boton_seleccionar_carpeta)
        fila_carpeta.addWidget(self.boton_escanear)
        fila_carpeta.addWidget(self.boton_exportar_lote)
        fila_carpeta.addWidget(self.boton_exportar_secuencia)
        fila_carpeta.addWidget(self.combo_modo_alcance)
        fila_carpeta.addWidget(self.escaneo_automatico)
        fila_carpeta.addWidget(self.etiqueta_cantidad_previews)
        fila_carpeta.addWidget(self.combo_cantidad_previews)
        fila_carpeta.addWidget(self.etiqueta_tamano_miniaturas)
        fila_carpeta.addWidget(self.combo_tamano_miniaturas)
        fila_carpeta.addWidget(self.boton_preferencias)
        fila_carpeta.addWidget(self.boton_modo_seleccion)
        fila_carpeta.addWidget(self.boton_modo_organizacion)
        fila_carpeta.addWidget(self.boton_copiar)
        fila_carpeta.addWidget(self.boton_pegar)
        fila_carpeta.addWidget(self.boton_eliminar)
        fila_carpeta.addWidget(self.boton_mover_seleccionados)
        fila_carpeta.addWidget(self.boton_copiar_seleccionados)
        fila_carpeta.addWidget(self.boton_eliminar_seleccionados)
        fila_carpeta.addWidget(self.boton_renombrar_masivo)
        fila_carpeta.addWidget(self.boton_cancelar_lote)
        fila_carpeta.addWidget(self.boton_cancelar_renombrar_masivo)
        fila_carpeta.addWidget(self.etiqueta_carpeta, 1)
        fila_carpeta.addWidget(self.estado_escaneo)
        fila_carpeta.addWidget(self.mensaje_carpeta)

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.etiqueta_filtro)
        barra.addWidget(self.combo_filtro)
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

        # B7.1 F2 renombrar (sin conflicto: no colisiona con Ctrl+A/Esc/Del)
        self._atajo_f2_renombrar = QShortcut(QKeySequence("F2"), self)
        self._atajo_f2_renombrar.activated.connect(self._atajo_renombrar)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        self.boton_cancelar_export = QPushButton("Cancelar exportación")
        self.boton_cancelar_export.setVisible(False)
        self.boton_cancelar_export.clicked.connect(self._cancelar_export)

        # B7.9 panel Organización compacto (no reemplaza biblioteca)
        # B7.10 navegación embebida del destino (sin FS directo en panel)
        # B7.12 preparación objetivo estable para futuro soltado (sin gesto arrastre)
        self._modo_organizacion = False
        self._organizacion_destino = None
        self._organizacion_destino_valido = False
        self._organizacion_subcarpetas = []
        self._organizacion_error = None
        self._organizacion_cargando = False
        self._organizacion_navegacion_version = 0
        self._organizacion_objetivo_nombre = None
        self._organizacion_objetivo_completo = None
        self.panel_organizacion = PanelOrganizacion(self)
        self.panel_organizacion.setObjectName("panel_organizacion")
        self.panel_organizacion.setVisible(False)
        self.panel_organizacion.seleccionarDestinoSolicitado.connect(self._seleccionar_destino_organizacion)
        self.panel_organizacion.moverSolicitado.connect(self._iniciar_lote_mover_organizacion)
        self.panel_organizacion.copiarSolicitado.connect(self._iniciar_lote_copiar_organizacion)
        self.panel_organizacion.entrarSubcarpetaSolicitada.connect(self._navegar_destino_a_subcarpeta)
        self.panel_organizacion.subirSolicitado.connect(self._navegar_destino_subir)
        self.panel_organizacion.objetivoSeleccionado.connect(self._al_objetivo_drop_seleccionado)
        self.panel_organizacion.dropVideosSolicitado.connect(self._al_drop_videos_solicitado)

        raiz = PanelPrincipal()
        layout = QVBoxLayout(raiz)
        layout.addLayout(fila_carpeta)
        layout.addLayout(barra)
        layout.addWidget(self.barra_progreso)
        fila_export = QHBoxLayout()
        fila_export.addWidget(self.boton_cancelar_export)
        fila_export.addStretch()
        layout.addLayout(fila_export)
        # B7.11 doble panel estructural: QSplitter vertical secundario dentro de PanelPrincipal
        # - panel Destino arriba, catálogo visual ORIGEN abajo, catálogo dominante, ajuste por handle
        self.splitter_organizacion = QSplitter(Qt.Vertical)
        self.splitter_organizacion.setObjectName("splitter_organizacion")
        self.splitter_organizacion.setHandleWidth(6)
        self.splitter_organizacion.setChildrenCollapsible(False)
        # Catálogo con mínimo útil para que no colapse; destino con mínimo razonable
        self.area.setMinimumHeight(140)
        self.panel_organizacion.setMinimumHeight(96)
        self.splitter_organizacion.addWidget(self.panel_organizacion)
        self.splitter_organizacion.addWidget(self.area)
        self.splitter_organizacion.setStretchFactor(0, 0)
        self.splitter_organizacion.setStretchFactor(1, 1)
        self.splitter_organizacion.setCollapsible(1, False)
        # Tamaño inicial razonable: destino ~25-30%, catálogo 70-75%
        self.splitter_organizacion.setSizes([150, 470])
        layout.addWidget(self.splitter_organizacion, 1)

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
        self.arbol_navegacion.nueva_carpeta_solicitada.connect(
            self._iniciar_crear_carpeta
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
        self._cola_exploracion_extra = []
        self._exploracion_op_actual = None
        self._exploracion_objetivo = None
        self._exploracion_objetivo_id = None
        self.tarea_exploracion = None
        # B9.3 virtualización REAL: gestor para carga visual acotada (QImage en worker)
        self.gestor_previews_visuales = GestorTareas(self)
        self.gestor_previews_visuales.tarea_resultado.connect(self._al_resultado_preview_visual)
        self.gestor_previews_visuales.tarea_error.connect(self._al_error_preview_visual)
        self.gestor_previews_visuales.tarea_finalizada.connect(self._al_previews_visuales_finalizada)
        self._cola_previews_visuales = []
        self._preview_visual_op_actual = None

        # B6.4 resumen colapsado: una sola tarea batch por lote de tarjetas, sin SQLite en UI
        self.gestor_resumen = GestorTareas(self)
        self.gestor_resumen.tarea_resultado.connect(self._al_resultado_resumen)
        self.gestor_resumen.tarea_error.connect(self._al_error_resumen)
        self.gestor_resumen.tarea_finalizada.connect(self._al_resumen_finalizada)
        self._cola_resumen = []
        self._resumen_op_actual = None
        self._resumen_ids_en_vuelo = set()

        # B8.2 migración legacy -> id en background (batch por página, no por tarjeta, sin FS en UI)
        self.gestor_migracion = GestorTareas(self)
        self.gestor_migracion.tarea_resultado.connect(self._al_resultado_migracion)
        self.gestor_migracion.tarea_error.connect(self._al_error_migracion)
        self.gestor_migracion.tarea_finalizada.connect(self._al_migracion_finalizada)
        self._cola_migracion = []
        self._migracion_op_actual = None
        self._migracion_ids_en_vuelo = set()
        self._previews_diferidas = set()

        # B6.7 exportación segura de un segmento (sin SQLite directo desde UI)
        self.gestor_export = GestorTareas(self)
        self.gestor_export.tarea_resultado.connect(self._al_resultado_export)
        self.gestor_export.tarea_error.connect(self._al_error_export)
        self.gestor_export.tarea_finalizada.connect(self._al_export_finalizada)
        self.gestor_export.actividad_cambiada.connect(self._al_actividad_export)
        self.gestor_export.tarea_progreso.connect(self._al_progreso_lote)
        self._export_segmento_actual = None
        self._export_destino_actual = None
        self._export_lote_activo = False
        self._export_tipo = None  # B6.10 fix: "individual"|"lote"|"secuencia" - discriminación explícita sin inferir por filename

        # B6.9 preparación asíncrona de segmentos para diálogo de lote (sin SQLite/FFmpeg en hilo UI)
        # Patrón reutilizado: GestorTareas + TareaListarSegmentosVarios + señales resultado/error/finalizada,
        # idéntico a gestor_marcadores/gestor_segmentos/gestor_resumen. La UI inicia tarea breve,
        # recibe datos en callback y recién entonces abre DialogoExportarLote (puramente presentacional).
        self.gestor_preparacion_lote = GestorTareas(self)
        self.gestor_preparacion_lote.tarea_resultado.connect(self._al_preparacion_lote_resultado)
        self.gestor_preparacion_lote.tarea_error.connect(self._al_preparacion_lote_error)
        self.gestor_preparacion_lote.tarea_finalizada.connect(self._al_preparacion_lote_finalizada)
        self._preparacion_lote_en_curso = False
        self._preparacion_lote_video_ids = None
        self._preparacion_lote_nombres = None
        self._preparacion_lote_rutas = None
        self._preparacion_lote_segmentos = None
        self._preparacion_lote_error = None

        # B6.10 preparación asíncrona para diálogo de secuencia (reutiliza misma infraestructura)
        self.gestor_preparacion_secuencia = GestorTareas(self)
        self.gestor_preparacion_secuencia.tarea_resultado.connect(self._al_preparacion_secuencia_resultado)
        self.gestor_preparacion_secuencia.tarea_error.connect(self._al_preparacion_secuencia_error)
        self.gestor_preparacion_secuencia.tarea_finalizada.connect(self._al_preparacion_secuencia_finalizada)
        self._preparacion_secuencia_en_curso = False
        self._preparacion_secuencia_video_ids = None
        self._preparacion_secuencia_nombres = None
        self._preparacion_secuencia_rutas = None
        self._preparacion_secuencia_segmentos = None
        self._preparacion_secuencia_error = None

        # B7.1 renombrado individual seguro (sin SQLite/FS directo desde UI)
        self.gestor_renombrado = GestorTareas(self)
        self.gestor_renombrado.tarea_resultado.connect(self._al_resultado_renombrado)
        self.gestor_renombrado.tarea_error.connect(self._al_error_renombrado)
        self.gestor_renombrado.tarea_finalizada.connect(self._al_renombrado_finalizada)
        self.gestor_renombrado.actividad_cambiada.connect(self._al_actividad_renombrado)
        self._renombrado_en_curso = False
        self._renombrado_nombre_anterior = None

        # B7.2 mover individual seguro (sin SQLite/FS directo desde UI)
        self.gestor_mover = GestorTareas(self)
        self.gestor_mover.tarea_resultado.connect(self._al_resultado_mover)
        self.gestor_mover.tarea_error.connect(self._al_error_mover)
        self.gestor_mover.tarea_finalizada.connect(self._al_mover_finalizada)
        self.gestor_mover.actividad_cambiada.connect(self._al_actividad_mover)
        self._mover_en_curso = False
        self._mover_nombre_anterior = None
        self._mover_video_id = None
        self._mover_ruta_inconsistente = None
        self._mover_error_sincronizacion = None

        # B7.3 creación segura de carpeta (sin SQLite/FS directo desde UI)
        self.gestor_crear_carpeta = GestorTareas(self)
        self.gestor_crear_carpeta.tarea_resultado.connect(self._al_resultado_crear_carpeta)
        self.gestor_crear_carpeta.tarea_error.connect(self._al_error_crear_carpeta)
        self.gestor_crear_carpeta.tarea_finalizada.connect(self._al_crear_carpeta_finalizada)
        self.gestor_crear_carpeta.actividad_cambiada.connect(self._al_actividad_crear_carpeta)
        self._crear_en_curso = False
        self._crear_padre_en_curso = None
        self._crear_nombre_en_curso = None

        # B7.4 copia individual segura (sin SQLite/FS directo desde UI)
        self.gestor_copiar = GestorTareas(self)
        self.gestor_copiar.tarea_resultado.connect(self._al_resultado_copiar)
        self.gestor_copiar.tarea_error.connect(self._al_error_copiar)
        self.gestor_copiar.tarea_finalizada.connect(self._al_copiar_finalizada)
        self.gestor_copiar.actividad_cambiada.connect(self._al_actividad_copiar)
        self._copiar_en_curso = False
        self._copiar_nombre_origen = None
        self._copiar_video_id = None
        self._copiar_ruta_inconsistente = None
        self._copiar_error_sincronizacion = None
        self._crear_ruta_inconsistente = None
        self._crear_error_refresco = None

        # B7.5 eliminación individual segura a Papelera (sin SQLite/FS directo desde UI)
        self.gestor_eliminar = GestorTareas(self)
        self.gestor_eliminar.tarea_resultado.connect(self._al_resultado_eliminar_video)
        self.gestor_eliminar.tarea_error.connect(self._al_error_eliminar_video)
        self.gestor_eliminar.tarea_finalizada.connect(self._al_eliminar_video_finalizada)
        self.gestor_eliminar.actividad_cambiada.connect(self._al_actividad_eliminar_video)
        self._eliminar_en_curso = False
        self._eliminar_video_id = None
        self._eliminar_nombre = None
        self._eliminar_ruta_inconsistente = None
        self._eliminar_error_sincronizacion = None

        # B7.6 operaciones masivas seguras sobre seleccionados (sin SQLite/FS directo desde UI)
        self.gestor_lote = GestorTareas(self)
        self.gestor_lote.tarea_resultado.connect(self._al_resultado_lote)
        self.gestor_lote.tarea_error.connect(self._al_error_lote)
        self.gestor_lote.tarea_finalizada.connect(self._al_lote_finalizada)
        self.gestor_lote.tarea_progreso.connect(self._al_progreso_lote)
        self.gestor_lote.actividad_cambiada.connect(self._al_actividad_lote)
        self._lote_en_curso = False
        self._lote_operacion = None
        self._lote_video_ids = None
        self._lote_carpeta_destino = None
        self._lote_resultado_pendiente = None
        self._lote_ultimo_error_completo = None

        # B7.7 renombrado masivo seguro (sin SQLite/FS directo desde UI, preview exacta, ciclos con temporales)
        self.gestor_renombrar_masivo = GestorTareas(self)
        self.gestor_renombrar_masivo.tarea_resultado.connect(self._al_resultado_renombrar_masivo)
        self.gestor_renombrar_masivo.tarea_error.connect(self._al_error_renombrar_masivo)
        self.gestor_renombrar_masivo.tarea_finalizada.connect(self._al_finalizada_renombrar_masivo)
        self.gestor_renombrar_masivo.tarea_progreso.connect(self._al_progreso_renombrar_masivo)
        self.gestor_renombrar_masivo.actividad_cambiada.connect(self._al_actividad_renombrar_masivo)
        self._renombrar_masivo_en_curso = False
        self._renombrar_masivo_plan = None
        # B7.7 post-rename fix: preservación de selección por video_id (no por nombre)
        self._renombrar_masivo_ids_origen = None
        self._renombrar_masivo_ids_a_restaurar = None
        # B7.7 UX final: preservación de contexto visual determinista (scroll/viewport)
        self._renombrar_masivo_scroll_previo = None
        self._renombrar_masivo_orden_previo = None

        # B7.10 navegación destino: gestor background sin consulta periódica, sin FS directo en panel
        self.gestor_navegacion_destino = GestorTareas(self)
        self.gestor_navegacion_destino.tarea_resultado.connect(self._al_resultado_navegacion_destino)
        self.gestor_navegacion_destino.tarea_error.connect(self._al_error_navegacion_destino)
        self.gestor_navegacion_destino.tarea_finalizada.connect(self._al_navegacion_destino_finalizada)

        # B7.13C corrección — prevalidación atómica antes de mover (fuera de UI, sin SQLite/FS directo)
        self.gestor_prevalidacion_drop = GestorTareas(self)
        self.gestor_prevalidacion_drop.tarea_resultado.connect(self._al_prevalidacion_drop_resultado)
        self.gestor_prevalidacion_drop.tarea_error.connect(self._al_prevalidacion_drop_error)
        self.gestor_prevalidacion_drop.tarea_finalizada.connect(self._al_prevalidacion_drop_finalizada)
        self._prevalidacion_drop_ids = None
        self._prevalidacion_drop_dest = None
        self._prevalidacion_drop_en_curso = False

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
        # B7.2 fix-017: modo recursivo cambia semántica de carpeta -> recargar paginado
        # Diferir 200ms para no colisionar con iniciar_escaneo inmediato (tests de modo)
        QTimer.singleShot(200, self._programar_recarga_por_carpeta)

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
        QTimer.singleShot(200, self._programar_recarga_por_carpeta)

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
            self._refrescar_textos_filtro()
            self._poblar_combo_filtro()

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

    def _poblar_combo_filtro(self):
        """Puebla el combo Mostrar: con Todos, Con marcadores/segmentos, Sin clasificar y por color (B6.5 UX)."""
        combo = getattr(self, "combo_filtro", None)
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todos", "todos")
        combo.addItem("Con marcadores", "con_marcadores")
        combo.addItem("Con segmentos", "con_segmentos")
        combo.addItem("Marcador: Sin clasificar", FILTRO_MARCADOR_SIN_CLASIFICAR)
        combo.addItem("Segmento: Sin clasificar", FILTRO_SEGMENTO_SIN_CLASIFICAR)
        for clave, *_resto in COLORES_CLASIFICACION:
            texto = texto_color(clave, self._ruta_config)
            combo.addItem(f"Marcador: {texto}", f"marcador:{clave}")
        for clave, *_resto in COLORES_CLASIFICACION:
            texto = texto_color(clave, self._ruta_config)
            combo.addItem(f"Segmento: {texto}", f"segmento:{clave}")
        # seleccionar filtro actual por data (no por texto)
        filtro = getattr(self, "_filtro_catalogo", "todos")
        idx = combo.findData(filtro)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _refrescar_textos_filtro(self):
        """Actualiza los textos visibles del filtro tras cambiar nombres globales (B6.5)."""
        combo = getattr(self, "combo_filtro", None)
        if combo is None:
            return
        # preservar selección por data (estable, no por texto visible)
        data_actual = combo.currentData()
        combo.blockSignals(True)
        # Fijos: Todos / Con marcadores / Con segmentos + 2 Sin clasificar
        combo.setItemText(0, "Todos")
        combo.setItemText(1, "Con marcadores")
        combo.setItemText(2, "Con segmentos")
        combo.setItemText(3, "Marcador: Sin clasificar")
        combo.setItemText(4, "Segmento: Sin clasificar")
        # Marcadores por color: índices 5..10
        for i, (clave, *_resto) in enumerate(COLORES_CLASIFICACION):
            idx = 5 + i
            if idx < combo.count():
                combo.setItemText(idx, f"Marcador: {texto_color(clave, self._ruta_config)}")
        for i, (clave, *_resto) in enumerate(COLORES_CLASIFICACION):
            idx = 5 + len(COLORES_CLASIFICACION) + i
            if idx < combo.count():
                combo.setItemText(idx, f"Segmento: {texto_color(clave, self._ruta_config)}")
        # restaurar índice por data (por si el orden textual cambió)
        if data_actual is not None:
            idx = combo.findData(data_actual)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _al_cambiar_filtro_catalogo(self, _indice):
        if getattr(self, "_bloqueo_filtro", False):
            return
        filtro = self.combo_filtro.currentData()
        if not isinstance(filtro, str):
            filtro = "todos"
        if filtro == self._filtro_catalogo:
            return
        self._filtro_catalogo = filtro
        self._orden_generacion += 1
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._cola_resumen.clear()
        self._resumen_ids_en_vuelo.clear()
        self.area.verticalScrollBar().setValue(0)
        self._reordenamiento_pendiente = True
        self._actualizar_botones_carpeta()
        self._procesar_reordenamiento()

    def _programar_recarga_por_filtro(self):
        """Recarga controlada si un marcador/segmento mutó bajo filtro activo (B6.5).

        Si el filtro es Todos no hay recarga. Si el gestor principal está ocupado,
        deja pendiente el reordenamiento para ejecutarse en `_al_tarea_finalizada`.
        No accede a SQLite ni hace consulta periódica.
        """
        if getattr(self, "_filtro_catalogo", "todos") == "todos":
            return
        self._orden_generacion += 1
        if self.gestor.activo:
            self._reordenamiento_pendiente = True
            return
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._cola_resumen.clear()
        self._resumen_ids_en_vuelo.clear()
        self.area.verticalScrollBar().setValue(0)
        self._reordenamiento_pendiente = True
        self._actualizar_botones_carpeta()
        self._procesar_reordenamiento()

    def _crear_tarea_lectura(self, desplazamiento=0):
        clave_orden, direccion_orden = self._orden_catalogo
        filtro = getattr(self, "_filtro_catalogo", "todos")
        filtro_param = None if filtro == "todos" else filtro
        # B7.2 fix-017: filtrar paginado por carpeta seleccionada (Windows-safe, inmediata)
        # Si no hay carpeta seleccionada o no existe en disco, no filtrar (comportamiento global legacy)
        carpeta_param = getattr(self, "carpeta_seleccionada", None)
        # Determinar si la carpeta es válida en disco; si no, no filtrar para no vaciar catálogo por config obsoleta
        # La validación ligera evita bloquear carga inicial cuando config apunta a carpeta eliminada
        if isinstance(carpeta_param, str) and carpeta_param.strip():
            try:
                if not os.path.isdir(carpeta_param):
                    carpeta_param = None
            except Exception:
                carpeta_param = None
        else:
            # Si es lista (selección personalizada) validar cada una
            if isinstance(carpeta_param, (list, tuple, set)):
                validas = [c for c in carpeta_param if isinstance(c, str) and os.path.isdir(c)]
                carpeta_param = validas if validas else None
            else:
                carpeta_param = None
        # Respetar modo alcance recursivo para paginación: si modo es con_subcarpetas o seleccion, incluir subcarpetas
        incluir_sub = False
        try:
            incluir_sub = bool(self._recursivo_actual())
        except Exception:
            incluir_sub = False
        # B8.2 fix multicarpeta: en modo SELECCION el catálogo visible debe ser la unión de carpetas seleccionadas,
        # no solo carpeta_seleccionada única. Esto restaura contrato histórico P05 (4 videos /12 previews).
        # Sin perder paginación: sigue LIMIT/OFFSET, solo cambia WHERE a OR de carpetas.
        try:
            if getattr(self, "_modo_alcance", None) == MODO_ALCANCE_SELECCION:
                sel = None
                try:
                    if hasattr(self, "seleccion_carpetas") and self.seleccion_carpetas is not None:
                        sel = self.seleccion_carpetas.obtener_seleccion()
                except (AttributeError, TypeError, RuntimeError):
                    sel = None
                if isinstance(sel, (set, list, tuple)) and sel:
                    validas_sel = [c for c in sel if isinstance(c, str) and c.strip() and os.path.isdir(c)]
                    if validas_sel:
                        # Usar lista completa como filtro OR, respetando incluir_sub actual (recursivo para SELECCION)
                        carpeta_param = validas_sel
        except Exception:
            pass
        # B8.3A — lectura multicarpeta por _alcance_sincronizacion (unión A∪B, padre+subcarpeta sin duplicados, sin SQLite directo)
        try:
            alcance = getattr(self, "_alcance_sincronizacion", None)
            if isinstance(alcance, (list, tuple, set)) and alcance:
                validas_alcance = [c for c in alcance if isinstance(c, str) and c.strip() and os.path.isdir(c)]
                if validas_alcance:
                    carpeta_param = validas_alcance
        except Exception:
            pass
        return TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL,
            desplazamiento,
            None,
            self._ruta_db,
            orden_clave=clave_orden,
            orden_direccion=direccion_orden,
            filtro=filtro_param,
            carpeta=carpeta_param,
            incluir_subcarpetas=incluir_sub,
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

    def _programar_recarga_por_carpeta(self):
        """Recarga paginada por cambio de carpeta seleccionada (B7.2 fix-017).

        Invalida paginación y reordena sin requerir escaneo: la nueva carpeta
        filtra en SQL antes de LIMIT/OFFSET (no post-filtro). Si el gestor
        está activo, deja pendiente el reordenamiento.
        """
        # FIX B8.3 navegación: incrementar generación incluso si queda pendiente
        # para invalidar resultados obsoletos de la carpeta anterior
        self._orden_generacion += 1
        if self.gestor.activo:
            self._reordenamiento_pendiente = True
            return
        self._pagina_pendiente = False
        self.tarea_pagina = None
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._cola_resumen.clear()
        self._resumen_ids_en_vuelo.clear()
        # B7.7 UX final: preservar contexto visual tras renombrado masivo (no salto ciego a 0)
        # Si hay recarga pendiente por renombrado masivo, conservar scroll previo y decidir después
        es_recarga_renombrado = (
            getattr(self, "_renombrar_masivo_ids_a_restaurar", None) is not None
            or getattr(self, "_renombrar_masivo_en_curso", False)
            or getattr(self, "_renombrar_masivo_scroll_previo", None) is not None
        )
        if not es_recarga_renombrado:
            self.area.verticalScrollBar().setValue(0)
        self._reordenamiento_pendiente = True
        self._actualizar_botones_carpeta()
        self._procesar_reordenamiento()

    # === B7.8 Política mínima de consistencia post-operaciones ===
    # Decisión explícita y testeable 'recarga paginada necesaria' vs 'actualización local suficiente'.
    # La lectura paginada desde SQLite se conserva cuando una operación puede cambiar membresía,
    # orden, filtro o paginación. No se reemplaza por manipulación manual frágil.
    def _b78_copia_debe_recargar(self, carpeta_destino):
        """B7.8: copia individual/lote debe recargar solo si destino es vista actual."""
        try:
            if not isinstance(carpeta_destino, str) or not carpeta_destino.strip():
                return False
            if not isinstance(self.carpeta_seleccionada, str) or not self.carpeta_seleccionada.strip():
                return False
            return carpetas_iguales(self.carpeta_seleccionada, carpeta_destino)
        except Exception:
            return False

    def _b78_lote_debe_recargar(self, operacion, exitosos, carpeta_destino=None):
        """B7.8: lote mover/eliminar con éxitos siempre recarga; copiar solo si destino visible."""
        try:
            if not isinstance(exitosos, list) or not exitosos:
                return False
            if operacion in ("mover", "eliminar"):
                return True
            if operacion == "copiar":
                return self._b78_copia_debe_recargar(carpeta_destino)
            return False
        except Exception:
            return True  # fallback seguro: si duda, recargar

    def _b78_renombrado_masivo_debe_recargar(self, exitosos):
        """B7.8 conservadora: renombrado masivo con éxitos siempre recarga (membresía/orden/filtro/paginación).

        Orden dependiente de nombre, filtro/búsqueda activos o paginación pueden cambiar;
        como la demostración local sin recarga es frágil, se conserva recarga paginada segura.
        Si en futuro se demuestra que orden != nombre y filtro == todos y búsqueda vacía,
        podría evitarse recarga y hacer actualización local por video_id, pero por ahora se mantiene segura.
        """
        try:
            if not isinstance(exitosos, list) or not exitosos:
                return False
            return True
        except Exception:
            return True

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
        # B7.2 fix-017: recargar solo si no hay escaneo automático (evita colisión gestor)
        if not self.escaneo_automatico.isChecked():
            self._programar_recarga_por_carpeta()
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
        if not self.escaneo_automatico.isChecked():
            self._programar_recarga_por_carpeta()
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
        self._actualizar_botones_lote()

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

    def _al_seleccionar_tarjeta(self, ident, ctrl):
        # B8.3B — identidad por video_id; compat legado: ident puede ser nombre str
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            if not ctrl:
                self._limpiar_seleccion()
            if vid in getattr(self, "_ids_seleccionados", set()):
                self._ids_seleccionados.discard(vid)
                tarjeta = self._tarjeta_por_id(vid)
                nombre = getattr(tarjeta, "nombre", None) if tarjeta else None
                if nombre is not None:
                    if not any(getattr(self._tarjeta_por_id(x), "nombre", None) == nombre for x in self._ids_seleccionados):
                        self._nombres_seleccionados.discard(nombre)
                self._marcar_tarjeta_por_id(vid, False)
            else:
                self._ids_seleccionados.add(vid)
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is not None:
                    self._nombres_seleccionados.add(tarjeta.nombre)
                self._marcar_tarjeta_por_id(vid, True)
            self._ancla_seleccion_id = vid if self._ids_seleccionados else None
            if self._ancla_seleccion_id is not None:
                t = self._tarjeta_por_id(self._ancla_seleccion_id)
                self._ancla_seleccion = getattr(t, "nombre", None) if t else None
            else:
                self._ancla_seleccion = None
            return
        nombre = ident
        if not ctrl:
            self._limpiar_seleccion()
        if nombre in self._nombres_seleccionados:
            self._nombres_seleccionados.discard(nombre)
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is not None:
                v = getattr(tarjeta, "_video_id", None)
                if isinstance(v, int):
                    self._ids_seleccionados.discard(v)
            self._marcar_tarjeta(nombre, False)
        else:
            self._nombres_seleccionados.add(nombre)
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is not None:
                v = getattr(tarjeta, "_video_id", None)
                if isinstance(v, int):
                    self._ids_seleccionados.add(v)
            self._marcar_tarjeta(nombre, True)
        self._ancla_seleccion = nombre if self._nombres_seleccionados else None
        self._ancla_seleccion_id = getattr(self._tarjeta_por_nombre(nombre), "_video_id", None) if self._nombres_seleccionados and nombre in self._nombres_seleccionados else None

    def _al_seleccion_por_rango(self, ident):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            if self._ancla_seleccion_id is None or self._ancla_seleccion_id not in [getattr(t, "_video_id", None) for _, t in self.tarjetas]:
                self._limpiar_seleccion()
                self._ids_seleccionados.add(vid)
                t = self._tarjeta_por_id(vid)
                if t:
                    self._nombres_seleccionados.add(t.nombre)
                self._marcar_tarjeta_por_id(vid, True)
                self._ancla_seleccion_id = vid
                self._ancla_seleccion = getattr(self._tarjeta_por_id(vid), "nombre", None)
                return
            ids_orden = [getattr(t, "_video_id", None) for _, t in self.tarjetas]
            try:
                idx_ancla = ids_orden.index(self._ancla_seleccion_id)
                idx_objetivo = ids_orden.index(vid)
            except ValueError:
                self._limpiar_seleccion()
                self._ids_seleccionados.add(vid)
                t = self._tarjeta_por_id(vid)
                if t:
                    self._nombres_seleccionados.add(t.nombre)
                self._marcar_tarjeta_por_id(vid, True)
                self._ancla_seleccion_id = vid
                return
            inicio = min(idx_ancla, idx_objetivo)
            fin = max(idx_ancla, idx_objetivo)
            self._limpiar_seleccion()
            for idx in range(inicio, fin + 1):
                _, tarjeta = self.tarjetas[idx]
                v = getattr(tarjeta, "_video_id", None)
                if isinstance(v, int):
                    self._ids_seleccionados.add(v)
                    self._nombres_seleccionados.add(tarjeta.nombre)
                    self._marcar_tarjeta_por_id(v, True)
            return
        nombre = ident
        visibles = self.tarjetas_visibles()
        if self._ancla_seleccion is None or self._ancla_seleccion not in visibles:
            self._limpiar_seleccion()
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
            try:
                t0 = self._tarjeta_por_nombre(nombre)
                if t0 is not None:
                    v0 = getattr(t0, "_video_id", None)
                    if _es_video_id_valido(v0):
                        self._ids_seleccionados.add(v0)
                        self._ancla_seleccion_id = v0
            except (AttributeError, TypeError, ValueError, RuntimeError) as _exc_sync_ids:
                # B8.3B: no-op seguro — sync de id es best-effort, no debe propagar
                print(f"[B8.3B] _al_seleccion_por_rango sync ancla error: {_exc_sync_ids}")
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
            # B8.3B sync ids for legacy path — Best-effort, no silencia Exception genérica
            try:
                t = self._tarjeta_por_nombre(n)
                if t is not None:
                    v = getattr(t, "_video_id", None)
                    if _es_video_id_valido(v):
                        self._ids_seleccionados.add(v)
            except (AttributeError, TypeError, ValueError, RuntimeError) as _exc_sync_ids2:
                print(f"[B8.3B] _al_seleccion_por_rango sync rango error: {_exc_sync_ids2}")

    def _limpiar_seleccion(self):
        for vid in list(getattr(self, "_ids_seleccionados", set())):
            self._marcar_tarjeta_por_id(vid, False)
        for nombre in list(self._nombres_seleccionados):
            self._marcar_tarjeta(nombre, False)
        self._nombres_seleccionados.clear()
        if hasattr(self, "_ids_seleccionados"):
            self._ids_seleccionados.clear()
        self._ancla_seleccion_id = None
        self._actualizar_resumen_seleccion()

    def _marcar_tarjeta(self, nombre, valor):
        for candidato, tarjeta in self.tarjetas:
            if candidato == nombre:
                tarjeta.marcar_seleccionada(valor)
                tarjeta.set_check(valor)
                self._actualizar_resumen_seleccion()
                return

    def _marcar_tarjeta_por_id(self, video_id, valor):
        tarjeta = self._tarjeta_por_id(video_id)
        if tarjeta is not None:
            tarjeta.marcar_seleccionada(valor)
            tarjeta.set_check(valor)
            self._actualizar_resumen_seleccion()
            return
        for _, t in self.tarjetas:
            if getattr(t, "_video_id", None) == video_id:
                t.marcar_seleccionada(valor)
                t.set_check(valor)
                self._actualizar_resumen_seleccion()
                return

    def _al_check_tarjeta(self, ident, marcado):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            if marcado:
                self._ids_seleccionados.add(vid)
                t = self._tarjeta_por_id(vid)
                if t:
                    self._nombres_seleccionados.add(t.nombre)
                self._marcar_tarjeta_por_id(vid, True)
            else:
                self._ids_seleccionados.discard(vid)
                t = self._tarjeta_por_id(vid)
                if t and not any(getattr(self._tarjeta_por_id(x), "nombre", None) == t.nombre for x in self._ids_seleccionados):
                    self._nombres_seleccionados.discard(t.nombre)
                self._marcar_tarjeta_por_id(vid, False)
            return
        nombre = ident
        if marcado:
            self._nombres_seleccionados.add(nombre)
            self._marcar_tarjeta(nombre, True)
        else:
            self._nombres_seleccionados.discard(nombre)
            self._marcar_tarjeta(nombre, False)

    def _al_expansion_tarjeta(self, ident, expandida):
        vid = ident if _es_video_id_valido(ident) else None
        nombre = None
        tarjeta_exp = None
        if vid is not None:
            tarjeta_exp = self._tarjeta_por_id(vid)
            nombre = getattr(tarjeta_exp, "nombre", None) if tarjeta_exp else None
        else:
            nombre = ident
            tarjeta_exp = self._tarjeta_por_nombre(nombre)
            vid = getattr(tarjeta_exp, "_video_id", None) if tarjeta_exp else None
        if not expandida:
            if self._exploracion_objetivo == nombre or getattr(self, "_exploracion_objetivo_id", None) == vid:
                self._exploracion_objetivo = None
                self._exploracion_objetivo_id = None
                self._cancelar_exploracion_en_curso()
            return
        # B9.2 — autocolapso respeta fijadas: nunca colapsar automáticamente una fijada
        for candidato, tarjeta in self.tarjetas:
            if getattr(tarjeta, "_fijada", False):
                continue
            if vid is not None:
                if getattr(tarjeta, "_video_id", None) != vid:
                    tarjeta.colapsar()
            else:
                if candidato != nombre:
                    tarjeta.colapsar()
        self._exploracion_objetivo = nombre
        self._exploracion_objetivo_id = vid
        self._encolar_exploracion(nombre)

    def _encolar_exploracion(self, nombre):
        if nombre != self._exploracion_objetivo:
            return
        if nombre in self._cola_exploracion:
            return
        self._cola_exploracion.append(nombre)
        self._cancelar_exploracion_en_curso()
        self._procesar_siguiente_exploracion()

    def _al_densidad_cambiada(self, ident, _valor):
        vid = ident if _es_video_id_valido(ident) else None
        tarjeta = self._tarjeta_por_id(vid) if _es_video_id_valido(vid) else self._tarjeta_por_nombre(ident)
        if tarjeta is None or not tarjeta._expandida:
            return
        self._encolar_exploracion(tarjeta.nombre)

    def _al_modo_tira_cambiada(self, ident, modo):
        # B9.3 virtualizada: densidad es autoridad, Tira solo cambia vista (no segundo pipeline)
        vid = ident if _es_video_id_valido(ident) else None
        tarjeta = self._tarjeta_por_id(vid) if _es_video_id_valido(vid) else self._tarjeta_por_nombre(ident)
        if tarjeta is None or not tarjeta._expandida:
            return
        if modo == MODO_TIRA:
            # asegurar que densidad actual tenga sus fotogramas (reutiliza cache)
            # si faltan, encolar (solo densidad, sin tiempos_tira)
            self._encolar_exploracion(tarjeta.nombre)
        else:
            # Dinámica: nada que encolar, tira ya liberada en Tarjeta
            pass

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
            objetivo_id = getattr(self, "_exploracion_objetivo_id", None)
            if _es_video_id_valido(objetivo_id):
                # B8.3B: identidad estricta por video_id — si no existe tarjeta para ese ID, no-op (no caer por nombre)
                tarjeta = self._tarjeta_por_id(objetivo_id)
                if tarjeta is None:
                    continue
                if getattr(tarjeta, "_video_id", None) != objetivo_id:
                    continue
                if nombre != self._exploracion_objetivo and getattr(tarjeta, "nombre", None) != self._exploracion_objetivo:
                    if getattr(tarjeta, "_video_id", None) != objetivo_id:
                        continue
            else:
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
            # B9.3 — Densidad es única autoridad (Auto o 15/30/60/120/200), tira reutiliza mismo conjunto
            objetivo_manual = getattr(tarjeta, "_densidad_manual", None)
            if isinstance(objetivo_manual, int) and not isinstance(objetivo_manual, bool) and objetivo_manual > 0:
                kwargs_tarea["objetivo_manual"] = objetivo_manual
            # No segundo conjunto tira: solo densidad
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
        if op.get("video_id") is not None and op.get("video_id") != getattr(self, "_exploracion_objetivo_id", None) and op.get("nombre") != self._exploracion_objetivo:
            return
        elif op.get("video_id") is None and op.get("nombre") != self._exploracion_objetivo:
            return
        if resultado.get("cancelado"):
            return
        vid = op.get("video_id")
        if _es_video_id_valido(vid):
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
        else:
            tarjeta = self._tarjeta_por_nombre(op.get("nombre"))
        if tarjeta is None or not tarjeta._expandida:
            return
        # B9.3 virtualizada: solo densos (tira reutiliza mismo conjunto)
        self._aplicar_exploracion_densa(tarjeta, op, resultado)

    def _al_resultado_parcial_exploracion(self, parcial):
        op = self._exploracion_op_actual
        if op is None:
            return
        if op.get("video_id") is not None and op.get("video_id") != getattr(self, "_exploracion_objetivo_id", None) and op.get("nombre") != self._exploracion_objetivo:
            if parcial.get("video_id") != op.get("video_id"):
                return
        elif op.get("nombre") != self._exploracion_objetivo:
            return
        if parcial.get("video_id") != op.get("video_id"):
            return
        vid = op.get("video_id")
        if _es_video_id_valido(vid):
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
        else:
            tarjeta = self._tarjeta_por_nombre(op.get("nombre"))
        if tarjeta is None or not tarjeta._expandida:
            return
        fotogramas = parcial.get("fotogramas") or []
        if not fotogramas:
            return
        # B9.3: todos los parciales son densos (no hay origen tira separado) - manejar ints o tuples
        if fotogramas and isinstance(fotogramas[0], (list, tuple)):
            ms_list = [ms for ms, _ in fotogramas]
            img_list = fotogramas
        else:
            ms_list = list(fotogramas)
            img_list = []
        self._aplicar_exploracion_densa(
            tarjeta,
            op,
            {
                "version": parcial.get("version"),
                "fotogramas": ms_list,
                "imagenes": img_list,
            },
        )

    def _al_error_exploracion(self, _mensaje):
        pass

    def _al_exploracion_finalizada(self):
        self._exploracion_op_actual = None
        self.tarea_exploracion = None
        self._procesar_siguiente_exploracion()

    def _aplicar_exploracion_densa(self, tarjeta, op, resultado):
        """B9.3 virtualización REAL: solo metadata, visuals vía TareaCargaPreviewsVisuales acotada."""
        version = resultado.get("version")
        fotogramas = resultado.get("fotogramas") or []
        if not version or not fotogramas:
            return
        video_id = op.get("video_id")
        # Compat: si resultado trae imagenes (parcial con QImage), poblar cache visual acotado directamente (evitar re-lectura)
        imagenes = {}
        for item in resultado.get("imagenes") or []:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                imagenes[item[0]] = item[1]
        # Filtrar por existencia en disco si no hay imagen en parcial (test B4.3.2 espera omitir si ruta no existe)
        filtrados = []
        for ms in fotogramas:
            if ms in imagenes:
                filtrados.append(ms)
                continue
            try:
                ruta = exploracion_cache.ruta_fotograma_version(video_id, ms, version)
                import os
                if os.path.isfile(ruta):
                    # verificar que QPixmap no sea nulo (carga ligera via QImage es costosa, pero para test con png pequeño ok)
                    # Para virtualización REAL evitamos carga masiva, pero para test de 1 archivo verificamos isfile
                    filtrados.append(ms)
                else:
                    continue
            except Exception:
                filtrados.append(ms)
        fotogramas = filtrados
        if not fotogramas:
            return
        # Guardar metadata ligera
        try:
            tarjeta.set_metadata_densa(fotogramas, version)
        except Exception:
            # fallback si metodo no existe (test legacy)
            try:
                tarjeta._densidad_version = version
            except Exception:
                pass
        # Si vinieron QImages (parcial), convertir a QPixmap y guardar en cache_visual derivada de necesidad
        if imagenes:
            try:
                ancho, alto = dimensiones_miniatura()
                requeridos = tarjeta._ms_visuales_necesarios() if hasattr(tarjeta, "_ms_visuales_necesarios") else set()
                for ms, img in imagenes.items():
                    if ms in fotogramas:
                        # solo conservar si está en requeridos (si requeridos vacío, conservar temporal para primer pintado)
                        if requeridos and ms not in requeridos:
                            continue
                        try:
                            pm = QPixmap.fromImage(img)
                            if not pm.isNull():
                                pm_s = pm.scaled(ancho, alto, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                tarjeta._cache_visual[ms] = pm_s
                        except Exception:
                            pass
                try:
                    tarjeta._sincronizar_cache_visual()
                except Exception:
                    pass
                try:
                    if getattr(tarjeta, "_modo_tira_b93", MODO_TIRA_DINAMICA) == MODO_TIRA:
                        tarjeta._tira_refrescar_viewport()
                except Exception:
                    pass
                try:
                    tarjeta._refrescar_exploracion()
                except Exception:
                    pass
            except Exception:
                pass

    def _al_preview_visual_solicitada(self, payload):
        """B9.3: cola FAIR por tarjeta/video — GestorTareas sin cola interna.

        Garantías:
        - Una sola op pendiente por video_id además de la activa (coalescing).
        - Orden FIFO entre videos distintos (round-robin); segunda solicitud del mismo video reemplaza/coalesce sin adelantar posición.
        - Deduplicación estable preservando orden de ms_lista / necesidad actual (no set aleatorio).
        - Si se fusiona, se limpia pending de ms que quedan fuera del op fusionado (F).
        - Cola acotada por tarjetas con demanda (máx práctico = nº tarjetas), no 32 batches arbitrarios (G).
        """
        try:
            video_id = payload.get("video_id")
            version = payload.get("version")
            ms_lista = payload.get("ms_lista") or []
            request_id = payload.get("request_id")
            if not _es_video_id_valido(video_id) or not version or not ms_lista:
                return
            tarjeta = self._tarjeta_por_id(video_id)
            if tarjeta is None:
                return
            # Normalizar ms_lista: int >0, dedup estable preservando orden de emisión, límite 12 por batch
            try:
                norm = []
                seen = set()
                for ms in ms_lista:
                    if isinstance(ms, int) and not isinstance(ms, bool) and ms > 0 and ms not in seen:
                        seen.add(ms)
                        norm.append(ms)
                ms_lista = norm[:12]
                if not ms_lista:
                    return
            except Exception:
                return
            # Deduplicación por video_id: coalescing en la misma posición (fairness D)
            try:
                for op_q in self._cola_previews_visuales:
                    if op_q.get("video_id") == video_id:
                        existing = list(op_q.get("ms_lista") or [])
                        # Merge ordenado: existing + nuevos, dedup preservando primera aparición (estable)
                        merged_ordered = []
                        seen_merge = set()
                        for m in existing + ms_lista:
                            if m not in seen_merge:
                                seen_merge.add(m)
                                merged_ordered.append(m)
                        # Si supera 12, priorizar requeridos actuales preservando orden relativo
                        if len(merged_ordered) > 12:
                            try:
                                req = tarjeta._ms_visuales_necesarios() if hasattr(tarjeta, "_ms_visuales_necesarios") else set()
                                if req:
                                    prioritized = [m for m in merged_ordered if m in req]
                                    remainder = [m for m in merged_ordered if m not in req]
                                    merged_ordered = (prioritized + remainder)[:12]
                                else:
                                    merged_ordered = merged_ordered[:12]
                            except Exception:
                                merged_ordered = merged_ordered[:12]
                        # Limpiar pending de ms descartados por fusión (F): viejos+new que quedan fuera
                        try:
                            dropped = (set(existing) | set(ms_lista)) - set(merged_ordered)
                            for m in dropped:
                                try:
                                    tarjeta._cache_visual_pending.discard(m)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        op_q["ms_lista"] = list(merged_ordered)
                        # Actualizar gen/version solo si la nueva generación reemplaza a la vieja (F)
                        # request_id nuevo es >= viejo si tarjeta incrementó gen; actualizar de todos modos porque representa necesidad más reciente
                        op_q["request_id"] = request_id
                        op_q["version"] = version
                        # Cola acotada: con coalescing el máximo práctico es nº tarjetas con demanda
                        # Mantener safety cap 32 solo como límite absoluto sin starvation (G)
                        if len(self._cola_previews_visuales) > 32:
                            old = self._cola_previews_visuales.pop(0)
                            try:
                                t_old = self._tarjeta_por_id(old.get("video_id"))
                                if t_old is not None:
                                    for m in old.get("ms_lista") or []:
                                        t_old._cache_visual_pending.discard(m)
                            except Exception:
                                pass
                        self._procesar_siguiente_preview_visual()
                        return
            except Exception:
                pass
            # Nuevo video distinto: append FIFO al final (fair entre videos)
            # Acotar cola total antes de encolar (cap 32 safety)
            if len(self._cola_previews_visuales) >= 32:
                old = self._cola_previews_visuales.pop(0)
                try:
                    t_old = self._tarjeta_por_id(old.get("video_id"))
                    if t_old is not None:
                        for m in old.get("ms_lista") or []:
                            t_old._cache_visual_pending.discard(m)
                except Exception:
                    pass
            self._cola_previews_visuales.append({"video_id": video_id, "version": version, "ms_lista": list(ms_lista), "request_id": request_id})
            self._procesar_siguiente_preview_visual()
        except Exception:
            pass

    def _procesar_siguiente_preview_visual(self):
        try:
            if self.gestor_previews_visuales.activo:
                return
            while self._cola_previews_visuales:
                op = self._cola_previews_visuales.pop(0)
                video_id = op.get("video_id")
                version = op.get("version")
                ms_lista = op.get("ms_lista") or []
                request_id = op.get("request_id")
                tarjeta = self._tarjeta_por_id(video_id)
                if tarjeta is None or not getattr(tarjeta, "_expandida", False):
                    if tarjeta is not None:
                        for ms in ms_lista:
                            try:
                                tarjeta._cache_visual_pending.discard(ms)
                            except Exception:
                                pass
                    continue
                if getattr(tarjeta, "_cache_visual_gen", None) != request_id:
                    for ms in ms_lista:
                        try:
                            tarjeta._cache_visual_pending.discard(ms)
                        except Exception:
                            pass
                    continue
                if getattr(tarjeta, "_densidad_version", None) != version:
                    for ms in ms_lista:
                        try:
                            tarjeta._cache_visual_pending.discard(ms)
                        except Exception:
                            pass
                    continue
                # filtrar ms ya en cache
                filtrados = [ms for ms in ms_lista if ms not in getattr(tarjeta, "_cache_visual", {})]
                # si todos ya en cache, limpiar pending y continuar
                if not filtrados:
                    for ms in ms_lista:
                        try:
                            tarjeta._cache_visual_pending.discard(ms)
                        except Exception:
                            pass
                    continue
                # si filtrados vacío parcial, actualizar pending: quitar los que ya no van a cargarse
                # pero mantener pending para los filtrados
                for ms in ms_lista:
                    if ms not in filtrados:
                        try:
                            tarjeta._cache_visual_pending.discard(ms)
                        except Exception:
                            pass
                from tareas_videos import TareaCargaPreviewsVisuales
                tarea = TareaCargaPreviewsVisuales(video_id, version, filtrados, request_id=request_id)
                self._preview_visual_op_actual = op
                if self.gestor_previews_visuales.iniciar(tarea):
                    return
                else:
                    self._preview_visual_op_actual = None
                    # reencolar al frente si rechazo inesperado (gestor aún ocupado)
                    self._cola_previews_visuales.insert(0, op)
                    return
            self._preview_visual_op_actual = None
        except Exception:
            pass

    def _al_previews_visuales_finalizada(self):
        try:
            self._preview_visual_op_actual = None
            self._procesar_siguiente_preview_visual()
        except Exception:
            pass

    def _al_resultado_preview_visual(self, resultado):
        try:
            video_id = resultado.get("video_id")
            version = resultado.get("version")
            request_id = resultado.get("request_id")
            imagenes = resultado.get("imagenes") or []
            tarjeta = self._tarjeta_por_id(video_id)
            if tarjeta is None or not tarjeta._expandida:
                return
            # invalidación por generación/version — no borrar pending de generación nueva válida (C)
            if getattr(tarjeta, "_cache_visual_gen", None) != request_id:
                # descartar resultado viejo pero preservar pending si ms aún requerido por op encolada vigente
                try:
                    queued_ms = set()
                    for op_q in self._cola_previews_visuales:
                        if op_q.get("video_id") == video_id:
                            queued_ms.update(op_q.get("ms_lista") or [])
                    # también considerar op activa si es del mismo video pero con gen vigente (no este stale)
                    if getattr(self, "_preview_visual_op_actual", None) and self._preview_visual_op_actual.get("video_id") == video_id:
                        # si activa es vigente, no aplica (este stale es diferente request_id)
                        pass
                except Exception:
                    queued_ms = set()
                for ms, _ in imagenes:
                    try:
                        if ms not in queued_ms:
                            tarjeta._cache_visual_pending.discard(ms)
                    except Exception:
                        pass
                return
            if getattr(tarjeta, "_densidad_version", None) != version:
                try:
                    queued_ms = set()
                    for op_q in self._cola_previews_visuales:
                        if op_q.get("video_id") == video_id:
                            queued_ms.update(op_q.get("ms_lista") or [])
                except Exception:
                    queued_ms = set()
                for ms, _ in imagenes:
                    try:
                        if ms not in queued_ms:
                            tarjeta._cache_visual_pending.discard(ms)
                    except Exception:
                        pass
                return
            ancho, alto = dimensiones_miniatura()
            for ms, qimg in imagenes:
                try:
                    tarjeta._cache_visual_pending.discard(ms)
                except Exception:
                    pass
                try:
                    pm = QPixmap.fromImage(qimg)
                    if not pm.isNull():
                        pm_s = pm.scaled(ancho, alto, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        tarjeta._cache_visual[ms] = pm_s
                except Exception:
                    pass
            # expulsar todo fuera del conjunto requerido
            try:
                tarjeta._sincronizar_cache_visual()
            except Exception:
                pass
            # refrescar vistas afectadas
            try:
                tarjeta._refrescar_exploracion()
                if getattr(tarjeta, "_modo_tira_b93", MODO_TIRA_DINAMICA)==MODO_TIRA:
                    tarjeta._tira_refrescar_viewport()
                # si hover espera ese ms, repintar
                hover = getattr(tarjeta, "_hover_instante_actual", None)
                if isinstance(hover, (int,float)) and not isinstance(hover,bool):
                    ms_hover = tarjeta._ms_mas_cercano(hover)
                    if ms_hover in [ms for ms,_ in imagenes]:
                        tarjeta._mostrar_preview_para_instante(hover)
            except Exception:
                pass
        except Exception:
            pass

    def _al_error_preview_visual(self, msg):
        pass

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
            else:
                self._programar_recarga_por_filtro()
        elif tipo == "eliminar":
            self._programar_recarga_por_filtro()
        elif tipo == "color":
            self._programar_recarga_por_filtro()

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
                vid = op.get("video_id")
                if _es_video_id_valido(vid):
                    tarjeta = self._tarjeta_por_id(vid)
                    if tarjeta is None:
                        # B8.3B: ID válido inexistente -> no-op seguro (no caer por nombre)
                        self.mensaje_carpeta.setText(f"No se pudo asignar el color del marcador: {mensaje}")
                        return
                else:
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
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    return
            else:
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
        try:
            tarjeta._tira_actualizar_decoraciones()
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

    def _tarjeta_por_id(self, video_id):
        for _, tarjeta in self.tarjetas:
            if getattr(tarjeta, "_video_id", None) == video_id:
                return tarjeta
        return None

    def _aplicar_marcadores_cargados(self, op, filas):
        vid = op.get("video_id")
        if _es_video_id_valido(vid):
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
        else:
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
        try:
            tarjeta._tira_actualizar_decoraciones()
        except Exception:
            pass

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
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    # B8.3B: no caer por nombre cuando ID válido no existe
                    if registro.get("eliminada"):
                        self._encolar_segmento(
                            {
                                "tipo": "eliminar",
                                "segmento_id": seg_id,
                                "video_id": op["video_id"],
                                "nombre": op["nombre"],
                            }
                        )
                    return
            else:
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
            else:
                self._programar_recarga_por_filtro()
        elif tipo == "eliminar":
            self._programar_recarga_por_filtro()
        elif tipo == "actualizar":
            # El registro local ya refleja el nuevo intervalo de forma
            # optimista; se reordena y se reaplica. Si el segmento ya no
            # existía en la base (resultado None), se restaura lo previo.
            registro = op["registro"]
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    # B8.3B: ID válido inexistente -> no-op seguro (no caer por nombre)
                    if resultado is None:
                        registro["inicio"] = op["previo"]["inicio"]
                        registro["fin"] = op["previo"]["fin"]
                        self.mensaje_carpeta.setText("No se pudo actualizar el segmento: ya no existe.")
                    return
            else:
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
        elif tipo == "color":
            self._programar_recarga_por_filtro()

    def _al_error_segmentos(self, mensaje):
        op = self._segmento_op_actual
        if op is None:
            return
        tipo = op.get("tipo")
        if tipo == "crear":
            registro = op["registro"]
            registro["eliminada"] = False
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    self.mensaje_carpeta.setText(f"No se pudo guardar el segmento: {mensaje}")
                    return
            else:
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
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    self.mensaje_carpeta.setText(f"No se pudo asignar el color del segmento: {mensaje}")
                    return
            else:
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
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    return
            else:
                tarjeta = self._tarjeta_por_nombre(op["nombre"])
            if tarjeta is not None:
                tarjeta._segmentos_cargados = False
                tarjeta._segmentos_eliminados_carga.clear()
        elif tipo == "actualizar":
            # La edición optimista se revierte al estado previo.
            registro = op["registro"]
            registro["inicio"] = op["previo"]["inicio"]
            registro["fin"] = op["previo"]["fin"]
            vid = op.get("video_id")
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    self.mensaje_carpeta.setText(f"No se pudo actualizar el segmento: {mensaje}")
                    return
            else:
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
        try:
            tarjeta._tira_actualizar_decoraciones()
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

    def _al_segmento_exportacion_solicitada(self, tarjeta, segmento):
        """Acción mínima B6.7: exportar un segmento individual a archivo nuevo."""
        if self.gestor_export.activo:
            QMessageBox.information(
                self, "Exportar segmento", "Ya hay una exportación en curso."
            )
            return
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            QMessageBox.warning(self, "Exportar segmento", "Video no disponible.")
            return
        inicio = segmento.get("inicio")
        fin = segmento.get("fin")
        if not isinstance(inicio, (int, float)) or not isinstance(fin, (int, float)):
            QMessageBox.warning(self, "Exportar segmento", "Segmento con tiempos inválidos.")
            return
        ruta_fuente = self._ruta_video_de(tarjeta)
        if ruta_fuente is None:
            QMessageBox.warning(
                self, "Exportar segmento", "El video de origen ya no está disponible."
            )
            return
        # Sugerir nombre delegando al motor puro B6.8 (sin duplicar reglas)
        try:
            sugerido = nombres.generar_sugerencia_exportacion(
                tarjeta.nombre, float(inicio), float(fin), extension=".mp4"
            )
        except nombres.NombresError as exc:
            QMessageBox.warning(self, "Exportar segmento", f"Nombre sugerido inválido: {exc}")
            return
        ruta_dest, filtro = QFileDialog.getSaveFileName(
            self,
            "Exportar segmento",
            sugerido,
            "Video MP4 (*.mp4);;Video MKV (*.mkv)",
        )
        if not ruta_dest:
            return
        # Asegurar extensión mediante helper puro del motor (no duplicar lógica)
        try:
            ruta_dest = nombres.asegurar_extension(ruta_dest, extensiones_validas={".mp4", ".mkv"}, default=".mp4")
        except nombres.NombresError as exc:
            QMessageBox.warning(self, "Exportar segmento", f"Extensión inválida: {exc}")
            return
        if os.path.exists(ruta_dest):
            QMessageBox.warning(
                self, "Exportar segmento", "El archivo de destino ya existe. Elija otro nombre."
            )
            return
        # No sobrescribir jamás el original ni un destino existente (segunda validación en servicio)
        if os.path.normcase(os.path.normpath(os.path.abspath(ruta_dest))) == os.path.normcase(
            os.path.normpath(os.path.abspath(ruta_fuente))
        ):
            QMessageBox.warning(
                self, "Exportar segmento", "El destino no puede ser el mismo archivo que el origen."
            )
            return
        segmento_id = segmento.get("id")
        # B6.11 alta incremental: pasar trazabilidad al task (fuera del hilo UI)
        try:
            tarea = TareaExportarSegmento(
                ruta_fuente, float(inicio), float(fin), ruta_dest,
                original_video_id=int(video_id) if isinstance(video_id, int) else None,
                segmento_id=int(segmento_id) if isinstance(segmento_id, int) and not isinstance(segmento_id, bool) else None,
                ruta_db=self._ruta_db,
            )
        except Exception:
            tarea = TareaExportarSegmento(ruta_fuente, float(inicio), float(fin), ruta_dest)
        if not self.gestor_export.iniciar(tarea):
            QMessageBox.warning(self, "Exportar segmento", f"No se pudo iniciar: {self.gestor_export.ultimo_rechazo}")
            return
        self._export_segmento_actual = segmento
        self._export_destino_actual = ruta_dest
        self._export_tipo = "individual"
        self._export_lote_activo = False
        self._mostrar_progreso("Exportando segmento…")
        self.boton_cancelar_export.setVisible(True)
        self.boton_cancelar_export.setEnabled(True)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(False)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(False)

    def _cancelar_export(self):
        tarea = getattr(self.gestor_export, "tarea", None)
        if tarea is not None and hasattr(tarea, "cancelar"):
            try:
                tarea.cancelar()
            except Exception:
                pass
        self.estado_escaneo.setText("Cancelando exportación…")
        self.boton_cancelar_export.setEnabled(False)

    # === B6.9 Exportación múltiple de segmentos separados ===
    def _video_ids_visibles(self):
        """Video_ids de los videos visibles (tarjetas filtradas por búsqueda y filtro)."""
        # Construir mapa nombre->tarjeta en una sola pasada O(N) para evitar O(V*T) por cada llamada
        mapa = {nombre: tarjeta for nombre, tarjeta in getattr(self, "tarjetas", [])}
        ids = []
        for nombre in getattr(self, "visibles", []):
            tarjeta = mapa.get(nombre)
            if tarjeta is None:
                continue
            vid = getattr(tarjeta, "_video_id", None)
            if isinstance(vid, int) and not isinstance(vid, bool) and vid > 0:
                ids.append(vid)
        return ids

    def _al_exportar_lote_solicitado(self):
        """Acción global Exportar segmentos… — preparación asíncrona + diálogo + lote secuencial B6.9.

        Flujo real asíncrono (sin SQLite/FFmpeg en hilo UI):
        1) UI construye mapas nombres/rutas en una sola pasada O(N) sobre `tarjetas` (sin O(N²)).
        2) Inicia `TareaListarSegmentosVarios` vía `gestor_preparacion_lote` (fuera del hilo principal).
        3) Mientras carga, bloquea doble disparo del botón y muestra progreso ligero.
        4) Al finalizar (resultado/error/finalizada) restaura UI y, si éxito, abre `DialogoExportarLote`
           puramente presentacional con `segmentos` y `nombres_por_id` ya resueltos.
        5) Tras el diálogo, mantiene exactamente Todos / Por color / Segmentos seleccionados,
           carpeta única, items deterministas y un FFmpeg secuencial.
        """
        if self.gestor_export.activo or getattr(self, "_preparacion_lote_en_curso", False) or getattr(self, "gestor_preparacion_lote", None) is not None and self.gestor_preparacion_lote.activo:
            QMessageBox.information(
                self, "Exportar segmentos", "Ya hay una exportación en curso."
            )
            return
        video_ids = self._video_ids_visibles()
        if not video_ids:
            QMessageBox.information(
                self, "Exportar segmentos", "No hay videos visibles con segmentos para exportar."
            )
            return
        # Construir mapas nombres/rutas en una sola pasada O(N) (evitar O(videos*tarjetas))
        mapa_por_id = {}
        for _nombre, tarjeta in getattr(self, "tarjetas", []):
            vid = getattr(tarjeta, "_video_id", None)
            if isinstance(vid, int) and not isinstance(vid, bool) and vid > 0:
                mapa_por_id[vid] = tarjeta
        nombres_por_id = {}
        rutas_por_id = {}
        for vid in video_ids:
            tarjeta = mapa_por_id.get(vid)
            if tarjeta is not None:
                nombres_por_id[vid] = getattr(tarjeta, "_nombre", f"video {vid}")
                ruta_v = self._ruta_video_de(tarjeta)
                if ruta_v:
                    rutas_por_id[vid] = ruta_v
                else:
                    rutas_por_id[vid] = getattr(tarjeta, "_carpeta_video", "") or nombres_por_id[vid]
            else:
                nombres_por_id[vid] = f"video {vid}"
                rutas_por_id[vid] = f"video {vid}"
        # Bloquear UI mientras carga en background
        self._preparacion_lote_en_curso = True
        self._preparacion_lote_video_ids = list(video_ids)
        self._preparacion_lote_nombres = dict(nombres_por_id)
        self._preparacion_lote_rutas = dict(rutas_por_id)
        self._preparacion_lote_segmentos = None
        self._preparacion_lote_error = None
        self.boton_exportar_lote.setEnabled(False)
        self.estado_escaneo.setText("Cargando segmentos…")
        self._mostrar_progreso("Cargando segmentos…")
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setFormat("Cargando segmentos…")
        self.barra_progreso.setVisible(True)
        # Tarea breve en background (sin SQLite directo en UI thread)
        try:
            from tareas_videos import TareaListarSegmentosVarios
            tarea_carga = TareaListarSegmentosVarios(list(video_ids), self._ruta_db)
        except Exception as exc:
            self._preparacion_lote_en_curso = False
            self.boton_exportar_lote.setEnabled(True)
            self._ocultar_progreso()
            self.estado_escaneo.setText(f"No se pudo preparar: {exc}")
            QMessageBox.warning(self, "Exportar segmentos", f"No se pudo preparar: {exc}")
            return
        if not self.gestor_preparacion_lote.iniciar(tarea_carga):
            self._preparacion_lote_en_curso = False
            self.boton_exportar_lote.setEnabled(True)
            self._ocultar_progreso()
            motivo = getattr(self.gestor_preparacion_lote, "ultimo_rechazo", "desconocido")
            self.estado_escaneo.setText(f"No se pudo iniciar carga: {motivo}")
            QMessageBox.warning(self, "Exportar segmentos", f"No se pudo iniciar carga: {motivo}")
            return

    def _al_preparacion_lote_resultado(self, resultado):
        """Callback de éxito de la tarea breve: guarda segmentos ordenados determinista."""
        if not getattr(self, "_preparacion_lote_en_curso", False):
            return
        try:
            if isinstance(resultado, list):
                self._preparacion_lote_segmentos = sorted(
                    resultado, key=lambda x: (x[1] if len(x) > 1 else 0, x[2] if len(x) > 2 else 0, x[3] if len(x) > 3 else 0, x[0] if len(x) > 0 else 0)
                )
            else:
                self._preparacion_lote_segmentos = []
        except Exception:
            try:
                self._preparacion_lote_segmentos = list(resultado) if isinstance(resultado, list) else []
            except Exception:
                self._preparacion_lote_segmentos = []

    def _al_preparacion_lote_error(self, mensaje):
        """Callback de error de la tarea breve: registra error y prepara restauración."""
        if not getattr(self, "_preparacion_lote_en_curso", False):
            return
        self._preparacion_lote_error = mensaje
        self._preparacion_lote_segmentos = []

    def _al_preparacion_lote_finalizada(self):
        """Restaura UI tras carga y abre diálogo puramente presentacional (o informa error)."""
        if not getattr(self, "_preparacion_lote_en_curso", False):
            return
        video_ids = list(getattr(self, "_preparacion_lote_video_ids", []) or [])
        nombres_por_id = dict(getattr(self, "_preparacion_lote_nombres", {}) or {})
        rutas_por_id = dict(getattr(self, "_preparacion_lote_rutas", {}) or {})
        segmentos = getattr(self, "_preparacion_lote_segmentos", None)
        error_msg = getattr(self, "_preparacion_lote_error", None)
        # Limpiar estado antes de restaurar UI (evita referencias colgadas en cierre/cancelación)
        self._preparacion_lote_en_curso = False
        self._preparacion_lote_video_ids = None
        self._preparacion_lote_nombres = None
        self._preparacion_lote_rutas = None
        self._preparacion_lote_segmentos = None
        self._preparacion_lote_error = None
        self.boton_exportar_lote.setEnabled(True)
        self._ocultar_progreso()
        self.estado_escaneo.clear()
        if error_msg is not None:
            QMessageBox.warning(self, "Exportar segmentos", f"No se pudieron cargar los segmentos: {error_msg}")
            self.estado_escaneo.setText(f"Error al cargar segmentos: {error_msg}")
            return
        if segmentos is None:
            segmentos = []
        # Abrir diálogo con datos ya resueltos (sin SQLite/FFmpeg/subprocess en UI)
        self._abrir_dialogo_lote_con_datos(video_ids, segmentos, nombres_por_id, rutas_por_id)

    def _abrir_dialogo_lote_con_datos(self, video_ids, segmentos_para_dialogo, nombres_por_id, rutas_por_id):
        """Construye DialogoExportarLote presentacional y lanza TareaExportarLoteSegmentos si el usuario acepta."""
        dialogo = DialogoExportarLote(
            self._filtro_catalogo, self._ruta_config, self,
            segmentos=segmentos_para_dialogo, nombres_por_id=nombres_por_id
        )
        if dialogo.exec() != QDialog.Accepted:
            return
        tipo, dato = dialogo.alcance_seleccionado()
        items_explicitos = None
        filtro_color = escanear_videos._SIN_FILTRO_LOTE
        if tipo == "seleccion":
            ids_sel = dato if isinstance(dato, list) else []
            if not ids_sel:
                QMessageBox.information(self, "Exportar segmentos", "No se seleccionó ningún segmento.")
                return
            seg_por_id = {}
            for seg in segmentos_para_dialogo:
                try:
                    seg_por_id[seg[0]] = seg
                except Exception:
                    continue
            items = []
            for seg_id in ids_sel:
                seg = seg_por_id.get(seg_id)
                if seg is None:
                    continue
                try:
                    _id, vid, inicio, fin, color = seg[0], seg[1], seg[2], seg[3], seg[4] if len(seg) > 4 else None
                except Exception:
                    continue
                ruta_fuente = rutas_por_id.get(vid)
                nombre_original = nombres_por_id.get(vid, f"video_{vid}.mp4")
                if not ruta_fuente:
                    ruta_fuente = nombre_original
                try:
                    ini_f = float(inicio)
                    fin_f = float(fin)
                except Exception:
                    continue
                items.append({
                    "segmento_id": _id,
                    "video_id": vid,
                    "ruta_fuente": ruta_fuente,
                    "nombre_original": nombre_original,
                    "inicio": ini_f,
                    "fin": fin_f,
                    "color": color,
                })
            try:
                items = sorted(items, key=lambda it: (it["video_id"], it["inicio"], it["fin"], it["segmento_id"] if it["segmento_id"] is not None else 0))
            except Exception:
                pass
            if not items:
                QMessageBox.information(self, "Exportar segmentos", "No se seleccionó ningún segmento válido.")
                return
            items_explicitos = items
            filtro_color = None
        elif tipo == "todos":
            filtro_color = escanear_videos._SIN_FILTRO_LOTE
        else:
            filtro_color = dato
        carpeta_dest = QFileDialog.getExistingDirectory(
            self, "Carpeta de destino para segmentos", ""
        )
        if not carpeta_dest:
            return
        if not os.path.isdir(carpeta_dest):
            QMessageBox.warning(self, "Exportar segmentos", "Carpeta de destino no válida.")
            return
        task = None
        try:
            from tareas_videos import TareaExportarLoteSegmentos
            if items_explicitos is not None:
                task = TareaExportarLoteSegmentos(
                    carpeta_dest,
                    items=items_explicitos,
                    extension=".mp4",
                    ruta_db=self._ruta_db,
                )
            else:
                task = TareaExportarLoteSegmentos(
                    carpeta_dest,
                    video_ids=video_ids,
                    filtro_color=filtro_color,
                    extension=".mp4",
                    ruta_db=self._ruta_db,
                )
        except Exception as exc:
            QMessageBox.warning(self, "Exportar segmentos", f"No se pudo preparar el lote: {exc}")
            return
        if not self.gestor_export.iniciar(task):
            QMessageBox.warning(
                self, "Exportar segmentos", f"No se pudo iniciar: {self.gestor_export.ultimo_rechazo}"
            )
            return
        self._export_lote_activo = True
        self._export_tipo = "lote"
        self._mostrar_progreso("Exportando segmentos 0/N…")
        total_inicial = len(items_explicitos) if items_explicitos is not None else (len(video_ids) or 1)
        self.barra_progreso.setRange(0, total_inicial)
        self.barra_progreso.setValue(0)
        self.boton_cancelar_export.setVisible(True)
        self.boton_cancelar_export.setEnabled(True)
        self.boton_exportar_lote.setEnabled(False)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(False)

    def _al_progreso_lote(self, procesado, total):
        if not getattr(self, "_export_lote_activo", False):
            return
        if total > 0:
            self.barra_progreso.setRange(0, total)
            self.barra_progreso.setValue(procesado)
            self.barra_progreso.setFormat(f"Exportando segmentos {procesado}/{total}…")
            self.barra_progreso.setVisible(True)
            self._texto_progreso = f"Exportando segmentos {procesado}/{total}…"
            self._progreso_detallado = True

    def _al_resultado_export(self, resultado):
        # Distinguir lote vs individual/secuencia: lote por claves, resto por _export_tipo explícito (sin inferir por filename)
        is_lote = isinstance(resultado, dict) and "total" in resultado and "exitos" in resultado
        if is_lote:
            self._export_lote_activo = False
            self._ocultar_progreso()
            self.boton_cancelar_export.setVisible(False)
            if hasattr(self, "boton_exportar_lote"):
                self.boton_exportar_lote.setEnabled(True)
            if hasattr(self, "boton_exportar_secuencia"):
                self.boton_exportar_secuencia.setEnabled(True)
            total = resultado.get("total", 0)
            exitos_lista = resultado.get("exitos", []) or []
            fallos_lista = resultado.get("fallos", []) or []
            exitos = len(exitos_lista)
            fallos = len(fallos_lista)
            omitidos = len(resultado.get("omitidos", []))
            cancelados = len(resultado.get("cancelados", []))
            omitidos_total = omitidos + cancelados
            cancelado = resultado.get("cancelado", False)
            if total == 0:
                QMessageBox.information(self, "Exportar segmentos", "No se encontraron segmentos para el alcance elegido.")
                self.estado_escaneo.setText("Sin segmentos para exportar")
                return
            if cancelado:
                QMessageBox.information(
                    self,
                    "Exportar segmentos",
                    f"Exportación cancelada: {exitos} exitosos / {fallos} fallidos / {omitidos_total} omitidos o cancelados (total {total}).",
                )
                self.estado_escaneo.setText(
                    f"Cancelado: {exitos} ok / {fallos} fallidos / {omitidos_total} omitidos"
                )
                return
            # B6.11 detalle de altas al catálogo por cada exitoso (solo exitosos, sin reescaneo)
            altas_ok = sum(1 for e in exitos_lista if isinstance(e, dict) and isinstance(e.get("alta_catalogo"), dict) and e.get("alta_catalogo", {}).get("ok"))
            altas_fail = sum(1 for e in exitos_lista if isinstance(e, dict) and isinstance(e.get("alta_catalogo"), dict) and not e.get("alta_catalogo", {}).get("ok"))
            # Mensaje informativo: si hubo fallos de catalogación, conservar archivos y reportar claramente
            detalle_catalogo = ""
            if altas_ok or altas_fail:
                detalle_catalogo = f"\nCatálogo: {altas_ok} incorporados / {altas_fail} fallos de catalogación (archivos conservados)."
            if altas_fail:
                # Reportar detalle de primer fallo si existe
                for e in exitos_lista:
                    if not isinstance(e, dict):
                        continue
                    ac = e.get("alta_catalogo")
                    if isinstance(ac, dict) and not ac.get("ok"):
                        detalle_catalogo += f"\nEj. {os.path.basename(e.get('destino',''))}: {ac.get('error')}"
                        break
            QMessageBox.information(
                self,
                "Exportar segmentos",
                f"Exportación completada: {exitos} exitosos / {fallos} fallidos / {omitidos_total} omitidos o cancelados (total {total}).{detalle_catalogo}",
            )
            estado_extra = f" | catálogo {altas_ok} ok / {altas_fail} fallos" if (altas_ok or altas_fail) else ""
            self.estado_escaneo.setText(
                f"Exportado lote: {exitos} ok / {fallos} fallidos / {omitidos_total} omitidos{estado_extra}"
            )
            return
        # Individual / secuencia: no inferir por filename; usar _export_tipo explícito
        self._ocultar_progreso()
        self.boton_cancelar_export.setVisible(False)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(True)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(True)
        if not isinstance(resultado, dict):
            QMessageBox.warning(self, "Exportar segmento", f"Resultado inesperado: {resultado}")
            return
        es_secuencia = getattr(self, "_export_tipo", None) == "secuencia"
        if resultado.get("cancelado"):
            titulo_cancel = "Unir segmentos" if es_secuencia else "Exportar segmento"
            QMessageBox.information(self, titulo_cancel, "Exportación cancelada.")
            self.estado_escaneo.setText("Exportación cancelada")
            return
        if resultado.get("ok"):
            salida = resultado.get("salida")
            dur = resultado.get("duracion")
            dur_txt = f"{dur:.2f}s" if isinstance(dur, (int, float)) else "desconocida"
            titulo = "Secuencia exportada" if es_secuencia else "Segmento exportado"
            # B6.11 alta incremental: informar si hubo fallo de catalogación conservando archivo
            alta = resultado.get("alta_catalogo")
            extra_catalogo = ""
            estado_catalogo = ""
            if isinstance(alta, dict):
                if alta.get("ok"):
                    extra_catalogo = f"\nIncorporado al catálogo (id {alta.get('derivado_video_id')})."
                    estado_catalogo = " + catálogo"
                else:
                    extra_catalogo = f"\nArchivo conservado pero fallo al incorporar al catálogo:\n{alta.get('error')}"
                    estado_catalogo = " (fallo catálogo, archivo conservado)"
            QMessageBox.information(
                self, titulo, f"{titulo} correctamente:\n{salida}\nDuración: {dur_txt}{extra_catalogo}"
            )
            try:
                nombre_salida = os.path.basename(salida) if isinstance(salida, str) else str(salida)
            except Exception:
                nombre_salida = str(salida)
            self.estado_escaneo.setText(f"Exportado: {nombre_salida} ({dur_txt}){estado_catalogo}")
            return
        error = resultado.get("error") or "error desconocido"
        titulo_error = "Unir segmentos" if es_secuencia else "Exportar segmento"
        QMessageBox.warning(self, titulo_error, f"No se pudo exportar:\n{error}")
        self.estado_escaneo.setText(f"Error al exportar: {error}")

    def _al_error_export(self, mensaje):
        self._export_lote_activo = False
        self._ocultar_progreso()
        self.boton_cancelar_export.setVisible(False)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(True)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(True)
        tipo = getattr(self, "_export_tipo", None)
        if tipo == "lote":
            titulo = "Exportar segmentos"
        elif tipo == "secuencia":
            titulo = "Unir segmentos"
        else:
            titulo = "Exportar segmento"
        QMessageBox.warning(self, titulo, f"Error en exportación:\n{mensaje}")
        self.estado_escaneo.setText(f"Error al exportar: {mensaje}")

    def _al_export_finalizada(self):
        self.boton_cancelar_export.setVisible(False)
        self._export_segmento_actual = None
        self._export_destino_actual = None
        self._export_lote_activo = False
        # limpiar tipo explícito aquí para evitar doble finalización y dejar estado consistente
        self._export_tipo = None
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(True)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(True)
        # Si no hay otro progreso activo, ocultar barra
        if not self._pipeline_activo and not self.gestor_export.activo and not self.gestor.activo:
            self._ocultar_progreso()

    def _al_actividad_export(self, activo):
        # No bloquear escaneo, solo reflejar que hay tarea en curso
        if activo:
            self.boton_cancelar_export.setVisible(True)
        else:
            # la visibilidad se maneja en resultado/error/finalizada
            pass

    # === B6.10 Unión de varios segmentos del mismo original ===
    def _al_exportar_secuencia_solicitado(self):
        """Acción Unir segmentos — reutiliza selección B6.9 con orden explícito.

        Flujo: preparación async de segmentos visibles -> diálogo secuencia con checkboxes + orden -> validación mismo original -> QFileDialog.getSaveFileName con naming B6.8 -> TareaExportarSecuencia en background.
        """
        if self.gestor_export.activo or getattr(self, "_preparacion_secuencia_en_curso", False) or getattr(self, "gestor_preparacion_secuencia", None) is not None and self.gestor_preparacion_secuencia.activo:
            QMessageBox.information(self, "Unir segmentos", "Ya hay una exportación en curso.")
            return
        video_ids = self._video_ids_visibles()
        if not video_ids:
            QMessageBox.information(self, "Unir segmentos", "No hay videos visibles con segmentos para unir.")
            return
        # Mapas nombres/rutas en una pasada O(N)
        mapa_por_id = {}
        for _nombre, tarjeta in getattr(self, "tarjetas", []):
            vid = getattr(tarjeta, "_video_id", None)
            if isinstance(vid, int) and not isinstance(vid, bool) and vid > 0:
                mapa_por_id[vid] = tarjeta
        nombres_por_id = {}
        rutas_por_id = {}
        for vid in video_ids:
            tarjeta = mapa_por_id.get(vid)
            if tarjeta is not None:
                nombres_por_id[vid] = getattr(tarjeta, "_nombre", f"video {vid}")
                ruta_v = self._ruta_video_de(tarjeta)
                if ruta_v:
                    rutas_por_id[vid] = ruta_v
                else:
                    rutas_por_id[vid] = getattr(tarjeta, "_carpeta_video", "") or nombres_por_id[vid]
            else:
                nombres_por_id[vid] = f"video {vid}"
                rutas_por_id[vid] = f"video {vid}"
        self._preparacion_secuencia_en_curso = True
        self._preparacion_secuencia_video_ids = list(video_ids)
        self._preparacion_secuencia_nombres = dict(nombres_por_id)
        self._preparacion_secuencia_rutas = dict(rutas_por_id)
        self._preparacion_secuencia_segmentos = None
        self._preparacion_secuencia_error = None
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(False)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(False)
        self.estado_escaneo.setText("Cargando segmentos para secuencia…")
        self._mostrar_progreso("Cargando segmentos…")
        self.barra_progreso.setRange(0, 0)
        self.barra_progreso.setFormat("Cargando segmentos…")
        self.barra_progreso.setVisible(True)
        try:
            from tareas_videos import TareaListarSegmentosVarios
            tarea_carga = TareaListarSegmentosVarios(list(video_ids), self._ruta_db)
        except Exception as exc:
            self._preparacion_secuencia_en_curso = False
            if hasattr(self, "boton_exportar_secuencia"):
                self.boton_exportar_secuencia.setEnabled(True)
            if hasattr(self, "boton_exportar_lote"):
                self.boton_exportar_lote.setEnabled(True)
            self._ocultar_progreso()
            self.estado_escaneo.setText(f"No se pudo preparar secuencia: {exc}")
            QMessageBox.warning(self, "Unir segmentos", f"No se pudo preparar: {exc}")
            return
        if not self.gestor_preparacion_secuencia.iniciar(tarea_carga):
            self._preparacion_secuencia_en_curso = False
            if hasattr(self, "boton_exportar_secuencia"):
                self.boton_exportar_secuencia.setEnabled(True)
            if hasattr(self, "boton_exportar_lote"):
                self.boton_exportar_lote.setEnabled(True)
            self._ocultar_progreso()
            motivo = getattr(self.gestor_preparacion_secuencia, "ultimo_rechazo", "desconocido")
            self.estado_escaneo.setText(f"No se pudo iniciar carga: {motivo}")
            QMessageBox.warning(self, "Unir segmentos", f"No se pudo iniciar carga: {motivo}")
            return

    def _al_preparacion_secuencia_resultado(self, resultado):
        if not getattr(self, "_preparacion_secuencia_en_curso", False):
            return
        try:
            if isinstance(resultado, list):
                self._preparacion_secuencia_segmentos = sorted(
                    resultado, key=lambda x: (x[1] if len(x) > 1 else 0, x[2] if len(x) > 2 else 0, x[3] if len(x) > 3 else 0, x[0] if len(x) > 0 else 0)
                )
            else:
                self._preparacion_secuencia_segmentos = []
        except Exception:
            try:
                self._preparacion_secuencia_segmentos = list(resultado) if isinstance(resultado, list) else []
            except Exception:
                self._preparacion_secuencia_segmentos = []

    def _al_preparacion_secuencia_error(self, mensaje):
        if not getattr(self, "_preparacion_secuencia_en_curso", False):
            return
        self._preparacion_secuencia_error = mensaje
        self._preparacion_secuencia_segmentos = []

    def _al_preparacion_secuencia_finalizada(self):
        if not getattr(self, "_preparacion_secuencia_en_curso", False):
            return
        video_ids = list(getattr(self, "_preparacion_secuencia_video_ids", []) or [])
        nombres_por_id = dict(getattr(self, "_preparacion_secuencia_nombres", {}) or {})
        rutas_por_id = dict(getattr(self, "_preparacion_secuencia_rutas", {}) or {})
        segmentos = getattr(self, "_preparacion_secuencia_segmentos", None)
        error_msg = getattr(self, "_preparacion_secuencia_error", None)
        self._preparacion_secuencia_en_curso = False
        self._preparacion_secuencia_video_ids = None
        self._preparacion_secuencia_nombres = None
        self._preparacion_secuencia_rutas = None
        self._preparacion_secuencia_segmentos = None
        self._preparacion_secuencia_error = None
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(True)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(True)
        self._ocultar_progreso()
        self.estado_escaneo.clear()
        if error_msg is not None:
            QMessageBox.warning(self, "Unir segmentos", f"No se pudieron cargar los segmentos: {error_msg}")
            self.estado_escaneo.setText(f"Error al cargar segmentos: {error_msg}")
            return
        if segmentos is None:
            segmentos = []
        self._abrir_dialogo_secuencia_con_datos(segmentos, nombres_por_id, rutas_por_id)

    def _abrir_dialogo_secuencia_con_datos(self, segmentos_para_dialogo, nombres_por_id, rutas_por_id):
        dialogo = DialogoExportarSecuencia(segmentos=segmentos_para_dialogo, nombres_por_id=nombres_por_id, parent=self)
        if dialogo.exec() != QDialog.Accepted:
            return
        ids_orden = dialogo.segmentos_ordenados()
        if len(ids_orden) < 2:
            QMessageBox.warning(self, "Unir segmentos", "Seleccione al menos 2 segmentos.")
            return
        vid_sel = dialogo.video_id_seleccionado()
        if vid_sel is None:
            QMessageBox.warning(self, "Unir segmentos", "Los segmentos deben ser del mismo video.")
            return
        # Construir dict segmento por id
        seg_por_id = {}
        for seg in segmentos_para_dialogo:
            try:
                seg_por_id[seg[0]] = seg
            except Exception:
                continue
        segmentos_orden = []
        segmentos_info_orden = []
        for sid in ids_orden:
            seg = seg_por_id.get(sid)
            if seg is None:
                continue
            try:
                _id, vid, inicio, fin = seg[0], seg[1], seg[2], seg[3]
            except Exception:
                continue
            if vid != vid_sel:
                continue
            segmentos_orden.append((float(inicio), float(fin)))
            segmentos_info_orden.append({"segmento_id": int(_id), "inicio": float(inicio), "fin": float(fin)})
        if len(segmentos_orden) < 2:
            QMessageBox.warning(self, "Unir segmentos", "No se obtuvieron 2 segmentos válidos del mismo video.")
            return
        # Validar que no hayan segmentos con fin <= inicio
        for ini, fin in segmentos_orden:
            if not (fin > ini and ini >= 0):
                QMessageBox.warning(self, "Unir segmentos", f"Segmento inválido {ini}-{fin}")
                return
        ruta_fuente = rutas_por_id.get(vid_sel)
        nombre_original = nombres_por_id.get(vid_sel, f"video_{vid_sel}.mp4")
        if not ruta_fuente or not os.path.isfile(ruta_fuente):
            QMessageBox.warning(self, "Unir segmentos", "El video de origen ya no está disponible.")
            return
        # Sugerir nombre via motor B6.8: reutiliza generar_sugerencia_exportacion con primer segmento
        # Para secuencia, sugerimos "{original}_secuencia_{cantidad}seg"
        try:
            sugerido_base = nombres.generar_sugerencia_exportacion(nombre_original, segmentos_orden[0][0], segmentos_orden[-1][1], extension=".mp4")
            # Reemplazar sufijo para indicar secuencia
            base_no_ext = os.path.splitext(sugerido_base)[0]
            sugerido = f"{base_no_ext}_secuencia_{len(segmentos_orden)}seg.mp4"
            # sanitizar ya hecho por motor, pero asegurar extensión
            sugerido = nombres.asegurar_extension(sugerido, extensiones_validas={".mp4", ".mkv"}, default=".mp4")
        except nombres.NombresError as exc:
            QMessageBox.warning(self, "Unir segmentos", f"Nombre sugerido inválido: {exc}")
            return
        ruta_dest, filtro = QFileDialog.getSaveFileName(
            self,
            "Unir segmentos — guardar secuencia",
            sugerido,
            "Video MP4 (*.mp4);;Video MKV (*.mkv)",
        )
        if not ruta_dest:
            return
        try:
            ruta_dest = nombres.asegurar_extension(ruta_dest, extensiones_validas={".mp4", ".mkv"}, default=".mp4")
        except nombres.NombresError as exc:
            QMessageBox.warning(self, "Unir segmentos", f"Extensión inválida: {exc}")
            return
        if os.path.exists(ruta_dest):
            QMessageBox.warning(self, "Unir segmentos", "El archivo de destino ya existe. Elija otro nombre.")
            return
        if os.path.normcase(os.path.normpath(os.path.abspath(ruta_dest))) == os.path.normcase(os.path.normpath(os.path.abspath(ruta_fuente))):
            QMessageBox.warning(self, "Unir segmentos", "El destino no puede ser el mismo archivo que el origen.")
            return
        # Lanzar tarea B6.10 fuera del hilo UI con alta incremental B6.11
        try:
            from tareas_videos import TareaExportarSecuencia
            tarea = TareaExportarSecuencia(
                ruta_fuente, segmentos_orden, ruta_dest,
                original_video_id=int(vid_sel),
                segmentos_info_orden=segmentos_info_orden,
                ruta_db=self._ruta_db,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Unir segmentos", f"No se pudo preparar secuencia: {exc}")
            return
        if not self.gestor_export.iniciar(tarea):
            QMessageBox.warning(self, "Unir segmentos", f"No se pudo iniciar: {self.gestor_export.ultimo_rechazo}")
            return
        self._export_tipo = "secuencia"
        self._export_lote_activo = False
        self._mostrar_progreso("Uniendo segmentos…")
        if hasattr(self, "boton_cancelar_export"):
            self.boton_cancelar_export.setVisible(True)
            self.boton_cancelar_export.setEnabled(True)
        if hasattr(self, "boton_exportar_secuencia"):
            self.boton_exportar_secuencia.setEnabled(False)
        if hasattr(self, "boton_exportar_lote"):
            self.boton_exportar_lote.setEnabled(False)

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
        vid = op.get("video_id")
        if _es_video_id_valido(vid):
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
        else:
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
        try:
            tarjeta._tira_actualizar_decoraciones()
        except Exception:
            pass

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
        for _, tarjeta in self.tarjetas:
            vid = getattr(tarjeta, "_video_id", None)
            if _es_video_id_valido(vid):
                if tarjeta.nombre in self.visibles:
                    self._ids_seleccionados.add(vid)
                    self._nombres_seleccionados.add(tarjeta.nombre)
                    self._marcar_tarjeta_por_id(vid, True)
                continue
            if tarjeta.nombre in self.visibles:
                self._nombres_seleccionados.add(tarjeta.nombre)
                self._marcar_tarjeta(tarjeta.nombre, True)
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

    def _atajo_renombrar(self):
        if self.busqueda.hasFocus():
            return
        if getattr(self, "_ids_seleccionados", set()) and len(self._ids_seleccionados) == 1:
            vid = next(iter(self._ids_seleccionados))
            self._iniciar_renombrar(vid)
            return
        if len(self._nombres_seleccionados) != 1:
            return
        nombre = next(iter(self._nombres_seleccionados))
        self._iniciar_renombrar(nombre)

    def _iniciar_renombrar(self, ident):
        if self.gestor_renombrado.activo or self.gestor.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
            video_id = vid
            nombre = getattr(tarjeta, "nombre", None) or str(vid)
        else:
            nombre = ident
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                return
            video_id = getattr(tarjeta, "_video_id", None)
            if video_id is None:
                self.mensaje_carpeta.setText("No se pudo identificar el video")
                return
        dialogo = DialogoRenombrar(nombre, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        nuevo = dialogo.texto()
        if not nuevo.strip():
            self.mensaje_carpeta.setText("El nombre no puede estar vacío")
            return
        self._renombrado_nombre_anterior = nombre
        tarea = TareaRenombrarVideo(video_id, nuevo, self._ruta_db)
        if not self.gestor_renombrado.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar el renombrado")
            return
        self._renombrado_en_curso = True
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, 0)
        self.mensaje_carpeta.setText(f"Renombrando {nombre}…")
        self._texto_progreso = f"Renombrando {nombre}…"

    def _al_resultado_renombrado(self, resultado):
        # Éxito: actualizar UI sin reescaneo — sincronizando Tarjeta con nueva_ruta (B7.1 fix)
        if not isinstance(resultado, dict) or not resultado.get("ok"):
            return
        video_id = resultado.get("video_id")
        nuevo_nombre = resultado.get("nombre")
        nueva_ruta = resultado.get("ruta")
        anterior = resultado.get("nombre_anterior") or self._renombrado_nombre_anterior
        if not nuevo_nombre or video_id is None:
            return
        # Validación conservadora de nueva_ruta: si falta o no es válida, no declarar éxito silencioso
        if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
            self.mensaje_carpeta.setText("Renombrado inconsistente: ruta no válida")
            self._renombrado_nombre_anterior = None
            return
        try:
            base = os.path.basename(nueva_ruta)
            carpeta = os.path.dirname(nueva_ruta)
            if base != nuevo_nombre or not carpeta:
                self.mensaje_carpeta.setText("Renombrado inconsistente: ruta no coincide con nombre")
                self._renombrado_nombre_anterior = None
                return
        except Exception:
            self.mensaje_carpeta.setText("Renombrado inconsistente: error en ruta")
            self._renombrado_nombre_anterior = None
            return
        # Actualizar estructuras internas
        # tarjetas: lista de (nombre, tarjeta)
        for idx, (nom, tarjeta) in enumerate(self.tarjetas):
            if nom == anterior:
                self.tarjetas[idx] = (nuevo_nombre, tarjeta)
                try:
                    tarjeta.actualizar_nombre(nuevo_nombre, nueva_ruta)
                except TypeError:
                    # Compatibilidad si la firma aún es antigua (un solo arg)
                    try:
                        tarjeta.actualizar_nombre(nuevo_nombre)
                        # Fallback manual de carpeta
                        try:
                            c = os.path.dirname(nueva_ruta)
                            if c:
                                tarjeta._carpeta_video = c.rstrip(os.sep) or c
                        except Exception:
                            pass
                    except Exception:
                        try:
                            tarjeta._nombre = nuevo_nombre
                        except Exception:
                            pass
                except Exception:
                    try:
                        tarjeta._nombre = nuevo_nombre
                    except Exception:
                        pass
                break
        # visibles
        self.visibles = [nuevo_nombre if n == anterior else n for n in self.visibles]
        # selección
        if anterior in self._nombres_seleccionados:
            self._nombres_seleccionados.discard(anterior)
            self._nombres_seleccionados.add(nuevo_nombre)
            if self._ancla_seleccion == anterior:
                self._ancla_seleccion = nuevo_nombre
        self._renombrado_nombre_anterior = None
        self.filtrar(self.busqueda.text())
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()
        self.mensaje_carpeta.setText(f"Renombrado a {nuevo_nombre}")

    def _al_error_renombrado(self, mensaje):
        self.mensaje_carpeta.setText(f"No se pudo renombrar: {mensaje}")
        self._renombrado_nombre_anterior = None

    def _al_renombrado_finalizada(self):
        self._renombrado_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._al_actividad_renombrado(False)

    def _al_actividad_renombrado(self, activa):
        # Deshabilitar botones durante renombrado si fuese necesario; por ahora solo barra
        pass

    def _iniciar_mover(self, ident):
        """Inicia movimiento B7.2 — selector de carpeta existente y tarea background."""
        if self.gestor_mover.activo or self.gestor_renombrado.activo or self.gestor.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
            video_id = vid
            nombre = getattr(tarjeta, "nombre", str(vid))
        else:
            nombre = ident
            tarjeta = self._tarjeta_por_nombre(nombre)
        if tarjeta is None:
            return
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            self.mensaje_carpeta.setText("No se pudo identificar el video")
            return
        # Selector de carpeta existente
        carpeta_destino = QFileDialog.getExistingDirectory(self, "Mover a…", "")
        if not carpeta_destino:
            return
        carpeta_destino = os.path.abspath(carpeta_destino)
        if not os.path.isdir(carpeta_destino):
            self.mensaje_carpeta.setText("Carpeta destino no válida")
            return
        self._mover_nombre_anterior = nombre
        self._mover_video_id = video_id
        tarea = TareaMoverVideo(video_id, carpeta_destino, self._ruta_db)
        if not self.gestor_mover.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar el movimiento")
            return
        self._mover_en_curso = True
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, 0)
        self.mensaje_carpeta.setText(f"Moviendo {nombre}…")
        self._texto_progreso = f"Moviendo {nombre}…"

    def _al_resultado_mover(self, resultado):
        if not isinstance(resultado, dict) or not resultado.get("ok"):
            return
        video_id = resultado.get("video_id")
        nombre = resultado.get("nombre")
        nueva_ruta = resultado.get("ruta")
        anterior = self._mover_nombre_anterior
        # Evidencia para diagnóstico si sincronización falla tras éxito FS/DB
        self._mover_ruta_inconsistente = None
        self._mover_error_sincronizacion = None
        if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
            self._mover_ruta_inconsistente = nueva_ruta
            self._mover_error_sincronizacion = "ruta no válida"
            self.mensaje_carpeta.setText(
                f"Movimiento completado pero UI inconsistente: ruta no válida ({nueva_ruta!r}) — evidencia conservada {nueva_ruta!r}"
            )
            self._mover_nombre_anterior = None
            self._mover_video_id = None
            return
        try:
            base = os.path.basename(nueva_ruta)
            carpeta = os.path.dirname(nueva_ruta)
            # Validación case-insensitive en Windows
            if not base or not carpeta or os.path.normcase(base) != os.path.normcase(nombre or ""):
                self._mover_ruta_inconsistente = nueva_ruta
                self._mover_error_sincronizacion = f"basename {base!r} != nombre {nombre!r}"
                self.mensaje_carpeta.setText(
                    f"Movimiento completado pero UI inconsistente: ruta {nueva_ruta!r} no coincide con nombre {nombre!r} — evidencia conservada"
                )
                self._mover_nombre_anterior = None
                self._mover_video_id = None
                return
        except Exception as exc:
            self._mover_ruta_inconsistente = nueva_ruta
            self._mover_error_sincronizacion = str(exc)
            self.mensaje_carpeta.setText(
                f"Movimiento completado pero UI inconsistente: error en ruta ({exc}) — evidencia {nueva_ruta!r}"
            )
            self._mover_nombre_anterior = None
            self._mover_video_id = None
            return
        # Buscar tarjeta objetivo (mismo nombre/video_id, sin reescaneo)
        tarjeta_objetivo = None
        for nom, tarjeta in self.tarjetas:
            if nom == anterior and getattr(tarjeta, "_video_id", None) == video_id:
                tarjeta_objetivo = tarjeta
                break
        if tarjeta_objetivo is None:
            for nom, tarjeta in self.tarjetas:
                if nom == nombre and getattr(tarjeta, "_video_id", None) == video_id:
                    tarjeta_objetivo = tarjeta
                    break
        if tarjeta_objetivo is None:
            self._mover_ruta_inconsistente = nueva_ruta
            self._mover_error_sincronizacion = "tarjeta no encontrada"
            self.mensaje_carpeta.setText(
                f"Movimiento completado pero UI inconsistente: tarjeta {nombre!r} id={video_id} no encontrada — ruta destino {nueva_ruta!r} conservada"
            )
            self._mover_nombre_anterior = None
            self._mover_video_id = None
            return
        # Sincronización UI estricta sin fallback silencioso
        try:
            tarjeta_objetivo.actualizar_ruta(nueva_ruta)
        except Exception as exc:
            self._mover_ruta_inconsistente = nueva_ruta
            self._mover_error_sincronizacion = str(exc)
            self.mensaje_carpeta.setText(
                f"Movimiento completado pero UI inconsistente: fallo sincronización tarjeta ({exc}) — ruta destino {nueva_ruta!r} conservada para diagnóstico"
            )
            self._mover_nombre_anterior = None
            self._mover_video_id = None
            return
        # Éxito: sincronización y —si la vista actual es la carpeta origen— remover de origen sin reescaneo
        ruta_anterior = resultado.get("ruta_anterior")
        carpeta_origen = None
        vista_es_origen = False
        try:
            if isinstance(ruta_anterior, str) and ruta_anterior:
                carpeta_origen = os.path.dirname(os.path.abspath(ruta_anterior))
                if isinstance(self.carpeta_seleccionada, str) and self.carpeta_seleccionada:
                    if os.path.normcase(os.path.normpath(os.path.abspath(self.carpeta_seleccionada))) == os.path.normcase(os.path.normpath(carpeta_origen)):
                        vista_es_origen = True
        except Exception:
            vista_es_origen = False
        if vista_es_origen:
            try:
                self.cuadricula.removeWidget(tarjeta_objetivo)
            except Exception:
                pass
            try:
                tarjeta_objetivo.hide()
                tarjeta_objetivo.setParent(None)
                tarjeta_objetivo.deleteLater()
            except Exception:
                pass
            for idx, (nom, t) in enumerate(list(self.tarjetas)):
                if t is tarjeta_objetivo:
                    try:
                        del self.tarjetas[idx]
                    except Exception:
                        pass
                    break
            try:
                if nombre in self.visibles:
                    self.visibles.remove(nombre)
            except Exception:
                pass
            try:
                self._nombres_seleccionados.discard(nombre)
                if getattr(self, "_ancla_seleccion", None) == nombre:
                    self._ancla_seleccion = None
            except Exception:
                pass
        self._mover_nombre_anterior = None
        self._mover_video_id = None
        self._mover_ruta_inconsistente = None
        self._mover_error_sincronizacion = None
        self.filtrar(self.busqueda.text())
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()
        self.mensaje_carpeta.setText(f"Movido a {os.path.dirname(nueva_ruta)}")

    def _al_error_mover(self, mensaje):
        self.mensaje_carpeta.setText(f"No se pudo mover: {mensaje}")
        self._mover_nombre_anterior = None
        self._mover_video_id = None

    def _al_mover_finalizada(self):
        self._mover_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._al_actividad_mover(False)

    def _al_actividad_mover(self, activa):
        pass

    # B7.3 creación segura de carpeta
    def _iniciar_crear_carpeta(self, carpeta_padre):
        """Inicia creación B7.3 — diálogo + tarea background."""
        if getattr(self, "gestor_crear_carpeta", None) is None or self.gestor_crear_carpeta.activo or self.gestor.activo or self.gestor_renombrado.activo or self.gestor_mover.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        if not isinstance(carpeta_padre, str) or not carpeta_padre.strip() or not os.path.isdir(carpeta_padre):
            self.mensaje_carpeta.setText("Carpeta padre no válida")
            return
        dialogo = DialogoCrearCarpeta(carpeta_padre, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        nombre = dialogo.texto()
        if not isinstance(nombre, str) or not nombre.strip():
            self.mensaje_carpeta.setText("El nombre no puede estar vacío")
            return
        self._crear_padre_en_curso = carpeta_padre
        self._crear_nombre_en_curso = nombre
        self._crear_ruta_inconsistente = None
        self._crear_error_refresco = None
        tarea = TareaCrearCarpeta(carpeta_padre, nombre)
        if not self.gestor_crear_carpeta.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar creación")
            return
        self._crear_en_curso = True
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, 0)
        self.mensaje_carpeta.setText(f"Creando carpeta {nombre}…")
        self._texto_progreso = f"Creando carpeta {nombre}…"

    def _al_resultado_crear_carpeta(self, resultado):
        if not isinstance(resultado, dict) or not resultado.get("ok"):
            return
        nueva_ruta = resultado.get("ruta")
        padre = resultado.get("padre") or self._crear_padre_en_curso
        if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
            self._crear_ruta_inconsistente = nueva_ruta
            self._crear_error_refresco = "ruta no válida"
            self.mensaje_carpeta.setText("Creación inconsistente: ruta no válida")
            return
        try:
            base = os.path.basename(nueva_ruta)
            carpeta = os.path.dirname(nueva_ruta)
            if base != resultado.get("nombre") or not carpeta:
                self._crear_ruta_inconsistente = nueva_ruta
                self._crear_error_refresco = "basename mismatch"
                self.mensaje_carpeta.setText("Creación inconsistente: ruta no coincide con nombre")
                return
            if not os.path.isdir(nueva_ruta):
                self._crear_ruta_inconsistente = nueva_ruta
                self._crear_error_refresco = "ruta no es directorio tras mkdir"
                self.mensaje_carpeta.setText(f"Carpeta creada pero no verificable en FS: {nueva_ruta!r}")
                return
        except Exception as exc:
            self._crear_ruta_inconsistente = nueva_ruta
            self._crear_error_refresco = str(exc)
            self.mensaje_carpeta.setText(f"Creación inconsistente: error en ruta ({exc})")
            return
        # Refrescar únicamente la rama necesaria sin reescaneo de videos
        try:
            # Buscar padre, revelar si es necesario
            nodo_padre = None
            try:
                nodo_padre = self.arbol_navegacion._buscar_ruta(self.arbol_navegacion.topLevelItem(0), padre)
            except Exception:
                nodo_padre = None
            if nodo_padre is None:
                try:
                    self.arbol_navegacion.revelar_ruta(padre)
                    nodo_padre = self.arbol_navegacion._buscar_ruta(self.arbol_navegacion.topLevelItem(0), padre)
                except Exception:
                    pass
            if nodo_padre is not None:
                try:
                    ok = self.arbol_navegacion.refrescar_carpeta(padre)
                    if not ok:
                        self._crear_ruta_inconsistente = nueva_ruta
                        self._crear_error_refresco = "refrescar_carpeta retornó False"
                        self.mensaje_carpeta.setText(f"Carpeta creada en {nueva_ruta} pero fallo refresco árbol: padre no hallado")
                        return
                except Exception as exc:
                    self._crear_ruta_inconsistente = nueva_ruta
                    self._crear_error_refresco = str(exc)
                    self.mensaje_carpeta.setText(f"Carpeta creada en {nueva_ruta} pero fallo refresco árbol: {exc}")
                    return
                # Seleccionar / hacer visible nueva carpeta
                try:
                    if not self.arbol_navegacion.seleccionar_ruta(nueva_ruta):
                        # fallback revelar
                        self.arbol_navegacion.revelar_ruta(nueva_ruta)
                    self.mensaje_carpeta.setText(f"Carpeta creada: {os.path.basename(nueva_ruta)}")
                except Exception as exc2:
                    self._crear_ruta_inconsistente = nueva_ruta
                    self._crear_error_refresco = str(exc2)
                    self.mensaje_carpeta.setText(f"Carpeta creada en {nueva_ruta} pero fallo selección árbol: {exc2}")
                    return
            else:
                self.mensaje_carpeta.setText(f"Carpeta creada en {nueva_ruta} (fuera de vista actual del árbol)")
        except Exception as exc:
            self._crear_ruta_inconsistente = nueva_ruta
            self._crear_error_refresco = str(exc)
            self.mensaje_carpeta.setText(f"Carpeta creada en {nueva_ruta} pero error UI: {exc}")
            return
        finally:
            # No borrar carpeta creada aunque UI falle (spec)
            pass
        self._crear_padre_en_curso = None
        self._crear_nombre_en_curso = None
        self._crear_ruta_inconsistente = None
        self._crear_error_refresco = None

    def _al_error_crear_carpeta(self, mensaje):
        self.mensaje_carpeta.setText(f"No se pudo crear carpeta: {mensaje}")
        self._crear_padre_en_curso = None
        self._crear_nombre_en_curso = None
        # No borrar nada: si error fue tras mkdir, el servicio ya no borraría; UI tampoco

    def _al_crear_carpeta_finalizada(self):
        self._crear_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._al_actividad_crear_carpeta(False)

    def _al_actividad_crear_carpeta(self, activa):
        pass

    # B7.4 copia individual segura
    def _iniciar_copiar(self, ident):
        """Inicia copia B7.4 — selector de carpeta existente y tarea background."""
        # Bloqueo si hay operación en curso (mover/renombrar/crear/copiar/escaneo)
        if self.gestor_copiar.activo or self.gestor_mover.activo or self.gestor_renombrado.activo or self.gestor.activo or (getattr(self, "gestor_crear_carpeta", None) and self.gestor_crear_carpeta.activo):
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                return
            video_id = vid
            nombre = getattr(tarjeta, "nombre", str(vid))
        else:
            nombre = ident
            tarjeta = self._tarjeta_por_nombre(nombre)
        if tarjeta is None:
            return
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            self.mensaje_carpeta.setText("No se pudo identificar el video")
            return
        carpeta_destino = QFileDialog.getExistingDirectory(self, "Copiar a…", "")
        if not carpeta_destino:
            return
        if not isinstance(carpeta_destino, str) or not carpeta_destino.strip():
            self.mensaje_carpeta.setText("Carpeta destino no válida")
            return
        # Validación FS delegada al servicio/tarea; UI solo consume la cadena del selector
        carpeta_destino = carpeta_destino.strip()
        self._copiar_nombre_origen = nombre
        self._copiar_video_id = video_id
        self._copiar_ruta_inconsistente = None
        self._copiar_error_sincronizacion = None
        tarea = TareaCopiarVideo(video_id, carpeta_destino, self._ruta_db)
        if not self.gestor_copiar.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar la copia")
            return
        self._copiar_en_curso = True
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, 0)
        self.mensaje_carpeta.setText(f"Copiando {nombre}…")
        self._texto_progreso = f"Copiando {nombre}…"

    def _al_resultado_copiar(self, resultado):
        if not isinstance(resultado, dict) or not resultado.get("ok"):
            return
        nombre = resultado.get("nombre")
        nueva_ruta = resultado.get("ruta")
        carpeta_destino = resultado.get("carpeta_destino")
        if carpeta_destino is None:
            carpeta_destino = resultado.get("carpeta_destino_normalizada")
        # Validación mínima sin FS: solo contrato de strings, el servicio ya validó/normalizó FS y existencia
        if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
            self._copiar_ruta_inconsistente = nueva_ruta
            self._copiar_error_sincronizacion = "ruta no válida"
            self.mensaje_carpeta.setText(f"Copia completada pero UI inconsistente: ruta no válida ({nueva_ruta!r}) — evidencia conservada")
            self._copiar_nombre_origen = None
            self._copiar_video_id = None
            return
        if not isinstance(nombre, str) or not nombre.strip():
            self._copiar_ruta_inconsistente = nueva_ruta
            self._copiar_error_sincronizacion = "nombre no válido"
            self.mensaje_carpeta.setText(f"Copia completada pero UI inconsistente: nombre no válido — evidencia {nueva_ruta!r}")
            self._copiar_nombre_origen = None
            self._copiar_video_id = None
            return
        # B7.8: decisión centralizada copia individual — solo recargar si destino es vista actual
        vista_es_destino = self._b78_copia_debe_recargar(carpeta_destino)
        self._copiar_nombre_origen = None
        self._copiar_video_id = None
        self._copiar_ruta_inconsistente = None
        self._copiar_error_sincronizacion = None
        try:
            carpeta_msg = carpeta_destino if isinstance(carpeta_destino, str) and carpeta_destino.strip() else nueva_ruta
            self.mensaje_carpeta.setText(f"Copiado a {carpeta_msg} como {nombre}")
        except Exception:
            self.mensaje_carpeta.setText(f"Copiado como {nombre}")
        if vista_es_destino:
            try:
                if self.gestor.activo:
                    self._reordenamiento_pendiente = True
                else:
                    self._programar_recarga_por_carpeta()
            except Exception:
                pass

    def _al_error_copiar(self, mensaje):
        # Si es inconsistencia post-publicación, mensaje ya indica archivo conservado
        self.mensaje_carpeta.setText(f"No se pudo copiar: {mensaje}")
        self._copiar_nombre_origen = None
        self._copiar_video_id = None

    def _al_copiar_finalizada(self):
        self._copiar_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._al_actividad_copiar(False)

    def _al_actividad_copiar(self, activa):
        pass

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
        gestor_elim = getattr(self, "gestor_eliminar", None)
        habilitado = (
            bool(self._nombres_seleccionados)
            and (gestor_op is None or not gestor_op.activo)
            and (gestor_elim is None or not gestor_elim.activo)
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

    # B7.5 eliminación individual a Papelera vía video_id
    def _iniciar_eliminar_video(self, ident):
        """Inicia eliminación individual segura a Papelera (B7.5).

        Flujo: resuelve video_id via tarjeta, confirma con QMessageBox
        (Eliminar/Cancelar, default Cancelar), delega a TareaEliminarVideo
        en segundo plano sin acceso directo a disco ni base y sin
        recodificación. Cancelación solo antes del punto de no retorno.
        """
        if getattr(self, "gestor_eliminar", None) is None:
            self.mensaje_carpeta.setText("Gestor de eliminación no disponible")
            return
        if self.gestor_eliminar.activo or self.gestor.activo or getattr(self, "_eliminar_en_curso", False):
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        if getattr(self, "gestor_renombrado", None) and self.gestor_renombrado.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        if getattr(self, "gestor_mover", None) and self.gestor_mover.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        if getattr(self, "gestor_copiar", None) and self.gestor_copiar.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is None:
                self.mensaje_carpeta.setText("No se pudo identificar el video")
                return
            video_id = vid
            nombre = getattr(tarjeta, "nombre", str(vid))
        else:
            nombre = ident
            tarjeta = self._tarjeta_por_nombre(nombre)
        if tarjeta is None:
            self.mensaje_carpeta.setText("No se pudo identificar el video")
            return
        video_id = getattr(tarjeta, "_video_id", None)
        if video_id is None:
            self.mensaje_carpeta.setText("No se pudo identificar el video")
            return
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Question)
        caja.setWindowTitle("Eliminar")
        caja.setText(
            f"¿Eliminar '{nombre}'?\n\n"
            "Será enviado a la Papelera de reciclaje y podrá "
            "restaurarse desde allí."
        )
        boton_eliminar = caja.addButton("Eliminar", QMessageBox.AcceptRole)
        boton_cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.setDefaultButton(boton_cancelar)
        caja.exec()
        if caja.clickedButton() != boton_eliminar:
            return
        self._eliminar_video_id = video_id
        self._eliminar_nombre = nombre
        self._eliminar_ruta_inconsistente = None
        self._eliminar_error_sincronizacion = None
        tarea = TareaEliminarVideo(video_id, self._ruta_db)
        if not self.gestor_eliminar.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar la eliminación")
            return
        self._eliminar_en_curso = True
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, 0)
        self.mensaje_carpeta.setText(f"Eliminando {nombre}…")
        self._texto_progreso = f"Eliminando {nombre}…"
        self._actualizar_boton_eliminar()

    def _al_resultado_eliminar_video(self, resultado):
        if not isinstance(resultado, dict) or not resultado.get("ok"):
            return
        if resultado.get("cancelado"):
            self.mensaje_carpeta.setText("Eliminación cancelada")
            self._eliminar_video_id = None
            self._eliminar_nombre = None
            return
        video_id = resultado.get("video_id") or self._eliminar_video_id
        nombre = resultado.get("nombre") or self._eliminar_nombre
        ruta = resultado.get("ruta")
        # Validación mínima de resultado sin FS
        if not isinstance(nombre, str) or not nombre.strip():
            self._eliminar_ruta_inconsistente = ruta
            self._eliminar_error_sincronizacion = "nombre no válido en resultado"
            self.mensaje_carpeta.setText(f"Eliminación completada pero UI inconsistente: nombre no válido — evidencia {ruta!r}")
            self._eliminar_video_id = None
            self._eliminar_nombre = None
            return
        # Remover tarjeta localmente sin reescaneo
        tarjeta_objetivo = None
        for nom, tarjeta in list(self.tarjetas):
            if nom == nombre and getattr(tarjeta, "_video_id", None) == video_id:
                tarjeta_objetivo = tarjeta
                break
        if tarjeta_objetivo is None:
            # fallback por nombre solo
            for nom, tarjeta in list(self.tarjetas):
                if nom == nombre:
                    tarjeta_objetivo = tarjeta
                    break
        if tarjeta_objetivo is None:
            self._eliminar_ruta_inconsistente = ruta
            self._eliminar_error_sincronizacion = "tarjeta no encontrada"
            self.mensaje_carpeta.setText(f"Eliminado {nombre} (archivo en Papelera) — tarjeta ya no estaba en vista")
            # actualizar contadores igualmente
            self._eliminar_video_id = None
            self._eliminar_nombre = None
            self.filtrar(self.busqueda.text())
            self.actualizar_contador()
            self._actualizar_resumen_seleccion()
            return
        try:
            self.cuadricula.removeWidget(tarjeta_objetivo)
        except Exception:
            pass
        try:
            tarjeta_objetivo.hide()
            tarjeta_objetivo.setParent(None)
            tarjeta_objetivo.deleteLater()
        except Exception:
            pass
        # quitar de estructuras
        for idx, (nom, t) in enumerate(list(self.tarjetas)):
            if t is tarjeta_objetivo:
                try:
                    del self.tarjetas[idx]
                except Exception:
                    pass
                break
        try:
            if nombre in self.visibles:
                self.visibles.remove(nombre)
        except Exception:
            pass
        try:
            self._nombres_seleccionados.discard(nombre)
            if getattr(self, "_ancla_seleccion", None) == nombre:
                self._ancla_seleccion = None
        except Exception:
            pass
        # actualizar total paginado
        try:
            if isinstance(getattr(self, "_total_catalogo", None), int) and self._total_catalogo is not None:
                self._total_catalogo = max(0, self._total_catalogo - 1)
        except Exception:
            pass
        self._eliminar_video_id = None
        self._eliminar_nombre = None
        self._eliminar_ruta_inconsistente = None
        self._eliminar_error_sincronizacion = None
        # Reaplicar filtro/orden sin escaneo
        try:
            self.filtrar(self.busqueda.text())
        except Exception:
            pass
        self.actualizar_contador()
        self._actualizar_resumen_seleccion()
        self._actualizar_boton_eliminar()
        self.mensaje_carpeta.setText(f"Eliminado: {nombre}")
        self.estado_escaneo.setText(f"Eliminado: {nombre}")

    def _al_error_eliminar_video(self, mensaje):
        # Si es inconsistencia post-Papelera, mensaje ya contiene ruta conservada
        self.mensaje_carpeta.setText(f"No se pudo eliminar: {mensaje}")
        self._eliminar_video_id = None
        self._eliminar_nombre = None
        self._al_actividad_eliminar_video(False)

    def _al_eliminar_video_finalizada(self):
        self._eliminar_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._al_actividad_eliminar_video(False)
        self._actualizar_boton_eliminar()

    def _al_actividad_eliminar_video(self, activa):
        self._actualizar_boton_eliminar()

    # B7.6 lote masivo seguro (sin FS/SQLite directo desde UI, un solo selector, una sola confirmación)
    def _video_ids_seleccionados_ordenados(self):
        ids_set = getattr(self, "_ids_seleccionados", set())
        if ids_set:
            ids = []
            for _, tarjeta in self.tarjetas:
                vid = getattr(tarjeta, "_video_id", None)
                if vid in ids_set and vid not in ids:
                    ids.append(vid)
            return ids
        ids = []
        for nombre in self.tarjetas_visibles():
            if nombre not in self._nombres_seleccionados:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            vid = getattr(tarjeta, "_video_id", None)
            if isinstance(vid, int) and not isinstance(vid, bool) and vid > 0:
                if vid not in ids:
                    ids.append(vid)
        return ids

    def _lote_esta_ocupado(self):
        if getattr(self, "gestor_lote", None) is not None and self.gestor_lote.activo:
            return True
        if getattr(self, "gestor_renombrado", None) is not None and self.gestor_renombrado.activo:
            return True
        if getattr(self, "gestor_mover", None) is not None and self.gestor_mover.activo:
            return True
        if getattr(self, "gestor_copiar", None) is not None and self.gestor_copiar.activo:
            return True
        if getattr(self, "gestor_eliminar", None) is not None and self.gestor_eliminar.activo:
            return True
        if getattr(self, "gestor_renombrar_masivo", None) is not None and self.gestor_renombrar_masivo.activo:
            return True
        if getattr(self, "gestor_prevalidacion_drop", None) is not None and self.gestor_prevalidacion_drop.activo:
            return True
        if getattr(self, "_prevalidacion_drop_en_curso", False):
            return True
        if getattr(self, "gestor", None) is not None and self.gestor.activo:
            return True
        return False

    def _actualizar_botones_lote(self):
        ocupado = self._lote_esta_ocupado()
        tiene_sel = bool(self._nombres_seleccionados)
        if hasattr(self, "boton_mover_seleccionados"):
            self.boton_mover_seleccionados.setEnabled(tiene_sel and not ocupado)
        if hasattr(self, "boton_copiar_seleccionados"):
            self.boton_copiar_seleccionados.setEnabled(tiene_sel and not ocupado)
        if hasattr(self, "boton_eliminar_seleccionados"):
            self.boton_eliminar_seleccionados.setEnabled(tiene_sel and not ocupado)
        if hasattr(self, "boton_renombrar_masivo"):
            self.boton_renombrar_masivo.setEnabled(tiene_sel and not ocupado)
        if hasattr(self, "boton_cancelar_lote"):
            self.boton_cancelar_lote.setVisible(bool(getattr(self, "_lote_en_curso", False)))
            self.boton_cancelar_lote.setEnabled(bool(getattr(self, "_lote_en_curso", False)))
        if hasattr(self, "boton_cancelar_renombrar_masivo"):
            self.boton_cancelar_renombrar_masivo.setVisible(bool(getattr(self, "_renombrar_masivo_en_curso", False)))
            self.boton_cancelar_renombrar_masivo.setEnabled(bool(getattr(self, "_renombrar_masivo_en_curso", False)))
        # B7.9 reflejar en panel organización (sin ocultar excepciones)
        self._actualizar_panel_organizacion()

    def _al_cambiar_modo_organizacion(self, activo):
        # Preservar selección, carpeta activa, filtros, orden y scroll sin efecto colateral
        # B7.11: splitter vertical secundario dentro de PanelPrincipal (panel arriba, catálogo abajo).
        # Mostrar/ocultar solo afecta distribución del splitter, no el maximum del contenido del catálogo.
        # Se preserva valor vertical exacto; se reprograma diferido por si layout difiere.
        # B7.10: al entrar, cargar navegación embebida del destino (lazy background)
        scroll_previo = None
        barra_previa = None
        if hasattr(self, "area") and self.area is not None:
            b = self.area.verticalScrollBar()
            if b is not None:
                scroll_previo = int(b.value())
                barra_previa = b
        self._modo_organizacion = bool(activo)
        if hasattr(self, "panel_organizacion") and self.panel_organizacion is not None:
            self.panel_organizacion.setVisible(self._modo_organizacion)
            self._actualizar_panel_organizacion()
            if self._modo_organizacion:
                # B7.11: asegurar proporción inicial razonable 25-30% destino / 70-75% catálogo
                try:
                    splitter = getattr(self, "splitter_organizacion", None)
                    if splitter is not None:
                        total = splitter.height()
                        # Si el splitter aún no tiene altura (primer show), usar sizes iniciales ya definidos
                        # Si tiene altura, forzar distribución ajustable inicial si estaba colapsado
                        if total > 80:
                            h_dest = max(110, min(260, int(total * 0.28)))
                            h_cat = total - h_dest
                            if h_cat < 140:
                                h_cat = 140
                                h_dest = total - h_cat
                            splitter.setSizes([h_dest, h_cat])
                        else:
                            splitter.setSizes([150, 470])
                except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
                    print(f"[B7.11] setSizes splitter error: {exc}")
                # Cargar navegación si hay destino, sin tocar origen/catálogo
                try:
                    self._cargar_navegacion_destino()
                except (RuntimeError, AttributeError, ValueError, OSError, TypeError) as exc:
                    print(f"[B7.10] _al_cambiar_modo_organizacion carga navegación error: {exc}")
                    if hasattr(self, "mensaje_carpeta") and self.mensaje_carpeta is not None:
                        try:
                            self.mensaje_carpeta.setText(f"Aviso: navegación destino no disponible ({exc})")
                        except (RuntimeError, AttributeError, TypeError) as exc2:
                            print(f"[B7.10] mensaje_carpeta setText error: {exc2}")
        if scroll_previo is not None and barra_previa is not None:
            barra_previa.setValue(scroll_previo)

            def _restaurar():
                # Restauración diferida para cuando layout recalcula geometría (splitter).
                # Captura solo RuntimeError por destrucción Qt y registra diagnóstico visible.
                b2 = None
                if hasattr(self, "area") and self.area is not None:
                    b2 = self.area.verticalScrollBar()
                if b2 is None:
                    return
                try:
                    b2.setValue(scroll_previo)
                except RuntimeError as exc:
                    print(f"[B7.10] _restaurar scroll RuntimeError: {exc}")
                    if hasattr(self, "mensaje_carpeta") and self.mensaje_carpeta is not None:
                        self.mensaje_carpeta.setText(f"Aviso: no se pudo restaurar scroll ({exc})")

            QTimer.singleShot(0, _restaurar)

    def _actualizar_panel_organizacion(self):
        if not hasattr(self, "panel_organizacion") or self.panel_organizacion is None:
            return
        destino = getattr(self, "_organizacion_destino", None)
        if not isinstance(destino, str) or not destino.strip():
            destino = None
        tiene = bool(getattr(self, "_nombres_seleccionados", set()))
        ocupado = False
        fn = getattr(self, "_lote_esta_ocupado", None)
        if callable(fn):
            ocupado = bool(fn())
        gestor = getattr(self, "gestor", None)
        if gestor is not None and bool(getattr(gestor, "activo", False)):
            ocupado = True
        destino_valido = bool(getattr(self, "_organizacion_destino_valido", False))
        # Si hay error visible, forzar invalido
        error = getattr(self, "_organizacion_error", None)
        if error:
            destino_valido = False
        subcarpetas = getattr(self, "_organizacion_subcarpetas", []) or []
        cargando = bool(getattr(self, "_organizacion_cargando", False))
        puede_subir = False
        if destino and not cargando and not error:
            # Inferir valido si no hay flag explícito pero destino existe (compat B7.9)
            # Si destino_valido es False pero no hay error/cargando, verificar existencia ligera
            if not destino_valido:
                try:
                    import os as _os_chk
                    if _os_chk.path.isdir(destino):
                        destino_valido = True
                except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
                    destino_valido = False
            if destino_valido:
                try:
                    padre = carpeta_padre(destino)
                    puede_subir = padre is not None
                except (OSError, ValueError, AttributeError, RuntimeError, TypeError):
                    puede_subir = False
        # Si no hay destino, destino_valido debe ser False; panel inferirá
        if destino is None:
            destino_valido = False
        try:
            self.panel_organizacion.actualizar(destino, tiene, ocupado, destino_valido=destino_valido, subcarpetas=subcarpetas, error=error, cargando=cargando, puede_subir=puede_subir)
        except TypeError:
            # Compat fallback B7.9 signature 3 args si panel antiguo
            self.panel_organizacion.actualizar(destino, tiene, ocupado)
        # B7.12: sincronizar objetivo completo tras actualizar panel (sin FS adicional)
        # Si panel cambió objetivo a None (reset por navegación), reflejar en estado visor
        # sin emitir ciclo; solo si visor tiene objetivo obsoleto que ya no existe
        try:
            panel_obj = getattr(self.panel_organizacion, "_objetivo_nombre", None)
            visor_obj = getattr(self, "_organizacion_objetivo_nombre", None)
            if panel_obj != visor_obj:
                # panel es fuente de verdad visual; alinear visor si diverge por reconstrucción lista
                if panel_obj is None and visor_obj is not None:
                    # solo alinear si visor tenía hijo que ya no figura en subcarpetas
                    if visor_obj not in (subcarpetas or []):
                        self._organizacion_objetivo_nombre = None
                        self._organizacion_objetivo_completo = None
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.12] sincronizacion objetivo post-actualizar error: {exc}")

    def _al_objetivo_drop_seleccionado(self, nombre):
        """B7.12 — recibe objetivo estable del panel sin FS ni recarga.

        Almacena identificación estable (nombre hijo o None) y resuelve
        destino completo vía rutas.resolver_destino_drop para futuro soltado.
        No modifica origen/filtros/orden/selección/viewport. No implementa
        gesto de arrastre; solo contrato y validación de destino.
        Preserva viewport del catálogo como resto de navegación B7.10+.
        """
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.12] _al_objetivo_drop_seleccionado scroll save error: {exc}")
        # Normalizar nombre recibido del panel (str hijo o None)
        objetivo = None
        if isinstance(nombre, str) and nombre.strip():
            try:
                objetivo = nombre.strip()
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"[B7.12] objetivo strip error: {exc}")
                objetivo = None
            if not objetivo or objetivo in ("(vacío)", "(cargando…)"):
                objetivo = None
            # Validar contra subcarpetas conocidas si destino válido
            try:
                conocidas = getattr(self, "_organizacion_subcarpetas", []) or []
                if objetivo is not None and objetivo not in conocidas:
                    objetivo = None
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"[B7.12] validacion conocida error: {exc}")
        else:
            objetivo = None
        # Si destino inválido/cargando/error, forzar None (panel ya lo hizo, pero visor refuerza)
        try:
            if not getattr(self, "_organizacion_destino_valido", False) or getattr(self, "_organizacion_cargando", False) or getattr(self, "_organizacion_error", None):
                objetivo = None
        except (AttributeError, TypeError) as exc:
            print(f"[B7.12] estado destino check error: {exc}")
        self._organizacion_objetivo_nombre = objetivo
        # Resolver completo vía helper puro (sin FS)
        try:
            from rutas import resolver_destino_drop
            destino = getattr(self, "_organizacion_destino", None)
            if isinstance(destino, str) and destino.strip():
                self._organizacion_objetivo_completo = resolver_destino_drop(destino, objetivo)
            else:
                self._organizacion_objetivo_completo = None
        except (ImportError, AttributeError, ValueError, TypeError, RuntimeError, OSError) as exc:
            print(f"[B7.12] resolver_destino_drop error: {exc}")
            self._organizacion_objetivo_completo = None
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.12] restore scroll error: {exc}")

    def _obtener_destino_drop_actual(self):
        """B7.12 — destino efectivo para futuro soltado (completo o None).

        Contrato reutilizable: si hay objetivo hijo seleccionado retorna
        destino/objetivo, else destino raíz. None si destino inválido/cargando.
        Sin FS directo, delega a rutas.resolver_destino_drop cuando es necesario
        recalcular (panel es fuente de verdad visual).
        """
        # Si ya está cacheado y coincide con estado actual, devolver cache
        try:
            if getattr(self, "_organizacion_objetivo_completo", None) is not None:
                # verificar coherencia con nombre actual y destino actual
                from rutas import resolver_destino_drop
                destino = getattr(self, "_organizacion_destino", None)
                nombre = getattr(self, "_organizacion_objetivo_nombre", None)
                esperado = resolver_destino_drop(destino, nombre) if isinstance(destino, str) and destino.strip() else None
                if esperado == self._organizacion_objetivo_completo:
                    return self._organizacion_objetivo_completo
                # si diverge, actualizar cache
                self._organizacion_objetivo_completo = esperado
                return esperado
        except (ImportError, AttributeError, ValueError, TypeError, RuntimeError, OSError) as exc:
            print(f"[B7.12] _obtener_destino_drop_actual cache error: {exc}")
        try:
            from rutas import resolver_destino_drop
            destino = getattr(self, "_organizacion_destino", None)
            nombre = getattr(self, "_organizacion_objetivo_nombre", None)
            if not isinstance(destino, str) or not destino.strip():
                return None
            if not getattr(self, "_organizacion_destino_valido", False):
                return None
            if getattr(self, "_organizacion_cargando", False) or getattr(self, "_organizacion_error", None):
                return None
            return resolver_destino_drop(destino, nombre)
        except (ImportError, AttributeError, ValueError, TypeError, RuntimeError, OSError) as exc:
            print(f"[B7.12] _obtener_destino_drop_actual error: {exc}")
            return None

    def _validar_destino_drop_actual(self):
        """B7.12 — validación pura de destino drop sin FS redundante."""
        try:
            # Estado ocupado invalida drop aunque destino sea válido (B7.12 contrato)
            try:
                if callable(getattr(self, "_lote_esta_ocupado", None)) and self._lote_esta_ocupado():
                    return False
                if getattr(self, "gestor", None) is not None and getattr(self.gestor, "activo", False):
                    return False
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.12] _validar ocupado check error: {exc}")
            dest = self._obtener_destino_drop_actual()
            if dest is None:
                return False
            from rutas import validar_destino_drop_completo
            return bool(validar_destino_drop_completo(dest))
        except (ImportError, AttributeError, ValueError, TypeError, RuntimeError, OSError) as exc:
            print(f"[B7.12] _validar_destino_drop_actual error: {exc}")
            return False

    # ── B7.13C — conectar drop aceptado a infraestructura existente mover por lote ──
    def _validar_ids_drop_b713c(self, ids):
        """Valida payload ids de drop (lista ordenada de video_id positivos, sin bool)."""
        try:
            if not isinstance(ids, list) or len(ids) == 0:
                return None
            for v in ids:
                if type(v) is not int:
                    return None
                if v <= 0:
                    return None
            return list(ids)
        except (TypeError, ValueError, AttributeError, RuntimeError) as exc:
            print(f"[B7.13C] _validar_ids_drop error: {exc}")
            return None

    def _al_drop_videos_solicitado(self, ids, objetivo):
        """B7.13C — drop → validación → delegación a TareaLoteOperaciones mover.

        - No toca SQLite/FS/FFmpeg directamente; delega a gestor_lote/TareaLoteOperaciones.
        - Preserva responsividad: validación pura y tarea en background; sin rescan global.
        - Validaciones obligatorias: destino válido, no cargando/error/ocupado, ids válidos,
          destino resoluble, lote no ocupado. Cero operación si cualquiera falla.
        - Objetivo puede ser str hijo o None (raíz). Se resuelve vía rutas.resolver_destino_drop.
        """
        # 1. Modo Organización
        try:
            if not getattr(self, "_modo_organizacion", False):
                return
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] modo check error: {exc}")
            return
        # 2. ids válidos
        ids_ok = self._validar_ids_drop_b713c(ids)
        if ids_ok is None:
            return
        # Normalizar objetivo: str strip o None
        objetivo_norm = None
        if isinstance(objetivo, str) and objetivo.strip():
            try:
                objetivo_norm = objetivo.strip()
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"[B7.13C] objetivo strip error: {exc}")
                objetivo_norm = None
            if objetivo_norm in ("(vacío)", "(cargando…)"):
                objetivo_norm = None
            if objetivo_norm in (".", ".."):
                return
            if "/" in objetivo_norm or "\\" in objetivo_norm:
                return
            # validar contra subcarpetas conocidas si destino válido; si no está en lista, rechazar
            try:
                conocidas = getattr(self, "_organizacion_subcarpetas", []) or []
                # solo rechazar si hay lista conocida no vacía y objetivo no está
                if conocidas and objetivo_norm not in conocidas:
                    return
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"[B7.13C] validacion conocida drop error: {exc}")
                return
        else:
            objetivo_norm = None
        # 3. Estado destino / lote ocupado / cargando / error
        try:
            if callable(getattr(self, "_lote_esta_ocupado", None)) and self._lote_esta_ocupado():
                return
            if getattr(self, "gestor", None) is not None and getattr(self.gestor, "activo", False):
                return
            if getattr(self, "_organizacion_cargando", False):
                return
            if getattr(self, "_organizacion_error", None):
                return
            if not getattr(self, "_organizacion_destino_valido", False):
                # compat: si flag invalido pero no hay error/cargando y destino isdir, considerar válido
                # pero para drop exigimos válido estricto para no iniciar operación con destino desaparecido
                # verificar isdir solo si helper dice no accesible; no tocar FS si ya invalido con error
                # B7.13C: sin FS directo, delegar a rutas.listar_subcarpetas ya validó; si invalido -> rechazar
                return
            dest_base = getattr(self, "_organizacion_destino", None)
            if not isinstance(dest_base, str) or not dest_base.strip():
                return
        except (AttributeError, TypeError, RuntimeError, OSError) as exc:
            print(f"[B7.13C] estado destino check error: {exc}")
            return
        # 4. Resolver destino real (objetivo_norm o raíz)
        try:
            dest = resolver_destino_drop(dest_base, objetivo_norm)
        except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
            print(f"[B7.13C] resolver_destino_drop error: {exc}")
            return
        if dest is None:
            return
        try:
            if not validar_destino_drop_completo(dest):
                return
        except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
            print(f"[B7.13C] validar_destino_drop error: {exc}")
            return
        # 5. Prevalidación atómica en background antes de mover (fuera de UI, sin SQLite/FS directo)
        # Evitar doble prevalidación/lote mientras hay operación en curso (incluye prevalidación)
        try:
            if getattr(self, "_prevalidacion_drop_en_curso", False) or (getattr(self, "gestor_prevalidacion_drop", None) is not None and self.gestor_prevalidacion_drop.activo):
                return
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] prevalidacion check error: {exc}")
            return
        # Iniciar tarea de prevalidación (valida existencia IDs + destino real)
        try:
            tarea_pre = TareaPrevalidarDrop(ids_ok, dest, self._ruta_db)
        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as exc:
            print(f"[B7.13C] crear TareaPrevalidarDrop error: {exc}")
            try:
                self.mensaje_carpeta.setText(f"Drop rechazado: {exc}")
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13C] mensaje prevalidacion error: {exc2}")
            return
        # guardar estado pendiente para el callback
        self._prevalidacion_drop_ids = list(ids_ok)
        self._prevalidacion_drop_dest = dest
        self._prevalidacion_drop_en_curso = True
        try:
            self.mensaje_carpeta.setText(f"Validando {len(ids_ok)} videos…")
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] ui prevalidacion progress error: {exc}")
        try:
            ok = self.gestor_prevalidacion_drop.iniciar(tarea_pre)
        except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
            print(f"[B7.13C] gestor_prevalidacion_drop.iniciar error: {exc}")
            self._prevalidacion_drop_en_curso = False
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
            return
        if not ok:
            try:
                motivo = getattr(self.gestor_prevalidacion_drop, "ultimo_rechazo", "")
                self.mensaje_carpeta.setText(f"No se pudo iniciar validación drop: {motivo}")
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13C] mensaje rechazo prevalidacion error: {exc}")
            self._prevalidacion_drop_en_curso = False
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
            return

    def _iniciar_lote_drop_real(self, ids, dest):
        """Inicia TareaLoteOperaciones mover tras prevalidación exitosa (intimo B7.13C)."""
        try:
            tarea = TareaLoteOperaciones("mover", ids, self._ruta_db, carpeta_destino=dest)
        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as exc:
            print(f"[B7.13C] crear TareaLoteOperaciones tras prevalidacion error: {exc}")
            try:
                self.mensaje_carpeta.setText(f"Drop rechazado tras validación: {exc}")
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13C] mensaje post-prevalidacion error: {exc2}")
            return False
        try:
            ok = self.gestor_lote.iniciar(tarea)
        except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
            print(f"[B7.13C] gestor_lote.iniciar tras prevalidacion error: {exc}")
            return False
        if not ok:
            try:
                motivo = getattr(self.gestor_lote, "ultimo_rechazo", "")
                self.mensaje_carpeta.setText(f"No se pudo iniciar mover por drop: {motivo}")
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13C] mensaje rechazo lote post-prevalidacion error: {exc}")
            return False
        self._lote_en_curso = True
        self._lote_operacion = "mover"
        self._lote_video_ids = list(ids)
        self._lote_carpeta_destino = dest
        try:
            self.barra_progreso.setVisible(True)
            self.barra_progreso.setRange(0, len(ids))
            self.barra_progreso.setValue(0)
            self.mensaje_carpeta.setText(f"Moviendo {len(ids)} videos…")
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] ui progress post-prevalidacion error: {exc}")
        try:
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13C] actualizar panel post-lote error: {exc}")
        return True

    def _al_prevalidacion_drop_resultado(self, resultado):
        """Callback background prevalidación B7.13C: si ok inicia lote, si no rechaza con cero movimiento."""
        # Preservar ids/dest guardados; ignorar resultados obsoletos si ya no en curso
        if not getattr(self, "_prevalidacion_drop_en_curso", False):
            return
        ids_guardados = getattr(self, "_prevalidacion_drop_ids", None)
        dest_guardado = getattr(self, "_prevalidacion_drop_dest", None)
        # Limpiar flag antes de decidir lote para evitar doble activación en callbacks reentrantes
        self._prevalidacion_drop_en_curso = False
        # Validar formato resultado
        try:
            if not isinstance(resultado, dict):
                raise ValueError("resultado no es dict")
            ok = bool(resultado.get("ok"))
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            print(f"[B7.13C] _al_prevalidacion_drop_resultado formato error: {exc} resultado={resultado!r}")
            try:
                self.mensaje_carpeta.setText(f"Drop rechazado: validación inválida ({exc})")
            except (AttributeError, RuntimeError) as exc2:
                print(f"[B7.13C] mensaje formato error: {exc2}")
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
            return
        if not ok:
            err = resultado.get("error") if isinstance(resultado, dict) else "error desconocido"
            try:
                self.mensaje_carpeta.setText(f"Drop rechazado: {err}")
                self.mensaje_carpeta.setToolTip(str(err))
            except (AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.13C] mensaje rechazo prevalidacion error: {exc}")
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
            return
        # Éxito: verificar coherencia ids/dest con resultado
        try:
            ids_res = resultado.get("ids")
            dest_res = resultado.get("destino")
            if ids_res is not None and ids_guardados is not None and list(ids_res) != list(ids_guardados):
                print(f"[B7.13C] incoherencia ids prevalidacion guardados {ids_guardados!r} vs resultado {ids_res!r}")
            if dest_res is not None and dest_guardado is not None and dest_res != dest_guardado:
                print(f"[B7.13C] incoherencia dest prevalidacion guardado {dest_guardado!r} vs resultado {dest_res!r}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            print(f"[B7.13C] coherencia check error: {exc}")
        # Estado ocupado puede haber cambiado entre prevalidación y ahora; re-validar lote ocupado
        # Nota: gestor_prevalidacion aún puede reportar activo en tarea_resultado (antes de finalizada),
        # por lo que se chequea solo lote/gestor general, no la propia prevalidación
        try:
            ocupado_post = False
            if getattr(self, "gestor_lote", None) is not None and self.gestor_lote.activo:
                ocupado_post = True
            elif getattr(self, "gestor", None) is not None and self.gestor.activo:
                ocupado_post = True
            elif getattr(self, "_lote_en_curso", False):
                ocupado_post = True
            elif getattr(self, "gestor_renombrar_masivo", None) is not None and self.gestor_renombrar_masivo.activo:
                ocupado_post = True
            elif getattr(self, "gestor_mover", None) is not None and self.gestor_mover.activo:
                ocupado_post = True
            elif getattr(self, "gestor_copiar", None) is not None and self.gestor_copiar.activo:
                ocupado_post = True
            elif getattr(self, "gestor_eliminar", None) is not None and self.gestor_eliminar.activo:
                ocupado_post = True
            if ocupado_post:
                try:
                    self.mensaje_carpeta.setText("Drop rechazado: operación en curso tras validación")
                except (AttributeError, RuntimeError) as exc:
                    print(f"[B7.13C] mensaje ocupado post-prevalidacion error: {exc}")
                self._prevalidacion_drop_ids = None
                self._prevalidacion_drop_dest = None
                self._actualizar_botones_lote()
                self._actualizar_panel_organizacion()
                return
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] ocupado post-prevalidacion check error: {exc}")
        # Iniciar lote real
        ids_final = ids_guardados if isinstance(ids_guardados, list) else resultado.get("ids")
        dest_final = dest_guardado if isinstance(dest_guardado, str) else resultado.get("destino")
        if not isinstance(ids_final, list) or not ids_final or not isinstance(dest_final, str) or not dest_final.strip():
            print(f"[B7.13C] _al_prevalidacion_drop_resultado ids/dest finales inválidos ids={ids_final!r} dest={dest_final!r}")
            try:
                self.mensaje_carpeta.setText("Drop rechazado: datos validados inválidos")
            except (AttributeError, RuntimeError) as exc:
                print(f"[B7.13C] mensaje datos finales error: {exc}")
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
            return
        # Limpiar pendientes antes de iniciar lote (el lote guarda su propio estado)
        self._prevalidacion_drop_ids = None
        self._prevalidacion_drop_dest = None
        ok_lote = self._iniciar_lote_drop_real(ids_final, dest_final)
        if not ok_lote:
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()

    def _al_prevalidacion_drop_error(self, mensaje):
        if not getattr(self, "_prevalidacion_drop_en_curso", False):
            return
        self._prevalidacion_drop_en_curso = False
        try:
            self.mensaje_carpeta.setText(f"Drop rechazado: error validación ({mensaje})")
            self.mensaje_carpeta.setToolTip(str(mensaje))
        except (AttributeError, TypeError, RuntimeError) as exc:
            print(f"[B7.13C] _al_prevalidacion_drop_error mensaje error: {exc}")
        self._prevalidacion_drop_ids = None
        self._prevalidacion_drop_dest = None
        try:
            self._actualizar_botones_lote()
            self._actualizar_panel_organizacion()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            print(f"[B7.13C] _al_prevalidacion_drop_error actualizar error: {exc}")

    def _al_prevalidacion_drop_finalizada(self):
        # Si quedó en curso sin resultado (cancel), limpiar
        if getattr(self, "_prevalidacion_drop_en_curso", False):
            # si gestor ya no activo y no se recibió resultado, limpiar y actualizar
            try:
                if getattr(self, "gestor_prevalidacion_drop", None) is not None and not self.gestor_prevalidacion_drop.activo:
                    self._prevalidacion_drop_en_curso = False
                    self._prevalidacion_drop_ids = None
                    self._prevalidacion_drop_dest = None
                    self._actualizar_botones_lote()
                    self._actualizar_panel_organizacion()
            except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
                print(f"[B7.13C] _al_prevalidacion_drop_finalizada error: {exc}")
                self._prevalidacion_drop_en_curso = False

    def _cargar_navegacion_destino(self):
        """Inicia carga background de subcarpetas del destino (B7.10).

        No toca carpeta origen ni dispara recarga catálogo. Usa helper
        rutas.listar_subcarpetas vía TareaListarSubcarpetasDestino.
        Si destino es None, limpia estado y actualiza panel sin I/O.
        Evita consulta periódica; solo carga bajo demanda (entrar, subir, seleccionar).
        """
        destino = getattr(self, "_organizacion_destino", None)
        if not isinstance(destino, str) or not destino.strip():
            self._organizacion_destino_valido = False
            self._organizacion_subcarpetas = []
            self._organizacion_error = None
            self._organizacion_cargando = False
            self._organizacion_objetivo_nombre = None
            self._organizacion_objetivo_completo = None
            self._actualizar_panel_organizacion()
            return
        # Si hay tarea en curso, no duplicar; esperar
        gestor = getattr(self, "gestor_navegacion_destino", None)
        if gestor is not None and gestor.activo:
            return
        self._organizacion_cargando = True
        self._organizacion_error = None
        self._organizacion_navegacion_version = int(getattr(self, "_organizacion_navegacion_version", 0)) + 1
        destino_norm = destino.strip()
        self._actualizar_panel_organizacion()
        try:
            from tareas_videos import TareaListarSubcarpetasDestino
            tarea = TareaListarSubcarpetasDestino(destino_norm)
        except (ImportError, AttributeError, ValueError, TypeError, RuntimeError, OSError) as exc:
            self._organizacion_cargando = False
            self._organizacion_destino_valido = False
            self._organizacion_error = f"no se pudo iniciar navegación: {exc}"
            self._organizacion_subcarpetas = []
            self._actualizar_panel_organizacion()
            return
        # Bloqueo competitivo: si lote activo, no iniciar navegación (reintentar luego)
        if self._lote_esta_ocupado():
            self._organizacion_cargando = False
            # No mostrar error; simplemente no navegar mientras lote activo
            self._actualizar_panel_organizacion()
            return
        if not gestor.iniciar(tarea):
            self._organizacion_cargando = False
            self._organizacion_error = f"navegación ocupada: {getattr(gestor, 'ultimo_rechazo', '')}"
            self._organizacion_destino_valido = False
            self._actualizar_panel_organizacion()

    def _al_resultado_navegacion_destino(self, resultado):
        """Callback background: actualiza estado navegación sin tocar origen/catálogo. Preserva viewport."""
        # Preservar viewport catálogo: navegación destino jamás debe causar salto de scroll
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _al_resultado_navegacion_destino scroll save error: {exc}")
        if not isinstance(resultado, dict):
            self._organizacion_cargando = False
            self._organizacion_destino_valido = False
            self._organizacion_error = "resultado navegación no válido"
            self._organizacion_subcarpetas = []
            self._actualizar_panel_organizacion()
            if scroll_previo is not None and barra_previa is not None:
                try:
                    barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc:
                    print(f"[B7.11] restore scroll error: {exc}")
            return
        destino_res = resultado.get("destino") or resultado.get("carpeta") or getattr(self, "_organizacion_destino", None)
        # Ignorar resultados obsoletos si destino cambió mientras cargaba
        actual = getattr(self, "_organizacion_destino", None)
        if isinstance(destino_res, str) and isinstance(actual, str):
            try:
                if os.path.normcase(os.path.normpath(destino_res)) != os.path.normcase(os.path.normpath(actual)):
                    # obsoleto, pero limpiar cargando si es el último?
                    self._organizacion_cargando = False
                    self._actualizar_panel_organizacion()
                    return
            except (OSError, ValueError, AttributeError, TypeError, RuntimeError) as exc:
                print(f"[B7.10] _al_resultado_navegacion_destino comparación obsoleta error: {exc}")
                # Continuar procesamiento normal; no ocultar error silencioso
        ok = bool(resultado.get("ok"))
        valido = bool(resultado.get("valido"))
        subcarpetas = resultado.get("subcarpetas") if isinstance(resultado.get("subcarpetas"), list) else []
        error = resultado.get("error")
        self._organizacion_cargando = False
        self._organizacion_destino_valido = bool(ok and valido)
        if not self._organizacion_destino_valido:
            self._organizacion_subcarpetas = []
            self._organizacion_error = error or "destino no disponible"
            # B7.12: destino inválido resetea objetivo estable
            self._organizacion_objetivo_nombre = None
            self._organizacion_objetivo_completo = None
        else:
            self._organizacion_subcarpetas = list(subcarpetas)
            self._organizacion_error = None
            # B7.12: si objetivo previo ya no existe en nueva lista, resetear
            try:
                obj = getattr(self, "_organizacion_objetivo_nombre", None)
                if obj is not None and obj not in subcarpetas:
                    self._organizacion_objetivo_nombre = None
                    self._organizacion_objetivo_completo = None
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"[B7.12] objetivo reset error post-result: {exc}")
        self._actualizar_panel_organizacion()
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] restore scroll error post-result: {exc}")

    def _al_error_navegacion_destino(self, mensaje):
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _al_error_navegacion_destino scroll save error: {exc}")
        self._organizacion_cargando = False
        self._organizacion_destino_valido = False
        self._organizacion_subcarpetas = []
        self._organizacion_error = mensaje or "error al listar destino"
        # B7.12: error resetea objetivo estable
        self._organizacion_objetivo_nombre = None
        self._organizacion_objetivo_completo = None
        self._actualizar_panel_organizacion()
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] restore scroll error: {exc}")

    def _al_navegacion_destino_finalizada(self):
        # Si quedó cargando sin resultado (cancel), limpiar flag
        if getattr(self, "_organizacion_cargando", False):
            # Si gestor ya no activo y no se recibió resultado, dejar como no cargando pero conservar destino_valido previo?
            # Forzar actualización para quitar spinner si no hay resultado
            self._organizacion_cargando = False
            self._actualizar_panel_organizacion()

    def _navegar_destino_a_subcarpeta(self, nombre):
        """Navega destino a subcarpeta hija (B7.10). No modifica origen. Preserva viewport."""
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _navegar_destino_a_subcarpeta scroll save error: {exc}")
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        if getattr(self, "gestor", None) is not None and self.gestor.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        destino = getattr(self, "_organizacion_destino", None)
        if not isinstance(destino, str) or not destino.strip():
            self.mensaje_carpeta.setText("Seleccione destino primero")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        if not isinstance(nombre, str) or not nombre.strip():
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        # Validar queDestino es valido antes de navegar (evitar navegar desde error)
        if not getattr(self, "_organizacion_destino_valido", False):
            self.mensaje_carpeta.setText("Destino no disponible")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        # Construir ruta hija via join (no listar aún)
        try:
            nueva = os.path.join(destino.strip(), nombre.strip())
            # Normalizar
            nueva = os.path.normpath(nueva)
            # Seguridad: debe ser hija directa (no traversal)
            if os.path.normcase(os.path.normpath(nueva)) == os.path.normcase(os.path.normpath(destino.strip())):
                if scroll_previo is not None and barra_previa is not None:
                    try: barra_previa.setValue(scroll_previo)
                    except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
                return
        except (OSError, ValueError, AttributeError, TypeError, RuntimeError) as exc:
            self.mensaje_carpeta.setText(f"No se pudo navegar: {exc}")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc2: print(f"[B7.11] restore scroll error: {exc2}")
            return
        # Actualizar destino y cargar background (sin recarga catálogo)
        # B7.12: navegación resetea objetivo estable (destino nuevo -> objetivo raíz)
        self._organizacion_objetivo_nombre = None
        self._organizacion_objetivo_completo = None
        self._organizacion_destino = nueva
        # No tocar carpeta_seleccionada, filtros, orden, selección
        self._cargar_navegacion_destino()
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
                # diferido
                def _r():
                    try: barra_previa.setValue(scroll_previo)
                    except RuntimeError as exc: print(f"[B7.11] diferido restore scroll error: {exc}")
                QTimer.singleShot(0, _r)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] restore scroll error: {exc}")

    def _navegar_destino_subir(self):
        """Sube destino al padre (B7.10). No modifica origen. Preserva viewport."""
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _navegar_destino_subir scroll save error: {exc}")
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        if getattr(self, "gestor", None) is not None and self.gestor.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        destino = getattr(self, "_organizacion_destino", None)
        if not isinstance(destino, str) or not destino.strip():
            self.mensaje_carpeta.setText("Seleccione destino primero")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        if not getattr(self, "_organizacion_destino_valido", False):
            self.mensaje_carpeta.setText("Destino no disponible")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        try:
            padre = carpeta_padre(destino.strip())
        except (OSError, ValueError, AttributeError, TypeError, RuntimeError) as exc:
            self.mensaje_carpeta.setText(f"No se pudo subir: {exc}")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc2: print(f"[B7.11] restore scroll error: {exc2}")
            return
        if not padre:
            self.mensaje_carpeta.setText("Ya está en la raíz")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        # B7.12: subir resetea objetivo estable
        self._organizacion_objetivo_nombre = None
        self._organizacion_objetivo_completo = None
        self._organizacion_destino = padre
        self._cargar_navegacion_destino()
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
                def _r():
                    try: barra_previa.setValue(scroll_previo)
                    except RuntimeError as exc: print(f"[B7.11] diferido restore scroll error: {exc}")
                QTimer.singleShot(0, _r)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] restore scroll error: {exc}")

    def _seleccionar_destino_organizacion(self):
        # Reutiliza QFileDialog existente; NO cambia carpeta origen ni recarga catálogo
        # B7.10 sincroniza navegador embebido tras elegir. Preserva viewport B7.11.
        scroll_previo = None
        barra_previa = None
        try:
            if hasattr(self, "area") and self.area is not None:
                b = self.area.verticalScrollBar()
                if b is not None:
                    scroll_previo = int(b.value())
                    barra_previa = b
        except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
            print(f"[B7.11] _seleccionar_destino_organizacion scroll save error: {exc}")
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar destino…", "")
        if not carpeta:
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        if isinstance(carpeta, str):
            carpeta_str = carpeta.strip()
        else:
            carpeta_str = carpeta
        if isinstance(carpeta_str, str) and carpeta_str:
            # B7.12: selección nueva resetea objetivo estable
            self._organizacion_objetivo_nombre = None
            self._organizacion_objetivo_completo = None
            self._organizacion_destino = carpeta_str
        else:
            if scroll_previo is not None and barra_previa is not None:
                try: barra_previa.setValue(scroll_previo)
                except (RuntimeError, AttributeError, TypeError) as exc: print(f"[B7.11] restore scroll error: {exc}")
            return
        # Sincronizar navegador embebido: cargar subcarpetas background
        self._cargar_navegacion_destino()
        self._actualizar_panel_organizacion()
        if scroll_previo is not None and barra_previa is not None:
            try:
                barra_previa.setValue(scroll_previo)
                def _r():
                    try: barra_previa.setValue(scroll_previo)
                    except RuntimeError as exc: print(f"[B7.11] diferido restore scroll error: {exc}")
                QTimer.singleShot(0, _r)
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"[B7.11] restore scroll error: {exc}")

    def _ejecutar_lote_organizacion(self, operacion):
        dest = getattr(self, "_organizacion_destino", None)
        if not isinstance(dest, str) or not dest.strip():
            self.mensaje_carpeta.setText("Seleccione destino primero")
            return
        # B7.10: destino debe ser válido y sin error; compat B7.9: inferir valido si isdir y no hay error/cargando
        valido = bool(getattr(self, "_organizacion_destino_valido", False))
        error = getattr(self, "_organizacion_error", None)
        cargando = bool(getattr(self, "_organizacion_cargando", False))
        if not valido and not error and not cargando:
            try:
                import os as _os_chk2
                if _os_chk2.path.isdir(dest.strip()):
                    valido = True
            except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
                valido = False
        if not valido or error:
            self.mensaje_carpeta.setText("Destino no disponible")
            return
        if cargando:
            self.mensaje_carpeta.setText("Destino cargando, intente nuevamente")
            return
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        video_ids = self._video_ids_seleccionados_ordenados()
        if not video_ids:
            return
        tarea = TareaLoteOperaciones(operacion, video_ids, self._ruta_db, carpeta_destino=dest)
        if not self.gestor_lote.iniciar(tarea):
            self.mensaje_carpeta.setText(f"No se pudo iniciar lote {operacion}")
            return
        self._lote_en_curso = True
        self._lote_operacion = operacion
        self._lote_video_ids = list(video_ids)
        self._lote_carpeta_destino = dest
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, len(video_ids))
        self.barra_progreso.setValue(0)
        if operacion == "mover":
            self.mensaje_carpeta.setText(f"Moviendo {len(video_ids)} videos…")
        else:
            self.mensaje_carpeta.setText(f"Copiando {len(video_ids)} videos…")
        self._actualizar_botones_lote()
        self._actualizar_panel_organizacion()

    def _iniciar_lote_mover_organizacion(self):
        self._ejecutar_lote_organizacion("mover")

    def _iniciar_lote_copiar_organizacion(self):
        self._ejecutar_lote_organizacion("copiar")

    def _iniciar_lote_mover(self):
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        video_ids = self._video_ids_seleccionados_ordenados()
        if not video_ids:
            return
        carpeta_destino = QFileDialog.getExistingDirectory(self, "Mover seleccionados a…", "")
        if not carpeta_destino:
            return
        tarea = TareaLoteOperaciones("mover", video_ids, self._ruta_db, carpeta_destino=carpeta_destino)
        if not self.gestor_lote.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar lote mover")
            return
        self._lote_en_curso = True
        self._lote_operacion = "mover"
        self._lote_video_ids = list(video_ids)
        self._lote_carpeta_destino = carpeta_destino
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, len(video_ids))
        self.barra_progreso.setValue(0)
        self.mensaje_carpeta.setText(f"Moviendo {len(video_ids)} videos…")
        self._actualizar_botones_lote()

    def _iniciar_lote_copiar(self):
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        video_ids = self._video_ids_seleccionados_ordenados()
        if not video_ids:
            return
        carpeta_destino = QFileDialog.getExistingDirectory(self, "Copiar seleccionados a…", "")
        if not carpeta_destino:
            return
        tarea = TareaLoteOperaciones("copiar", video_ids, self._ruta_db, carpeta_destino=carpeta_destino)
        if not self.gestor_lote.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar lote copiar")
            return
        self._lote_en_curso = True
        self._lote_operacion = "copiar"
        self._lote_video_ids = list(video_ids)
        self._lote_carpeta_destino = carpeta_destino
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, len(video_ids))
        self.barra_progreso.setValue(0)
        self.mensaje_carpeta.setText(f"Copiando {len(video_ids)} videos…")
        self._actualizar_botones_lote()

    def _iniciar_lote_eliminar(self):
        if self._lote_esta_ocupado():
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        video_ids = self._video_ids_seleccionados_ordenados()
        if not video_ids:
            return
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Question)
        caja.setWindowTitle("Eliminar")
        caja.setText(
            f"¿Eliminar los {len(video_ids)} videos seleccionados?\n\n"
            "Serán enviados a la Papelera de reciclaje y podrán "
            "restaurarse desde allí."
        )
        boton_eliminar = caja.addButton("Eliminar", QMessageBox.AcceptRole)
        boton_cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.setDefaultButton(boton_cancelar)
        caja.exec()
        if caja.clickedButton() != boton_eliminar:
            return
        tarea = TareaLoteOperaciones("eliminar", video_ids, self._ruta_db)
        if not self.gestor_lote.iniciar(tarea):
            self.mensaje_carpeta.setText("No se pudo iniciar lote eliminar")
            return
        self._lote_en_curso = True
        self._lote_operacion = "eliminar"
        self._lote_video_ids = list(video_ids)
        self._lote_carpeta_destino = None
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, len(video_ids))
        self.barra_progreso.setValue(0)
        self.mensaje_carpeta.setText(f"Eliminando {len(video_ids)} videos…")
        self._actualizar_botones_lote()

    def _cancelar_lote(self):
        # Manejo explícito sin ocultamiento: caso esperado vs error inesperado visible
        gestor = getattr(self, "gestor_lote", None)
        tarea = getattr(gestor, "tarea", None) if gestor is not None else None
        if tarea is None or not hasattr(tarea, "cancelar"):
            self.mensaje_carpeta.setText("No hay lote en curso para cancelar")
            self.estado_escaneo.setText("Cancelación lote: sin tarea activa")
            if hasattr(self, "boton_cancelar_lote"):
                self.boton_cancelar_lote.setEnabled(False)
            return
        try:
            tarea.cancelar()
        except RuntimeError as exc:
            self.mensaje_carpeta.setText(f"No se pudo cancelar lote (estado): {exc}")
            self.estado_escaneo.setText(f"Error cancelación lote RuntimeError: {exc}")
            if hasattr(self, "boton_cancelar_lote"):
                self.boton_cancelar_lote.setEnabled(False)
            return
        except AttributeError as exc:
            self.mensaje_carpeta.setText(f"No se pudo cancelar lote (interfaz): {exc}")
            self.estado_escaneo.setText(f"Error cancelación lote AttributeError: {exc}")
            if hasattr(self, "boton_cancelar_lote"):
                self.boton_cancelar_lote.setEnabled(False)
            return
        except Exception as exc:
            self.mensaje_carpeta.setText(f"Error inesperado al cancelar lote: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(f"Error inesperado cancelación lote: {type(exc).__name__}: {exc}")
            if hasattr(self, "boton_cancelar_lote"):
                self.boton_cancelar_lote.setEnabled(False)
            return
        self.mensaje_carpeta.setText("Cancelando lote…")
        self.estado_escaneo.setText("Cancelando lote…")
        if hasattr(self, "boton_cancelar_lote"):
            self.boton_cancelar_lote.setEnabled(False)

    def _al_progreso_lote(self, actual, total):
        if not getattr(self, "_lote_en_curso", False):
            return
        self.barra_progreso.setRange(0, total)
        self.barra_progreso.setValue(actual)
        self.barra_progreso.setVisible(True)

    def _al_resultado_lote(self, resultado):
        # Corrección auditoría B7.6: sin except pass genérico; inconsistencia UI visible y recarga paginada segura
        if not isinstance(resultado, dict):
            self.mensaje_carpeta.setText("Resultado de lote no válido — inconsistencia de sincronización: recarga necesaria")
            self.estado_escaneo.setText("Resultado de lote no válido — recarga programada")
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                self.mensaje_carpeta.setText(f"Resultado inválido y fallo recarga: {exc} — operación física/DB preservada, UI desincronizada")
                self.estado_escaneo.setText(f"Fallo recarga tras lote inválido: {exc}")
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Error inesperado tras lote inválido: {type(exc).__name__}: {exc} — UI desincronizada, DB preservada")
                self.estado_escaneo.setText(f"Error inesperado recarga: {type(exc).__name__}: {exc}")
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            self._actualizar_botones_lote()
            return
        self._lote_resultado_pendiente = resultado
        oper = resultado.get("operacion") or getattr(self, "_lote_operacion", None)
        exitosos = resultado.get("exitosos", []) or []
        fallidos = resultado.get("fallidos", []) or []
        cancelados = resultado.get("cancelados", []) or []
        total = resultado.get("total", 0)
        # Validación de tipos específica sin ocultamiento
        if not isinstance(exitosos, list):
            self.mensaje_carpeta.setText("Lote inconsistente: exitosos no es lista — recarga programada, DB preservada")
            self.estado_escaneo.setText("Inconsistencia UI: exitosos no lista — recarga paginada")
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                self.mensaje_carpeta.setText(f"Inconsistencia UI y fallo recarga: {exc} — DB preservada")
                self.estado_escaneo.setText(f"Fallo recarga: {exc}")
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Error inesperado recarga: {type(exc).__name__}: {exc} — DB preservada")
                self.estado_escaneo.setText(f"Error inesperado recarga: {type(exc).__name__}: {exc}")
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            self._actualizar_botones_lote()
            return
        if not isinstance(fallidos, list):
            self.mensaje_carpeta.setText("Lote inconsistente: fallidos no es lista — recarga programada, DB preservada")
            self.estado_escaneo.setText("Inconsistencia UI: fallidos no lista")
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                self.mensaje_carpeta.setText(f"Inconsistencia UI y fallo recarga: {exc} — DB preservada")
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Error inesperado recarga: {type(exc).__name__}: {exc} — DB preservada")
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            return
        if not isinstance(cancelados, list):
            self.mensaje_carpeta.setText("Lote inconsistente: cancelados no es lista — recarga programada, DB preservada")
            self.estado_escaneo.setText("Inconsistencia UI: cancelados no lista")
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                self.mensaje_carpeta.setText(f"Inconsistencia UI y fallo recarga: {exc} — DB preservada")
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Error inesperado recarga: {type(exc).__name__}: {exc} — DB preservada")
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            return
        inconsistencias = []
        destino = getattr(self, "_lote_carpeta_destino", None)
        # B7.8: decisión centralizada lote — evita recarga duplicada y respeta política segura
        # usa helper _b78_lote_debe_recargar -> carpetas_iguales sin FS directo (rutas)
        try:
            recarga_necesaria = self._b78_lote_debe_recargar(oper, exitosos, destino)
        except Exception as exc:
            inconsistencias.append(f"verificación destino falló: {exc}")
            recarga_necesaria = bool(exitosos)
        # Si hubo exitosos y fallo posterior de refresco UI, no revertir DB: recarga es recuperación segura sin Escanear carpeta y sin tocar FS
        _b78_recarga_programada = False
        if recarga_necesaria:
            try:
                self._programar_recarga_por_carpeta()
                _b78_recarga_programada = True
            except (RuntimeError, AttributeError, ValueError) as exc:
                inconsistencias.append(f"fallo recarga paginada: {exc}")
            except Exception as exc:
                inconsistencias.append(f"error inesperado recarga: {type(exc).__name__}: {exc}")
        # Preservar filtros/orden/paginación: _programar_recarga_por_carpeta usa orden/filtro actuales, no Escanear carpeta
        # Mensaje usuario: resultado parcial e inconsistencia visible; operación física/DB no revertida por fallo visual
        if inconsistencias:
            base = f"Lote {oper}: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total}) — INCONSISTENCIA SINCRONIZACIÓN: {'; '.join(inconsistencias)} — DB preservada, recarga intentada"
            self.mensaje_carpeta.setText(base)
            self.estado_escaneo.setText(base)
        elif fallidos or cancelados:
            detalle = f"Lote {oper}: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total})"
            if fallidos:
                try:
                    ej = fallidos[0].get("error", "")
                    if isinstance(ej, str) and ej:
                        detalle += f" — ej. {ej[:80]}"
                except (AttributeError, TypeError, IndexError) as exc:
                    detalle += f" — (error al extraer ejemplo: {exc})"
                except Exception as exc:
                    detalle += f" — (error inesperado ejemplo: {type(exc).__name__}: {exc})"
            self.mensaje_carpeta.setText(detalle)
            self.estado_escaneo.setText(detalle)
        else:
            self.mensaje_carpeta.setText(f"Lote {oper} completado: {len(exitosos)}/{total}")
            self.estado_escaneo.setText(f"Lote {oper} completado")
        # UX fix-040: tooltip con mensaje completo (aunque detalle recortado a 80, tooltip con error completo si hay fallidos)
        try:
            # si hay fallido, tooltip con error completo sin recortar
            if fallidos:
                try:
                    err_completo = fallidos[0].get("error", "")
                    if isinstance(err_completo, str) and err_completo:
                        tt = f"Lote {oper}: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total}) — ej. {err_completo}"
                        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(tt)
                        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(tt)
                    else:
                        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
                except Exception as exc_tt:
                    hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                    hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            else:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
        except Exception as exc_tt2:
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
        # Reaplicar filtro/orden local sin reescaneo; no propaga FS. Errores visibles, no silencio.
        # B7.8: evitar recarga duplicada si ya se programó por membresía/copia a vista
        try:
            self.filtrar(self.busqueda.text())
        except (AttributeError, TypeError, RuntimeError) as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo filtrar: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — fallo filtrar: {exc}")
            if not _b78_recarga_programada:
                try:
                    self._programar_recarga_por_carpeta()
                    _b78_recarga_programada = True
                except Exception as exc2:
                    self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo recarga tras filtrar: {type(exc2).__name__}: {exc2}")
        except Exception as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado filtrar: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado filtrar: {type(exc).__name__}: {exc}")
            if not _b78_recarga_programada:
                try:
                    self._programar_recarga_por_carpeta()
                    _b78_recarga_programada = True
                except Exception as exc2:
                    self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo recarga: {type(exc2).__name__}: {exc2}")
        try:
            self.actualizar_contador()
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — fallo contador: {exc}")
        except Exception as exc:
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado contador: {type(exc).__name__}: {exc}")
        try:
            self._actualizar_resumen_seleccion()
        except (AttributeError, RuntimeError) as exc:
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — fallo resumen: {exc}")
        except Exception as exc:
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado resumen: {type(exc).__name__}: {exc}")
        # Tooltip final: si hay fallidos con error largo, asegurar que tooltip contiene completo (no recortado 80)
        try:
            if fallidos:
                try:
                    err_full = fallidos[0].get("error", "")
                    if isinstance(err_full, str) and err_full and len(err_full) > 80:
                        full_tt = f"Lote {oper}: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total}) — ej. {err_full}"
                        # append any appended suffix from filtrar/contador if present
                        cur = self.mensaje_carpeta.text()
                        if cur != full_tt and " — fallo" in cur:
                            # preservar sufijo adicional pero tooltip sigue con error completo
                            suffix = cur[cur.find(" — fallo"):]
                            full_tt = full_tt + suffix
                        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(full_tt)
                        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(full_tt)
                    else:
                        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
                except Exception as exc_tt3:
                    hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                    hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            else:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
        except Exception as exc_tt4:
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
        self._actualizar_botones_lote()

    def _al_error_lote(self, mensaje):
        texto_carpeta = f"No se pudo completar lote: {mensaje}"
        texto_estado = f"Error lote: {mensaje}"
        self.mensaje_carpeta.setText(texto_carpeta)
        self.estado_escaneo.setText(texto_estado)
        # UX B7.6 fix-040: mensaje completo accesible aunque QLabel esté truncada (elide)
        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(texto_carpeta)
        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(texto_estado)
        # Guardar detalle completo para inspección/tests y para fallback QMessageBox si se desea
        self._lote_ultimo_error_completo = texto_estado
        # Si el error es global (excepción no capturada por lote), exponer detalle en tooltip ya cubre
        # el requisito sin bloquear UI; QMessageBox opcional no modal no se usa aquí para no bloquear tests

    def _al_lote_finalizada(self):
        self._lote_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._lote_operacion = None
        self._lote_video_ids = None
        self._lote_carpeta_destino = None
        self._al_actividad_lote(False)

    def _al_actividad_lote(self, activa):
        self._actualizar_botones_lote()
        self._actualizar_botones_carpeta()

    # B7.7 renombrado masivo seguro (sin FS/SQLite directo desde UI, preview exacta, ciclos con temporales)
    def _iniciar_renombrar_masivo(self):
        if self._lote_esta_ocupado() or getattr(self, "gestor_renombrar_masivo", None) is not None and self.gestor_renombrar_masivo.activo:
            self.mensaje_carpeta.setText("Hay una operación en curso")
            return
        video_ids = self._video_ids_seleccionados_ordenados()
        if not video_ids:
            self.mensaje_carpeta.setText("Seleccione al menos un video para renombrar")
            return
        # Construir video_infos en orden visible estable
        video_infos = []
        for nombre in self.tarjetas_visibles():
            if nombre not in self._nombres_seleccionados:
                continue
            tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            vid = getattr(tarjeta, "_video_id", None)
            if vid not in video_ids:
                continue
            carpeta = getattr(tarjeta, "_carpeta_video", None) or self.carpeta_seleccionada or ""
            ruta = os.path.join(carpeta, nombre) if carpeta else nombre
            # usar ruta existente si posible
            r_existente = self._ruta_video_de(tarjeta)
            if isinstance(r_existente, str) and r_existente:
                ruta = r_existente
            video_infos.append({"video_id": vid, "nombre": nombre, "ruta": ruta})
        # asegurar orden según ids
        # video_infos ya está en orden visibles, que coincide con ids
        if not video_infos:
            self.mensaje_carpeta.setText("No se pudieron resolver los videos seleccionados")
            return
        dialogo = DialogoRenombrarMasivo(video_infos, self._ruta_db, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        plan = dialogo.plan()
        if not plan:
            self.mensaje_carpeta.setText("Plan de renombrado no válido")
            return
        plantilla = dialogo.plantilla_text()
        texto = dialogo.texto_personalizado()
        try:
            from tareas_videos import TareaRenombrarMasivo
            tarea = TareaRenombrarMasivo(video_infos, plantilla, self._ruta_db, texto=texto)
            tarea.set_plan(plan)
        except Exception as exc:
            self.mensaje_carpeta.setText(f"No se pudo preparar renombrado masivo: {exc}")
            return
        if not self.gestor_renombrar_masivo.iniciar(tarea):
            self.mensaje_carpeta.setText(f"No se pudo iniciar renombrado masivo: {self.gestor_renombrar_masivo.ultimo_rechazo}")
            return
        self._renombrar_masivo_en_curso = True
        self._renombrar_masivo_plan = plan
        # Preservar selección lógica por video_id para restauración post-recarga (fix B7.7 post-rename)
        # video_infos ya validado por construir_plan; validar tipos explícitamente sin captura genérica
        ids_origen_validos = set()
        diagnostico_ids = None
        for idx_info, info_item in enumerate(video_infos):
            if not isinstance(info_item, dict):
                diagnostico_ids = f"video_infos[{idx_info}] no es dict: {type(info_item).__name__}"
                break
            vid_val = info_item.get("video_id")
            if isinstance(vid_val, bool) or not isinstance(vid_val, int) or vid_val <= 0:
                diagnostico_ids = f"video_id inválido en índice {idx_info}: {vid_val!r}"
                break
            ids_origen_validos.add(int(vid_val))
        if diagnostico_ids is not None:
            detalle_ids = f"Inconsistencia al preservar selección por video_id: {diagnostico_ids} — fallback a video_ids ordenados"
            self.mensaje_carpeta.setText(detalle_ids)
            self.estado_escaneo.setText(detalle_ids)
            self.mensaje_carpeta.setToolTip(detalle_ids)
            self.estado_escaneo.setToolTip(detalle_ids)
            if isinstance(video_ids, list) and all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in video_ids):
                self._renombrar_masivo_ids_origen = set(video_ids)
            else:
                self._renombrar_masivo_ids_origen = None
        else:
            self._renombrar_masivo_ids_origen = ids_origen_validos
        self._renombrar_masivo_ids_a_restaurar = None
        # B7.7 UX final: guardar contexto visual mínimo previo (scroll + orden determinista por video_id)
        try:
            self._renombrar_masivo_scroll_previo = int(self.area.verticalScrollBar().value())
        except (AttributeError, TypeError, ValueError, RuntimeError):
            self._renombrar_masivo_scroll_previo = None
        try:
            self._renombrar_masivo_orden_previo = list(self._video_ids_seleccionados_ordenados())
        except (AttributeError, TypeError, RuntimeError, ValueError):
            self._renombrar_masivo_orden_previo = None
        self.barra_progreso.setVisible(True)
        self.barra_progreso.setRange(0, len(plan))
        self.barra_progreso.setValue(0)
        self.mensaje_carpeta.setText(f"Renombrando {len(plan)} videos…")
        self._actualizar_botones_lote()
        self._actualizar_botones_carpeta()

    def _cancelar_renombrar_masivo(self):
        gestor = getattr(self, "gestor_renombrar_masivo", None)
        tarea = getattr(gestor, "tarea", None) if gestor is not None else None
        if tarea is None or not hasattr(tarea, "cancelar"):
            self.mensaje_carpeta.setText("No hay renombrado masivo en curso para cancelar")
            self.estado_escaneo.setText("Cancelación renombrado: sin tarea activa")
            if hasattr(self, "boton_cancelar_renombrar_masivo"):
                self.boton_cancelar_renombrar_masivo.setEnabled(False)
            return
        try:
            tarea.cancelar()
        except (RuntimeError, AttributeError, ValueError) as exc:
            self.mensaje_carpeta.setText(f"No se pudo cancelar renombrado masivo: {exc}")
            self.estado_escaneo.setText(f"Error cancelación renombrado RuntimeError: {exc}")
            if hasattr(self, "boton_cancelar_renombrar_masivo"):
                self.boton_cancelar_renombrar_masivo.setEnabled(False)
            return
        except Exception as exc:
            self.mensaje_carpeta.setText(f"Error inesperado al cancelar renombrado masivo: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(f"Error inesperado cancelación renombrado: {type(exc).__name__}: {exc}")
            if hasattr(self, "boton_cancelar_renombrar_masivo"):
                self.boton_cancelar_renombrar_masivo.setEnabled(False)
            return
        self.mensaje_carpeta.setText("Cancelando renombrado masivo…")
        self.estado_escaneo.setText("Cancelando renombrado masivo…")
        if hasattr(self, "boton_cancelar_renombrar_masivo"):
            self.boton_cancelar_renombrar_masivo.setEnabled(False)

    def _al_progreso_renombrar_masivo(self, actual, total):
        if not getattr(self, "_renombrar_masivo_en_curso", False):
            return
        self.barra_progreso.setRange(0, total)
        self.barra_progreso.setValue(actual)
        self.barra_progreso.setVisible(True)

    def _al_resultado_renombrar_masivo(self, resultado):
        if not isinstance(resultado, dict):
            self.mensaje_carpeta.setText("Resultado renombrado masivo no válido — inconsistencia: recarga necesaria")
            self.estado_escaneo.setText("Resultado renombrado no válido — recarga programada")
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                self.mensaje_carpeta.setText(f"Resultado inválido y fallo recarga: {exc} — DB preservada")
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Error inesperado tras renombrado inválido: {type(exc).__name__}: {exc} — DB preservada")
            hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
            hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            self._actualizar_botones_lote()
            self._actualizar_botones_carpeta()
            return
        exitosos = resultado.get("exitosos", []) or []
        fallidos = resultado.get("fallidos", []) or []
        cancelados = resultado.get("cancelados", []) or []
        total = resultado.get("total", 0)
        if not isinstance(exitosos, list) or not isinstance(fallidos, list):
            self.mensaje_carpeta.setText("Renombrado masivo inconsistente: listas no válidas — recarga programada, DB preservada")
            try:
                self._programar_recarga_por_carpeta()
            except Exception as exc:
                self.mensaje_carpeta.setText(f"Inconsistencia y fallo recarga: {exc} — DB preservada")
            return
        # B7.8: Recarga catálogo mediante política centralizada — si hay éxitos, recarga segura (orden/filtro/paginación)
        # FIX B7.7 post-rename: preservar selección por video_id (no por nombre) y no disparar Escanear/FFprobe
        recarga_necesaria = self._b78_renombrado_masivo_debe_recargar(exitosos)
        # Preparar restauración por video_id: conservar exactamente los mismos video_id (incluye parcial: los que sigan en carpeta/vista)
        # Si el lote fue exitoso o parcial, restauraremos por video_id tras la recarga catalog SQLite
        ids_a_restaurar = None
        _diag_ids_restaurar = None
        try:
            # origen = ids enviados al servicio (preservación exacta)
            origen = getattr(self, "_renombrar_masivo_ids_origen", None)
            if isinstance(origen, set) and origen:
                ids_a_restaurar = set(origen)
            elif isinstance(origen, (list, tuple)):
                ids_a_restaurar = {int(x) for x in origen if isinstance(x, int)}
            # Si no hay origen (fallback), usar exitosos + fallidos que sigan en carpeta
            if not ids_a_restaurar:
                cand = []
                for lst in (exitosos, fallidos, cancelados):
                    for it in lst:
                        vid = it.get("video_id") if isinstance(it, dict) else None
                        if _es_video_id_valido(vid):
                            cand.append(vid)
                if cand:
                    ids_a_restaurar = set(cand)
        except Exception as exc:
            ids_a_restaurar = None
            _diag_ids_restaurar = f"Diagnostico ids_a_restaurar: {type(exc).__name__}: {exc}"
            try:
                self.mensaje_carpeta.setToolTip(_diag_ids_restaurar)
                self.estado_escaneo.setToolTip(_diag_ids_restaurar)
                if not self.mensaje_carpeta.text():
                    self.mensaje_carpeta.setText(_diag_ids_restaurar[:200])
            except Exception as _exc_diag_ids2:
                _diag_ids_fallback = str(_exc_diag_ids2)
        # Solo programar restauración si hay exitosos (hay recarga) y tenemos ids
        if recarga_necesaria and ids_a_restaurar:
            self._renombrar_masivo_ids_a_restaurar = set(ids_a_restaurar)
        elif not recarga_necesaria:
            # Sin recarga (todo falló o cancelado): liberar pendientes de restauración previa
            self._renombrar_masivo_ids_a_restaurar = None
        inconsistencias = []
        if recarga_necesaria:
            try:
                self._programar_recarga_por_carpeta()
            except (RuntimeError, AttributeError, ValueError) as exc:
                inconsistencias.append(f"fallo recarga: {exc}")
            except Exception as exc:
                inconsistencias.append(f"error inesperado recarga: {type(exc).__name__}: {exc}")
        if inconsistencias:
            base = f"Renombrado masivo: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total}) — INCONSISTENCIA: {'; '.join(inconsistencias)} — DB preservada"
            self.mensaje_carpeta.setText(base)
            self.estado_escaneo.setText(base)
        elif fallidos or cancelados:
            detalle = f"Renombrado masivo: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total})"
            if fallidos:
                try:
                    ej = fallidos[0].get("error", "")
                    if isinstance(ej, str) and ej:
                        detalle += f" — ej. {ej[:80]}"
                except (AttributeError, TypeError, IndexError, KeyError) as exc:
                    detalle += f" — error al extraer ejemplo: {exc}"
                    self.mensaje_carpeta.setToolTip(detalle)
                    self.estado_escaneo.setToolTip(detalle)
                except Exception as exc:
                    detalle += f" — error inesperado al extraer ejemplo: {type(exc).__name__}: {exc}"
                    self.mensaje_carpeta.setToolTip(detalle)
                    self.estado_escaneo.setToolTip(detalle)
            self.mensaje_carpeta.setText(detalle)
            self.estado_escaneo.setText(detalle)
        else:
            self.mensaje_carpeta.setText(f"Renombrado masivo completado: {len(exitosos)}/{total}")
            self.estado_escaneo.setText("Renombrado masivo completado")
        # Tooltip completo (auxiliar: no convierte éxito DB en fallo total)
        try:
            if fallidos:
                err_full = fallidos[0].get("error", "")
                if isinstance(err_full, str) and err_full:
                    tt = f"Renombrado masivo: {len(exitosos)} ok / {len(fallidos)} fallidos / {len(cancelados)} cancelados (total {total}) — ej. {err_full}"
                    hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(tt)
                    hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(tt)
                else:
                    hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                    hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            else:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
        except (AttributeError, TypeError, RuntimeError) as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — inconsistencia tooltip: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — inconsistencia tooltip: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" | tooltip falló: {type(exc2).__name__}: {exc2}")
        except Exception as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado tooltip: {type(exc).__name__}: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except (AttributeError, TypeError, RuntimeError) as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — inconsistencia tooltip secundaria: {exc2}")
                self.estado_escaneo.setToolTip(self.mensaje_carpeta.text())
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip secundaria: {type(exc2).__name__}: {exc2}")
        # Actualizar filtros/contadores localmente; recarga ya programada (auxiliares: registrar inconsistencia visible sin falsa falla total)
        try:
            self.filtrar(self.busqueda.text())
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — inconsistencia filtrar: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — inconsistencia filtrar: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except (AttributeError, TypeError, RuntimeError) as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo tooltip tras filtrar: {exc2}")
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip tras filtrar: {type(exc2).__name__}: {exc2}")
        except Exception as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado filtrar: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado filtrar: {type(exc).__name__}: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except (AttributeError, TypeError, RuntimeError) as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo tooltip tras filtrar: {exc2}")
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip tras filtrar: {type(exc2).__name__}: {exc2}")
        try:
            self.actualizar_contador()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — inconsistencia contador: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — inconsistencia contador: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except (AttributeError, TypeError, RuntimeError) as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo tooltip tras contador: {exc2}")
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip tras contador: {type(exc2).__name__}: {exc2}")
        except Exception as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado contador: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado contador: {type(exc).__name__}: {exc}")
        try:
            self._actualizar_resumen_seleccion()
        except (AttributeError, TypeError, RuntimeError, ValueError) as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — inconsistencia resumen: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — inconsistencia resumen: {exc}")
            try:
                hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(self.mensaje_carpeta.text())
                hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(self.estado_escaneo.text())
            except (AttributeError, TypeError, RuntimeError) as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — fallo tooltip tras resumen: {exc2}")
            except Exception as exc2:
                self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado tooltip tras resumen: {type(exc2).__name__}: {exc2}")
        except Exception as exc:
            self.mensaje_carpeta.setText(self.mensaje_carpeta.text() + f" — error inesperado resumen: {type(exc).__name__}: {exc}")
            self.estado_escaneo.setText(self.estado_escaneo.text() + f" — error inesperado resumen: {type(exc).__name__}: {exc}")
        self._actualizar_botones_lote()
        self._actualizar_botones_carpeta()

    def _al_error_renombrar_masivo(self, mensaje):
        texto = f"No se pudo completar renombrado masivo: {mensaje}"
        self.mensaje_carpeta.setText(texto)
        self.estado_escaneo.setText(texto)
        hasattr(self.mensaje_carpeta, "setToolTip") and self.mensaje_carpeta.setToolTip(texto)
        hasattr(self.estado_escaneo, "setToolTip") and self.estado_escaneo.setToolTip(texto)

    def _al_finalizada_renombrar_masivo(self):
        self._renombrar_masivo_en_curso = False
        self.barra_progreso.setVisible(False)
        self.barra_progreso.setRange(0, 100)
        self._renombrar_masivo_plan = None
        # No limpiar scroll/orden aquí si aún hay recarga pendiente (se limpia en _reemplazar_tarjetas)
        # Pero si no hay recarga pendiente, limpiar para no quedar stale
        if not getattr(self, "_recarga_catalogo_pendiente", False):
            self._renombrar_masivo_scroll_previo = None
            self._renombrar_masivo_orden_previo = None
        self._al_actividad_renombrar_masivo(False)

    def _al_actividad_renombrar_masivo(self, activa):
        self._actualizar_botones_lote()
        self._actualizar_botones_carpeta()

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
        # B8.3B: para homónimos, si ids tiene 2 entradas con mismo nombre, el conteo por nombre ya da 2 (visibles duplicados), pero si ids tiene selección más precisa, asegurar conteo por ids cuando nombre colapsa
        try:
            ids = getattr(self, "_ids_seleccionados", set())
            if ids and len(ids) != len(self._nombres_seleccionados):
                # homónimo: ids distingue, usar conteo por tarjetas visibles cuyo id está en ids
                x_id = sum(1 for _, t in self.tarjetas if getattr(t, "_video_id", None) in ids and t.nombre in visibles)
                # si visibles tiene duplicados, x_id puede ser 2 mientras x por nombre también 2; tomar max para no subcontar
                if x_id > x:
                    x = x_id
        except Exception:
            pass
        self.resumen_seleccion.setText(
            f"{x} de {len(visibles)} seleccionados"
        )
        self._actualizar_boton_copiar()
        self._actualizar_boton_pegar()
        self._actualizar_boton_eliminar()
        self._actualizar_botones_lote()

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
        self._actualizar_miniaturas_pendiente = False
        self._sincronizacion_pendiente = False
        self._recarga_catalogo_pendiente = False
        self._pagina_pendiente = False
        self._carpeta_sincronizacion = carpeta
        self.registros_guardados = None
        self._guardado_por_ruta_normalizada = None
        self._guardado_rutas_por_id = None
        self._guardado_nombres_por_id = None
        self._registros_para_guardar = None
        self.resultado_sincronizacion = None
        self.tarea_escaneo = None
        self.tarea_tamanos = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_actualizar_miniaturas = None
        self.tarea_sincronizacion = None
        self.tarea_recarga_catalogo = None
        self.tarea_pagina = None
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.resultado_actualizar_miniaturas = None
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
        self._actualizar_miniaturas_pendiente = False
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
        self.tarea_actualizar_miniaturas = None
        self.tarea_sincronizacion = None
        self._guardado_por_ruta_normalizada = None
        self._guardado_rutas_por_id = None
        self._guardado_nombres_por_id = None
        self._registros_para_guardar = None
        self.resultado_actualizar_miniaturas = None
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
        if self._guardado_pendiente:
            self._al_resultado_guardado(resultado)
            return
        if self._miniaturas_pendiente:
            self._al_resultado_miniaturas(resultado)
            return
        if self._actualizar_miniaturas_pendiente:
            self._al_resultado_actualizar_miniaturas(resultado)
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
        self._guardado_pendiente = True
        self.tarea_ffprobe = None
        self.resultado_ffprobe = resultado
        self._actualizar_botones_carpeta()

    def _al_error_ffprobe(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_FFPROBE)
        self._actualizar_botones_carpeta()

    def _iniciar_miniaturas(self):
        # B8.2: miniaturas por video_id (requiere guardado previo)
        # B8.3A: si no hay videos nuevos, no limpiar — ir directo a sincronización
        if self._guardado_ids is None or not self._guardado_ids:
            self._miniaturas_pendiente = False
            self._actualizar_miniaturas_pendiente = False
            self._sincronizacion_pendiente = True
            self._actualizar_botones_carpeta()
            if not self.gestor.activo:
                self._iniciar_sincronizacion()
            return
        if self._guardado_rutas_por_id is None or self._guardado_nombres_por_id is None:
            self._miniaturas_pendiente = False
            self._actualizar_miniaturas_pendiente = False
            self._sincronizacion_pendiente = True
            self._actualizar_botones_carpeta()
            if not self.gestor.activo:
                self._iniciar_sincronizacion()
            return
        duraciones = self._duraciones_desde_ffprobe()
        tarea = TareaMiniaturasPorId(
            self._guardado_ids,
            self._guardado_rutas_por_id,
            duraciones=duraciones,
            nombres_por_id=self._guardado_nombres_por_id,
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
        self._actualizar_miniaturas_pendiente = True
        self.tarea_miniaturas = None
        self.resultado_miniaturas = resultado
        self._actualizar_botones_carpeta()

    def _al_error_miniaturas(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_MINIATURAS)
        self._actualizar_botones_carpeta()

    def _iniciar_guardado(self):
        # B8.1: guardado antes de miniaturas; solo ffprobe + tamanos, no miniaturas
        # B8.2: guarda registros para mapear id->ruta/nombre para caché por id
        if (
            self.tarea_escaneo is None
            or self.videos_detectados is None
            or self.resultado_tamanos is None
            or self.resultado_ffprobe is None
        ):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        registros = combinar_registros_con_ffprobe(
            self.videos_detectados, self.tarea_escaneo.carpeta, self.resultado_ffprobe
        )
        # B8.1: no combinar con miniaturas aquí; cantidad_miniaturas se actualizará por id después
        registros = combinar_registros_con_tamanos(
            registros, self.resultado_tamanos
        )
        self._registros_para_guardar = list(registros)
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
        if self._guardado_pendiente:
            self._iniciar_guardado()
            return
        if self._miniaturas_pendiente:
            self._iniciar_miniaturas()
            return
        if self._actualizar_miniaturas_pendiente:
            self._iniciar_actualizar_miniaturas()
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
                c for c in self._alcance_sincronizacion if not carpetas_iguales(c, carpeta)
            ]
        # B8.3A — retiradas solo en último tramo, solo previamente escaneadas ya no en alcance; delegar shrink a backend
        # FIX B8.3: no retirar ancestro/descendiente de la carpeta actual (evita borrar A al escanear A tras MADRE)
        retiradas = None
        if not self._cola_carpetas_escaneo:
            try:
                escaneadas = getattr(self, "carpetas_escaneadas", set()) or set()
                if self._alcance_sincronizacion:
                    alcance_set = list(self._alcance_sincronizacion)
                    candidatas = []
                    for esc in escaneadas:
                        if not any(carpetas_iguales(esc, a) for a in alcance_set):
                            # B8.3 FIX: si esc es ancestro o descendiente de la carpeta actual, no es retirada
                            try:
                                if _ruta_contiene(esc, carpeta) or _ruta_contiene(carpeta, esc):
                                    continue
                            except Exception:
                                pass
                            candidatas.append(esc)
                    if candidatas:
                        retiradas = candidatas
                else:
                    candidatas = []
                    for esc in escaneadas:
                        if not carpetas_iguales(esc, carpeta):
                            try:
                                if _ruta_contiene(esc, carpeta) or _ruta_contiene(carpeta, esc):
                                    continue
                            except Exception:
                                pass
                            candidatas.append(esc)
                    if candidatas:
                        retiradas = candidatas
            except Exception as exc:
                print(f"[B8.3A] _iniciar_sincronizacion retiradas error: {exc}")
                retiradas = None
        tarea = TareaSincronizacionCatalogo(
            carpeta, self._ruta_db, carpetas_protegidas=protegidas, carpetas_retiradas=retiradas
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
            if getattr(self, "_renombrar_masivo_ids_a_restaurar", None) is not None:
                self._renombrar_masivo_ids_a_restaurar = None
                self._renombrar_masivo_ids_origen = None
                self._renombrar_masivo_scroll_previo = None
                self._renombrar_masivo_orden_previo = None
            return
        self._recarga_catalogo_pendiente = False
        self.tarea_recarga_catalogo = None
        self._total_catalogo = resultado.get("total", self._total_catalogo)
        filas_recarga = resultado.get("videos", [])
        # B7.7 UX final: detectar si esta recarga corresponde a renombrado masivo para no saltar ciego a 0
        es_recarga_renombrado = (
            getattr(self, "_renombrar_masivo_ids_a_restaurar", None) is not None
            or getattr(self, "_renombrar_masivo_scroll_previo", None) is not None
            or getattr(self, "_renombrar_masivo_orden_previo", None) is not None
        )
        self._reemplazar_tarjetas(filas_recarga)
        self.estado_carga.hide()
        self._carga_completada = True
        self._encolar_resumen_para_lote(filas_recarga)
        self._programar_previews()
        if not es_recarga_renombrado:
            self.area.verticalScrollBar().setValue(0)
        # Si fue recarga por renombrado, el contexto visual ya fue asegurado dentro de _reemplazar_tarjetas
        # de forma determinista (asegurar primer seleccionado según nuevo orden si corresponde)
        self._ocultar_progreso()
        self._actualizar_botones_carpeta()

    def _al_error_recarga(self, mensaje):
        if self._lectura_obsoleta():
            self._recarga_catalogo_pendiente = False
            self.tarea_recarga_catalogo = None
            # Si había pending por renombrar masivo, liberar para no quedar stale
            if getattr(self, "_renombrar_masivo_ids_a_restaurar", None) is not None:
                self._renombrar_masivo_ids_a_restaurar = None
                self._renombrar_masivo_ids_origen = None
                self._renombrar_masivo_scroll_previo = None
                self._renombrar_masivo_orden_previo = None
            return
        self._limpiar_cadena()
        # Liberar pending renombrar masivo si recarga falló (evitar stale)
        if getattr(self, "_renombrar_masivo_ids_a_restaurar", None) is not None:
            self._renombrar_masivo_ids_a_restaurar = None
            self._renombrar_masivo_ids_origen = None
            self._renombrar_masivo_scroll_previo = None
            self._renombrar_masivo_orden_previo = None
        self.estado_escaneo.setText(MENSAJE_ERROR_RECARGA)
        self._actualizar_botones_carpeta()

    def _reemplazar_tarjetas(self, filas):
        self._ocultar_vista()
        # FIX B7.7 post-rename: si hay ids pendientes por video_id (renombrado masivo), restaurar por identidad no por nombre
        pending_ids = getattr(self, "_renombrar_masivo_ids_a_restaurar", None)
        if isinstance(pending_ids, set) and pending_ids:
            # Consumo pendiente: limpiar selección y reconstruir, luego restaurar por video_id
            self._limpiar_seleccion()
            self._ancla_seleccion = None
            for nombre, tarjeta in self.tarjetas:
                self.cuadricula.removeWidget(tarjeta)
                tarjeta.deleteLater()
            self.tarjetas = []
            self.visibles = []
            self._crear_tarjetas(filas)
            ids_a_restaurar = set(pending_ids)
            # Filtrar a los que sigan perteneciendo a la carpeta/vista actual (presentes en filas)
            ids_presentes = {getattr(t, "_video_id", None) for _, t in self.tarjetas}
            ids_a_restaurar = ids_a_restaurar.intersection(ids_presentes)
            # Marcar por video_id: mapear video_id -> nombre actual (nuevo nombre tras rename)
            vid_a_nombre = {}
            for nombre, tarjeta in self.tarjetas:
                vid = getattr(tarjeta, "_video_id", None)
                if isinstance(vid, int) and vid in ids_a_restaurar:
                    # Si hay duplicado improbable, conservar primero
                    if vid not in vid_a_nombre:
                        vid_a_nombre[vid] = nombre
            for vid, nombre in vid_a_nombre.items():
                self._nombres_seleccionados.add(nombre)
                self._marcar_tarjeta(nombre, True)
                if self._ancla_seleccion is None:
                    self._ancla_seleccion = nombre
            # Consumir pendientes y origen
            self._renombrar_masivo_ids_a_restaurar = None
            self._renombrar_masivo_ids_origen = None
            # Asegurar resumen y botones coherentes (sin silenciamiento)
            self._actualizar_resumen_seleccion()
            # B7.7 UX final: preservación de contexto visual determinista tras renombrado masivo
            # Regla: reordenar respetando orden/filtros vigentes (ya hecho via _crear_tarjetas),
            # mantener seleccionados por video_id (hecho arriba), luego asegurar contexto visual:
            # - si orden cambió (especialmente por nombre), llevar vista al PRIMERO según NUEVO orden visible
            # - si posición no cambió y scroll previo deja visibles, evitar salto innecesario
            # Determinista y no dependiente de nombre/ruta (usa video_id ordenado).
            orden_previo = getattr(self, "_renombrar_masivo_orden_previo", None)
            # Construir orden nuevo determinista por video_id según nuevo orden visible vigente
            try:
                orden_nuevo = list(self._video_ids_seleccionados_ordenados())
            except (AttributeError, TypeError, RuntimeError, ValueError):
                orden_nuevo = []
            # Determinar nombres ordenados según nuevo orden visible (visibles ya filtrado)
            nombres_orden_nuevo = []
            try:
                for nombre in list(self.visibles):
                    if nombre in self._nombres_seleccionados:
                        nombres_orden_nuevo.append(nombre)
                if not nombres_orden_nuevo:
                    nombres_orden_nuevo = [n for n, _ in self.tarjetas if n in self._nombres_seleccionados]
            except (AttributeError, TypeError, RuntimeError):
                nombres_orden_nuevo = []
            # Solo aplicar regla a seleccionados disponibles en vista cargada (paginación/filtro)
            if nombres_orden_nuevo:
                cambiaron = False
                if isinstance(orden_previo, list) and isinstance(orden_nuevo, list):
                    if orden_previo != orden_nuevo:
                        cambiaron = True
                else:
                    cambiaron = True
                # Verificar si algún seleccionado ya está razonablemente visible en viewport
                alguna_visible = False
                _diag_activate = None
                _diag_viewport = None
                try:
                    if self.contenedor.layout() is not None:
                        try:
                            self.contenedor.layout().activate()
                        except (AttributeError, RuntimeError) as exc:
                            _diag_activate = f"Diagnostico viewport activate fallo: {type(exc).__name__}: {exc}"
                            try:
                                self.mensaje_carpeta.setToolTip(_diag_activate)
                                self.estado_escaneo.setToolTip(_diag_activate)
                            except Exception as _exc_diag_act:
                                _diag_activate_fallback = str(_exc_diag_act)
                    vp = self.area.viewport()
                    vp_h = int(vp.height()) if vp is not None else 0
                    scroll_val = int(self.area.verticalScrollBar().value())
                    if vp_h > 0:
                        for n in nombres_orden_nuevo:
                            t = None
                            try:
                                for vid in (orden_nuevo or []):
                                    cand = self._tarjeta_por_id(vid)
                                    if cand is not None and cand.nombre == n:
                                        t = cand
                                        break
                            except Exception:
                                t = None
                            if t is None:
                                t = self._tarjeta_por_nombre(n)
                            if t is None:
                                continue
                            try:
                                y = int(t.y())
                                h = int(t.height())
                            except (AttributeError, TypeError, RuntimeError, ValueError):
                                continue
                            if not (y + h < scroll_val or y > scroll_val + vp_h):
                                alguna_visible = True
                                break
                    else:
                        alguna_visible = False
                except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                    alguna_visible = False
                    _diag_viewport = f"Diagnostico viewport visible fallo: {type(exc).__name__}: {exc}"
                    try:
                        self.mensaje_carpeta.setToolTip(_diag_viewport)
                        self.estado_escaneo.setToolTip(_diag_viewport)
                    except Exception as _exc_diag_vp:
                        _diag_vp_fallback = str(_exc_diag_vp)
                scroll_previo_vp = getattr(self, "_renombrar_masivo_scroll_previo", None)
                if cambiaron:
                    primero = nombres_orden_nuevo[0]
                    t_prim = None
                    try:
                        vid_prim = None
                        for vid in (orden_nuevo or []):
                            cand = self._tarjeta_por_id(vid)
                            if cand is not None and cand.nombre == primero:
                                vid_prim = vid
                                break
                        if vid_prim is not None:
                            t_prim = self._tarjeta_por_id(vid_prim)
                    except Exception:
                        t_prim = None
                    if t_prim is None:
                        t_prim = self._tarjeta_por_nombre(primero)
                    if t_prim is not None:
                        try:
                            self.area.ensureWidgetVisible(t_prim, 0, 0)
                        except (AttributeError, RuntimeError) as exc:
                            _diag_ensure = f"Diagnostico viewport ensureWidgetVisible fallo (orden cambio): {type(exc).__name__}: {exc}"
                            try:
                                if isinstance(scroll_previo_vp, int) and scroll_previo_vp >= 0:
                                    try:
                                        self.area.verticalScrollBar().setValue(scroll_previo_vp)
                                    except Exception as _exc_rest1:
                                        _diag_rest1 = str(_exc_rest1)
                                self.mensaje_carpeta.setToolTip(_diag_ensure)
                                self.estado_escaneo.setToolTip(_diag_ensure)
                            except Exception as _exc_diag_ens:
                                _diag_ens_fallback = str(_exc_diag_ens)
                elif not alguna_visible:
                    primero = nombres_orden_nuevo[0]
                    t_prim = None
                    try:
                        vid_prim2 = None
                        for vid in (orden_nuevo or []):
                            cand = self._tarjeta_por_id(vid)
                            if cand is not None and cand.nombre == primero:
                                vid_prim2 = vid
                                break
                        if vid_prim2 is not None:
                            t_prim = self._tarjeta_por_id(vid_prim2)
                    except Exception:
                        t_prim = None
                    if t_prim is None:
                        t_prim = self._tarjeta_por_nombre(primero)
                    if t_prim is not None:
                        try:
                            self.area.ensureWidgetVisible(t_prim, 0, 0)
                        except (AttributeError, RuntimeError) as exc:
                            _diag_ensure2 = f"Diagnostico viewport ensureWidgetVisible fallo (orden estable): {type(exc).__name__}: {exc}"
                            try:
                                if isinstance(scroll_previo_vp, int) and scroll_previo_vp >= 0:
                                    try:
                                        self.area.verticalScrollBar().setValue(scroll_previo_vp)
                                    except Exception as _exc_rest2:
                                        _diag_rest2 = str(_exc_rest2)
                                self.mensaje_carpeta.setToolTip(_diag_ensure2)
                                self.estado_escaneo.setToolTip(_diag_ensure2)
                            except Exception as _exc_diag_ens2:
                                _diag_ens2_fallback = str(_exc_diag_ens2)
            # Limpiar contexto visual guardado
            self._renombrar_masivo_scroll_previo = None
            self._renombrar_masivo_orden_previo = None
            return
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
        # B8.2: usar video_id para previews
        ids = []
        for _, tarjeta in self.tarjetas:
            vid = getattr(tarjeta, "_video_id", None)
            if isinstance(vid, int) and not isinstance(vid, bool) and vid>0:
                ids.append(vid)
        if ids:
            self._encolar_previews_por_id(ids)
        else:
            # fallback legacy por nombre (solo para tests antiguos)
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

    def _encolar_previews_por_id(self, video_ids):
        # B8.2 cola por video_id, evita duplicados; secuenciada tras migración legacy (B8.2 carrera)
        # B8.2 007 diferidos: si la solicitud llega mientras migra, no se pierde: se registra en
        # _previews_diferidas y se mantiene en _cola_previews para que esperas no retornen prematuramente;
        # _siguiente_lote_previews filtrará el inicio hasta que vuelo se libere, evitando carrera.
        if not hasattr(self, "_previews_diferidas"):
            self._previews_diferidas = set()
        pendientes = set()
        for item in self._cola_previews:
            try:
                pendientes.add(item[0])
            except (AttributeError, TypeError, IndexError, ValueError):
                continue
        # evitar doble dispatch: considerar diferidos y tarea activa
        pendientes |= self._previews_diferidas
        try:
            if getattr(self, "gestor_previews", None) is not None and self.gestor_previews.activo and getattr(self, "tarea_previews", None) is not None:
                tarea = self.tarea_previews
                vids_act = getattr(tarea, "video_ids", None)
                if vids_act is None:
                    vids_act = getattr(tarea, "_video_ids", None)
                if isinstance(vids_act, (list, tuple, set)):
                    for v in vids_act:
                        if isinstance(v, int) and not isinstance(v, bool):
                            pendientes.add(v)
        except (AttributeError, TypeError, RuntimeError):
            pass
        for vid in video_ids:
            if not isinstance(vid, int) or isinstance(vid, bool) or vid <= 0:
                continue
            if vid in pendientes:
                continue
            tarjeta_tmp = self._tarjeta_por_id(vid)
            if tarjeta_tmp is None:
                continue
            # B8.2: no encolar generación automática de previews cuando no existe duración válida y finita >0.
            # Regla productiva coherente: evita gestor/hilo efímero y FFmpeg para videos sin duración usable.
            dur_tmp = getattr(tarjeta_tmp, "_duracion", None)
            try:
                dur_val = float(dur_tmp) if isinstance(dur_tmp, (int,float)) and not isinstance(dur_tmp,bool) else None
                if dur_val is None or not math.isfinite(dur_val) or dur_val <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            if getattr(tarjeta_tmp, "_previews_completas", False):
                continue
            # B8.2 carrera: si aún migra, registrar diferido (deduplicado) y mantener en cola para no perder
            if hasattr(self, "_migracion_ids_en_vuelo") and vid in self._migracion_ids_en_vuelo:
                self._previews_diferidas.add(vid)
                carpeta_tmp = getattr(tarjeta_tmp, "_carpeta_video", "") if tarjeta_tmp is not None else ""
                self._cola_previews.append((vid, carpeta_tmp))
                continue
            self._cola_previews.append((vid, getattr(tarjeta_tmp, "_carpeta_video", "")))

    def _al_previews_finalizada(self):
        if self.gestor_previews.estado != Estado.INACTIVO:
            return
        self._siguiente_lote_previews()

    def _siguiente_lote_previews(self):
        if self.gestor_previews.activo:
            return
        # Detectar si la cola es por id (primer elemento es int) o por nombre
        if self._cola_previews and isinstance(self._cola_previews[0][0], int):
            # B8.2 por id — secuenciación diferida: si el lote aún migra, no iniciar (mantener en cola)
            lote_ids = []
            restantes = []
            for item in self._cola_previews:
                vid, _ = item
                if len(lote_ids) < TAMANIO_LOTE_PREVIEWS:
                    lote_ids.append(vid)
                else:
                    restantes.append(item)
            # Si algún vid del lote aún está en vuelo, reencolar al inicio y esperar a migración
            if any(hasattr(self, "_migracion_ids_en_vuelo") and vid in self._migracion_ids_en_vuelo for vid in lote_ids):
                # Mantener orden: lote al frente + restantes (no consumir)
                # No limpiar diferidos aún; se drenan al iniciar
                return
            self._cola_previews = restantes
            if not lote_ids:
                return
            # Drenar diferidos para los vids que ahora inician (evita doble dispatch)
            if hasattr(self, "_previews_diferidas"):
                for vid in lote_ids:
                    self._previews_diferidas.discard(vid)
            # construir rutas_por_id, duraciones y nombres_por_id por id (B8.2: propagación real sin SQLite/FS pesado UI)
            rutas_por_id = {}
            duraciones = {}
            nombres_por_id = {}
            for vid in lote_ids:
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    continue
                nombre = getattr(tarjeta, "_nombre", None)
                carpeta = getattr(tarjeta, "_carpeta_video", "")
                ruta_video = os.path.join(carpeta, nombre) if isinstance(nombre, str) and isinstance(carpeta, str) else ""
                rutas_por_id[vid] = ruta_video
                if isinstance(nombre, str) and nombre:
                    nombres_por_id[vid] = nombre
                dur = getattr(tarjeta, "_duracion", None)
                if isinstance(dur, (int, float)) and not isinstance(dur, bool):
                    duraciones[vid] = dur
                    if ruta_video:
                        duraciones[ruta_video] = dur
            tarea = TareaPreviewsPorId(lote_ids, rutas_por_id, duraciones=duraciones, nombres_por_id=nombres_por_id)
            if not self.gestor_previews.iniciar(tarea):
                self._cola_previews = restantes + [(vid, "") for vid in lote_ids]
                return
            self.tarea_previews = tarea
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
            # B8.3B: identidad estricta — si vid válido, solo por ID (no caer a homónimo por nombre)
            vid = item.get("video_id")
            nombre = item.get("nombre")
            rutas = item.get("previews")
            ruta_video = item.get("ruta")
            if not rutas:
                continue
            tarjeta = None
            if _es_video_id_valido(vid):
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    continue
            elif isinstance(nombre, str):
                tarjeta = self._tarjeta_por_nombre(nombre)
            if tarjeta is None:
                continue
            # validación de carpeta solo si ambos son strs y no vacíos (para evitar falso negativo con id)
            if _es_video_id_valido(vid):
                tarjeta.actualizar_previews(rutas)
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
            try:
                tarjeta.preview_visual_solicitada.connect(self._al_preview_visual_solicitada)
            except Exception:
                pass
            tarjeta.modo_tira_cambiada.connect(self._al_modo_tira_cambiada)
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
            tarjeta.segmento_exportacion_solicitada.connect(
                lambda segmento, t=tarjeta: self._al_segmento_exportacion_solicitada(
                    t, segmento
                )
            )
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, posicion, 0)
        self.filtrar(self.busqueda.text())
        # B8.2: migración legacy batch para tarjetas agregadas por paginación
        try:
            self._encolar_migracion_legacy(filas)
        except Exception as exc:
            print(f"[B8.2] _agregar_tarjetas migracion error: {exc}")

    def _al_resultado_guardado(self, resultado):
        self._guardado_pendiente = False
        self.tarea_guardado = None
        # B8.1: conservar ids para actualizar miniaturas por video_id; no limpiar ffprobe aún
        self.registros_guardados = resultado.get("guardados")
        # guardar mapeo ruta_normalizada -> video_id para correspondencia inequívoca
        try:
            self._guardado_por_ruta_normalizada = dict(resultado.get("por_ruta_normalizada") or {})
        except Exception:
            self._guardado_por_ruta_normalizada = {}
        # También guardar ids list para referencia
        try:
            self._guardado_ids = list(resultado.get("ids") or resultado.get("video_ids") or [])
        except Exception:
            self._guardado_ids = []
        # B8.2: mapear id -> ruta/nombre para caché por id (sin silenciar genérico)
        try:
            self._guardado_rutas_por_id = {}
            self._guardado_nombres_por_id = {}
            ids = self._guardado_ids
            regs = self._registros_para_guardar or []
            for idx, vid in enumerate(ids):
                if idx < len(regs):
                    self._guardado_rutas_por_id[vid] = regs[idx].get("ruta")
                    self._guardado_nombres_por_id[vid] = regs[idx].get("nombre")
        except (TypeError, ValueError, AttributeError, IndexError) as exc:
            print(f"[B8.2] _al_resultado_guardado mapping error: {exc}")
            self._guardado_rutas_por_id = {}
            self._guardado_nombres_por_id = {}
        self._miniaturas_pendiente = True
        self._actualizar_botones_carpeta()

    def _iniciar_actualizar_miniaturas(self):
        # B8.1: actualizar exclusivamente cantidad_miniaturas por video_id después de miniaturas
        # B8.2: resultado ya trae video_id directamente
        if self.resultado_miniaturas is None:
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        actualizaciones = []
        for item in (self.resultado_miniaturas.get("resultados") or []):
            if not isinstance(item, dict):
                continue
            vid = item.get("video_id")
            cantidad = item.get("cantidad_miniaturas")
            if _es_video_id_valido(vid):
                actualizaciones.append((vid, cantidad))
                continue
            # fallback legacy por ruta
            ruta = item.get("ruta")
            if not isinstance(ruta, str) or not ruta:
                continue
            try:
                norm = normalizar_ruta_clave(ruta)
            except Exception:
                continue
            if self._guardado_por_ruta_normalizada is None:
                continue
            vid2 = self._guardado_por_ruta_normalizada.get(norm)
            if vid2 is None:
                continue
            actualizaciones.append((vid2, cantidad))
        # Si no hay actualizaciones, ir directo a sincronización sin tarea
        if not actualizaciones:
            self._actualizar_miniaturas_pendiente = False
            self.resultado_actualizar_miniaturas = {"actualizados": 0}
            self._sincronizacion_pendiente = True
            self._actualizar_botones_carpeta()
            return
        tarea = TareaActualizarCantidadMiniaturas(actualizaciones, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_actualizar_miniaturas = tarea
        self._mostrar_progreso("Actualizando miniaturas…")

    def _al_resultado_actualizar_miniaturas(self, resultado):
        self._actualizar_miniaturas_pendiente = False
        self.tarea_actualizar_miniaturas = None
        self.resultado_actualizar_miniaturas = resultado
        # Limpiar temporales de guardado/miniaturas antes de sincronización
        self.resultado_tamanos = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self._guardado_por_ruta_normalizada = None
        self._guardado_ids = None
        self._guardado_rutas_por_id = None
        self._guardado_nombres_por_id = None
        self._registros_para_guardar = None
        self._sincronizacion_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error_actualizar_miniaturas(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText("No se pudo actualizar miniaturas")
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
        if self._guardado_pendiente:
            self._al_error_guardado(mensaje)
            return
        if self._miniaturas_pendiente:
            self._al_error_miniaturas(mensaje)
            return
        if self._actualizar_miniaturas_pendiente:
            self._al_error_actualizar_miniaturas(mensaje)
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
            try:
                tarjeta.preview_visual_solicitada.connect(self._al_preview_visual_solicitada)
            except Exception:
                pass
            tarjeta.modo_tira_cambiada.connect(self._al_modo_tira_cambiada)
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
            tarjeta.segmento_exportacion_solicitada.connect(
                lambda segmento, t=tarjeta: self._al_segmento_exportacion_solicitada(
                    t, segmento
                )
            )
            tarjeta.mostrar_check(self._modo_seleccion)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice, 0)
        self.filtrar(self.busqueda.text())
        # B8.2: migración legacy batch para tarjetas recién creadas (no bloquea UI)
        try:
            self._encolar_migracion_legacy(filas)
        except Exception as exc:
            print(f"[B8.2] _crear_tarjetas migracion error: {exc}")

    def _abrir_video(self, ident):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is not None:
                nombre = getattr(tarjeta, "nombre", None) or str(vid)
                carpeta = getattr(tarjeta, "_carpeta_video", None) or self.carpeta_seleccionada
                try:
                    abrir_video_con_aplicacion_predeterminada(nombre, carpeta)
                except (ValueError, FileNotFoundError, OSError):
                    self.mensaje_carpeta.setText(MENSAJE_ERROR_ABRIR)
                    return
                self.mensaje_carpeta.clear()
                return
        nombre = ident
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

    def _mostrar_menu_contextual(self, ident):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta_ctx = self._tarjeta_por_id(vid)
            nombre = getattr(tarjeta_ctx, "nombre", str(vid)) if tarjeta_ctx else str(vid)
        else:
            nombre = ident
            tarjeta_ctx = self._tarjeta_por_nombre(nombre)
            vid = getattr(tarjeta_ctx, "_video_id", None) if tarjeta_ctx else None
        menu = QMenu(self)
        accion_abrir = menu.addAction("Abrir")
        accion_abrir_carpeta = menu.addAction("Abrir carpeta")
        accion_copiar_ruta = menu.addAction("Copiar ruta")
        accion_copiar_seleccionados = menu.addAction("Copiar rutas de los seleccionados")
        accion_abrir_seleccionados = menu.addAction("Abrir carpetas de los seleccionados")
        accion_renombrar = menu.addAction("Renombrar…")
        accion_mover = menu.addAction("Mover a…")
        accion_reproducir_marcadores = menu.addAction(
            "Reproducir marcadores en VLC"
        )
        accion_reproducir_segmentos = menu.addAction(
            "Reproducir segmentos en VLC"
        )
        ident_uso = vid if _es_video_id_valido(vid) else nombre
        accion_abrir.triggered.connect(lambda: self._abrir_video(ident_uso))
        accion_abrir_carpeta.triggered.connect(lambda: self._abrir_carpeta(ident_uso))
        accion_copiar_ruta.triggered.connect(lambda: self._copiar_ruta(ident_uso))
        accion_copiar_seleccionados.triggered.connect(self._copiar_rutas_seleccionados)
        accion_abrir_seleccionados.triggered.connect(self._abrir_carpetas_seleccionados)
        accion_renombrar.triggered.connect(lambda: self._iniciar_renombrar(ident_uso))
        accion_mover.triggered.connect(lambda: self._iniciar_mover(ident_uso))
        accion_copiar = menu.addAction("Copiar a…")
        accion_copiar.triggered.connect(lambda: self._iniciar_copiar(ident_uso))
        accion_eliminar_ind = menu.addAction("Eliminar…")
        accion_eliminar_ind.triggered.connect(lambda: self._iniciar_eliminar_video(ident_uso))
        accion_mover_sel = menu.addAction("Mover seleccionados…")
        accion_mover_sel.triggered.connect(self._iniciar_lote_mover)
        accion_copiar_sel = menu.addAction("Copiar seleccionados…")
        accion_copiar_sel.triggered.connect(self._iniciar_lote_copiar)
        accion_eliminar_sel = menu.addAction("Enviar seleccionados a Papelera…")
        accion_eliminar_sel.triggered.connect(self._iniciar_lote_eliminar)
        accion_renombrar_sel = menu.addAction("Renombrar seleccionados…")
        accion_renombrar_sel.triggered.connect(self._iniciar_renombrar_masivo)
        # Coherente con botones lote B7.6/B7.7: habilitado con selección y sin operación en curso
        has_sel = bool(getattr(self, "_ids_seleccionados", set()) or self._nombres_seleccionados)
        accion_renombrar_sel.setEnabled(has_sel and not self._lote_esta_ocupado())
        accion_reproducir_marcadores.setEnabled(has_sel)
        accion_reproducir_marcadores.triggered.connect(
            self._reproducir_marcadores_en_vlc
        )
        accion_reproducir_segmentos.setEnabled(has_sel)
        accion_reproducir_segmentos.triggered.connect(
            self._reproducir_segmentos_en_vlc
        )
        menu.exec(QCursor.pos())

    def _abrir_carpeta(self, ident):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is not None:
                carpeta = getattr(tarjeta, "_carpeta_video", None)
                if carpeta and os.path.isdir(carpeta):
                    os.startfile(carpeta)
                    return
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            os.startfile(carpeta)

    def _copiar_ruta(self, ident):
        vid = ident if _es_video_id_valido(ident) else None
        if vid is not None:
            tarjeta = self._tarjeta_por_id(vid)
            if tarjeta is not None:
                ruta = self._ruta_video_de(tarjeta)
                if ruta:
                    QApplication.clipboard().setText(os.path.abspath(ruta))
                    return
        nombre = ident
        carpeta = self.carpeta_seleccionada
        if carpeta and os.path.isdir(carpeta):
            ruta = os.path.abspath(os.path.join(carpeta, nombre))
            QApplication.clipboard().setText(ruta)

    def _copiar_rutas_seleccionados(self):
        ids = getattr(self, "_ids_seleccionados", set())
        if ids:
            rutas = []
            for vid in self._video_ids_seleccionados_ordenados():
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is not None:
                    ruta = self._ruta_video_de(tarjeta)
                    if ruta:
                        rutas.append(os.path.abspath(ruta))
            if rutas:
                QApplication.clipboard().setText("\n".join(rutas))
            return
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
        ids = getattr(self, "_ids_seleccionados", set())
        if ids:
            carpetas = []
            for vid in self._video_ids_seleccionados_ordenados():
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is not None:
                    ruta = self._ruta_video_de(tarjeta)
                    if ruta:
                        carpetas.append(os.path.dirname(os.path.abspath(ruta)))
            for c in dict.fromkeys(carpetas):
                if os.path.isdir(c):
                    os.startfile(c)
            return
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
        ids = getattr(self, "_ids_seleccionados", set())
        if ids:
            seleccionados = []
            for vid in self._video_ids_seleccionados_ordenados():
                tarjeta = self._tarjeta_por_id(vid)
                if tarjeta is None:
                    continue
                seleccionados.append(
                    {
                        "nombre": getattr(tarjeta, "nombre", str(vid)),
                        "video_id": vid,
                        "ruta": self._ruta_video_de(tarjeta),
                    }
                )
            return seleccionados
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

    # ── B8.2 migración legacy -> id al cargar página (batch, background, no I/O en UI) ──
    def _encolar_migracion_legacy(self, filas):
        """Encola migración batch para filas recién visibles (B8.2).

        No realiza recorrido de carpeta ni duplicado ni acceso a base ni
        generación. Solo prepara video_id<->nombre inequívoco según los datos
        del catálogo (fila[0]=nombre, fila[8]=id) y delega copia no destructiva
        a tarea worker. Batch por página: una tarea para todo el lote.
        """
        if not filas:
            return
        video_ids = []
        nombres_por_id = {}
        for fila in filas:
            try:
                nombre = fila[0]
                vid = fila[8]
            except IndexError:
                continue
            if not isinstance(vid, int) or isinstance(vid, bool) or vid <= 0:
                continue
            if not isinstance(nombre, str) or not nombre:
                continue
            if vid in self._migracion_ids_en_vuelo:
                continue
            # Solo asociación inequívoca: la fila ya es la verdad del catálogo
            # No inferir por ruta ni fallback por nombre ambiguo
            if vid in nombres_por_id and nombres_por_id[vid] != nombre:
                # colisión intra-lote (no debería ocurrir si DB íntegra)
                continue
            video_ids.append(vid)
            nombres_por_id[vid] = nombre
        if not video_ids:
            return
        # deduplicar preservando orden
        video_ids = list(dict.fromkeys(video_ids))
        for vid in video_ids:
            self._migracion_ids_en_vuelo.add(vid)
        self._cola_migracion.append({"video_ids": video_ids, "nombres_por_id": nombres_por_id})
        self._procesar_siguiente_migracion()

    def _procesar_siguiente_migracion(self):
        if getattr(self, "gestor_migracion", None) is None:
            return
        if self.gestor_migracion.activo:
            return
        if not self._cola_migracion:
            return
        op = self._cola_migracion.pop(0)
        video_ids = op.get("video_ids", [])
        nombres_por_id = op.get("nombres_por_id", {})
        # Filtrar tarjetas que ya no existen (recarga/paginación) y ya migradas
        vigentes = []
        vigentes_nombres = {}
        for vid in video_ids:
            tarjeta = self._tarjeta_por_video_id(vid)
            if tarjeta is None:
                self._migracion_ids_en_vuelo.discard(vid)
                continue
            vigentes.append(vid)
            vigentes_nombres[vid] = nombres_por_id.get(vid)
        if not vigentes:
            self._procesar_siguiente_migracion()
            return
        tarea = TareaMigrarCacheLegacy(vigentes, vigentes_nombres, self._ruta_db)
        self._migracion_op_actual = {"video_ids": vigentes, "nombres_por_id": vigentes_nombres}
        if not self.gestor_migracion.iniciar(tarea):
            self._cola_migracion.insert(0, {"video_ids": vigentes, "nombres_por_id": vigentes_nombres})
            self._migracion_op_actual = None

    def _al_resultado_migracion(self, resultado):
        op = getattr(self, "_migracion_op_actual", None)
        if op is None:
            return
        # Actualizar solo tarjetas afectadas, sin recargar catálogo ni perder selección/scroll
        detalles = resultado.get("detalles", []) if isinstance(resultado, dict) else []
        afectados = set()
        for det in detalles:
            vid = det.get("video_id")
            res = det.get("res", {}) if isinstance(det, dict) else {}
            if not isinstance(vid, int):
                continue
            # Si hubo copiados o ya_existentes, la id ya está poblada
            copiados = res.get("copiados", 0) if isinstance(res, dict) else 0
            ya = res.get("ya_existentes", 0) if isinstance(res, dict) else 0
            # También considerar éxito parcial aunque fallos, si legacy fue copiada
            if copiados > 0 or ya > 0:
                afectados.add(vid)
            # Si la copia generó archivos, forzar refresh aunque conteo 0 (caso preview)
            if isinstance(res, dict) and res.get("detalles"):
                # si alguna entry copiada, marcar
                for d in res.get("detalles", []):
                    if d.get("estado") == "copiado":
                        afectados.add(vid)
                        break
        # Fallback: si detalles vacío pero procesados>0, considerar todos los del lote como potenciales
        if not afectados and isinstance(resultado, dict) and resultado.get("copiados", 0) > 0:
            for vid in op.get("video_ids", []):
                afectados.add(vid)
        for vid in afectados:
            tarjeta = self._tarjeta_por_video_id(vid)
            if tarjeta is None:
                self._migracion_ids_en_vuelo.discard(vid)
                # limpiar diferidos y cola para vid sin tarjeta
                if hasattr(self, "_previews_diferidas"):
                    self._previews_diferidas.discard(vid)
                try:
                    self._cola_previews = [it for it in self._cola_previews if it[0] != vid]
                except (AttributeError, TypeError, RuntimeError, ValueError):
                    pass
                continue
            # Refrescar miniatura principal (sin listdir/copy)
            try:
                tarjeta.actualizar_miniatura_por_id()
            except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
                print(f"[B8.2] actualizar_miniatura_por_id vid={vid} error: {exc}")
            # Refrescar previews por id (si existen tras migración)
            try:
                rutas = previews_de_por_id(vid)
                if rutas:
                    tarjeta.actualizar_previews(rutas)
            except (AttributeError, TypeError, RuntimeError, ValueError, OSError) as exc:
                print(f"[B8.2] actualizar_previews por id vid={vid} error: {exc}")
            self._migracion_ids_en_vuelo.discard(vid)
        # Limpiar ids no afectados (fallos o sin copia)
        for vid in list(op.get("video_ids", [])):
            self._migracion_ids_en_vuelo.discard(vid)
            # si tarjeta ya no existe, limpiar diferidos/cola para ese vid
            try:
                if self._tarjeta_por_video_id(vid) is None:
                    if hasattr(self, "_previews_diferidas"):
                        self._previews_diferidas.discard(vid)
                    self._cola_previews = [it for it in self._cola_previews if it[0] != vid]
            except (AttributeError, TypeError, RuntimeError, ValueError):
                pass
        # B8.2 007: tras liberar vuelo, si hay diferidos pendientes, asegurar que _siguiente_lote_previews se intente
        try:
            if getattr(self, "_previews_diferidas", set()):
                self._al_previews_finalizada()
        except (AttributeError, TypeError, RuntimeError):
            pass

    def _al_error_migracion(self, mensaje):
        op = getattr(self, "_migracion_op_actual", None)
        ids_para_previews = list(op.get("video_ids", [])) if isinstance(op, dict) else []
        if op is not None:
            for vid in op.get("video_ids", []):
                self._migracion_ids_en_vuelo.discard(vid)
                # limpiar diferidos/cola si tarjeta ya no existe
                try:
                    if self._tarjeta_por_video_id(vid) is None:
                        if hasattr(self, "_previews_diferidas"):
                            self._previews_diferidas.discard(vid)
                        self._cola_previews = [it for it in self._cola_previews if it[0] != vid]
                except (AttributeError, TypeError, RuntimeError, ValueError):
                    pass
        # Fallo observable: no borrar legacy (worker nunca borra), no recargar catálogo
        # Dejar mensaje en estado_carga si visible, pero no modificar tarjetas
        print(f"[B8.2] migración error: {mensaje}")
        self._migracion_op_actual = None
        self._procesar_siguiente_migracion()
        # B8.2 secuenciar: tras fallo, igual intentar previews (fallback FFmpeg) sin carrera
        if ids_para_previews:
            filtrados = []
            for vid in ids_para_previews:
                tarjeta = self._tarjeta_por_video_id(vid)
                if tarjeta is None:
                    continue
                if getattr(tarjeta, "_previews_completas", False):
                    continue
                filtrados.append(vid)
            if filtrados:
                self._encolar_previews_por_id(filtrados)
                self._al_previews_finalizada()

    def _al_migracion_finalizada(self):
        op = getattr(self, "_migracion_op_actual", None)
        ids_para_previews = list(op.get("video_ids", [])) if isinstance(op, dict) else []
        self._migracion_op_actual = None
        self._procesar_siguiente_migracion()
        # Limpiar diferidos de vids sin tarjeta (no reintentar)
        if ids_para_previews:
            for vid in list(ids_para_previews):
                try:
                    if self._tarjeta_por_video_id(vid) is None:
                        if hasattr(self, "_previews_diferidas"):
                            self._previews_diferidas.discard(vid)
                        self._cola_previews = [it for it in self._cola_previews if it[0] != vid]
                except (AttributeError, TypeError, RuntimeError, ValueError):
                    pass
        # B8.2 secuenciar: tras migración exitosa, encolar previews para ese lote (evita carrera)
        # Si ya había solicitudes diferidas, _encolar las deduplicará y _cola_previews ya contiene placeholders;
        # solo disparamos _siguiente si queda trabajo.
        if ids_para_previews:
            filtrados = []
            for vid in ids_para_previews:
                tarjeta = self._tarjeta_por_video_id(vid)
                if tarjeta is None:
                    continue
                if getattr(tarjeta, "_previews_completas", False):
                    # si ya completa, limpiar diferido sin reencolar
                    if hasattr(self, "_previews_diferidas") and vid in self._previews_diferidas:
                        self._previews_diferidas.discard(vid)
                        # también quitar placeholder de cola si quedó
                        try:
                            self._cola_previews = [it for it in self._cola_previews if it[0] != vid]
                        except (AttributeError, TypeError, RuntimeError, ValueError):
                            pass
                    continue
                filtrados.append(vid)
            if filtrados:
                self._encolar_previews_por_id(filtrados)
        # Siempre intentar drenar diferidos/cola tras liberar vuelo
        try:
            self._al_previews_finalizada()
        except (AttributeError, TypeError, RuntimeError):
            pass

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
        if getattr(self, "gestor_export", None) is not None:
            self.gestor_export.cerrar()
        if getattr(self, "gestor_preparacion_lote", None) is not None:
            self.gestor_preparacion_lote.cerrar()
            # limpiar referencias colgadas
            self._preparacion_lote_en_curso = False
            self._preparacion_lote_video_ids = None
            self._preparacion_lote_nombres = None
            self._preparacion_lote_rutas = None
            self._preparacion_lote_segmentos = None
            self._preparacion_lote_error = None
        if getattr(self, "gestor_preparacion_secuencia", None) is not None:
            self.gestor_preparacion_secuencia.cerrar()
            self._preparacion_secuencia_en_curso = False
            self._preparacion_secuencia_video_ids = None
            self._preparacion_secuencia_nombres = None
            self._preparacion_secuencia_rutas = None
            self._preparacion_secuencia_segmentos = None
            self._preparacion_secuencia_error = None
        if getattr(self, "gestor_crear_carpeta", None) is not None:
            self.gestor_crear_carpeta.cerrar()
            self._crear_en_curso = False
            self._crear_padre_en_curso = None
            self._crear_nombre_en_curso = None
            self._crear_ruta_inconsistente = None
            self._crear_error_refresco = None
        if getattr(self, "gestor_renombrado", None) is not None:
            self.gestor_renombrado.cerrar()
        if getattr(self, "gestor_mover", None) is not None:
            self.gestor_mover.cerrar()
        if getattr(self, "gestor_copiar", None) is not None:
            self.gestor_copiar.cerrar()
            self._copiar_en_curso = False
            self._copiar_nombre_origen = None
            self._copiar_video_id = None
            self._copiar_ruta_inconsistente = None
            self._copiar_error_sincronizacion = None
        if getattr(self, "gestor_eliminar", None) is not None:
            self.gestor_eliminar.cerrar()
            self._eliminar_en_curso = False
            self._eliminar_video_id = None
            self._eliminar_nombre = None
            self._eliminar_ruta_inconsistente = None
            self._eliminar_error_sincronizacion = None
        if getattr(self, "gestor_lote", None) is not None:
            self.gestor_lote.cerrar()
            self._lote_en_curso = False
            self._lote_operacion = None
            self._lote_video_ids = None
            self._lote_carpeta_destino = None
            self._lote_resultado_pendiente = None
            self._lote_ultimo_error_completo = None
        if getattr(self, "gestor_renombrar_masivo", None) is not None:
            self.gestor_renombrar_masivo.cerrar()
            self._renombrar_masivo_en_curso = False
            self._renombrar_masivo_plan = None
            self._renombrar_masivo_ids_origen = None
            self._renombrar_masivo_ids_a_restaurar = None
            self._renombrar_masivo_scroll_previo = None
            self._renombrar_masivo_orden_previo = None
        if getattr(self, "gestor_navegacion_destino", None) is not None:
            self.gestor_navegacion_destino.cerrar()
        if getattr(self, "gestor_prevalidacion_drop", None) is not None:
            self.gestor_prevalidacion_drop.cerrar()
            self._prevalidacion_drop_en_curso = False
            self._prevalidacion_drop_ids = None
            self._prevalidacion_drop_dest = None
        if getattr(self, "gestor_migracion", None) is not None:
            self.gestor_migracion.cerrar()
            self._migracion_op_actual = None
            self._cola_migracion = []
            self._migracion_ids_en_vuelo = set()
            if hasattr(self, "_previews_diferidas"):
                self._previews_diferidas = set()
            # limpiar placeholders diferidos de _cola_previews
            try:
                self._cola_previews = []
            except (AttributeError, TypeError, RuntimeError):
                pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(900, 600)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
