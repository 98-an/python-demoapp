pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  stages {

    // 1) Checkout
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

    // 2) Python: flake8 + pytest (facultatif) + Bandit
    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux

          # Tout s’exécute dans un conteneur Python propre
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -eux

            python -m pip install --upgrade pip

            # 1) Chercher un requirements.txt (var toujours initialisée)
            REQ_FILE=""
            REQ_FILE=$(find . -type f -name requirements.txt \
              -not -path "./.git/*" \
              -not -path "./reports/*" \
              -not -path "./_pycache_/*" \
              -not -path "./.pytest_cache/*" \
              -not -path "./.venv/*" \
              -not -path "./node_modules/*" \
              -not -path "./build/*" \
              -not -path "./ci/*" \
              -print -quit || true)

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
            pytest --maxfail=1 \
              --cov=. \
              --cov-report=xml:/ws/reports/coverage.xml \
              --junitxml=/ws/reports/pytest-report.xml || :

            # 5) Bandit : scanner le code
            mkdir -p /ws/reports
            TARGET="."
            [ -d src ] && TARGET="src"

            # Sorties HTML + TXT + JSON (SARIF non supporté par Bandit 1.x)
            bandit -r "$TARGET" -f html  -o /ws/reports/bandit-report.html || :
            bandit -r "$TARGET" -f txt   -o /ws/reports/bandit.txt        || :
            bandit -r "$TARGET" -f json  -o /ws/reports/bandit.json       || :

            # (Optionnel) aperçu texte dans la console
            bandit -r "$TARGET" -f txt || :
          '

          # 6) Fallback JUnit si pas de tests
          if [ ! -s reports/pytest-report.xml ] || ! grep -q "<testcase" reports/pytest-report.xml; then
            cat > reports/pytest-report.xml <<'XML'
<testsuite name="fallback" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="smoke" name="no_tests_found"/>
</testsuite>
XML
          fi

          # 7) Résumé Bandit basé sur JSON
          COUNT=$(grep -o '"issue_severity"' reports/bandit.json 2>/dev/null | wc -l || echo 0)
          {
            echo "<html><body><h2>Bandit (résumé)</h2><pre>"
            echo "Findings: ${COUNT}"
            echo "</pre><p><a href=\\"bandit-report.html\\">➡ Rapport HTML détaillé</a> • <a href=\\"bandit.json\\">JSON</a></p>"
            echo "</body></html>"
          } > reports/bandit-summary.html
        '''

        // Publications
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

    // 3) Semgrep
    stage('Semgrep SAST') {
      steps {
        sh '''
          set -eux
          mkdir -p reports

          # Règles
          if [ -f security/semgrep-rules.yml ]; then
            CFG="--config security/semgrep-rules.yml"
          else
            CFG="--config p/ci"
          fi

          # Exclusions (bon nom: _pycache_)
          EXCLUDES="--exclude .git --exclude .venv --exclude _pycache_ \
                    --exclude .pytest_cache --exclude node_modules \
                    --exclude build --exclude ci --exclude container \
                    --exclude deploy --exclude infra --exclude monitoring \
                    --exclude reports"

          # JSON + SARIF
          docker run --rm -v "$PWD":/src -w /src semgrep/semgrep:latest \
            semgrep scan $CFG $EXCLUDES --timeout 0 --error \
            --json  --output /src/reports/semgrep.json || true

          docker run --rm -v "$PWD":/src -w /src semgrep/semgrep:latest \
            semgrep scan $CFG $EXCLUDES --timeout 0 --error \
            --sarif --output /src/reports/semgrep.sarif || true

          # Résumé HTML sans Python/JQ sur l’agent
          COUNT=$(grep -o '"check_id"' reports/semgrep.json 2>/dev/null | wc -l || echo 0)
          {
            echo "<html><body><h2>Semgrep (résumé)</h2><pre>"
            echo "Findings: ${COUNT}"
            echo "</pre><p><a href=\\"semgrep.sarif\\">Télécharger SARIF</a> • <a href=\\"semgrep.json\\">JSON</a></p>"
            echo "<p><em>Config:</em> ${CFG}</p>"
            echo "</body></html>"
          } > reports/semgrep-summary.html
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

    // 4) Dockerfile Lint (Hadolint)
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

          # Lister tous les Dockerfile possibles
          mapfile -t DFILES < <(find . -type f -name "Dockerfile*")

          if [ "${#DFILES[@]}" -eq 0 ]; then
            echo "No Dockerfile found, skipping Hadolint."
            exit 0
          fi

          # Scanner chaque fichier
          for f in "${DFILES[@]}"; do
            safe=$(echo "$f" | sed "s#[/ ]#_#g")
            docker run --rm -i hadolint/hadolint hadolint -f json - < "$f" \
              > "reports/hadolint-${safe}.json" || true
            docker run --rm -i hadolint/hadolint hadolint -f tty - < "$f" \
              > "reports/hadolint-${safe}.txt"  || true
          done

          # Résumé global
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
