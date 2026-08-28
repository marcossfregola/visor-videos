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


def _clipboard():
    # B9.9 robustez headless Windows: clipboard puede tardar tras setText
    for _ in range(20):
        QApplication.processEvents()
        txt = QApplication.clipboard().text()
        # si hay contenido, esperar un poco más por estabilidad y retornar
        if txt:
            time.sleep(0.02)
            QApplication.processEvents()
            txt2 = QApplication.clipboard().text()
            return txt2 if txt2 else txt
        time.sleep(0.015)
    QApplication.processEvents()
    return QApplication.clipboard().text()


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

    # B9.9 fix: alinear fixture con contrato ruta_video_existente —
    # los archivos deben existir exactamente en la ruta persistida del catálogo
    # (temp.name), no en una carpeta separada.
    carpeta_temp = None  # compat: mantener nombre para lecturas si hiciera falta
    try:
        for nombre_arch in ["v001.mp4", "v002.mp4", "v003.mp4", "v004.mp4", "v005.mp4"]:
            with open(os.path.join(temp.name, nombre_arch), "w") as f:
                f.write("contenido")

        ventana.carpeta_seleccionada = temp.name

        # --- unico elemento seleccionado ---
        ventana._limpiar_seleccion()
        ventana._al_seleccionar_tarjeta("v003.mp4", False)
        ventana._copiar_rutas_seleccionados()
        ruta_esperada = os.path.abspath(os.path.join(temp.name, "v003.mp4"))
        verifica(
            _clipboard() == ruta_esperada,
            "unico seleccionado: una ruta en el portapapeles",
        )

        # --- multiples elementos en orden visible ---
        ventana._limpiar_seleccion()
        ventana._al_seleccionar_tarjeta("v001.mp4", False)
        ventana._al_seleccionar_tarjeta("v003.mp4", True)
        ventana._al_seleccionar_tarjeta("v005.mp4", True)
        ventana._copiar_rutas_seleccionados()
        rutas = _clipboard().split("\n")
        verifica(
            len(rutas) == 3,
            "multiples seleccionados: 3 lineas en el portapapeles",
        )
        ruta_001 = os.path.abspath(os.path.join(temp.name, "v001.mp4"))
        ruta_003 = os.path.abspath(os.path.join(temp.name, "v003.mp4"))
        ruta_005 = os.path.abspath(os.path.join(temp.name, "v005.mp4"))
        verifica(
            rutas == [ruta_001, ruta_003, ruta_005],
            "multiples seleccionados: orden visible correcto",
        )

        # --- sin carpeta seleccionada no falla ---
        ventana.carpeta_seleccionada = None
        ventana._copiar_rutas_seleccionados()
        verifica(True, "sin carpeta seleccionada: no lanza excepcion")

        # --- sin elementos seleccionados no copia nada ---
        ventana.carpeta_seleccionada = temp.name
        ventana._limpiar_seleccion()
        QApplication.clipboard().clear()
        QApplication.processEvents()
        QApplication.clipboard().setText("antes")
        QApplication.processEvents()
        # robustez headless Windows: clipboard puede tardar tras multi-line
        for _ in range(30):
            QApplication.processEvents()
            if QApplication.clipboard().text() == "antes":
                break
            time.sleep(0.02)
        ventana._copiar_rutas_seleccionados()
        verifica(
            _clipboard() == "antes",
            "sin seleccion: portapapeles no modificado",
        )

        # --- "Copiar ruta" original sigue funcionando ---
        ventana.carpeta_seleccionada = temp.name
        ventana._copiar_ruta("v002.mp4")
        ruta_002 = os.path.abspath(os.path.join(temp.name, "v002.mp4"))
        verifica(
            _clipboard() == ruta_002,
            "Copiar ruta original: ruta individual correcta",
        )

        # --- todos los seleccionados copian todas las rutas ---
        ventana._limpiar_seleccion()
        for nombre in ["v001.mp4", "v002.mp4", "v003.mp4", "v004.mp4", "v005.mp4"]:
            ventana._nombres_seleccionados.add(nombre)
            ventana._marcar_tarjeta(nombre, True)
        ventana._copiar_rutas_seleccionados()
        lineas = _clipboard().split("\n")
        verifica(
            len(lineas) == 5,
            "todos seleccionados: 5 lineas en el portapapeles",
        )

        # --- metodo existe ---
        verifica(
            hasattr(ventana, "_copiar_rutas_seleccionados"),
            "VisorVideos tiene metodo _copiar_rutas_seleccionados",
        )
    finally:
        if carpeta_temp is not None:
            try:
                carpeta_temp.cleanup()
            except Exception:
                pass

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
