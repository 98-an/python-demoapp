pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME   = "demoapp:${env.BUILD_NUMBER}"

    // ---- SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'                   // <= clé exacte d’org
    SONAR_PROJECT_KEY = '98-an_python-demoapp'    // <= clé exacte du projet (désactive l’Automatic Analysis côté SC)

    // ---- Trivy
    TRIVY_VER   = '0.50.2'

    // ---- DAST
    DAST_TARGET = 'http://13.62.105.249:5000'     // adapte si besoin

    // ---- S3
    S3_BUCKET   = 'cryptonext-reports-98an'
    AWS_REGION  = 'eu-north-1'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        script { env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim() }
        sh 'rm -rf reports && mkdir -p reports && echo "commit=${GIT_COMMIT}" > reports/build-info.txt || true'
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
            pip install pytest flake8 bandit
            flake8 || true
            pytest --maxfail=1 --junitxml=/ws/pytest-report.xml || true
            bandit -r . -f html -o /ws/reports/bandit-report.html || true
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
          docker run --rm -i hadolint/hadolint < "$DF" | tee reports/hadolint.txt || true
          {
            echo '<html><body><h2>Hadolint</h2><pre>';
            sed -e 's/&/\\&amp;/g' -e 's/</\\&lt;/g' reports/hadolint.txt || true;
            echo '</pre></body></html>';
          } > reports/hadolint.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'hadolint.html',
          reportName: 'Hadolint (Dockerfile)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect --no-git -s /repo -f sarif -r /repo/reports/gitleaks.sarif || true
          {
            echo '<html><body><h2>Gitleaks SARIF</h2><pre>';
            sed -e 's/&/\\&amp;/g' -e 's/</\\&lt;/g' reports/gitleaks.sarif || true;
            echo '</pre></body></html>';
          } > reports/gitleaks.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'gitleaks.html',
          reportName: 'Gitleaks (Secrets)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/gitleaks.sarif', allowEmptyArchive: true
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/src returntocorp/semgrep:latest \
            semgrep --config p/ci --sarif --output /src/reports/semgrep.sarif --timeout 0 || true
          {
            echo '<html><body><h2>Semgrep SARIF</h2><pre>';
            sed -e 's/&/\\&amp;/g' -e 's/</\\&lt;/g' reports/semgrep.sarif || true;
            echo '</pre></body></html>';
          } > reports/semgrep.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL="${SONAR_HOST_URL}" \
              -e SONAR_LOGIN="${SONAR_TOKEN}" \
              -v "$PWD":/usr/src \
              sonarsource/sonar-scanner-cli:latest \
                -Dsonar.organization="${SONAR_ORG}" \
                -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
                -Dsonar.projectName="${SONAR_PROJECT_KEY}" \
                -Dsonar.projectVersion="${BUILD_NUMBER}" \
                -Dsonar.sources=. \
                -Dsonar.inclusions=/.py,/.js,/*.ts \
                -Dsonar.exclusions=/venv/,/.venv/,/node_modules/,/tests/** \
                -Dsonar.python.version=3.11 \
                -Dsonar.scanner.skipJreProvisioning=true
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
          docker run --rm -v "$PWD":/src -v "$PWD/reports":/reports aquasec/trivy:${TRIVY_VER} \
            fs --no-progress --scanners vuln,secret,config --format sarif -o /reports/trivy-fs.sarif /src || true
          docker run --rm -v "$PWD":/src -v "$PWD/reports":/reports aquasec/trivy:${TRIVY_VER} \
            fs --no-progress --severity HIGH,CRITICAL --format table -o /reports/trivy-fs.txt /src || true
          {
            echo '<html><body><h2>Trivy FS</h2><pre>';
            sed -e 's/&/\\&amp;/g' -e 's/</\\&lt;/g' reports/trivy-fs.txt || true;
            echo '</pre></body></html>';
          } > reports/trivy-fs.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy FS (workspace)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif, reports/trivy-fs.txt', allowEmptyArchive: true
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMAGE=$(cat image.txt)
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD/reports":/reports aquasec/trivy:${TRIVY_VER} \
            image --no-progress --format sarif -o /reports/trivy-image.sarif "$IMAGE" || true
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD/reports":/reports aquasec/trivy:${TRIVY_VER} \
            image --no-progress --severity HIGH,CRITICAL --format table -o /reports/trivy-image.txt "$IMAGE" || true
          {
            echo '<html><body><h2>Trivy Image</h2><pre>';
            sed -e 's/&/\\&amp;/g' -e 's/</\\&lt;/g' reports/trivy-image.txt || true;
            echo '</pre></body></html>';
          } > reports/trivy-image.html
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy Image', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/trivy-image.sarif, reports/trivy-image.txt', allowEmptyArchive: true
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
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/, image.txt, presigned-urls.txt, */target/.jar, */.log', allowEmptyArchive: true
    }
  }
}
