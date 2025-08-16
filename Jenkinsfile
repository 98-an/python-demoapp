pipeline {
  agent any
  options { timestamps(); ansiColor('xterm') }

  environment {
    IMAGE = "python-demoapp:${BUILD_NUMBER}"
    PIP_CACHE = "${WORKSPACE}/.pip-cache"
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Python Lint, Tests, Bandit, pip-audit') {
      steps {
        sh '''
          mkdir -p ${PIP_CACHE}

          # On exécute tout dans un conteneur Python propre
          docker run --rm \
            -v "$PWD":/workspace -w /workspace \
            -v "${PIP_CACHE}":/root/.cache/pip \
            python:3.11 bash -lc "
              python -m pip install --upgrade pip &&
              if [ -f requirements.txt ]; then pip install -r requirements.txt; fi &&
              pip install pytest pytest-html flake8 bandit pip-audit &&
              echo '--- FLAKE8 ---' &&
              flake8 || true &&
              echo '--- PYTEST ---' &&
              pytest -q --junitxml=pytest-report.xml --html=pytest-report.html --self-contained-html || true &&
              echo '--- BANDIT ---' &&
              bandit -r . -f html -o bandit-report.html || true &&
              echo '--- PIP-AUDIT ---' &&
              if [ -f requirements.txt ]; then pip-audit -r requirements.txt -f json -o pip-audit.json || true; else echo 'no requirements.txt'; fi
            "
        '''
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: '.', reportFiles: 'pytest-report.html', reportName: 'PyTest Report', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        publishHTML(target: [reportDir: '.', reportFiles: 'bandit-report.html', reportName: 'Bandit (Python SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'pip-audit.json', allowEmptyArchive: true, fingerprint: true
      }
    }

    stage('OWASP Dependency-Check (SCA)') {
      steps {
        sh '''
          mkdir -p reports
          docker run --rm \
            -v "$PWD":/src \
            -v "$PWD/reports":/report \
            owasp/dependency-check:latest \
            --scan /src --format HTML --out /report \
            --project "$(basename $PWD)" || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'dependency-check-report.html', reportName: 'OWASP Dependency-Check', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true, fingerprint: true
      }
    }

    stage('Build Docker image') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          docker build -t "${IMAGE}" .
          echo "${IMAGE}" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    stage('Smoke test (HTTP 200)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          IMAGE=$(cat image.txt)
          # Démarre l'app SANS publier de port, puis curl dans son espace réseau
          docker rm -f demoapp >/dev/null 2>&1 || true
          docker run -d --name demoapp "${IMAGE}"
          # Certains repos exposent /health, sinon on teste la page d'accueil
          docker run --rm --network container:demoapp curlimages/curl:8.6.0 -fsS http://localhost:5000/ | head -n 1
          docker rm -f demoapp
        '''
      }
    }

    stage('Trivy (scan image)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          IMAGE=$(cat image.txt)
          mkdir -p trivy
          docker run --rm -v "$PWD/trivy":/root/.cache/ \
            aquasec/trivy:latest image --no-progress --exit-code 0 "${IMAGE}" > trivy/trivy-image.txt || true
        '''
        archiveArtifacts artifacts: 'trivy/**', allowEmptyArchive: true, fingerprint: true
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '**/*.log', allowEmptyArchive: true
    }
  }
}
