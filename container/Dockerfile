
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# On travaillera directement dans /app/src pour que "app:app" fonctionne
WORKDIR /app/src

# Dépendances
COPY src/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r /app/requirements.txt \
 && pip install gunicorn

# Si tu restes sur Flask==1.1.2, force Jinja2<3.1 (sinon upgrade Flask et retire cette ligne)
RUN python - <<'PY'
from pathlib import Path
req = Path('/app/requirements.txt').read_text().lower()
if 'flask==1.1' in req or 'flask==1.1.2' in req:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Jinja2<3.1'])
PY

# Code
COPY src/ /app/src/

# Important: rendre /app/src importable sous le nom "app"
ENV PYTHONPATH=/app/src

EXPOSE 5000

# Si ton fichier **src/app/__init__.py** définit bien `app = Flask(__name__)`
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]

# Si tu utilises une factory: def create_app(): return app
# CMD ["gunicorn","-w","2","-b","0.0.0.0:5000","app:create_app()"]
