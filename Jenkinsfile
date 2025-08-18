pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME        = "demoapp:${env.BUILD_NUMBER}"
    S3_BUCKET         = 'cryptonext-reports-98an'
    AWS_REGION        = 'eu-north-1'
    DAST_TARGET       = 'http://16.170.87.165:5000'

    // SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
  }

  stages {

    /* -------------------- 1) CHECKOUT -------------------- */
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        }
        sh 'rm -rf reports && mkdir -p reports'
      }
    }

    /* -------- 2) PYTHON: Lint + Tests + Bandit (+summary) -------- */
    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux
          docker run --rm \
            -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
              set -e
              python -m pip install --upgrade pip
              if   [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt
              elif [ -f requirements.txt ];    then pip install --prefer-binary -r requirements.txt
              fi
              pip install pytest flake8 bandit pytest-cov pyyaml

              # Lint (ne casse pas le build)
              flake8 || :

              # Tests → rapports centralisés dans /ws/reports
              mkdir -p /ws/reports
              pytest --maxfail=1 \
                --cov=. \
                --cov-report=xml:/ws/reports/coverage.xml \
                --junitxml=/ws/reports/pytest-report.xml || :

              # Bandit : HTML + JSON (pour le summary)
              TARGET="src"; [ -d src ] || TARGET="."
              bandit -r "$TARGET" -f html -o /ws/reports/bandit-report.html || :
              bandit -r "$TARGET" -f json -o /ws/reports/bandit.json       || :
            '

          # Fallback XML si aucun test n'existe (pour satisfaire junit)
          test -f reports/pytest-report.xml || echo '<testsuite tests="0"></testsuite>' > reports/pytest-report.xml

          # Summary Bandit fiable via Python (compte les résultats JSON)
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json, pathlib
p = pathlib.Path("reports/bandit.json")
count = 0
if p.exists():
  try:
    data = json.loads(p.read_text() or "{}")
    res  = data.get("results") or []
    count = len(res) if isinstance(res, list) else 0
  except Exception:
    pass
pathlib.Path("reports/bandit-summary.html").write_text(
  f"<html><body><h2>Bandit (résumé)</h2><pre>Findings: {count}</pre>"
  f"<p><a href='bandit-report.html'>Rapport HTML</a> • "
  f"<a href='bandit.json'>JSON</a></p></body></html>"
)
PY
        '''

        junit allowEmptyResults: true, testResults: 'reports/pytest-report.xml'
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-summary.html',
          reportName: 'Bandit (Résumé)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/bandit.*, reports/coverage.xml, reports/pytest-report.xml', allowEmptyArchive: true
      }
    }

    /* -------------------- 3) HADOLINT -------------------- */
    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') || fileExists('build/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF="Dockerfile"
          [ -f "$DF" ] || DF="container/Dockerfile"
          [ -f "$DF" ] || DF="build/Dockerfile"
          mkdir -p reports

          # Rapports TXT + JSON (pour summary)
          docker run --rm -i hadolint/hadolint hadolint -f tty  - < "$DF" > reports/hadolint.txt  || true
          docker run --rm -i hadolint/hadolint hadolint -f json - < "$DF" > reports/hadolint.json || true

          # Summary HTML
          COUNT=$(grep -o '"level"' reports/hadolint.json 2>/dev/null | wc -l || echo 0)
          {
            echo "<html><body><h2>Hadolint (résumé)</h2><pre>"
            echo "Dockerfile: ${DF}"
            echo "Findings: ${COUNT}"
            echo "</pre><p><a href=\\"hadolint.txt\\">TXT</a> • <a href=\\"hadolint.json\\">JSON</a></p></body></html>"
          } > reports/hadolint-summary.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'hadolint-summary.html',
          reportName: 'Hadolint (Résumé)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/hadolint.*', allowEmptyArchive: true
      }
    }

    /* -------------------- 4) GITLEAKS -------------------- */
    stage('Gitleaks (Secrets, repo + historique)') {
      steps {
        sh '''
          set -eux
          docker run --rm \
            -v "$PWD":/repo \
            -v "$PWD/.git":/repo/.git:ro \
            -e GIT_DISCOVERY_ACROSS_FILESYSTEM=1 \
            zricethezav/gitleaks:latest bash -lc "
              set -eux
              git config --global --add safe.directory /repo || :
              gitleaks detect --source /repo --report-format sarif --report-path /repo/reports/gitleaks.sarif || :
            "

          {
            echo '<html><body><h2>Gitleaks (résumé)</h2><pre>'
            if [ -f reports/gitleaks.sarif ]; then
              grep -o '\"ruleId\":' reports/gitleaks.sarif | wc -l | xargs echo "Findings:"
            else
              echo "Findings: 0"
            fi
            echo '</pre><p><a href="gitleaks.sarif">SARIF</a></p></body></html>'
          } > reports/gitleaks.html
        '''
        archiveArtifacts artifacts: 'reports/gitleaks.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'gitleaks.html',
          reportName: 'Gitleaks (Secrets)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* -------------------- 5) SEMGREP -------------------- */
    stage('Semgrep (SAST, avec Git & excludes)') {
      steps {
        sh '''
          set -eux
          docker run --rm \
            -v "$PWD":/src \
            -v "$PWD/.git":/src/.git:ro \
            -e GIT_DISCOVERY_ACROSS_FILESYSTEM=1 \
            returntocorp/semgrep:latest bash -lc "
              set -eux
              git config --global --add safe.directory /src || :
              CFGS='--config p/ci'
              if [ -f /src/security/semgrep-rules.yml ]; then
                CFGS=\\"$CFGS --config /src/security/semgrep-rules.yml\\"
              fi
              semgrep ${CFGS} \
                --sarif --output /src/reports/semgrep.sarif \
                --error --timeout 0 \
                --exclude .git --exclude reports --exclude .pytest_cache --exclude pycache \
                --exclude .venv --exclude node_modules --exclude build --exclude ci \
                --exclude .github --exclude .vscode \
                /src || :
            "

          {
            echo '<html><body><h2>Semgrep (résumé)</h2><pre>'
            if [ -f reports/semgrep.sarif ]; then
              grep -o '\"ruleId\":' reports/semgrep.sarif | wc -l | xargs echo "Findings:"
            else
              echo "Findings: 0"
            fi
            echo '</pre><p><a href="semgrep.sarif">SARIF</a></p></body></html>'
          } > reports/semgrep.html
        '''
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* -------------------- 6) SONARCLOUD -------------------- */
    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL="$SONAR_HOST_URL" \
              -e SONAR_TOKEN="$SONAR_TOKEN" \
              -v "$PWD":/usr/src \
              -v "$PWD/.git":/usr/src/.git:ro \
              sonarsource/sonar-scanner-cli:latest \
                -Dsonar.organization="$SONAR_ORG" \
                -Dsonar.projectKey="$SONAR_PROJECT_KEY" \
                -Dsonar.projectName="$SONAR_PROJECT_KEY" \
                -Dsonar.projectBaseDir=/usr/src \
                -Dsonar.sources="src,app" \
                -Dsonar.tests="tests" \
                -Dsonar.exclusions="/tests/postman_collection.json,/pycache/,/.pytest_cache/" \
                -Dsonar.scm.provider=git \
                -Dsonar.python.version=3.11 \
                -Dsonar.python.coverage.reportPaths=reports/coverage.xml \
                -Dsonar.scanner.skipJreProvisioning=true || :
          '''
        }
      }
    }

    /* -------------------- 7) BUILD IMAGE -------------------- */
    stage('Build Image (si Dockerfile présent)') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') || fileExists('build/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF="Dockerfile"
          [ -f "$DF" ] || DF="container/Dockerfile"
          [ -f "$DF" ] || DF="build/Dockerfile"
          docker build -f "$DF" -t "$IMAGE_NAME" .
          echo "$IMAGE_NAME" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    /* -------------------- 8) TRIVY FS -------------------- */
    stage('Trivy FS (src/)') {
      steps {
        sh '''
          set -eux
          mkdir -p reports
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig \
               --format sarif -o /project/reports/trivy-fs.sarif \
               /project/src || :

          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig -f table /project/src > reports/trivy-fs.txt || :

          { echo '<html><body><h2>Trivy FS</h2><pre>'; cat reports/trivy-fs.txt 2>/dev/null || true; echo '</pre></body></html>'; } \
            > reports/trivy-fs.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif, reports/trivy-fs.txt', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy FS', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* -------------------- 9) TRIVY IMAGE -------------------- */
    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMG=$(cat image.txt)

          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/project aquasec/trivy:latest \
            image --format sarif -o /project/reports/trivy-image.sarif "$IMG" || :

          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image -f table "$IMG" > reports/trivy-image.txt || :

          { echo '<html><body><h2>Trivy Image</h2><pre>'; cat reports/trivy-image.txt 2>/dev/null || true; echo '</pre></body></html>'; } \
            > reports/trivy-image.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-image.sarif, reports/trivy-image.txt', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy Image', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* -------------------- 10) ZAP DAST -------------------- */
    stage('DAST - ZAP Baseline') {
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD/reports:/zap/wrk" ghcr.io/zaproxy/zap2docker-stable \
            zap-baseline.py -t "$DAST_TARGET" -r zap-baseline.html || :
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'zap-baseline.html',
          reportName: 'ZAP Baseline', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* ----------- (Optionnel) Publication S3 des rapports ----------- 
    stage('Publish reports to S3') {
      when { expression { fileExists('reports') } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            if [ -z "$(ls -A reports || true)" ]; then
              echo "Aucun rapport à publier, on saute."
              exit 0
            fi
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"
            docker run --rm \
              -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
              -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
              -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD/reports:/reports" amazon/aws-cli \
              s3 cp /reports "${DEST}" --recursive --sse AES256
            [ -f image.txt ] && docker run --rm \
              -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
              -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
              -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD:/w" amazon/aws-cli s3 cp /w/image.txt "${DEST}" || true
          '''
        }
      }
    }
    */
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/, */.log, */target/.jar', allowEmptyArchive: true
    }
  }
}
