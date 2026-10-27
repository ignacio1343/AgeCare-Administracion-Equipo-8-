"""Evalúa el CSV de Locust contra los criterios de aceptación y escribe una tabla Markdown.

Uso: python tests/carga/evaluar.py carga_stats.csv [--p95-consultas 800] [--p95-login 1500]
Sale con código 1 si algún criterio no se cumple (el workflow queda en rojo).
"""
import argparse
import csv
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--p95-consultas", type=float, default=800)
    ap.add_argument("--p95-login", type=float, default=1500)
    a = ap.parse_args()
    filas = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    ok_total = True
    out = ["| Endpoint | Peticiones | Errores | p50 ms | p95 ms | Límite p95 | Resultado |", "|---|---|---|---|---|---|---|"]
    for f in filas:
        if f["Name"] == "Aggregated":
            continue
        lim = a.p95_login if "login" in f["Name"] else a.p95_consultas
        n, err, p95 = int(f["Request Count"]), int(f["Failure Count"]), float(f["95%"])
        ok = err == 0 and p95 < lim
        ok_total &= ok
        out.append(f"| {f['Name']} | {n} | {err} | {f['50%']} | {p95:.0f} | {lim:.0f} | {'Cumple' if ok else 'NO cumple'} |")
    print("\n".join(out))
    print(f"\n**Resultado general: {'cumple' if ok_total else 'no cumple'} el criterio de aceptación.**")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
