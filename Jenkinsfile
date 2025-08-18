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
        checkout([$class: 'GitSCM',
          userRemoteConfigs: [[url: 'https://github.com/98-an/python-demoapp.git', credentialsId: 'git-cred']],
          branches: [[name: '*/master']],
          extensions: [[$class: 'CloneOption', depth: 1, noTags: true, shallow: true]]
        ])
        script {
          sh 'rm -rf reports && mkdir -p reports'
          // commit short sha pour tag d’image
          env.GIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
        }
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
              set -eux
              python -m pip install --upgrade pip
              if   [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt
              elif [ -f requirements.txt ];    then pip install --prefer-binary -r requirements.txt
              fi
              pip install pytest flake8 bandit pytest-cov

              flake8 || true
              pytest --maxfail=1 --cov=. --cov-report=xml:coverage.xml --junitxml=pytest-report.xml || true
              bandit -r . -f html -o reports/bandit-report.html || true
          '
        '''
      }
      post {
        always {
          // S’il n’y a pas de tests, JUnit se plaindra mais ce n’est pas bloquant
          junit allowEmptyResults: true, testResults: 'pytest-report.xml'
          archiveArtifacts artifacts: 'coverage.xml, pytest-report.xml, reports/bandit-report.html', allowEmptyArchive: true
        }
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF=Dockerfile; [ -f "$DF" ] || DF=container/Dockerfile
          docker run --rm -i hadolint/hadolint < "$DF" || true
        '''
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect --no-git -s /repo -f sarif -r /repo/reports/gitleaks.sarif || true

          # mini résumé HTML
          echo "<html><body><h2>Gitleaks (résumé)</h2><pre>Findings: $(grep -o \\"ruleId\\": reports/gitleaks.sarif | wc -l)</pre></body></html>" \
            > reports/gitleaks.html || true
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/gitleaks.*', allowEmptyArchive: true
        }
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/src returntocorp/semgrep:latest \
            semgrep scan --config p/ci --sarif --output /src/reports/semgrep.sarif \
            --no-git --timeout 0 || true

          echo "<html><body><h2>Semgrep (résumé)</h2><pre>Findings: $(grep -o \\"ruleId\\": reports/semgrep.sarif | wc -l)</pre></body></html>" \
            > reports/semgrep.html || true
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/semgrep.*', allowEmptyArchive: true
        }
      }
    }

    stage('SonarCloud') {
      environment {
        SONAR_ORG   = '98-an'
        SONAR_KEY   = '98-an_python-demoapp'
      }
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL=https://sonarcloud.io \
              -e SONAR_TOKEN="$SONAR_TOKEN" \
              -v "$PWD":/usr/src sonarsource/sonar-scanner-cli:latest \
              -Dsonar.organization='${SONAR_ORG}' \
              -Dsonar.projectKey='${SONAR_KEY}' \
              -Dsonar.projectName='${SONAR_KEY}' \
              -Dsonar.sources=. \
              -Dsonar.python.version=3.11 \
              -Dsonar.python.coverage.reportPaths=coverage.xml \
              -Dsonar.scm.disabled=true \
              -Dsonar.scanner.skipJreProvisioning=true || true
          '''
        }
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF=Dockerfile; [ -f "$DF" ] || DF=container/Dockerfile
          TAG="demoapp:${GIT_SHORT}"
          docker build -f "$DF" -t "$TAG" .
          echo "$TAG" > image.txt
          echo "$TAG"
        '''
        archiveArtifacts artifacts: 'image.txt', allowEmptyArchive: false
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig --format sarif -o /project/reports/trivy-fs.sarif /project || true
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,misconfig -f table /project > reports/trivy-fs.txt || true

          printf '<html><body><h2>Trivy FS</h2><pre>\n' > reports/trivy-fs.html
          cat reports/trivy-fs.txt >> reports/trivy-fs.html || true
          printf '\n</pre></body></html>\n' >> reports/trivy-fs.html
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/trivy-fs.*', allowEmptyArchive: true
        }
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMG="$(cat image.txt)"
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD":/project aquasec/trivy:latest \
            image --format sarif -o /project/reports/trivy-image.sarif "$IMG" || true
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
            image -f table "$IMG" > reports/trivy-image.txt || true

          printf '<html><body><h2>Trivy Image</h2><pre>\n' > reports/trivy-image.html
          cat reports/trivy-image.txt >> reports/trivy-image.html || true
          printf '\n</pre></body></html>\n' >> reports/trivy-image.html
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/trivy-image.*', allowEmptyArchive: true
        }
      }
    }

    stage('DAST - ZAP Baseline') {
      steps {
        sh '''
          set -eux
          # Remplace l’URL cible par celle de ton app si besoin
          TARGET="http://13.62.105.249:5000"
          docker run --rm -v "$PWD/reports":/zap/wrk ghcr.io/zaproxy/zaproxy:stable \
            zap-baseline.py -t "$TARGET" -r zap-baseline.html || true
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: 'reports/zap-baseline.html', allowEmptyArchive: true
        }
      }
    }

    stage('Publish Reports (HTML)') {
      steps {
        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'bandit-report.html, gitleaks.html, semgrep.html, trivy-fs.html, trivy-image.html, zap-baseline.html',
          reportName: 'Security Reports',
          keepAll: true,
          alwaysLinkToLastBuild: true,
          allowMissing: true
        ])
      }
    }
  }

  post {
    always {
      // Copie “interne” (facultatif) pour retrouver facilement les rapports d’un build
      sh '''
        mkdir -p reports/by-build/${BUILD_NUMBER}
        cp -f reports/* reports/by-build/${BUILD_NUMBER}/ || true
        ls -al reports || true
      '''
    }
  }
}
