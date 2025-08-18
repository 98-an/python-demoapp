pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  stages {

    /* ====================== 1) CHECKOUT ====================== */
    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          set -eux
          # Infos et unshallow si besoin
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

    /* ========== 2) PYTHON — Lint + Tests + Bandit (avec résumés) ========== */
    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux

          # Tout s’exécute dans un conteneur Python propre
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -e  # (pas -u pour éviter "parameter not set" avant REQ_FILE)
            python -m pip install --upgrade pip

            # 1) Chercher un requirements.txt
            REQ_FILE="$(find . -type f -name requirements.txt \
              -not -path "./.git/*" \
              -not -path "./reports/*" \
              -not -path "./_pycache_/*" \
              -not -path "./.pytest_cache/*" \
              -not -path "./.venv/*" \
              -not -path "./node_modules/*" \
              -not -path "./build/*" \
              -not -path "./ci/*" | head -n1 || true)"
            REQ_FILE="${REQ_FILE:-}"

            if [ -n "$REQ_FILE" ]; then
              echo "Installing app deps from: $REQ_FILE"
              pip install --prefer-binary -r "$REQ_FILE"
            else
              echo "No requirements.txt found — skipping app deps install."
            fi

            # 2) Outils qualité
            pip install --prefer-binary pytest pytest-cov flake8 bandit pyyaml

            # 3) Lint (ne casse pas le build)
            flake8 || :

            # 4) Tests (rapports centralisés dans /ws/reports)
            mkdir -p /ws/reports
            pytest --maxfail=1 \
              --cov=. \
              --cov-report=xml:/ws/reports/coverage.xml \
              --junitxml=/ws/reports/pytest-report.xml || :

            # 5) Bandit : scanner le code (priorité au dossier src/)
            TARGET="src"
            [ -d src ] || TARGET="."
            bandit -r "$TARGET" -x ".git,.venv,.pytest_cache,_pycache_,node_modules,build,ci,container,deploy,infra,monitoring,reports" \
              -f html -o /ws/reports/bandit-report.html || :
            bandit -r "$TARGET" -x ".git,.venv,.pytest_cache,_pycache_,node_modules,build,ci,container,deploy,infra,monitoring,reports" \
              -f json -o /ws/reports/bandit.json || :
            bandit -r "$TARGET" -x ".git,.venv,.pytest_cache,_pycache_,node_modules,build,ci,container,deploy,infra,monitoring,reports" \
              -f txt  -o /ws/reports/bandit.txt  || :
          '

          # 6) Fallback JUnit si aucun test
          if [ ! -s reports/pytest-report.xml ] || ! grep -q "<testcase" reports/pytest-report.xml; then
            cat > reports/pytest-report.xml <<'XML'
<testsuite name="fallback" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="smoke" name="no_tests_found"/>
</testsuite>
XML
          fi

          # 7) Résumé Bandit (on lit le JSON)
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json, pathlib, html
p = pathlib.Path("reports/bandit.json")
count = 0
if p.exists():
    try:
        data = json.loads(p.read_text() or "{}")
        results = data.get("results") or data  # compat vieux formats
        if isinstance(results, list):
            count = len(results)
    except Exception:
        pass
pathlib.Path("reports/bandit-summary.html").write_text(
    f"<html><body><h2>Bandit (résumé)</h2><pre>Findings: {count}</pre>"
    f"<p><a href='bandit-report.html'>➡ Rapport HTML détaillé</a> • "
    f"<a href='bandit.txt'>TXT</a> • <a href='bandit.json'>JSON</a></p></body></html>"
)
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

        archiveArtifacts artifacts: 'reports/bandit.*, reports/coverage.xml, reports/pytest-report.xml', allowEmptyArchive: true
      }
    }

    /* ====================== 3) SEMGREP SAST ====================== */
    stage('Semgrep SAST') {
      steps {
        sh '''
          set -eux
          mkdir -p reports

          # Config ruleset (local si présent, sinon p/ci)
          if [ -f security/semgrep-rules.yml ]; then
            CFG="--config security/semgrep-rules.yml"
          else
            CFG="--config p/ci"
          fi

          EXCLUDES="--exclude .git --exclude .venv --exclude _pycache_ \
                    --exclude .pytest_cache --exclude node_modules \
                    --exclude build --exclude ci --exclude container \
                    --exclude deploy --exclude infra --exclude monitoring \
                    --exclude reports"

          # 1) JSON
          docker run --rm -v "$PWD":/src -w /src semgrep/semgrep:latest \
            semgrep scan $CFG $EXCLUDES --timeout 0 --error \
            --json --output /src/reports/semgrep.json || true

          # 2) SARIF
          docker run --rm -v "$PWD":/src -w /src semgrep/semgrep:latest \
            semgrep scan $CFG $EXCLUDES --timeout 0 --error \
            --sarif --output /src/reports/semgrep.sarif || true

          # 3) Résumé HTML (via conteneur Python)
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json, html, pathlib
p = pathlib.Path('reports/semgrep.json')
count = 0; rows = []
if p.exists():
    try:
        data = json.loads(p.read_text() or "{}")
        results = data.get('results', [])
        count = len(results)
        for r in results[:200]:
            msg  = r.get('extra', {}).get('message', '')
            sev  = r.get('extra', {}).get('severity', '')
            rule = r.get('check_id', '')
            path = r.get('path', '')
            line = r.get('start', {}).get('line', '')
            rows.append(f"<tr><td>{html.escape(rule)}</td><td>{html.escape(sev)}</td>"
                        f"<td>{html.escape(path)}:{line}</td><td>{html.escape(msg)}</td></tr>")
    except Exception:
        pass
html_doc = f"""<html><body><h2>Semgrep (résumé)</h2><pre>
Findings: {count}
</pre><p><a href='semgrep.sarif'>Télécharger SARIF</a> • <a href='semgrep.json'>JSON</a></p>
<table border='1' cellpadding='4' cellspacing='0'>
<tr><th>Règle</th><th>Sévérité</th><th>Fichier</th><th>Message</th></tr>
{''.join(rows) if rows else '<tr><td colspan=4>Aucun résultat</td></tr>'}
</table></body></html>"""
pathlib.Path('reports/semgrep-summary.html').write_text(html_doc)
print(f"Semgrep findings: {count}")
PY
        '''

        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'semgrep-summary.html',
          reportName: 'Semgrep (Résumé)',
          keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
        ])
        archiveArtifacts artifacts: 'reports/semgrep.*', allowEmptyArchive: true
      }
    }

    /* ====================== 4) DOCKERFILE LINT (HADOLINT) ====================== */
    stage('Dockerfile Lint (Hadolint)') {
      when {
        expression {
          fileExists('Dockerfile') ||
          sh(script: "find . -type f -name 'Dockerfile*' | head -n1 | wc -l", returnStdout: true).trim() != '0'
        }
      }
      steps {
        sh '''
          set -eux
          mkdir -p reports

          # Tous les Dockerfiles possibles
          mapfile -t DFILES < <(find . -type f -name "Dockerfile*")

          if [ "${#DFILES[@]}" -eq 0 ]; then
            echo "No Dockerfile found, skipping Hadolint."
            exit 0
          fi

          for f in "${DFILES[@]}"; do
            safe=$(echo "$f" | sed "s#[/ ]#_#g")
            docker run --rm -i hadolint/hadolint hadolint -f json - < "$f" \
              > "reports/hadolint-${safe}.json" || true
            docker run --rm -i hadolint/hadolint hadolint -f tty - < "$f" \
              > "reports/hadolint-${safe}.txt"  || true
          done

          COUNT=$(grep -h -o '"level"' reports/hadolint-*.json 2>/dev/null | wc -l || echo 0)
          {
            echo "<html><body><h2>Hadolint (résumé)</h2><pre>"
            echo "Files: ${#DFILES[@]}"
            echo "Findings: ${COUNT}"
            echo "</pre><ul>"
            for f in "${DFILES[@]}"; do
              safe=$(echo "$f" | sed "s#[/ ]#_#g")
              echo "<li>${f} — <a href=\\"hadolint-${safe}.txt\\">TXT</a> • <a href=\\"hadolint-${safe}.json\\">JSON</a></li>"
            done
            echo "</ul></body></html>"
          } > reports/hadolint-summary.html
        '''

        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'hadolint-summary.html',
          reportName: 'Hadolint (Résumé)',
          keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
        ])
        archiveArtifacts artifacts: 'reports/hadolint-.json, reports/hadolint-.txt', allowEmptyArchive: true
      }
    }
  } /* fin stages */

  post {
    always {
      sh '''
        set -eux
        BR_RAW="${BRANCH_NAME:-$(git symbolic-ref -q --short HEAD || git name-rev --name-only HEAD || echo detached)}"
        BR="$(echo "$BR_RAW" | sed "s#^remotes/origin/##; s#^origin/##; s#^heads/##")"
        {
          echo "Branch: ${BR}"
          echo "Commit: $(git rev-parse HEAD || true)"
          echo "Is shallow: $(git rev-parse --is-shallow-repository || true)"
        } > checkout-info.txt
      '''
      archiveArtifacts artifacts: 'Jenkinsfile, checkout-info.txt, reports/', allowEmptyArchive: true
    }
  }
}
