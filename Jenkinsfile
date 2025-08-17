pipeline {
  agent any
  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  environment {
    SNYK_ORG      = '98-an'
    IMAGE_NAME    = "demoapp:${env.BUILD_NUMBER}"
    S3_BUCKET     = 'cryptonext-reports-98an'
    AWS_REGION    = 'eu-north-1'
    DAST_TARGET   = 'http://13.62.105.249:5000'
    SNYK_FAIL_SEV = 'high'     // medium|high|critical
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

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect -s /repo --no-git -f sarif -r /repo/reports/gitleaks.sarif || true
          printf '<h2>Gitleaks SARIF généré</h2><p>Fichier: reports/gitleaks.sarif</p>' > reports/gitleaks.html
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
          printf '<h2>Semgrep SARIF généré</h2><p>Fichier: reports/semgrep.sarif</p>' > reports/semgrep.html
        '''
        archiveArtifacts artifacts: 'reports/semgrep.sarif', allowEmptyArchive: true
        publishHTML(target: [reportDir: 'reports', reportFiles: 'semgrep.html',
          reportName: 'Semgrep (SAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    /* -------- Snyk Open Source (SCA) -------- */
    stage('Snyk (SCA)') {
      when { expression { fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pom.xml') || fileExists('pyproject.toml') } }
      options { timeout(time: 6, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            TARGET_FILE=""; PKG_MGR=""
            if   [ -f src/requirements.txt ]; then TARGET_FILE="src/requirements.txt"; PKG_MGR="--package-manager=pip"
            elif [ -f requirements.txt ];    then TARGET_FILE="requirements.txt";    PKG_MGR="--package-manager=pip"
            elif [ -f pom.xml ];             then TARGET_FILE="pom.xml";             PKG_MGR=""
            fi

            docker run --rm -v "$PWD":/project -w /project python:3.11-alpine sh -lc "
              set -eux
              apk add --no-cache nodejs npm
              npm -g i snyk@latest snyk-to-html@latest snyk-to-sarif@latest
              if [ -n \\"$TARGET_FILE\\" ]; then
                SNYK_TOKEN=$SNYK_TOKEN snyk test --file=\\"$TARGET_FILE\\" $PKG_MGR \
                  --org=$SNYK_ORG --severity-threshold=medium --json \
                  | tee /project/reports/snyk-sca.json >/dev/null || true
              else
                SNYK_TOKEN=$SNYK_TOKEN snyk test --org=$SNYK_ORG --all-projects \
                  --severity-threshold=medium --json \
                  | tee /project/reports/snyk-sca.json >/dev/null || true
              fi
              if [ -s /project/reports/snyk-sca.json ]; then
                snyk-to-html -i /project/reports/snyk-sca.json -o /project/reports/snyk-sca.html || true
                snyk-to-sarif /project/reports/snyk-sca.json > /project/reports/snyk-sca.sarif || true
              fi
            "
            echo '--- ls reports après Snyk SCA ---'; ls -l reports || true
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-sca.html',
          reportName: 'Snyk Open Source (SCA)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/snyk-sca.json,reports/snyk-sca.sarif', allowEmptyArchive: true
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

    /* -------- Snyk Container -------- */
    stage('Snyk Container (image)') {
      when { expression { fileExists('image.txt') } }
      options { timeout(time: 6, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            IMAGE=$(cat image.txt)
            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              -v "$PWD":/work -w /work node:18-alpine sh -lc "
                set -eux
                npm -g i snyk@latest snyk-to-html@latest snyk-to-sarif@latest
                snyk container test \\"$IMAGE\\" --org=$SNYK_ORG --severity-threshold=medium \
                  --json --file=container.Dockerfile > /work/reports/snyk-container.json || true
                snyk-to-html -i /work/reports/snyk-container.json -o /work/reports/snyk-container.html || true
                snyk-to-sarif /work/reports/snyk-container.json > /work/reports/snyk-container.sarif || true
              "
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-container.html',
          reportName: 'Snyk Container (Image)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/snyk-container.json,reports/snyk-container.sarif', allowEmptyArchive: true
      }
    }

    /* -------- Gates (fail si vuln ≥ seuil) -------- */
    stage('Snyk Gates (fail si ≥ seuil)') {
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            TARGET_FILE=""; PKG_MGR=""
            if   [ -f src/requirements.txt ]; then TARGET_FILE="src/requirements.txt"; PKG_MGR="--package-manager=pip"
            elif [ -f requirements.txt ];    then TARGET_FILE="requirements.txt";    PKG_MGR="--package-manager=pip"
            elif [ -f pom.xml ];             then TARGET_FILE="pom.xml";             PKG_MGR=""
            fi

            docker run --rm -v "$PWD":/project -w /project python:3.11-alpine sh -lc "
              set -eux
              apk add --no-cache nodejs npm
              npm -g i snyk@latest
              if [ -n \\"$TARGET_FILE\\" ]; then
                SNYK_TOKEN=$SNYK_TOKEN snyk test --file=\\"$TARGET_FILE\\" $PKG_MGR \
                  --org=$SNYK_ORG --severity-threshold=${SNYK_FAIL_SEV}
              else
                SNYK_TOKEN=$SNYK_TOKEN snyk test --org=$SNYK_ORG --all-projects \
                  --severity-threshold=${SNYK_FAIL_SEV}
              fi
            "
          '''
        }
      }
    }

    /* -------- Deploy via Ansible -------- */
    stage('Deploy (Ansible)') {
      when { expression { fileExists('ansible/site.yml') } }
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'ansible-ssh',
                                           keyFileVariable: 'SSH_KEY',
                                           usernameVariable: 'SSH_USER')]) {
          sh '''
            set -eux
            docker run --rm \
              -v "$PWD/ansible:/ansible:ro" \
              -v "$SSH_KEY:/id_rsa:ro" \
              --entrypoint bash willhallonline/ansible:2.15-ubuntu -lc "
                chmod 600 /id_rsa &&
                ansible-playbook -i /ansible/inventory.ini /ansible/site.yml \
                  --key-file /id_rsa \
                  -e ansible_user=${SSH_USER} \
                  -e image='${IMAGE_NAME}'
              "
          '''
        }
      }
    }

    /* -------- DAST -------- */
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

    /* -------- Upload S3 -------- */
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
      // jar éventuels + logs
      archiveArtifacts artifacts: '/target/.jar, **/.log', allowEmptyArchive: true
    }
  }
}
