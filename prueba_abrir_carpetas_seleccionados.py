import os
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

from visor_videos import VisorVideos

_CONTADOR = [0]
_FALLOS = [0]


def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]


def ok(mensaje):
    _paso()
    print(f"T{_CONTADOR[0]:02d} OK - {mensaje}")


def falla(mensaje, extra=None):
    _FALLOS[0] += 1
    _paso()
    texto = f"T{_CONTADOR[0]:02d} ERROR - {mensaje}"
    if extra is not None:
        texto += f" ({extra})"
    print(texto)


def verifica(condicion, descripcion):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion)


def main():
    app = QApplication(sys.argv)

    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")

    from tareas_videos import conectar_bd, guardar_videos
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    guardar_videos(
        [
            {
                "nombre": f"v{i:03d}.mp4",
                "ruta": os.path.join(temp.name, f"v{i:03d}.mp4"),
                "extension": ".mp4",
                "fecha_importacion": "2026-08-05T00:00:00",
            }
            for i in range(1, 6)
        ],
        ruta_db,
    )

    _CONFIG = tempfile.TemporaryDirectory()
    os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    def esperar(predicado, intentos=200):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)

    _CONTADOR[0] = 1

    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        for nombre_arch in ["v001.mp4", "v002.mp4", "v003.mp4", "v004.mp4", "v005.mp4"]:
            with open(os.path.join(carpeta_temp.name, nombre_arch), "w") as f:
                f.write("contenido")

        ventana.carpeta_seleccionada = carpeta_temp.name

        original_startfile = os.startfile
        llamadas = []

        def _startfile_prueba(ruta):
            llamadas.append(ruta)

        # --- metodo existe ---
        verifica(
            hasattr(ventana, "_abrir_carpetas_seleccionados"),
            "VisorVideos tiene metodo _abrir_carpetas_seleccionados",
        )

        # --- unico seleccionado: abre una carpeta ---
        ventana._limpiar_seleccion()
        ventana._al_seleccionar_tarjeta("v003.mp4", False)

        os.startfile = _startfile_prueba
        try:
            ventana._abrir_carpetas_seleccionados()
            carpeta_esperada = os.path.abspath(carpeta_temp.name)
            verifica(
                len(llamadas) == 1,
                "unico seleccionado: 1 carpeta abierta",
            )
            verifica(
                llamadas[0] == carpeta_esperada,
                "unico seleccionado: carpeta correcta",
            )
        finally:
            os.startfile = original_startfile

        # --- multiples seleccionados misma carpeta: se abre una sola vez ---
        ventana._limpiar_seleccion()
        ventana._al_seleccionar_tarjeta("v001.mp4", False)
        ventana._al_seleccionar_tarjeta("v003.mp4", True)
        ventana._al_seleccionar_tarjeta("v005.mp4", True)

        llamadas.clear()
        os.startfile = _startfile_prueba
        try:
            ventana._abrir_carpetas_seleccionados()
            verifica(
                len(llamadas) == 1,
                "misma carpeta: 1 sola apertura con 3 seleccionados",
            )
            verifica(
                llamadas[0] == carpeta_esperada,
                "misma carpeta: carpeta correcta",
            )
        finally:
            os.startfile = original_startfile

        # --- sin carpeta seleccionada no falla ---
        ventana.carpeta_seleccionada = None
        try:
            ventana._abrir_carpetas_seleccionados()
            verifica(True, "sin carpeta seleccionada: no lanza excepcion")
        except Exception as exc:
            falla(f"sin carpeta lanzo {type(exc).__name__}")

        # --- sin seleccion no abre nada ---
        ventana.carpeta_seleccionada = carpeta_temp.name
        ventana._limpiar_seleccion()
        llamadas.clear()
        os.startfile = _startfile_prueba
        try:
            ventana._abrir_carpetas_seleccionados()
            verifica(
                len(llamadas) == 0,
                "sin seleccion: no abre ninguna carpeta",
            )
        finally:
            os.startfile = original_startfile

        # --- "Abrir carpeta" original sigue funcionando ---
        llamadas.clear()
        os.startfile = _startfile_prueba
        try:
            ventana._abrir_carpeta("v002.mp4")
            verifica(
                len(llamadas) == 1,
                "Abrir carpeta original: llama a os.startfile 1 vez",
            )
            verifica(
                llamadas[0] == carpeta_esperada,
                "Abrir carpeta original: carpeta correcta",
            )
        finally:
            os.startfile = original_startfile

        # --- deduplicacion funciona: todos los seleccionados comparten carpeta ---
        ventana._limpiar_seleccion()
        for nombre in ["v001.mp4", "v002.mp4", "v003.mp4", "v004.mp4", "v005.mp4"]:
            ventana._nombres_seleccionados.add(nombre)
            ventana._marcar_tarjeta(nombre, True)

        llamadas.clear()
        os.startfile = _startfile_prueba
        try:
            ventana._abrir_carpetas_seleccionados()
            verifica(
                len(llamadas) == 1,
                "5 seleccionados misma carpeta: 1 sola apertura",
            )
        finally:
            os.startfile = original_startfile
    finally:
        carpeta_temp.cleanup()

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp.cleanup()
    _CONFIG.cleanup()

    total = _CONTADOR[0] - 1
    errores = _FALLOS[0]
    print(f"TOTAL={total - errores}/{total}")
    if errores == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
