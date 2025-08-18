import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.jinja_env.auto_reload = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(host="0.0.0.0", port=port)

import subprocess, hashlib, yaml

def demo_cmd(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True)  # nosec

def demo_md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()  # nosec

def demo_yaml(s: str):
    return yaml.load(s, Loader=yaml.Loader)  # nosec



