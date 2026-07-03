#!/usr/bin/env python3
"""
validate_checks.py — valida os arquivos do repo contra checks.json.

Usado por:
  - GitHub Action (validate.yml): roda sem argumentos -> valida TODOS os arquivos
    listados em checks.json contra a copia do repo (checkout).
  - Uso local: python validate_checks.py [arquivo ...] valida apenas os informados.

Regra por arquivo (checks.json):
  must_contain     -> todas as substrings devem estar presentes
  must_not_contain -> nenhuma pode estar presente
Arquivo listado no manifesto e ausente no disco = FALHA.

Saida: relatorio legivel. Codigo de saida 1 se houver qualquer falha, 0 se tudo ok.
"""
import json, os, sys

def load_manifest(path="checks.json"):
    if not os.path.isfile(path):
        print(f"ERRO: manifesto {path} nao encontrado.")
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def check_file(path, entry):
    if not os.path.isfile(path):
        return [f"arquivo ausente no repo (listado no manifesto)"]
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    problems = []
    for tok in entry.get("must_contain", []):
        if tok not in content:
            problems.append(f"faltando marcador obrigatorio: {tok!r}")
    for tok in entry.get("must_not_contain", []):
        if tok in content:
            problems.append(f"marcador proibido presente: {tok!r}")
    return problems

def main():
    manifest = load_manifest()
    targets = sys.argv[1:] or list(manifest.keys())
    total_fail = 0
    print("Validacao de integridade (checks.json)")
    print("-" * 52)
    for path in targets:
        entry = manifest.get(path) or manifest.get(os.path.basename(path))
        if not entry:
            print(f"  ~ {path}: sem regra no manifesto (ignorado)")
            continue
        problems = check_file(path, entry)
        if problems:
            total_fail += 1
            print(f"  X {path}")
            for p in problems:
                print(f"      - {p}")
        else:
            print(f"  OK {path}")
    print("-" * 52)
    if total_fail:
        print(f"FALHA: {total_fail} arquivo(s) com problema.")
        sys.exit(1)
    print("Tudo integro.")
    sys.exit(0)

if __name__ == "__main__":
    main()
