pipeline {
  agent any
  options { timestamps(); ansiColor('xterm'); skipDefaultCheckout(true) }
  environment {
    IMAGE = "python-demoapp:${BUILD_NUMBER}"
    SCANNER_HOME = tool 'SonarScanner'      // Tools > SonarQube Scanner
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'mkdir -p reports trivy'
      }
    }

    stage('Setup Python') {
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        python3 -m venv .venv
        . .venv/bin/activate
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt || true; fi
        pip install pytest pytest-cov flake8 pip-audit
        '''
      }
    }

    stage('Lint & Tests (+Coverage)') {
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        . .venv/bin/activate
        flake8 . || true
        pytest -q --junitxml=reports/pytest-junit.xml --cov=. --cov-report=xml:reports/coverage.xml || true
        '''
      }
      post { always { junit 'reports/pytest-junit.xml' } }
    }

    stage('SCA - pip-audit') {
      when { expression { return fileExists('requirements.txt') } }
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        . .venv/bin/activate
        pip-audit -r requirements.txt -f json -o reports/pip-audit.json || true
        '''
      }
    }

    stage('OWASP Dependency-Check') {
      when {
        expression { return fileExists('requirements.txt') || fileExists('pom.xml') || fileExists('package.json') }
      }
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        mkdir -p reports/dc
        docker run --rm -u $(id -u):$(id -g) \
          -v "$PWD":/src -v "$PWD/reports/dc":/report \
          owasp/dependency-check:latest \
          --scan /src --format "HTML" --out /report --project "python-demoapp" || true
        '''
      }
    }

    stage('Build Image (Dockerfile)') {
      when { expression { return fileExists('Dockerfile') } }
      steps { sh 'docker build -t "$IMAGE" .' }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { return fileExists('Dockerfile') } }
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        # texte lisible
        docker run --rm -i hadolint/hadolint < Dockerfile | tee reports/hadolint.txt || true
        # json exploitable
        docker run --rm -i hadolint/hadolint hadolint -f json - < Dockerfile > reports/hadolint.json || true
        '''
      }
    }

    stage('Trivy - Image Scan') {
      when { expression { return fileExists('Dockerfile') } }
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
          -v "$PWD/trivy":/trivy aquasec/trivy:latest image \
          --skip-db-update --format table -o /trivy/trivy-image.txt "$IMAGE" || true
        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
          -v "$PWD/trivy":/trivy aquasec/trivy:latest image \
          --skip-db-update --format json -o /trivy/trivy-image.json "$IMAGE" || true
        '''
      }
    }

    stage('DAST - OWASP ZAP Baseline') {
      when { expression { return fileExists('Dockerfile') } }
      steps {
        sh '''#!/usr/bin/env bash
        set -euxo pipefail
        docker network inspect jenkins-net >/dev/null 2>&1 || docker network create jenkins-net
        docker rm -f demoapp || true
        docker run -d --rm --name demoapp --network jenkins-net -p 5000:5000 "$IMAGE"
        for i in $(seq 1 40); do
          if curl -fsS http://localhost:5000 >/dev/null; then break; fi
          sleep 1
        done
        docker run --rm --network jenkins-net -v "$PWD/reports":/zap/wrk:rw \
          owasp/zap2docker-stable zap-baseline.py \
          -t http://demoapp:5000 -r zap-baseline.html -m 5 -I || true
        '''
      }
      post { always { sh 'docker rm -f demoapp || true' } }
    }

    stage('SonarQube Analysis') {
      steps {
        withSonarQubeEnv('sonarqube-local') {   // ou 'sonarcloud' si tu utilises SonarCloud
          sh '''#!/usr/bin/env bash
          set -euxo pipefail
          ${SCANNER_HOME}/bin/sonar-scanner
          '''
        }
      }
    }
  }

  post {
    always {
      publishHTML([
        allowMissing: true, alwaysLinkToLastBuild: true, keepAll: true,
        reportDir: 'reports',
        reportFiles: 'zap-baseline.html,dependency-check-report.html',
        reportName: 'Security Reports'
      ])
      archiveArtifacts artifacts: 'reports/**,trivy/**', fingerprint: true, allowEmptyArchive: true
    }
  }
}
