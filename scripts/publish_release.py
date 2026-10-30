#!/usr/bin/env python3
"""
Automatisches Veröffentlichungsskript für EasyDateien.
- Liest die Version aus 'easydateien'
- Führt Tests aus
- Inkrementiert bei Bedarf die Version (Patch)
- Erstellt Git-Tag und GitHub-Release
- Berechnet den SHA-256-Hash des GitHub-Release-Tarballs
- Aktualisiert die Formula 'easydateien.rb' in jonathank55/homebrew-tap
"""

import os
import sys
import re
import time
import shutil
import hashlib
import tempfile
import subprocess
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAIN_FILE = os.path.join(REPO_ROOT, "easydateien")
TEST_RUNNER = os.path.join(REPO_ROOT, "run_tests.py")

FORMULA_TEMPLATE = """class Easydateien < Formula
  desc "Deutschsprachiger Terminaldateimanager für macOS mit integrierter Konsole"
  homepage "https://github.com/jonathank55/easydateien"
  url "https://github.com/jonathank55/easydateien/archive/refs/tags/v__VERSION__.tar.gz"
  sha256 "__SHA256__"
  license "MIT"

  depends_on "python@3.12"

  def install
    libexec.install "easydateien",
                    "easydateien_actions.py",
                    "easydateien_clip.m",
                    "easydateien_common.py",
                    "easydateien_konfigurator.py",
                    "easydateien_pdf.m",
                    "easydateien_preview.py",
                    "easydateien_symlink.py",
                    "easydateien_ui.py",
                    "easydateien_view.py",
                    "config.json"

    (bin/"easydateien").write <<~EOS
      #!/usr/bin/env bash
      exec python3 "#{libexec}/easydateien" "$@"
    EOS
    chmod 0755, bin/"easydateien"
    bin.install_symlink bin/"easydateien" => "ed"
  end

  def caveats
    <<~EOS
      Hinweis: EasyDateien ist ein rein deutschsprachiges Programm.
      Konfiguration liegt unter ~/.config/easydateien/config.json.
      Startbefehle: 'easydateien' oder 'ed'.

      Automatischer Verzeichniswechsel beim Beenden:
      Füge Folgendes in deine ~/.zshrc (oder ~/.bashrc) ein:
        eval "$(easydateien --init zsh)"
    EOS
  end

  test do
    assert_predicate libexec/"easydateien", :executable?
    assert_path_exists libexec/"easydateien_common.py"
    assert_path_exists libexec/"easydateien_preview.py"
    assert_match "EasyDateien __VERSION__", shell_output("#{bin}/easydateien -v")
    assert_match "easydateien()", shell_output("#{bin}/easydateien --init zsh")
  end
end
"""

def run(cmd, cwd=REPO_ROOT, check=True, env=None, capture=True):
    print(f"-> Führe aus: {cmd} (in {cwd})")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(cmd, shell=True, cwd=cwd, env=merged_env, text=True, capture_output=capture)
    if check and res.returncode != 0:
        print(f"FEHLER bei Befehl: {cmd}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)
    return res

def get_current_version():
    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'EasyDateien ([0-9]+\.[0-9]+\.[0-9]+)', content)
    if not m:
        raise ValueError("Konnte Versionsnummer in 'easydateien' nicht finden!")
    return m.group(1)

def bump_patch_version(current_ver):
    major, minor, patch = current_ver.split(".")
    new_ver = f"{major}.{minor}.{int(patch) + 1}"
    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = content.replace(f"EasyDateien {current_ver}", f"EasyDateien {new_ver}", 1)
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    py_copy = os.path.join(REPO_ROOT, "easydateien.py")
    if os.path.exists(py_copy):
        shutil.copy2(MAIN_FILE, py_copy)
    print(f"-> Version automatisch erhöht: {current_ver} -> {new_ver}")
    return new_ver

def compute_tarball_sha256(version, max_retries=10, delay=3):
    url = f"https://github.com/jonathank55/easydateien/archive/refs/tags/v{version}.tar.gz"
    print(f"-> Lade Archiv für SHA256-Berechnung: {url}")
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EasyDateien-Publisher"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) > 1000:
                        sha = hashlib.sha256(data).hexdigest()
                        print(f"-> SHA256 erfolgreich berechnet ({len(data)} Bytes): {sha}")
                        return sha
        except Exception as e:
            print(f"   [Versuch {attempt}/{max_retries}] Warten auf Bereitstellung durch GitHub: {e}")
        time.sleep(delay)
    raise RuntimeError(f"Konnte Tarball nach {max_retries} Versuchen nicht abrufen: {url}")

def update_homebrew_tap(version, sha256_hash, is_ci=False):
    print("-> Aktualisiere jonathank55/homebrew-tap...")
    work_dir = tempfile.mkdtemp(prefix="tap-update-")
    try:
        git_env = {}
        if is_ci and "TAP_DEPLOY_KEY" in os.environ and os.environ["TAP_DEPLOY_KEY"].strip():
            key_path = os.path.join(work_dir, "id_ed25519")
            with open(key_path, "w", encoding="utf-8") as kf:
                kf.write(os.environ["TAP_DEPLOY_KEY"].strip() + "\n")
            os.chmod(key_path, 0o600)
            git_env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=no"
            tap_url = "git@github.com:jonathank55/homebrew-tap.git"
        else:
            tap_url = "https://github.com/jonathank55/homebrew-tap.git"

        run(f"git clone {tap_url} tap_repo", cwd=work_dir, env=git_env)
        tap_repo = os.path.join(work_dir, "tap_repo")

        formula_dir = os.path.join(tap_repo, "Formula")
        os.makedirs(formula_dir, exist_ok=True)
        formula_path = os.path.join(formula_dir, "easydateien.rb")

        rendered = FORMULA_TEMPLATE.replace("__VERSION__", version).replace("__SHA256__", sha256_hash)
        with open(formula_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        # Auch lokale Formel im Hauptrepository synchron halten
        local_formula = os.path.join(REPO_ROOT, "easydateien.rb")
        with open(local_formula, "w", encoding="utf-8") as f:
            f.write(rendered)

        run("git add Formula/easydateien.rb", cwd=tap_repo, env=git_env)
        status = run("git status --porcelain", cwd=tap_repo, env=git_env).stdout.strip()
        if not status:
            print("-> Formula in Homebrew-Tap ist bereits auf dem neuesten Stand.")
            return

        run(f'git commit -m "Release EasyDateien v{version}"', cwd=tap_repo, env=git_env)
        run("git push origin main", cwd=tap_repo, env=git_env)
        print("-> Homebrew-Tap erfolgreich aktualisiert und gepusht!")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def main():
    is_ci = "--ci" in sys.argv
    print(f"=== EasyDateien Veröffentlichungsprozess (CI: {is_ci}) ===")

    # 1. Tests ausführen
    print("-> Führe Testsuite aus...")
    run(f"python3 {TEST_RUNNER}")

    # 2. Version ermitteln
    current_version = get_current_version()
    print(f"-> Aktuelle Version im Quellcode: {current_version}")

    # 3. Tags prüfen
    run("git fetch --tags origin", check=False)
    tag_name = f"v{current_version}"
    res = run(f"git rev-parse -q --verify refs/tags/{tag_name}", check=False)
    tag_exists = (res.returncode == 0)

    if tag_exists:
        # Prüfen, ob Tag bereits auf HEAD zeigt
        tag_commit = run(f"git rev-parse refs/tags/{tag_name}^{{commit}}").stdout.strip()
        head_commit = run("git rev-parse HEAD").stdout.strip()
        if tag_commit == head_commit:
            print(f"-> Tag {tag_name} zeigt bereits auf aktuellen HEAD ({head_commit[:8]}).")
            # Prüfen, ob Homebrew-Tap aktualisiert werden muss
            sha = compute_tarball_sha256(current_version)
            update_homebrew_tap(current_version, sha, is_ci=is_ci)
            print("-> Alles aktuell!")
            return
        else:
            print(f"-> Tag {tag_name} existiert bereits für einen älteren Commit. Erhöhe Patchversion...")
            current_version = bump_patch_version(current_version)
            tag_name = f"v{current_version}"
            run('git commit -am "chore: Inkrementiere Version auf ' + current_version + ' [skip ci]"')
            run("git push origin main")

    # 4. Tag erstellen und pushen
    print(f"-> Erstelle Git-Tag {tag_name}...")
    run(f'git tag -a "{tag_name}" -m "Release {tag_name} - Deutschsprachiger Terminaldateimanager"')
    run(f'git push origin "{tag_name}"')

    # 5. GitHub Release erstellen
    print(f"-> Erstelle GitHub-Release {tag_name}...")
    release_notes = f"Offizielles Release von EasyDateien {tag_name}. Minimalistischer, deutschsprachiger Terminaldateimanager für macOS."
    run(f'gh release create "{tag_name}" --title "EasyDateien {tag_name}" --notes "{release_notes}"', check=False)

    # 6. SHA256 berechnen
    sha = compute_tarball_sha256(current_version)

    # 7. Homebrew-Tap aktualisieren
    update_homebrew_tap(current_version, sha, is_ci=is_ci)

    # 8. Lokale easydateien.rb committen, falls geändert
    run("git add easydateien.rb", check=False)
    status = run("git status --porcelain easydateien.rb").stdout.strip()
    if status:
        run(f'git commit -m "docs: Aktualisiere Formula auf v{current_version} [skip ci]"', check=False)
        run("git push origin main", check=False)

    print(f"\n=======================================================")
    print(f" ERFOLG: EasyDateien v{current_version} wurde erfolgreich")
    print(f" auf GitHub und im Homebrew-Tap veröffentlicht!")
    print(f" Installation: brew install jonathank55/tap/easydateien")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
