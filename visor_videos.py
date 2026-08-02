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

from escanear_videos import listar_videos

ANCHO_TARJETA = 320
ALTO_TARJETA = 180
COLUMNAS = 2


def formatear_valor(valor):
    if valor is None:
        return "No disponible"
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def miniatura_principal(nombre):
    prefijo = os.path.splitext(nombre)[0]
    carpeta = "miniaturas"
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biblioteca de videos")
        self.tarjetas = []

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()

        barra = QHBoxLayout()
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.contador)

        self.contenedor = QWidget()
        self.cuadricula = QGridLayout(self.contenedor)
        self.cargar_tarjetas()
        self.actualizar_contador()

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(self.contenedor)

        raiz = QWidget()
        layout = QVBoxLayout(raiz)
        layout.addLayout(barra)
        layout.addWidget(self.area)
        self.setCentralWidget(raiz)

    def cargar_tarjetas(self):
        self.visibles = []
        for indice, fila in enumerate(listar_videos()):
            tarjeta = Tarjeta(fila)
            self.tarjetas.append((fila[0], tarjeta))
            self.visibles.append(fila[0])
            self.cuadricula.addWidget(tarjeta, indice // COLUMNAS, indice % COLUMNAS)
        self.cuadricula.setColumnStretch(0, 1)
        self.cuadricula.setColumnStretch(1, 1)

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


def main():
    app = QApplication(sys.argv)
    ventana = VisorVideos()
    ventana.resize(720, 540)
    ventana.show()

    print(f"visibles_inicio={ventana.tarjetas_visibles()}")
    print(f"contador_inicio={ventana.contador.text()}")

    QTimer.singleShot(2000, lambda: ventana.busqueda.setText("real"))

    def verificar_y_cerrar():
        visibles = ventana.tarjetas_visibles()
        print(f"visibles_filtro={visibles}")
        print(f"contador_final={ventana.contador.text()}")
        app.quit()

    QTimer.singleShot(5000, verificar_y_cerrar)
    codigo = app.exec()
    sys.exit(codigo)


if __name__ == "__main__":
    main()
