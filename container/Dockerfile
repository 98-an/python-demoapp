FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# On travaille dans /app/src pour que "app:create_app()" fonctionne
WORKDIR /app/src

# Dépendances
COPY src/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r /app/requirements.txt

# Code
COPY src/ /app/src/

# Important : rendre /app/src importable (module "app")
ENV PYTHONPATH=/app/src

EXPOSE 5000

# Ta factory Flask est dans src/app/__init__.py -> def create_app()
# Comme WORKDIR = /app/src et PYTHONPATH=/app/src, on référence juste "app:create_app()"
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:create_app()"]
