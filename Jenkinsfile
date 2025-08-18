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

    // S3
    S3_BUCKET         = 'cryptonext-reports-98an'
    AWS_REGION        = 'eu-north-1'

    // ZAP DAST (modifie l’URL si besoin)
    DAST_TARGET       = 'http://13.62.105.249:5000'

    // SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        script { env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim() }
        sh 'rm -rf reports && mkdir -p reports'
      }
    }

    stage('Java Build & Tests') {
      when { expression { fileExists('pom.xml') } }
      steps {
        sh '''
          docker run --rm -v "$PWD":/ws -w /ws \
            maven:3.9-eclipse-temurin-17 mvn -B -DskipTests=false clean test
        '''
        junit '/target/surefire-reports/*.xml'
      }
    }

    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
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
            # tests + coverage (pour Sonar)
            pytest --maxfail=1 --cov=. --cov-report=xml:coverage.xml --junitxml=pytest-report.xml || true

            # rapport HTML Bandit
            bandit -r . -f html -o reports/bandit-report.html || true
          '
        '''
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
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
          # SARIF
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect -s /repo -f sarif -r /repo/reports/gitleaks.sarif || true

          # Résumé HTML simple
          {
            echo '<html><body><h2>Gitleaks (résumé)</h2><pre>'
            grep -o '"ruleId":' reports/gitleaks.sarif | wc -l | xargs echo "Findings:" || true
            echo '</pre></body></html>'
          } > reports/gitleaks.html
        '''
        archiveArtifacts artifacts: 'reports/gitleaks.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'gitleaks.html',
          reportName: 'Gitleaks (Secrets)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/src returntocorp/semgrep:latest \
            semgrep --config p/ci --sarif --output /src/reports/semgrep.sarif --error --timeout 0 || true

          {
            echo '<html><body><h2>Semgrep (résumé)</h2><pre>'
            grep -o '"ruleId":' reports/semgrep.sarif | wc -l | xargs echo "Findings:" || true
            echo '</pre></body></html>'
          } > reports/semgrep.html
        '''
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL="$SONAR_HOST_URL" \
              -e SONAR_TOKEN="$SONAR_TOKEN" \
              -v "$PWD":/usr/src \
              sonarsource/sonar-scanner-cli:latest \
                -Dsonar.organization="$SONAR_ORG" \
                -Dsonar.projectKey="$SONAR_PROJECT_KEY" \
                -Dsonar.projectName="$SONAR_PROJECT_KEY" \
                -Dsonar.sources="." \
                -Dsonar.scm.provider=git \
                -Dsonar.python.version=3.11 \
                -Dsonar.python.coverage.reportPaths=coverage.xml \
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
          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,config --format sarif -o /project/reports/trivy-fs.sarif /project || true

          docker run --rm -v "$PWD":/project aquasec/trivy:latest \
            fs --scanners vuln,secret,config -f table /project > reports/trivy-fs.txt || true
          { echo '<html><body><h2>Trivy FS</h2><pre>'; cat reports/trivy-fs.txt; echo '</pre></body></html>'; } \
            > reports/trivy-fs.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif, reports/trivy-fs.txt', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy FS', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMG=$(cat image.txt)

          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/project aquasec/trivy:latest \
            image --format sarif -o /project/reports/trivy-image.sarif "$IMG" || true

          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image -f table "$IMG" > reports/trivy-image.txt || true

          { echo '<html><body><h2>Trivy Image</h2><pre>'; cat reports/trivy-image.txt; echo '</pre></body></html>'; } \
            > reports/trivy-image.html
        '''
        archiveArtifacts artifacts: 'reports/trivy-image.sarif, reports/trivy-image.txt', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy Image', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('DAST - ZAP Baseline') {
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD/reports:/zap/wrk" owasp/zap2docker-stable \
            zap-baseline.py -t "$DAST_TARGET" -r zap-baseline.html || true
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

    stage('List uploaded S3 files') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"
            docker run --rm \
              -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
              -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
              -e AWS_DEFAULT_REGION="${AWS_REGION}" \
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
                url=$(docker run --rm \
                  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
                  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
                  -e AWS_DEFAULT_REGION="${AWS_REGION}" \
                  amazon/aws-cli s3 presign "s3://${S3_BUCKET}/${key}" --expires-in 3600)
                echo "${key} -> ${url}" | tee -a presigned-urls.txt
              done
            fi
          '''
        }
        archiveArtifacts artifacts: 'presigned-urls.txt,image.txt', allowEmptyArchive: true
      }
    }

    stage('Deploy Monitoring (Prometheus/Grafana/cAdvisor)') {
      when { expression { fileExists('monitoring/docker-compose.yml') } }
      steps {
        sh '''
          set -eux
          cd monitoring

          # Utilisation de Docker Compose en conteneur (fallback stable v1)
          COMPOSE_IMG=docker/compose:1.29.2

          # Validation du fichier
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/work -w /work \
            -e COMPOSE_PROJECT_NAME=monitoring \
            $COMPOSE_IMG config -q

          # Démarrage
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/work -w /work \
            -e COMPOSE_PROJECT_NAME=monitoring \
            $COMPOSE_IMG up -d --remove-orphans

          # Etat
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/work -w /work \
            -e COMPOSE_PROJECT_NAME=monitoring \
            $COMPOSE_IMG ps
        '''
      }
    }

  } // stages

  post {
    always {
      archiveArtifacts artifacts: 'reports/, /target/.jar, /.log', allowEmptyArchive: true
    }
  }
}
