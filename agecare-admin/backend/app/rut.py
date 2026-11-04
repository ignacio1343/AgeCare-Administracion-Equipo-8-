"""RUT chileno: validación del dígito verificador (módulo 11) y formato."""
import re


def dv(cuerpo: str) -> str:
    """Dígito verificador de un RUT sin puntos ni guion (algoritmo módulo 11)."""
    s, m = 0, 2
    for d in reversed(cuerpo):
        s += int(d) * m
        m = 2 if m == 7 else m + 1
    r = 11 - s % 11
    return {11: "0", 10: "K"}.get(r, str(r))


def normalizar(rut: str | None) -> str | None:
    """«12.345.678-5», «12345678-5» o «123456785» → «12345678-5». Devuelve None si el RUT no es válido."""
    if not rut:
        return None
    r = re.sub(r"[.\-\s]", "", rut).upper()
    if not re.fullmatch(r"\d{7,8}[\dK]", r):
        return None
    cuerpo, digito = r[:-1].lstrip("0") or "0", r[-1]
    if len(cuerpo) < 6 or dv(cuerpo) != digito:
        return None
    return f"{cuerpo}-{digito}"


def valido(rut: str | None) -> bool:
    return normalizar(rut) is not None


def formatear(rut: str | None) -> str | None:
    """«12345678-5» → «12.345.678-5» (para mostrar)."""
    if not rut or "-" not in rut:
        return rut
    cuerpo, d = rut.split("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{d}"
