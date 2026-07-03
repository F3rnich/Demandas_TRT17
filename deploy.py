#!/usr/bin/env python3
"""
deploy.py — deploy confiavel para o GitHub Pages do repo Demandas_TRT17.

Por que existe:
  - Editor web do GitHub (CodeMirror 6) nao e automatizavel de forma confiavel.
  - Commits soltos em sequencia disparam builds concorrentes do Pages que falham
    ("Deployment failed, try again later").
  - "commit OK" != "publicado": o build do Pages roda depois e pode falhar.

O que faz:
  1. INTEGRIDADE: valida cada arquivo contra checks.json ANTES de commitar.
     Aborta se algum violar o manifesto (use --force para ignorar).
  2. Commit ATOMICO de N arquivos numa unica revisao (Git Data API). 1 commit = 1 build.
  3. Verifica o build do Pages ate status terminal, travado no proprio commit.
  4. Em falha transiente, re-dispara via COMMIT VAZIO (o PAT nao tem Pages:write).

Seguranca:
  - Token lido de GITHUB_PAT (env). NUNCA no repo (publico -> GitHub revoga PAT commitado).

Uso:
  export GITHUB_PAT=***
  python deploy.py "mensagem" arquivo1.html [arquivo2.html ...]
     # cada arg pode ser  local  ou  local:caminho_no_repo  (sem ':' usa o basename)
  python deploy.py --rebuild ["mensagem"]     # so re-dispara o build (recupera de erro transiente)
  python deploy.py --force "msg" arquivo...   # ignora a checagem de integridade
"""
import os, sys, json, base64, time, urllib.request, urllib.error

REPO   = os.environ.get("GITHUB_REPO", "F3rnich/Demandas_TRT17")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
PAT    = os.environ.get("GITHUB_PAT", "")
API    = "https://api.github.com"
owner, name = REPO.split("/")
PAGES_URL = f"https://{owner.lower()}.github.io/{name}/"

if not PAT:
    sys.exit("ERRO: defina o token em GITHUB_PAT (nao commitar o token; repo publico).")

HDR = {"Authorization": f"Bearer {PAT}", "Accept": "application/vnd.github+json",
       "User-Agent": "deploy.py", "Content-Type": "application/json"}

def api(method, path, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=HDR)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, {"raw": raw}

def repo_file(path):
    st, d = api("GET", f"/repos/{REPO}/contents/{path}")
    if st >= 300: return None
    return base64.b64decode(d["content"]).decode("utf-8", "replace")

# ---------- integridade ----------
def load_rules(pairs):
    for local, repopath in pairs:                 # prefere checks.json local (se estiver no deploy)
        if repopath == "checks.json":
            try: return json.load(open(local, encoding="utf-8"))
            except Exception as e: print("  aviso: checks.json local ilegivel:", e); return None
    content = repo_file("checks.json")            # senao, o do repo
    if content is None: return None
    try: return json.loads(content)
    except Exception as e: print("  aviso: checks.json do repo ilegivel:", e); return None

def integrity(pairs, rules):
    report = {}
    for local, repopath in pairs:
        entry = rules.get(repopath)
        if not entry: continue
        content = open(local, encoding="utf-8", errors="replace").read()
        problems = []
        for tok in entry.get("must_contain", []):
            if tok not in content: problems.append(f"faltando: {tok!r}")
        for tok in entry.get("must_not_contain", []):
            if tok in content: problems.append(f"proibido presente: {tok!r}")
        if problems: report[repopath] = problems
    return report

# ---------- commit atomico ----------
def commit_files(message, pairs):
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    base = ref["object"]["sha"]
    _, cinfo = api("GET", f"/repos/{REPO}/git/commits/{base}")
    tree = []
    for local, repopath in pairs:
        b64 = base64.b64encode(open(local, "rb").read()).decode()
        st, blob = api("POST", f"/repos/{REPO}/git/blobs", {"content": b64, "encoding": "base64"})
        if st >= 300: sys.exit(f"ERRO blob {local}: {st} {blob}")
        tree.append({"path": repopath, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  blob  {local} -> {repopath}")
    st, nt = api("POST", f"/repos/{REPO}/git/trees", {"base_tree": cinfo["tree"]["sha"], "tree": tree})
    if st >= 300: sys.exit(f"ERRO tree: {st} {nt}")
    st, nc = api("POST", f"/repos/{REPO}/git/commits", {"message": message, "tree": nt["sha"], "parents": [base]})
    if st >= 300: sys.exit(f"ERRO commit: {st} {nc}")
    st, up = api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": nc["sha"], "force": False})
    if st >= 300: sys.exit(f"ERRO ref (permissao? workflow files exigem escopo Workflows): {st} {up}")
    print(f"  commit {nc['sha'][:7]} ({len(pairs)} arquivo(s), 1 build)")
    return nc["sha"]

# ---------- verificacao do build ----------
def latest_build():
    st, b = api("GET", f"/repos/{REPO}/pages/builds/latest")
    return b if st < 300 else {}

def wait_build(expect_commit, timeout=240):
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        b = latest_build(); status = b.get("status"); commit = (b.get("commit") or "")
        if status != last: print(f"  build: {status} ({commit[:7]})"); last = status
        if status in ("built", "errored") and expect_commit and commit.startswith(expect_commit[:7]):
            return status, b
        time.sleep(4)
    return "timeout", b

def retrigger_build(message="retry: re-dispara build do Pages (commit vazio)"):
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    base = ref["object"]["sha"]
    _, cinfo = api("GET", f"/repos/{REPO}/git/commits/{base}")
    st, nc = api("POST", f"/repos/{REPO}/git/commits", {"message": message, "tree": cinfo["tree"]["sha"], "parents": [base]})
    if st >= 300: print(f"  falha ao re-disparar: {st} {nc}"); return None
    api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": nc["sha"], "force": False})
    print(f"  re-disparado via commit vazio {nc['sha'][:7]}")
    return nc["sha"]

def ensure_deployed(expect_commit, retries=3):
    for attempt in range(1, retries + 1):
        status, _ = wait_build(expect_commit)
        if status == "built":
            print(f"OK — publicado. {PAGES_URL}"); return True
        print(f"  tentativa {attempt}: build '{status}'. Re-disparando...")
        expect_commit = retrigger_build()
        if not expect_commit: time.sleep(5)
    print("FALHA — build nao ficou 'built'. Provavel incidente transiente do GitHub Pages; "
          "rode  python deploy.py --rebuild  em alguns minutos.")
    return False

# ---------- main ----------
def main():
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if not args: sys.exit(__doc__)
    if args[0] == "--rebuild":
        print("Re-disparando build do Pages...")
        ensure_deployed(expect_commit=retrigger_build()); return
    message, files = args[0], args[1:]
    if not files: sys.exit("ERRO: informe ao menos um arquivo.")
    pairs = []
    for a in files:
        local, repopath = (a.split(":", 1) if (":" in a and not a.startswith("http")) else (a, os.path.basename(a)))
        if not os.path.isfile(local): sys.exit(f"ERRO: arquivo nao encontrado: {local}")
        pairs.append((local, repopath))

    print(f"Deploy -> {REPO}@{BRANCH}")
    rules = load_rules(pairs)
    if rules:
        report = integrity(pairs, rules)
        if report:
            print("INTEGRIDADE — problemas:")
            for f, ps in report.items():
                for p in ps: print(f"  {f}: {p}")
            if not force: sys.exit("Deploy ABORTADO. Corrija, ou use --force para ignorar.")
            print("  (--force: prosseguindo mesmo assim)")
        else:
            print("  integridade: OK")
    else:
        print("  (sem checks.json aplicavel; checagem pulada)")
    ensure_deployed(expect_commit=commit_files(message, pairs))

if __name__ == "__main__":
    main()
