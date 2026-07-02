#!/usr/bin/env python3
"""
deploy.py — deploy confiavel para o GitHub Pages do repo Demandas_TRT17.

Por que existe:
  - O editor web do GitHub (CodeMirror 6) nao e automatizavel de forma confiavel.
  - Commits soltos em sequencia disparam builds concorrentes do Pages que se
    cancelam e falham ("Deployment failed, try again later").
  - "commit OK" != "publicado": o build do Pages roda depois e pode falhar.

O que faz:
  1. Commit ATOMICO de N arquivos em uma unica revisao (Git Data API):
     blobs -> tree (sobre a arvore atual) -> commit -> update ref. 1 commit = 1 build.
  2. Verifica o build do Pages ate status terminal (built | errored).
  3. Em falha transiente, re-dispara o build (POST /pages/builds) e re-verifica.

Seguranca:
  - O token NUNCA fica no repo. E lido de GITHUB_PAT (variavel de ambiente).
  - Repo publico + PAT commitado => GitHub revoga o token. Por isso, env var.

Uso:
  export GITHUB_PAT=***        # token na memoria do projeto; injete na hora
  python deploy.py "mensagem do commit" arquivo1.html [arquivo2.html ...]
    # cada arg de arquivo pode ser  caminho_local  ou  caminho_local:caminho_no_repo
    # sem ':' o destino no repo = nome do arquivo (basename)

  python deploy.py --rebuild ["mensagem"]
    # nao commita nada; so re-dispara o build do Pages e verifica (recupera de erro transiente)
"""
import os, sys, json, base64, time, urllib.request, urllib.error

REPO   = os.environ.get("GITHUB_REPO", "F3rnich/Demandas_TRT17")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
PAT    = os.environ.get("GITHUB_PAT", "")
API    = "https://api.github.com"
PAGES_URL = f"https://{REPO.split('/')[0].lower()}.github.io/{REPO.split('/')[1]}/"

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

# ---------- commit atomico ----------
def commit_files(message, pairs):
    # ref atual -> commit base -> tree base
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    base_commit = ref["object"]["sha"]
    _, cinfo = api("GET", f"/repos/{REPO}/git/commits/{base_commit}")
    base_tree = cinfo["tree"]["sha"]

    tree = []
    for local, repopath in pairs:
        with open(local, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st, blob = api("POST", f"/repos/{REPO}/git/blobs", {"content": b64, "encoding": "base64"})
        if st >= 300: sys.exit(f"ERRO ao criar blob de {local}: {st} {blob}")
        tree.append({"path": repopath, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  blob  {local} -> {repopath}")

    st, newtree = api("POST", f"/repos/{REPO}/git/trees", {"base_tree": base_tree, "tree": tree})
    if st >= 300: sys.exit(f"ERRO ao criar tree: {st} {newtree}")
    st, newcommit = api("POST", f"/repos/{REPO}/git/commits",
                        {"message": message, "tree": newtree["sha"], "parents": [base_commit]})
    if st >= 300: sys.exit(f"ERRO ao criar commit: {st} {newcommit}")
    st, upd = api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": newcommit["sha"], "force": False})
    if st >= 300: sys.exit(f"ERRO ao atualizar ref: {st} {upd}")
    print(f"  commit {newcommit['sha'][:7]} ({len(pairs)} arquivo(s), 1 build)")
    return newcommit["sha"]

# ---------- verificacao do build do Pages ----------
def latest_build():
    st, b = api("GET", f"/repos/{REPO}/pages/builds/latest")
    return b if st < 300 else {}

def wait_build(expect_commit, timeout=240):
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        b = latest_build()
        status = b.get("status"); commit = (b.get("commit") or "")
        if status != last:
            print(f"  build: {status} ({commit[:7]})"); last = status
        fresh = expect_commit and commit.startswith(expect_commit[:7])
        if status in ("built", "errored") and fresh:
            return status, b
        time.sleep(4)
    return "timeout", b

def retrigger_build(message="retry: re-dispara build do Pages (commit vazio)"):
    # Re-dispara o build com um commit VAZIO (mesma arvore). Usa so permissao de Contents,
    # pois POST /pages/builds exige Pages:write (que o PAT pode nao ter -> 403).
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    base = ref["object"]["sha"]
    _, cinfo = api("GET", f"/repos/{REPO}/git/commits/{base}")
    st, nc = api("POST", f"/repos/{REPO}/git/commits",
                 {"message": message, "tree": cinfo["tree"]["sha"], "parents": [base]})
    if st >= 300:
        print(f"  falha ao re-disparar: {st} {nc}"); return None
    api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": nc["sha"], "force": False})
    print(f"  re-disparado via commit vazio {nc['sha'][:7]}")
    return nc["sha"]

def ensure_deployed(expect_commit, retries=3):
    for attempt in range(1, retries + 1):
        status, b = wait_build(expect_commit=expect_commit)
        if status == "built":
            print(f"OK — publicado. {PAGES_URL}")
            return True
        print(f"  tentativa {attempt}: build '{status}'. Re-disparando...")
        expect_commit = retrigger_build()
        if not expect_commit:
            time.sleep(5)
    print(f"FALHA — build nao ficou 'built' apos {retries} tentativas. "
          f"Provavel incidente transiente do GitHub Pages; rode  python deploy.py --rebuild  em alguns minutos.")
    return False

# ---------- main ----------
def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--rebuild":
        print("Re-disparando build do Pages...")
        sha = retrigger_build()
        ensure_deployed(expect_commit=sha)
        return
    message, files = args[0], args[1:]
    if not files:
        sys.exit("ERRO: informe ao menos um arquivo para deploy.")
    pairs = []
    for a in files:
        if ":" in a and not a.startswith("http"):
            local, repopath = a.split(":", 1)
        else:
            local, repopath = a, os.path.basename(a)
        if not os.path.isfile(local):
            sys.exit(f"ERRO: arquivo nao encontrado: {local}")
        pairs.append((local, repopath))
    print(f"Deploy -> {REPO}@{BRANCH}")
    sha = commit_files(message, pairs)
    ensure_deployed(expect_commit=sha)

if __name__ == "__main__":
    main()
