import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rutas import ruta_carpeta_miniaturas
from tareas import GestorTareas
from tareas_videos import TareaLecturaCatalogoPaginada

ANCHO_TARJETA = 320
ALTO_TARJETA = 180
COLUMNAS = 2
TAMANIO_PAGINA_INICIAL = 100

MENSAJE_CARGANDO = "Cargando catálogo…"
MENSAJE_ERROR = "No se pudo cargar el catálogo"


def formatear_valor(valor):
    if valor is None:
        return "No disponible"
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def miniatura_principal(nombre):
    prefijo = os.path.splitext(nombre)[0]
    carpeta = ruta_carpeta_miniaturas()
    if os.path.isdir(carpeta):
        for archivo in sorted(os.listdir(carpeta)):
            if os.path.splitext(archivo)[0].startswith(prefijo):
                ruta = os.path.join(carpeta, archivo)
                if os.path.isfile(ruta):
                    return ruta
    return None


class Tarjeta(QFrame):
    def __init__(self, fila, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QVBoxLayout(self)

        nombre, duracion, ancho, alto, codec, miniaturas = fila

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
            layout.addWidget(imagen)
        else:
            recuadro = QLabel("Sin miniatura")
            recuadro.setFixedSize(ANCHO_TARJETA, ALTO_TARJETA)
            recuadro.setAlignment(Qt.AlignCenter)
            recuadro.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")
            layout.addWidget(recuadro)

        resolucion = "No disponible"
        if ancho is not None and alto is not None:
            resolucion = f"{ancho}x{alto}"

        campos = [
            ("Nombre", nombre),
            ("Duración", formatear_valor(duracion)),
            ("Resolución", resolucion),
            ("Codec", formatear_valor(codec)),
            ("Miniaturas", formatear_valor(miniaturas)),
        ]
        for etiqueta, valor in campos:
            campo = QLabel(f"<b>{etiqueta}:</b> {valor}")
            campo.setWordWrap(True)
            layout.addWidget(campo)


class VisorVideos(QMainWindow):
    def __init__(self, ruta_db=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de videos")
        self.tarjetas = []
        self.visibles = []
        self._ruta_db = ruta_db
        self._carga_completada = False
        self.tarea_lectura = None

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()
        self.estado_carga = QLabel(MENSAJE_CARGANDO)

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.contador)
        barra.addWidget(self.estado_carga)

        self.contenedor = QWidget()
        self.cuadricula = QGridLayout(self.contenedor)
        self.cuadricula.setColumnStretch(0, 1)
        self.cuadricula.setColumnStretch(1, 1)
        self.actualizar_contador()

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        raiz = QWidget()
        layout = QVBoxLayout(raiz)
        layout.addLayout(barra)
        layout.addWidget(self.area)
        self.setCentralWidget(raiz)

        self.gestor = GestorTareas(self)
        self.gestor.tarea_resultado.connect(self._al_resultado)
        self.gestor.tarea_error.connect(self._al_error)
        self._iniciar_carga()

    def _iniciar_carga(self):
        self.tarea_lectura = TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL, 0, None, self._ruta_db
        )
        self.gestor.iniciar(self.tarea_lectura)

    def _al_resultado(self, resultado):
        if self._carga_completada:
            return
        self.estado_carga.hide()
        self._crear_tarjetas(resultado.get("videos", []))
        self._carga_completada = True

    def _al_error(self, mensaje):
        if self._carga_completada:
            return
        self.estado_carga.setText(MENSAJE_ERROR)
        self._carga_completada = True

    def _crear_tarjetas(self, filas):
        for indice, fila in enumerate(filas):
            tarjeta = Tarjeta(fila)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice // COLUMNAS, indice % COLUMNAS)
        self.filtrar(self.busqueda.text())

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
        self.gestor.cerrar()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(720, 540)
    ventana.show()

    print(f"visibles_inicio={ventana.tarjetas_visibles()}")
    print(f"estado_inicio={ventana.estado_carga.text()}")

    intentos = {"valor": 0}

    def comprobar_carga():
        if not ventana._carga_completada and intentos["valor"] < 100:
            intentos["valor"] += 1
            QTimer.singleShot(100, comprobar_carga)
            return
        print(f"visibles_cargados={ventana.tarjetas_visibles()}")
        print(f"contador_cargado={ventana.contador.text()}")
        ventana.busqueda.setText("real")

        def verificar_y_cerrar():
            visibles = ventana.tarjetas_visibles()
            print(f"visibles_filtro={visibles}")
            print(f"contador_final={ventana.contador.text()}")
            ventana.close()
            app.quit()

        QTimer.singleShot(1500, verificar_y_cerrar)

    QTimer.singleShot(200, comprobar_carga)
    codigo = app.exec()
    sys.exit(codigo)


if __name__ == "__main__":
    main()
