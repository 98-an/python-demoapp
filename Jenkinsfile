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

    stage('Checkout') {
      steps {
        checkout([$class: 'GitSCM',
          branches: [[name: '*/master']],
          extensions: [[$class: 'CloneOption', shallow: true, depth: 1]],
          userRemoteConfigs: [[url: 'https://github.com/98-an/python-demoapp.git', credentialsId: 'git-cred']]
        ])
        sh 'rm -rf "${REPORTS}" && mkdir -p "${REPORTS}"'
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh '''
          set -euxo pipefail
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -euxo pipefail
            python -m pip install --upgrade pip
            if   [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt;
            elif [ -f requirements.txt ];    then pip install --prefer-binary -r requirements.txt; fi
            pip install pytest flake8 bandit pytest-cov

            flake8 || true

            # JUnit -> reports/, coverage à la racine (coverage.xml)
            pytest --maxfail=1 --cov=. --cov-report=xml:coverage.xml \
                   --junitxml=reports/pytest-report.xml || true

            bandit -r . -f html -o reports/bandit-report.html || true
            [ -s reports/bandit-report.html ] || echo "<html><body><h2>Bandit</h2><p>Aucun résultat.</p></body></html>" > reports/bandit-report.html
          '
        '''
        junit allowEmptyResults: true, testResults: 'reports/pytest-report.xml'
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "bandit-report.html", reportName: "Bandit (Python SAST)"])
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { anyOf { fileExists('Dockerfile'); fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -euxo pipefail
          DF=Dockerfile; [ -f Dockerfile ] || DF=container/Dockerfile
          docker pull hadolint/hadolint || true
          docker run --rm -i hadolint/hadolint < "$DF" || true
        '''
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p "${REPORTS}"
          docker pull zricethezav/gitleaks:latest || true
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest detect \
            --no-git -s /repo -f sarif -r /repo/${REPORTS}/gitleaks.sarif || true

          # petit résumé HTML
          ( echo '<html><body><h2>Gitleaks (résumé)</h2><pre>';
            (grep -o '"'"'ruleId'"'"' ${REPORTS}/gitleaks.sarif | wc -l | xargs echo Findings: ) 2>/dev/null || true;
            echo '</pre></body></html>' ) > ${REPORTS}/gitleaks.html
        '''
        archiveArtifacts artifacts: "${REPORTS}/gitleaks.sarif", allowEmptyArchive: true
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "gitleaks.html", reportName: "Gitleaks (Secrets)"])
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p "${REPORTS}"
          docker pull returntocorp/semgrep:latest || true
          docker run --rm -v "$PWD":/src -w /src returntocorp/semgrep:latest semgrep \
            --no-git --config p/ci --sarif --output /src/${REPORTS}/semgrep.sarif \
            --error --timeout 0 || true

          ( echo '<html><body><h2>Semgrep (résumé)</h2><pre>';
            (grep -o '"'"'ruleId'"'"' ${REPORTS}/semgrep.sarif | wc -l | xargs echo Findings: ) 2>/dev/null || true;
            echo '</pre></body></html>' ) > ${REPORTS}/semgrep.html
        '''
        archiveArtifacts artifacts: "${REPORTS}/semgrep.sarif", allowEmptyArchive: true
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "semgrep.html", reportName: "Semgrep (SAST)"])
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -euxo pipefail
            docker pull sonarsource/sonar-scanner-cli:latest || true
            docker run --rm -e SONAR_HOST_URL -e SONAR_TOKEN \
              -v "$PWD":/usr/src sonarsource/sonar-scanner-cli:latest \
              -Dsonar.organization=98-an \
              -Dsonar.projectKey=98-an_python-demoapp \
              -Dsonar.projectName=98-an_python-demoapp \
              -Dsonar.sources=. \
              -Dsonar.scm.disabled=true \
              -Dsonar.python.version=3.11 \
              -Dsonar.python.coverage.reportPaths=coverage.xml \
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
          DF=Dockerfile; [ -f Dockerfile ] || DF=container/Dockerfile
          TAG=$(git rev-parse --short HEAD || echo latest)
          docker build -f "$DF" -t demoapp:${TAG} .
          echo demoapp:${TAG} > image.txt
        '''
        archiveArtifacts 'image.txt'
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p "${REPORTS}"
          docker pull aquasec/trivy:latest || true

          docker run --rm -v "$PWD":/project aquasec/trivy:latest fs \
            --scanners vuln,secret,misconfig --format sarif \
            -o /project/${REPORTS}/trivy-fs.sarif /project || true

          docker run --rm -v "$PWD":/project aquasec/trivy:latest fs \
            --scanners vuln,secret,misconfig -f table /project > ${REPORTS}/trivy-fs.txt || true

          ( echo '<html><body><h2>Trivy FS</h2><pre>'; cat ${REPORTS}/trivy-fs.txt 2>/dev/null || true; echo '</pre></body></html>' ) > ${REPORTS}/trivy-fs.html
        '''
        archiveArtifacts artifacts: "${REPORTS}/trivy-fs.sarif, ${REPORTS}/trivy-fs.txt", allowEmptyArchive: true
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "trivy-fs.html", reportName: "Trivy FS"])
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { return fileExists('image.txt') } }
      steps {
        sh '''
          set -euxo pipefail
          IMG=$(cat image.txt)

          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/project aquasec/trivy:latest image --format sarif \
            -o /project/${REPORTS}/trivy-image.sarif "$IMG" || true

          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image -f table "$IMG" > ${REPORTS}/trivy-image.txt || true

          ( echo '<html><body><h2>Trivy Image</h2><pre>'; cat ${REPORTS}/trivy-image.txt 2>/dev/null || true; echo '</pre></body></html>' ) > ${REPORTS}/trivy-image.html
        '''
        archiveArtifacts artifacts: "${REPORTS}/trivy-image.sarif, ${REPORTS}/trivy-image.txt", allowEmptyArchive: true
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "trivy-image.html", reportName: "Trivy Image"])
      }
    }

    stage('DAST - ZAP Baseline') {
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        sh '''
          set -euxo pipefail
          mkdir -p "${REPORTS}"
          # multiples fallback d’images (DockerHub/weekly puis GHCR)
          docker pull owasp/zap2docker-stable || docker pull owasp/zap2docker-weekly || docker pull ghcr.io/zaproxy/zap2docker-stable || true

          ( docker run --rm -v "$PWD/${REPORTS}":/zap/wrk owasp/zap2docker-stable \
              zap-baseline.py -t "${DAST_TARGET}" -r zap-baseline.html ) || true

          [ -f ${REPORTS}/zap-baseline.html ] || echo "<html><body><p>ZAP non exécuté (pull bloqué ou cible indisponible).</p></body></html>" > ${REPORTS}/zap-baseline.html
        '''
        publishHTML(target: [allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
          reportDir: "${REPORTS}", reportFiles: "zap-baseline.html", reportName: "ZAP Baseline"])
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: "coverage.xml, image.txt, ${REPORTS}/*", allowEmptyArchive: true
      echo "Pour récupérer localement :"
      echo "docker cp jenkins:/var/jenkins_home/workspace/${JOB_NAME}/reports ./reports_from_jenkins && ls -al ./reports_from_jenkins || true"
    }
  }
}
