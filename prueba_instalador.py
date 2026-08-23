"""Prueba ESTÁTICA de contrato del instalador (Beta 6 / B6.1): preservar datos
persistentes del usuario al desinstalar.

Esta prueba NO acepta ruta de Setup, NO ejecuta el Setup, NO instala ni
desinstala la aplicación, NO comprueba reinstalación ni modifica el sistema.
Únicamente inspecciona de forma estática `instalador.iss` y `rutas.py`.

Verifica de forma estatica el script Inno Setup `instalador.iss` y las rutas
de persistencia reales de `rutas.py`:

- que NO exista una regla de desinstalacion que elimine recursivamente `{app}`
  completo (seccion `[UninstallDelete]` tipo filesandordirs sobre `{app}`);
- que la entrada de `biblioteca.db` conserve `onlyifdoesntexist`
  (reinstalacion/actualizacion preserva una base existente);
- que la entrada de `biblioteca.db` incluya `uninsneveruninstall`
  (no se elimina al desinstalar aunque forme parte de `[Files]`);
- que `configuracion.json` y `miniaturas/` no queden cubiertos por ninguna
  regla destructiva de desinstalacion;
- que no se hayan introducido cambios de rutas de persistencia (`rutas.py`
  sigue resolviendo los datos junto a la raiz de la instalacion);
- que el instalador siga apuntando al mismo destino por usuario
  (`{localappdata}` Programas VisorVideos).

No instala ni desinstala nada: es una verificacion estatica de contrato.
"""

import os
import re
import sys

RUTA_ISS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instalador.iss")
RUTA_RUTAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rutas.py")

DESTINO_ESPERADO = "{localappdata}\\Programs\\VisorVideos"


def _texto_iss():
    with open(RUTA_ISS, encoding="utf-8") as f:
        return f.read()


def _texto_rutas():
    with open(RUTA_RUTAS, encoding="utf-8") as f:
        return f.read()


def test_01():
    texto = _texto_iss()
    if "[UninstallDelete]" not in texto:
        return True, "sin seccion [UninstallDelete]"
    seccion = texto.split("[UninstallDelete]", 1)[1]
    seccion = seccion.split("[", 1)[0]
    patron = re.compile(
        r"Name\s*:\s*[\"']{app}[\"']", re.IGNORECASE
    )
    ok = not patron.search(seccion)
    detalle = (
        "sin regla destructiva sobre {app}"
        if ok
        else "HALLAZGO: [UninstallDelete] aun apunta a {app}"
    )
    return ok, detalle


def test_02():
    texto = _texto_iss()
    linea = re.search(
        r'^Source:\s*"dist\\VisorVideos\\biblioteca\.db".*$',
        texto,
        re.MULTILINE | re.IGNORECASE,
    )
    ok_linea = linea is not None
    flags = ""
    if linea:
        flags = linea.group(0)
    ok = ok_linea and "onlyifdoesntexist" in flags.lower()
    return ok, (
        f"linea biblioteca.db={bool(linea)} "
        f"onlyifdoesntexist={'onlyifdoesntexist' in flags.lower()}"
    )


def test_03():
    texto = _texto_iss()
    linea = re.search(
        r'^Source:\s*"dist\\VisorVideos\\biblioteca\.db".*$',
        texto,
        re.MULTILINE | re.IGNORECASE,
    )
    flags = linea.group(0) if linea else ""
    ok = bool(linea) and "uninsneveruninstall" in flags.lower()
    return ok, (
        f"linea biblioteca.db={bool(linea)} "
        f"uninsneveruninstall={'uninsneveruninstall' in flags.lower()}"
    )


def test_04():
    texto = _texto_iss()
    hay_delete = "[UninstallDelete]" in texto
    if not hay_delete:
        return True, "sin [UninstallDelete]"
    seccion = texto.split("[UninstallDelete]", 1)[1]
    seccion = seccion.split("[", 1)[0]
    cubre_config = re.search(r"configuracion\.json", seccion, re.IGNORECASE)
    cubre_miniaturas = re.search(r"miniaturas", seccion, re.IGNORECASE)
    ok = (not hay_delete) or not (cubre_config or cubre_miniaturas)
    detalle = (
        "configuracion.json/miniaturas sin regla destructiva"
        if ok
        else "HALLAZGO: datos persistentes cubiertos por una regla destructiva"
    )
    return ok, detalle


def test_05():
    texto = _texto_rutas()
    joins_esperados = (
        'os.path.join(ruta_raiz(), "biblioteca.db")',
        'os.path.join(ruta_raiz(), "configuracion.json")',
        'os.path.join(ruta_raiz(), "miniaturas")',
        'os.path.join(ruta_raiz(), "miniaturas", "exploracion")',
    )
    faltantes = [j for j in joins_esperados if j not in texto]
    ok = not faltantes
    detalle = (
        "rutas de persistencia sin cambios"
        if ok
        else f"HALLAZGO: joins esperados no encontrados en rutas.py: {faltantes}"
    )
    return ok, detalle


def test_06():
    texto = _texto_rutas()
    destino_frozen = texto.count('os.path.dirname(sys.executable)')
    ok = destino_frozen >= 1
    return ok, (
        f"resolucion por sys.executable (modo empaquetado) presente "
        f"en {destino_frozen} lugar(es)"
    )


def test_07():
    texto = _texto_iss()
    ok = DESTINO_ESPERADO in texto
    return ok, (
        f"DestDir/DefaultDirName={DESTINO_ESPERADO!r} "
        f"presente={'si' if ok else 'no'}"
    )


def test_08():
    texto = _texto_iss()
    ok = texto.count("DefaultDirName") == 1
    if ok:
        m = re.search(r"DefaultDirName\s*=\s*([^\r\n]+)", texto)
        valor = m.group(1).strip() if m else ""
        ok = valor.lower().replace(" ", "") == DESTINO_ESPERADO.lower().replace(
            " ", ""
        )
    return ok, (
        f"instalacion por usuario en {DESTINO_ESPERADO!r}"
        if ok
        else "HALLAZGO: DefaultDirName no coincide con el destino por usuario"
    )


def main():
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"I{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())