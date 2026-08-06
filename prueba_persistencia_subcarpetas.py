import json
import os
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

from configuracion import (
    CLAVE_SUBCARPETAS,
    guardar_preferencia_subcarpetas,
    obtener_preferencia_subcarpetas,
)
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

    # --- guardar True persiste en JSON ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_preferencia_subcarpetas(True, ruta_config)
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_SUBCARPETAS) is True,
            "guardar True persiste en JSON",
        )
    finally:
        temp_config.cleanup()

    # --- guardar False persiste en JSON ---
    temp_config2 = tempfile.TemporaryDirectory()
    ruta_config2 = os.path.join(temp_config2.name, "config.json")
    try:
        guardar_preferencia_subcarpetas(False, ruta_config2)
        with open(ruta_config2, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_SUBCARPETAS) is False,
            "guardar False persiste en JSON",
        )
    finally:
        temp_config2.cleanup()

    # --- obtener sin archivo devuelve False ---
    temp_config3 = tempfile.TemporaryDirectory()
    ruta_config3 = os.path.join(temp_config3.name, "inexistente.json")
    try:
        resultado = obtener_preferencia_subcarpetas(ruta_config3)
        verifica(
            resultado is False,
            "obtener sin archivo devuelve False",
        )
    finally:
        temp_config3.cleanup()

    # --- obtener con archivo sin la clave devuelve False ---
    temp_config4 = tempfile.TemporaryDirectory()
    ruta_config4 = os.path.join(temp_config4.name, "config.json")
    try:
        with open(ruta_config4, "w", encoding="utf-8") as f:
            json.dump({"otra_cosa": True}, f)
        resultado = obtener_preferencia_subcarpetas(ruta_config4)
        verifica(
            resultado is False,
            "obtener sin clave devuelve False",
        )
    finally:
        temp_config4.cleanup()

    # --- round-trip guardar y obtener ---
    temp_config5 = tempfile.TemporaryDirectory()
    ruta_config5 = os.path.join(temp_config5.name, "config.json")
    try:
        guardar_preferencia_subcarpetas(True, ruta_config5)
        resultado = obtener_preferencia_subcarpetas(ruta_config5)
        verifica(
            resultado is True,
            "round-trip: guardar True, obtener True",
        )
        guardar_preferencia_subcarpetas(False, ruta_config5)
        verifica(
            obtener_preferencia_subcarpetas(ruta_config5) is False,
            "round-trip: guardar False, obtener False",
        )
    finally:
        temp_config5.cleanup()

    # --- checkbox restaurado al iniciar con preferencia True ---
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    from tareas_videos import conectar_bd
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()

    temp_config6 = tempfile.TemporaryDirectory()
    ruta_config6 = os.path.join(temp_config6.name, "config.json")
    try:
        guardar_preferencia_subcarpetas(True, ruta_config6)

        os.environ.pop("VISOR_CONFIG", None)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config6)
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
            ventana.incluir_subcarpetas.isChecked(),
            "checkbox restaurado a True al iniciar",
        )

        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
    finally:
        temp_config6.cleanup()

    # --- checkbox restaurado al iniciar con preferencia False ---
    temp_config7 = tempfile.TemporaryDirectory()
    ruta_config7 = os.path.join(temp_config7.name, "config.json")
    try:
        guardar_preferencia_subcarpetas(False, ruta_config7)

        os.environ.pop("VISOR_CONFIG", None)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config7)
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
            not ventana.incluir_subcarpetas.isChecked(),
            "checkbox restaurado a False al iniciar",
        )

        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
    finally:
        temp_config7.cleanup()

    # --- al cambiar checkbox se persiste ---
    temp_config8 = tempfile.TemporaryDirectory()
    ruta_config8 = os.path.join(temp_config8.name, "config.json")
    try:
        os.environ.pop("VISOR_CONFIG", None)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config8)
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

        ventana.incluir_subcarpetas.setChecked(True)
        QApplication.processEvents()

        with open(ruta_config8, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_SUBCARPETAS) is True,
            "cambiar checkbox persiste True",
        )

        ventana.incluir_subcarpetas.setChecked(False)
        QApplication.processEvents()

        with open(ruta_config8, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_SUBCARPETAS) is False,
            "cambiar checkbox persiste False",
        )

        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
    finally:
        temp_config8.cleanup()

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
