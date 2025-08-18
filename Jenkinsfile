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
    DAST_TARGET       = 'http://16.170.87.165/:5000'

    // SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          set -euxo pipefail
          rm -rf reports
          mkdir -p reports
        '''
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh '''
          set -euxo pipefail
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -euxo pipefail
            python -m pip install --upgrade pip
            if   [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt
            elif [ -f requirements.txt ];    then pip install --prefer-binary -r requirements.txt
            fi
            pip install pytest flake8 bandit pytest-cov

            # Lint
            flake8 || true

            # Tests + coverage -> dans reports/
            pytest --maxfail=1 --cov=. \
                   --cov-report=xml:coverage.xml \
                   --junitxml=reports/pytest-report.xml || true

            # SAST Python
            bandit -r . -f html -o reports/bandit-report.html || true
          '
          ls -al reports || true
        '''
        junit allowEmptyResults: true, testResults: 'reports/pytest-report.xml'
        publishHTML target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
        archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { anyOf { fileExists('Dockerfile'); fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -euxo pipefail
          DF=Dockerfile; [ -f "$DF" ] || DF=container/Dockerfile
          docker run --rm -i hadolint/hadolint < "$DF" | tee reports/hadolint.txt || true
          printf '<html><body><h2>Hadolint</h2><pre>%s</pre></body></html>\n' \
            "$(sed 's/&/&amp;/g;s/</\\&lt;/g;s/>/\\&gt;/g' reports/hadolint.txt)" > reports/hadolint.html
        '''
        publishHTML target: [reportDir: 'reports', reportFiles: 'hadolint.html',
          reportName: 'Hadolint (Dockerfile)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -euxo pipefail
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect -s /repo --no-git -f sarif -r /repo/reports/gitleaks.sarif || true
          python3 - << "PY"
import json, os, html
p="reports/gitleaks.sarif"; n=0
if os.path.exists(p) and os.path.getsize(p)>0:
    try:
        j=json.load(open(p,encoding="utf-8"))
        n=sum(len(run.get("results",[])) for run in j.get("runs",[]))
    except Exception: n=0
open("reports/gitleaks.html","w",encoding="utf-8").write(f"<html><body><h2>Gitleaks</h2><p>Findings: {n}</p></body></html>")
PY
          ls -al reports || true
        '''
        archiveArtifacts artifacts: 'reports/gitleaks.sarif', allowEmptyArchive: true
        publishHTML target: [reportDir: 'reports', reportFiles: 'gitleaks.html',
          reportName: 'Gitleaks (Secrets)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -euxo pipefail
          docker run --rm -v "$PWD":/src -w /src returntocorp/semgrep:latest \
            semgrep --config p/ci --sarif --output /src/reports/semgrep.sarif \
                    --no-git --timeout 0 || true
          python3 - << "PY"
import json, os
p="reports/semgrep.sarif"; n=0
if os.path.exists(p) and os.path.getsize(p)>0:
    try:
        j=json.load(open(p,encoding="utf-8"))
        n=sum(len(run.get("results",[])) for run in j.get("runs",[]))
    except Exception: n=0
open("reports/semgrep.html","w",encoding="utf-8").write(f"<html><body><h2>Semgrep</h2><p>Findings: {n}</p></body></html>")
PY
        '''
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
        publishHTML target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -euxo pipefail
            docker run --rm \
              -e SONAR_HOST_URL=https://sonarcloud.io \
              -e SONAR_TOKEN="$SONAR_TOKEN" \
              -v "$PWD":/usr/src \
              -v "$PWD/.git":/usr/src/.git:ro \
              sonarsource/sonar-scanner-cli:latest \
              -Dsonar.organization=98-an \
              -Dsonar.projectKey=98-an_python-demoapp \
              -Dsonar.projectName=98-an_python-demoapp \
              -Dsonar.sources=. \
              -Dsonar.python.version=3.11 \
              -Dsonar.python.coverage.reportPaths=coverage.xml \
              -Dsonar.scm.provider=git \
              -Dsonar.scanner.skipJreProvisioning=true || true
          '''
        }
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { anyOf { fileExists('Dockerfile'); fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -euxo pipefail
          DF=Dockerfile; [ -f "$DF" ] || DF=container/Dockerfile
          TAG="demoapp:${BUILD_NUMBER}"
          docker build -f "$DF" -t "$TAG" .
          echo "$TAG" | tee image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', onlyIfSuccessful: true
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh '''
          set -euxo pipefail
          # SARIF
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig --format sarif \
            -o /project/reports/trivy-fs.sarif /project || true
          # Tableau lisible
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig -f table /project \
            | tee reports/trivy-fs.txt || true
          printf '<html><body><h2>Trivy FS</h2><pre>%s</pre></body></html>\n' \
            "$(sed 's/&/&amp;/g;s/</\\&lt;/g;s/>/\\&gt;/g' reports/trivy-fs.txt)" > reports/trivy-fs.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif', allowEmptyArchive: true
        publishHTML target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy FS', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { return fileExists('image.txt') } }
      steps {
        sh '''
          set -euxo pipefail
          IMG="$(cat image.txt)"
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/project aquasec/trivy:latest \
            image --format sarif -o /project/reports/trivy-image.sarif "$IMG" || true
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image -f table "$IMG" \
            | tee reports/trivy-image.txt || true
          printf '<html><body><h2>Trivy Image</h2><pre>%s</pre></body></html>\n' \
            "$(sed 's/&/&amp;/g;s/</\\&lt;/g;s/>/\\&gt;/g' reports/trivy-image.txt)" > reports/trivy-image.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-image.sarif', allowEmptyArchive: true
        publishHTML target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy Image', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }

    stage('DAST - ZAP Baseline') {
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p reports
          IMG=owasp/zap2docker-stable
          docker pull "$IMG" || IMG=owasp/zap2docker-weekly
          docker pull "$IMG" || IMG=ghcr.io/zaproxy/zap2docker-stable
          docker run --rm -v "$PWD/reports:/zap/wrk" "$IMG" \
            zap-baseline.py -t "${DAST_TARGET}" -r zap-baseline.html || true
          ls -al reports || true
        '''
        publishHTML target: [reportDir: 'reports', reportFiles: 'zap-baseline.html',
          reportName: 'ZAP Baseline', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]
      }
    }
  } // stages

  post {
    always {
      archiveArtifacts artifacts: 'reports/, coverage.xml, image.txt, */.log', allowEmptyArchive: true
    }
  }
}
