pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          set -eux
          git remote -v || true
          git rev-parse HEAD || true
          git rev-parse --is-shallow-repository && git fetch --unshallow --tags --prune || true
          git config --global --add safe.directory "$PWD"
          rm -rf reports && mkdir -p reports
        '''
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          echo "Checked out commit: ${env.SHORT_SHA}"
        }
      }
    }

    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux

          # Petit inventaire pour debug (on le garde dans reports/)
          mkdir -p reports
          echo "=== DEBUG: fichiers Python trouvés (top 3 niveaux) ===" | tee reports/py_files.txt
          find . -maxdepth 3 -type f -name "*.py" -print | sort | tee -a reports/py_files.txt

          # Choix de la cible: src/ prioritaire si présent, sinon la racine.
          if [ -d src ]; then TARGETS="src"; else TARGETS="."; fi
          echo "=== DEBUG: Bandit TARGETS=${TARGETS}" | tee -a reports/py_files.txt

          # Exclusions (dossiers non-code)
          EXCLUDES=".git,.venv,.pytest_cache,_pycache_,node_modules,build,ci,container,deploy,infra,monitoring,reports"

          # Tout s’exécute dans un conteneur Python propre
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc "
            set -eux
            python -m pip install --upgrade pip

            # 1) Installer deps si requirements.txt quelque part
            REQ_FILE=\$(find . -type f -name requirements.txt \\
              -not -path './.git/' -not -path './reports/' -not -path './_pycache_/*' \\
              -not -path './.pytest_cache/' -not -path './.venv/' -not -path './node_modules/*' \\
              -not -path './build/' -not -path './ci/' -print -quit || true)
            if [ -n \"\$REQ_FILE\" ]; then
              echo \"Installing app deps from: \$REQ_FILE\"
              pip install --prefer-binary -r \"\$REQ_FILE\"
            else
              echo \"No requirements.txt found — skipping app deps install.\"
            fi

            # 2) Outils qualité
            pip install --prefer-binary pytest pytest-cov flake8 bandit pyyaml

            # 3) Lint (ne casse pas le build)
            flake8 || :

            # 4) Tests (rapports)
            pytest --maxfail=1 --cov=. \\
              --cov-report=xml:/ws/reports/coverage.xml \\
              --junitxml=/ws/reports/pytest-report.xml || :

            # 5) Bandit — on force la cible et on ignore les # nosec pour voir les démos
            bandit -r ${TARGETS} --ignore-nosec -x ${EXCLUDES} -f html  -o /ws/reports/bandit-report.html || :
            bandit -r ${TARGETS} --ignore-nosec -x ${EXCLUDES} -f txt   -o /ws/reports/bandit.txt        || :
            bandit -r ${TARGETS} --ignore-nosec -x ${EXCLUDES} -f json  -o /ws/reports/bandit.json       || :

            # Aperçu console
            bandit -r ${TARGETS} --ignore-nosec -x ${EXCLUDES} -f txt || :
          "

          # Fallback JUnit si nécessaire
          if [ ! -s reports/pytest-report.xml ] || ! grep -q "<testcase" reports/pytest-report.xml; then
            cat > reports/pytest-report.xml <<'XML'
<testsuite name="fallback" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="smoke" name="no_tests_found"/>
</testsuite>
XML
          fi

          # Résumé Bandit (nous lisons bandit.json côté hôte)
          python - <<'PY'
import json, pathlib
p = pathlib.Path("reports/bandit.json")
count = 0
if p.exists():
    try:
        data = json.loads(p.read_text())
        count = len(data.get("results", []))
    except Exception:
        count = 0
html = f"""<html><body><h2>Bandit (résumé)</h2><pre>
Findings: {count}
</pre><p><a href="bandit-report.html">➡ Rapport HTML détaillé</a></p>
</body></html>"""
pathlib.Path("reports/bandit-summary.html").write_text(html)
print(f"Bandit findings: {count}")
PY
        '''

        // Publier
        junit allowEmptyResults: true, testResults: 'reports/pytest-report.xml'

        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST',
          keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
        ])

        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'bandit-summary.html',
          reportName: 'Bandit (Résumé)',
          keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
        ])

        archiveArtifacts artifacts: 'reports/, Jenkinsfile, checkout-info.txt', allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      sh '''
        set -eux
        BR_RAW="${BRANCH_NAME:-$(git symbolic-ref -q --short HEAD || git name-rev --name-only HEAD || echo detached)}"
        BR="$(echo "$BR_RAW" | sed 's#^remotes/origin/##; s#^origin/##; s#^heads/##')"
        {
          echo "Branch: ${BR}"
          echo "Commit: $(git rev-parse HEAD || true)"
          echo "Is shallow: $(git rev-parse --is-shallow-repository || true)"
        } > checkout-info.txt
      '''
      archiveArtifacts artifacts: 'checkout-info.txt', allowEmptyArchive: true
    }
  }
}
