#!/usr/bin/env python3
"""Monta calculadora_aposentadoria.html (raiz do repo) a partir de template.html + motor.js."""
import pathlib, subprocess, sys
aqui = pathlib.Path(__file__).resolve().parent
r = subprocess.run(["node", str(aqui / "testes.js")], capture_output=True, text=True)
print(r.stdout.splitlines()[-1] if r.stdout else r.stderr)
if r.returncode: sys.exit("Testes falharam — build abortado.")
t = (aqui / "template.html").read_text(encoding="utf-8")
m = (aqui / "motor.js").read_text(encoding="utf-8")
assert "/*__MOTOR__*/" in t
(aqui.parent / "calculadora_aposentadoria.html").write_text(t.replace("/*__MOTOR__*/", m), encoding="utf-8")
print("OK → calculadora_aposentadoria.html")
