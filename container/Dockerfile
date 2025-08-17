# Image de base légère et stable
FROM python:3.8-slim

# Bonnes pratiques Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dossier de travail
WORKDIR /app

# (Optionnel) Paquets système minimaux. On évite gcc pour garder l'image petite,
# psutil==5.8.0 a des wheels pour py3.8, donc pas besoin de compiler.
# Si un jour tu as besoin de builder des wheels:
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copie des requirements en premier pour profiter du cache Docker
COPY src/requirements.txt /app/requirements.txt

# Installer les dépendances Python
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Copie du code applicatif
COPY src/ /app/src/

# S'assurer que 'src' est importable en top-level
ENV PYTHONPATH=/app

# Exposer le port Flask/Gunicorn
EXPOSE 5000

# Passer en utilisateur non-root (bonne pratique)
# Crée un user "app" et lui donne la propriété du dossier /app
RUN addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app
USER app

# Lancement avec Gunicorn
# CAS 1 (le plus courant) :
#   il y a une variable "app = Flask(__name__)" dans src/app/__init__.py
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "src.app:app"]

# --- ALTERNATIVE (décommente si tu utilises une factory) ---
# CAS 2 (factory):
#   il y a "def create_app(...):" dans src/app/__init__.py
# CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "src.app:create_app()"]
