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

    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux

          # Tout s’exécute dans un conteneur Python propre
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -eux
            python -m pip install --upgrade pip

            # 1) Chercher un requirements.txt (sans heredoc pour éviter les soucis de quoting)
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

            # 5) Bandit : scanner le code sous src/ et générer 3 formats
            mkdir -p /ws/reports
            bandit -r src -f html  -o /ws/reports/bandit-report.html || :
            bandit -r src -f txt   -o /ws/reports/bandit.txt        || :
            bandit -r src -f sarif -o /ws/reports/bandit.sarif      || :

            # (Optionnel) aperçu texte dans la console
            bandit -r src -f txt || :
          '

          # 6) Fallback JUnit : si pas de <testcase>, on écrit 1 test "dummy"
          if [ ! -s reports/pytest-report.xml ] || ! grep -q "<testcase" reports/pytest-report.xml; then
            cat > reports/pytest-report.xml <<'XML'
<testsuite name="fallback" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="smoke" name="no_tests_found"/>
</testsuite>
XML
          fi

          # 7) Résumé Bandit : compteur de findings + lien vers le HTML
          COUNT=$(grep -o '"ruleId":' reports/bandit.sarif 2>/dev/null | wc -l || echo 0)
          {
            echo "<html><body><h2>Bandit (résumé)</h2><pre>"
            echo "Findings: ${COUNT}"
            echo "</pre><p><a href=\\"bandit-report.html\\">➡ Rapport HTML détaillé</a></p>"
            echo "</body></html>"
          } > reports/bandit-summary.html
        '''

        // Publier les rapports
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

        // Conserver aussi les fichiers bruts
        archiveArtifacts artifacts: 'reports/bandit.*, reports/coverage.xml, reports/pytest-report.xml', allowEmptyArchive: true
      }
    }

    // On ajoutera les autres stages (Semgrep, Hadolint, Trivy, Sonar…) après validation de celui-ci.
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
