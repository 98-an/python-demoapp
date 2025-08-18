pipeline {
  agent any
  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME  = "demoapp:${env.BUILD_NUMBER}"
    DAST_TARGET = 'http://16.170.87.165:5000'     // adapte à l’URL de ton app
    AWS_REGION  = 'eu-north-1'
    S3_BUCKET   = 'cryptonext-reports-98an'

    // SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh 'mkdir -p reports'
        script { env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim() }
      }
    }

    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('requirements.txt') || fileExists('src/requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -eux
            python -m pip install --upgrade pip
            if   [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt
            elif [ -f requirements.txt ];    then pip install --prefer-binary -r requirements.txt
            fi
            pip install flake8 pytest pytest-cov bandit
            flake8 || true
            pytest --maxfail=1 --junitxml=/ws/pytest-report.xml --cov=. --cov-report=xml:/ws/coverage.xml || true
            bandit -r . -f html -o /ws/reports/bandit-report.html || true
          '
        '''
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit (Python SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF="Dockerfile"; [ -f "$DF" ] || DF="container/Dockerfile"
          docker run --rm -i hadolint/hadolint < "$DF" || true
        '''
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -e GIT_DISCOVERY_ACROSS_FILESYSTEM=1 \
            -v "$PWD":/repo -w /repo zricethezav/gitleaks:latest \
            detect -f sarif -r /repo/reports/gitleaks.sarif || true
          # petit résumé HTML simple
          echo "<h2>Gitleaks (résumé)</h2><p>Voir gitleaks.sarif pour le détail.</p>" > reports/gitleaks.html
        '''
        archiveArtifacts artifacts: 'reports/gitleaks.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'gitleaks.html',
          reportName: 'Gitleaks (résumé)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/src -w /src returntocorp/semgrep:latest \
            semgrep scan --config p/ci --sarif --output reports/semgrep.sarif --error --timeout 0 || true
          echo "<h2>Semgrep (résumé)</h2><p>Voir semgrep.sarif pour le détail.</p>" > reports/semgrep.html
        '''
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (résumé)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            # IMPORTANT : monter .git et fixer le workdir
            docker run --rm \
              -e SONAR_HOST_URL="$SONAR_HOST_URL" \
              -e SONAR_TOKEN="$SONAR_TOKEN" \
              -v "$PWD":/usr/src \
              -v "$PWD/.git":/usr/src/.git \
              -w /usr/src \
              sonarsource/sonar-scanner-cli:latest \
              -Dsonar.organization="${SONAR_ORG}" \
              -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
              -Dsonar.projectName="${SONAR_PROJECT_KEY}" \
              -Dsonar.projectVersion="${BUILD_NUMBER}" \
              -Dsonar.sources=. \
              -Dsonar.scm.provider=git \
              -Dsonar.python.version=3.11 \
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
          DF="Dockerfile"; [ -f "$DF" ] || DF="container/Dockerfile"
          docker build -f "$DF" -t "$IMAGE_NAME" .
          echo "$IMAGE_NAME" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/project -w /project aquasecurity/trivy:latest \
            fs --scanners vuln,secret,misconfig --format sarif -o /project/reports/trivy-fs.sarif /project || true
          # joli HTML avec le template intégré
          docker run --rm -v "$PWD":/project -w /project aquasecurity/trivy:latest \
            fs --scanners vuln,secret,misconfig --format template --template "@/contrib/html.tpl" \
            -o /project/reports/trivy-fs.html /project || true
        '''
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy FS', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMAGE=$(cat image.txt)
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasecurity/trivy:latest \
            image --format sarif -o /tmp/trivy-image.sarif "$IMAGE" || true
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD/reports":/out aquasecurity/trivy:latest \
            image --format template --template "@/contrib/html.tpl" -o /out/trivy-image.html "$IMAGE" || true
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD/reports":/out alpine:3.19 \
            sh -lc 'cp /tmp/trivy-image.sarif /out/trivy-image.sarif || true' || true
        '''
        archiveArtifacts artifacts: 'reports/trivy-image.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy Image', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('DAST - ZAP Baseline') {
      steps {
        sh '''
          set -eux
          mkdir -p reports
          # essayer d'abord le repo zaproxy, sinon l'ancien owasp
          docker pull zaproxy/zap2docker-stable || docker pull owasp/zap2docker-stable || true
          ( docker run --rm -v "$PWD/reports":/zap/wrk zaproxy/zap2docker-stable \
              zap-baseline.py -t "$DAST_TARGET" -r zap-baseline.html -z "-config api.disablekey=true" \
            || docker run --rm -v "$PWD/reports":/zap/wrk owasp/zap2docker-stable \
              zap-baseline.py -t "$DAST_TARGET" -r zap-baseline.html -z "-config api.disablekey=true" ) || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'zap-baseline.html',
          reportName: 'ZAP Baseline', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Publish reports to S3') {
      when { expression { fileExists('reports') } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"
            docker run --rm \
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD/reports:/reports" amazon/aws-cli s3 cp /reports "${DEST}" --recursive --sse AES256 || true
            [ -f image.txt ] && docker run --rm \
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD:/w" amazon/aws-cli s3 cp /w/image.txt "${DEST}" || true
          '''
        }
      }
    }

    stage('List uploaded S3 files') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"
            docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              amazon/aws-cli s3 ls "$DEST" --recursive || true
          '''
        }
      }
    }

    stage('Make presigned URLs (1h)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            : > presigned-urls.txt
            if [ -d reports ] && [ -n "$(ls -A reports || true)" ]; then
              PREFIX="${JOB_NAME}/${BUILD_NUMBER}"
              for f in reports/*; do
                key="${PREFIX}/$(basename "$f")"
                url=$(docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
                  amazon/aws-cli s3 presign "s3://${S3_BUCKET}/${key}" --expires-in 3600)
                echo "${key} -> ${url}" | tee -a presigned-urls.txt
              done
            fi
          '''
        }
        archiveArtifacts artifacts: 'presigned-urls.txt,image.txt', allowEmptyArchive: true
      }
    }

  } // stages

  post {
    always {
      archiveArtifacts artifacts: '/*.log', allowEmptyArchive: true
    }
  }
}
