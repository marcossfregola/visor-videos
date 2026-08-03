import os
import sys
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rutas import ruta_carpeta_miniaturas
from tareas import Estado, GestorTareas
from tareas_videos import (
    TareaEscaneo,
    TareaFFprobe,
    TareaGuardarVideos,
    TareaLecturaCatalogoPaginada,
    TareaMiniaturas,
    TareaSincronizacionCatalogo,
    combinar_registros_con_ffprobe,
    combinar_registros_con_miniaturas,
    conectar_bd,
)

ANCHO_TARJETA = 320
ALTO_TARJETA = 180
COLUMNAS = 2
TAMANIO_PAGINA_INICIAL = 100

MENSAJE_CARGANDO = "Cargando catálogo…"
MENSAJE_ERROR = "No se pudo cargar el catálogo"
MENSAJE_SIN_CARPETA = "Ninguna carpeta seleccionada"
MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"
MENSAJE_ESCANEANDO = "Escaneando carpeta…"
MENSAJE_ERROR_ESCANEO = "No se pudo escanear la carpeta"
MENSAJE_ERROR_FFPROBE = "No se pudieron obtener los metadatos"
MENSAJE_ERROR_MINIATURAS = "No se pudieron generar las miniaturas"
MENSAJE_ERROR_GUARDADO = "No se pudieron guardar los videos"
MENSAJE_SINCRONIZANDO = "Sincronizando catálogo…"
MENSAJE_ERROR_SINCRONIZACION = "No se pudo sincronizar el catálogo"
MENSAJE_SIN_ESCANEO = "Sin escanear"


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
        self.carpeta_seleccionada = None
        self._escaneo_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self.tarea_escaneo = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.videos_detectados = None
        self.registros_guardados = None
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = None

        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText("Buscar por nombre...")
        self.busqueda.textChanged.connect(self.filtrar)

        self.contador = QLabel()
        self.estado_carga = QLabel(MENSAJE_CARGANDO)

        self.boton_seleccionar_carpeta = QPushButton("Seleccionar carpeta")
        self.boton_seleccionar_carpeta.clicked.connect(self.seleccionar_carpeta)

        self.boton_escanear = QPushButton("Escanear carpeta")
        self.boton_escanear.setEnabled(False)
        self.boton_escanear.clicked.connect(self.iniciar_escaneo)

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
        layout.addLayout(fila_carpeta)
        layout.addLayout(barra)
        layout.addWidget(self.area)
        self.setCentralWidget(raiz)

        self.gestor = GestorTareas(self)
        self.gestor.tarea_resultado.connect(self._al_resultado)
        self.gestor.tarea_error.connect(self._al_error)
        self.gestor.tarea_finalizada.connect(self._al_tarea_finalizada)
        self.gestor.actividad_cambiada.connect(self._al_actividad)
        self._iniciar_carga()

    def _iniciar_carga(self):
        self.tarea_lectura = TareaLecturaCatalogoPaginada(
            TAMANIO_PAGINA_INICIAL, 0, None, self._ruta_db
        )
        self.gestor.iniciar(self.tarea_lectura)

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
        self._actualizar_botones_carpeta()

    def _actualizar_botones_carpeta(self):
        carpeta_valida = (
            self.carpeta_seleccionada is not None
            and os.path.isdir(self.carpeta_seleccionada)
        )
        cadena_activa = (
            self._escaneo_pendiente
            or self._ffprobe_pendiente
            or self._miniaturas_pendiente
            or self._guardado_pendiente
            or self._sincronizacion_pendiente
        )
        self.boton_seleccionar_carpeta.setEnabled(not cadena_activa)
        self.boton_escanear.setEnabled(
            carpeta_valida and not self.gestor.activo and not cadena_activa
        )

    def _al_actividad(self, activo):
        self._actualizar_botones_carpeta()

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
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self.registros_guardados = None
        self.resultado_sincronizacion = None
        self.tarea_escaneo = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        if not self.gestor.iniciar(tarea):
            self._escaneo_pendiente = False
            self._actualizar_botones_carpeta()
            return
        self.tarea_escaneo = tarea
        self.estado_escaneo.setText(MENSAJE_ESCANEANDO)
        self._actualizar_botones_carpeta()

    def _limpiar_cadena(self):
        self._escaneo_pendiente = False
        self._ffprobe_pendiente = False
        self._miniaturas_pendiente = False
        self._guardado_pendiente = False
        self._sincronizacion_pendiente = False
        self.tarea_escaneo = None
        self.tarea_ffprobe = None
        self.tarea_miniaturas = None
        self.tarea_guardado = None
        self.tarea_sincronizacion = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None

    def _al_resultado_escaneo(self, videos):
        self._escaneo_pendiente = False
        self._ffprobe_pendiente = True
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
        if self._carga_completada:
            return
        self.estado_carga.hide()
        self._crear_tarjetas(resultado.get("videos", []))
        self._carga_completada = True

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
        tarea = TareaGuardarVideos(registros, self._ruta_db)
        if not self.gestor.iniciar(tarea):
            self._limpiar_cadena()
            self._actualizar_botones_carpeta()
            return
        self.tarea_guardado = tarea

    def _al_tarea_finalizada(self):
        if self.gestor.estado != Estado.INACTIVO:
            self._limpiar_cadena()
            return
        if self._escaneo_pendiente:
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
        self._actualizar_botones_carpeta()

    def _al_resultado_sincronizacion(self, resultado):
        self._sincronizacion_pendiente = False
        self.tarea_sincronizacion = None
        self.resultado_sincronizacion = resultado
        self.estado_escaneo.setText(
            texto_resumen_sincronizacion(resultado.get("resumen"))
        )
        self._actualizar_botones_carpeta()

    def _al_error_sincronizacion(self, mensaje):
        self._limpiar_cadena()
        self.estado_escaneo.setText(MENSAJE_ERROR_SINCRONIZACION)
        self._actualizar_botones_carpeta()

    def _al_resultado_guardado(self, resultado):
        self._guardado_pendiente = False
        self.tarea_guardado = None
        self.resultado_ffprobe = None
        self.resultado_miniaturas = None
        self.registros_guardados = resultado.get("guardados")
        self._sincronizacion_pendiente = True
        self._actualizar_botones_carpeta()

    def _al_error(self, mensaje):
        if self._escaneo_pendiente:
            self._al_error_escaneo(mensaje)
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
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    print(f"carpeta_inicio={ventana.carpeta_seleccionada}")
    print(f"etiqueta_inicio={ventana.etiqueta_carpeta.text()}")
    print(f"estado_inicio={ventana.estado_carga.text()}")
    print(f"escanear_boton_inicio={ventana.boton_escanear.isEnabled()}")
    print(f"estado_escaneo_inicio={ventana.estado_escaneo.text()}")

    original_dialogo = QFileDialog.getExistingDirectory
    temp_carpeta = tempfile.TemporaryDirectory()
    try:
        for nombre in ["peli.mp4", "serie.mkv", "clip.avi", "doc.txt", "nota.log"]:
            with open(
                os.path.join(temp_carpeta.name, nombre), "w", encoding="utf-8"
            ) as f:
                f.write("contenido")

        QFileDialog.getExistingDirectory = lambda *args, **kwargs: temp_carpeta.name
        ventana.seleccionar_carpeta()
        print(f"carpeta_seleccion={ventana.carpeta_seleccionada}")
        print(f"etiqueta_seleccion={ventana.etiqueta_carpeta.text()}")
        print(f"escanear_boton_activo={ventana.boton_escanear.isEnabled()}")

        QFileDialog.getExistingDirectory = lambda *args, **kwargs: ""
        ventana.seleccionar_carpeta()
        print(f"carpeta_tras_cancelar={ventana.carpeta_seleccionada}")
        print(f"etiqueta_tras_cancelar={ventana.etiqueta_carpeta.text()}")
        print(f"escanear_boton_tras_cancelar={ventana.boton_escanear.isEnabled()}")

        espera_carga = {"intentos": 0}
        espera_escaneo = {"intentos": 0}

        def comprobar_escaneo():
            if (
                ventana.gestor.activo
                or ventana._escaneo_pendiente
                or ventana._ffprobe_pendiente
                or ventana._miniaturas_pendiente
                or ventana._guardado_pendiente
                or ventana._sincronizacion_pendiente
            ) and espera_escaneo["intentos"] < 200:
                espera_escaneo["intentos"] += 1
                QTimer.singleShot(25, comprobar_escaneo)
                return
            print(f"videos_detectados={ventana.videos_detectados}")
            print(f"estado_escaneo_final={ventana.estado_escaneo.text()}")
            print(f"escanear_boton_final={ventana.boton_escanear.isEnabled()}")
            print(f"guardado_total={ventana.registros_guardados}")
            if ventana.resultado_sincronizacion is not None:
                print(
                    "resumen_sincronizacion="
                    + texto_resumen_sincronizacion(
                        ventana.resultado_sincronizacion.get("resumen")
                    )
                )
            ventana.busqueda.setText("real")

            def verificar_y_cerrar():
                visibles = ventana.tarjetas_visibles()
                print(f"visibles_filtro={visibles}")
                print(f"contador_final={ventana.contador.text()}")
                ventana.close()
                app.quit()

            QTimer.singleShot(1500, verificar_y_cerrar)

        def comprobar_carga():
            if (
                not ventana._carga_completada or ventana.gestor.activo
            ) and espera_carga["intentos"] < 100:
                espera_carga["intentos"] += 1
                QTimer.singleShot(100, comprobar_carga)
                return
            print(f"visibles_cargados={ventana.tarjetas_visibles()}")
            print(f"contador_cargado={ventana.contador.text()}")
            print(f"escanear_boton_habilitado={ventana.boton_escanear.isEnabled()}")
            ventana.boton_escanear.click()
            print(f"estado_escaneo_mientras={ventana.estado_escaneo.text()}")
            print(f"escanear_boton_mientras={ventana.boton_escanear.isEnabled()}")
            espera_escaneo["intentos"] = 0
            QTimer.singleShot(0, comprobar_escaneo)

        QTimer.singleShot(200, comprobar_carga)
        codigo = app.exec()
    finally:
        QFileDialog.getExistingDirectory = original_dialogo
        temp_carpeta.cleanup()
        temp.cleanup()
    sys.exit(codigo)


if __name__ == "__main__":
    main()
