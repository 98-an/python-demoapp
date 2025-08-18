import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.jinja_env.auto_reload = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(host="0.0.0.0", port=port)

# --- Démo vulnérabilités pour les scanners (non utilisées à l'exécution) ---
# NOTE: ces fonctions existent uniquement pour que Bandit/Semgrep aient des findings.
# Elles ne sont jamais appelées par l'application.

import subprocess  # B602/B603: shell=True / subprocess dangereux
import hashlib     # B303: usage de MD5 (hash faible)
import yaml        # B506: yaml.load non sécurisé

def _vuln_cmd(cmd: str) -> str:
    # Command injection (ne JAMAIS faire ça en vrai)
    return subprocess.check_output(cmd, shell=True, text=True)  # nosec

def _vuln_md5(data: str) -> str:
    # Hash faible MD5 (non recommandé)
    return hashlib.md5(data.encode()).hexdigest()  # nosec

def _vuln_yaml_load(s: str):
    # Chargement YAML non sûr (peut exécuter du code selon le contenu)
    return yaml.load(s, Loader=yaml.Loader)  # nosec
# --- fin démo ---
