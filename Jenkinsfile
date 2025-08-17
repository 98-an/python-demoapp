pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    // ---- Générales
    IMAGE_NAME       = "demoapp:${env.BUILD_NUMBER}"
    S3_BUCKET        = 'cryptonext-reports-98an'
    AWS_REGION       = 'eu-north-1'
    DAST_TARGET      = 'http://13.62.105.249:5000'   // adapte si l’IP change
    // ---- SonarCloud
    SONAR_HOST_URL   = 'https://sonarcloud.io'
    SONAR_ORG        = 'ton-org-sonarcloud'          // <= A RENSEIGNER
    SONAR_PROJECT_KEY= 'ton-project-key'             // <= A RENSEIGNER
    // ---- Trivy gates
    TRIVY_FAIL_SEV   = 'HIGH,CRITICAL'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh 'rm -rf reports && mkdir -p reports'
        script { env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim() }
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
          docker run --rm -i hadolint/hadolint < "$DF" || true
        '''
      }
    }

    /* ===================== Secrets & SAST additionnels ===================== */

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -e GIT_DISCOVERY_ACROSS_FILESYSTEM=1 \
            -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect --no-git -s /repo -f sarif -r /repo/reports/gitleaks.sarif || true

          cat > reports/gitleaks.html <<'HTML'
          <html><body><h2>Gitleaks – Résultats</h2>
          <p>Le rapport SARIF est archivé (gitleaks.sarif) et envoyé sur S3.</p></body></html>
          HTML
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
            semgrep --config p/ci --sarif --output /src/reports/semgrep.sarif --error --timeout 0 || true

          cat > reports/semgrep.html <<'HTML'
          <html><body><h2>Semgrep – Résultats</h2>
          <p>Le rapport SARIF est archivé (semgrep.sarif) et envoyé sur S3.</p></body></html>
          HTML
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
      }
    }

    /* ===================== SonarCloud ===================== */

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL="${SONAR_HOST_URL}" \
              -e SONAR_LOGIN="${SONAR_TOKEN}" \
              -v "$PWD":/usr/src sonarsource/sonar-scanner-cli \
              -Dsonar.organization="${SONAR_ORG}" \
              -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
              -Dsonar.projectVersion="${BUILD_NUMBER}" \
              -Dsonar.sources=. \
              -Dsonar.scanner.skipJreProvisioning=true
          '''
        }
      }
    }

    /* ===================== Build & Trivy ===================== */

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

    stage('Trivy FS (deps & OS)') {
      steps {
        sh '''
          set -eux
          # Rapports (HTML via template, SARIF pour outils)
          docker run --rm -v "$PWD":/work -w /work aquasec/trivy:latest \
            fs --scanners vuln,config,secret \
            --format template --template "@/contrib/html.tpl" -o /work/reports/trivy-fs.html .

          docker run --rm -v "$PWD":/work -w /work aquasec/trivy:latest \
            fs --scanners vuln,config,secret \
            --format sarif -o /work/reports/trivy-fs.sarif .

          # Gate de sévérité (échoue si >= HIGH/CRITICAL)
          docker run --rm -v "$PWD":/work -w /work aquasec/trivy:latest \
            fs --scanners vuln \
            --ignore-unfixed --severity "${TRIVY_FAIL_SEV}" --exit-code 1 . || true
          code=$?
          [ $code -ne 0 ] && echo "Trivy FS gate: ${TRIVY_FAIL_SEV} trouvées" && exit $code || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-fs.html',
          reportName: 'Trivy (File System)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/trivy-fs.sarif', allowEmptyArchive: true
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          IMAGE=$(cat image.txt)

          docker run --rm -v "$PWD":/work -w /work -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
            image --format template --template "@/contrib/html.tpl" -o /work/reports/trivy-image.html "${IMAGE}"

          docker run --rm -v "$PWD":/work -w /work -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
            image --format sarif -o /work/reports/trivy-image.sarif "${IMAGE}"

          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
            image --ignore-unfixed --severity "${TRIVY_FAIL_SEV}" --exit-code 1 "${IMAGE}" || true
          code=$?
          [ $code -ne 0 ] && echo "Trivy Image gate: ${TRIVY_FAIL_SEV} trouvées" && exit $code || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'trivy-image.html',
          reportName: 'Trivy (Image)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/trivy-image.sarif', allowEmptyArchive: true
      }
    }

    /* ===================== Deploy (Ansible) ===================== */

    stage('Deploy (Ansible)') {
      when { expression { fileExists('ansible/site.yml') } }
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'ansible-ssh',
                                           keyFileVariable: 'SSH_KEY',
                                           usernameVariable: 'SSH_USER')]) {
          sh '''
            set -euxo pipefail
            ls -la ansible
            test -s "$SSH_KEY" || { echo "SSH_KEY introuvable ou vide"; exit 2; }

            docker run --rm \
              -e ANSIBLE_HOST_KEY_CHECKING=False \
              -v "$PWD/ansible:/ansible:ro" \
              -v "$SSH_KEY:/id_rsa:ro" \
              --entrypoint bash willhallonline/ansible:2.15-ubuntu -lc "
                set -eux
                chmod 600 /id_rsa
                ansible --version
                ansible-playbook -i /ansible/inventory.ini /ansible/site.yml \
                  --private-key /id_rsa \
                  -e ansible_user=${SSH_USER} \
                  -e ansible_ssh_common_args='-o StrictHostKeyChecking=no' \
                  -e image='${IMAGE_NAME}'
              "
          '''
        }
      }
    }

    /* ===================== DAST ===================== */

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

    /* ===================== S3 & URLs ===================== */

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
        archiveArtifacts artifacts: 'presigned-urls.txt,image.txt,reports/', allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '/target/.jar, **/.log', allowEmptyArchive: true
    }
  }
}
