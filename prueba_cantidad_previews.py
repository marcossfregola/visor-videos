import json
import os
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos
from configuracion import CLAVE_CANTIDAD_PREVIEWS, guardar_cantidad_previews, obtener_cantidad_previews
from escanear_videos import configurar_cantidad_previews, previews_existentes
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

    _CONTADOR[0] = 1

    # --- configurar_cantidad_previews existe ---
    verifica(
        callable(configurar_cantidad_previews),
        "configurar_cantidad_previews es invocable",
    )

    # --- CANTIDAD_PREVIEWS es mutable ---
    original = escanear_videos.CANTIDAD_PREVIEWS
    configurar_cantidad_previews(5)
    verifica(
        escanear_videos.CANTIDAD_PREVIEWS == 5,
        "CANTIDAD_PREVIEWS se puede cambiar a 5",
    )
    configurar_cantidad_previews(original)

    # --- previews_existentes respeta la nueva cantidad ---
    temp_mini = tempfile.TemporaryDirectory()
    try:
        original_mini = escanear_videos.ruta_carpeta_miniaturas
        escanear_videos.ruta_carpeta_miniaturas = lambda: temp_mini.name
        try:
            for idx in range(1, 10):
                ruta = escanear_videos.ruta_preview("video_test.mp4", idx)
                with open(ruta, "w") as f:
                    f.write("x")
            configurar_cantidad_previews(5)
            existentes = previews_existentes("video_test.mp4")
            verifica(
                len(existentes) == 5,
                "previews_existentes con cantidad 5 devuelve 5 existentes",
            )
            configurar_cantidad_previews(9)
            existentes = previews_existentes("video_test.mp4")
            verifica(
                len(existentes) == 9,
                "previews_existentes con cantidad 9 devuelve 9 existentes",
            )
        finally:
            escanear_videos.ruta_carpeta_miniaturas = original_mini
    finally:
        temp_mini.cleanup()
    configurar_cantidad_previews(original)

    # --- persistencia: guardar y obtener cantidad ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_cantidad_previews(7, ruta_config)
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_CANTIDAD_PREVIEWS) == 7,
            "guardar 7 persiste en JSON",
        )
        verifica(
            obtener_cantidad_previews(ruta_config) == 7,
            "obtener devuelve 7",
        )
    finally:
        temp_config.cleanup()

    # --- obtener sin archivo devuelve 3 ---
    temp_no = tempfile.TemporaryDirectory()
    ruta_no = os.path.join(temp_no.name, "inexistente.json")
    try:
        verifica(
            obtener_cantidad_previews(ruta_no) == 3,
            "obtener sin archivo devuelve 3",
        )
    finally:
        temp_no.cleanup()

    # --- UI: cantidad aplicada inmediatamente sin reescaneo ---
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    from tareas_videos import conectar_bd, guardar_videos
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    guardar_videos(
        [{
            "nombre": "v001.mp4",
            "ruta": os.path.join(temp_db.name, "v001.mp4"),
            "extension": ".mp4",
            "fecha_importacion": "2026-08-05T00:00:00",
        }],
        ruta_db,
    )

    temp_mini2 = tempfile.TemporaryDirectory()
    original_mini = escanear_videos.ruta_carpeta_miniaturas
    escanear_videos.ruta_carpeta_miniaturas = lambda: temp_mini2.name
    try:
        for idx in range(1, 10):
            ruta = escanear_videos.ruta_preview("v001.mp4", idx)
            with open(ruta, "w") as f:
                f.write("x")

        configurar_cantidad_previews(9)

        temp_config2 = tempfile.TemporaryDirectory()
        ruta_config2 = os.path.join(temp_config2.name, "config.json")
        try:
            guardar_cantidad_previews(9, ruta_config2)

            os.environ.pop("VISOR_CONFIG", None)
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config2)
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

            verifica(
                len(ventana.tarjetas) >= 1,
                "hay al menos 1 tarjeta cargada",
            )

            tarjeta = ventana.tarjetas[0][1]
            visibles = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles == 9, "9 labels visibles al iniciar con cantidad 9")

            # Caso 1: 9 -> 3. Cambio inmediato sin escaneo.
            idx_3 = ventana.combo_cantidad_previews.findText("3")
            ventana.combo_cantidad_previews.setCurrentIndex(idx_3)
            QApplication.processEvents()
            visibles_3 = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles_3 == 3, "caso 1 (9->3): solo 3 labels visibles")

            # Caso 2: 3 -> 7. Ya existen 9 archivos en cache.
            idx_7 = ventana.combo_cantidad_previews.findText("7")
            ventana.combo_cantidad_previews.setCurrentIndex(idx_7)
            QApplication.processEvents()
            visibles_7 = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles_7 == 7, "caso 2 (3->7): 7 labels visibles inmediatamente")

            # Caso 3: 5 <-> 9
            idx_5 = ventana.combo_cantidad_previews.findText("5")
            idx_9 = ventana.combo_cantidad_previews.findText("9")
            ventana.combo_cantidad_previews.setCurrentIndex(idx_5)
            QApplication.processEvents()
            visibles_5 = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles_5 == 5, "caso 3 (9->5): 5 labels visibles")
            ventana.combo_cantidad_previews.setCurrentIndex(idx_9)
            QApplication.processEvents()
            visibles_9 = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles_9 == 9, "caso 3 (5->9): 9 labels visibles de vuelta")

            # Caso 4: misma cantidad, sin cambios
            ventana.combo_cantidad_previews.setCurrentIndex(idx_9)
            QApplication.processEvents()
            visibles_9b = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
            verifica(visibles_9b == 9, "caso 4 (9->9): 9 labels visibles")

            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
        finally:
            temp_config2.cleanup()
    finally:
        escanear_videos.ruta_carpeta_miniaturas = original_mini
        temp_mini2.cleanup()

    temp_db.cleanup()

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
