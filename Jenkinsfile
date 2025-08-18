pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    // --- Project
    REPORT_DIR       = 'reports'
    IMAGE_NAME       = 'demoapp'
    DOCKERFILE       = 'container/Dockerfile'   // mets 'Dockerfile' si c’est ton cas

    // --- SonarCloud
    SONAR_HOST_URL   = 'https://sonarcloud.io'
    SONAR_ORG        = '98-an'
    SONAR_PROJECT_KEY= '98-an_python-demoapp'

    // --- AWS S3 (rapports)
    AWS_REGION       = 'eu-north-1'
    S3_BUCKET        = 'cryptonext-reports-98an'  // nom exact du bucket

    // --- DAST (optionnel)
    DAST_TARGET      = 'http://16.170.87.165:5000' // commente si tu n’as pas d’app exposée
  }

  stages {

    stage('Checkout') {
      steps {
        checkout([
          $class: 'GitSCM',
          branches: [[name: '*/master']],
          doGenerateSubmoduleConfigurations: false,
          extensions: [[$class: 'CloneOption', depth: 1, noTags: false, shallow: true]],
          userRemoteConfigs: [[
            url: 'https://github.com/98-an/python-demoapp.git',
            credentialsId: 'git-cred'
          ]]
        ])
        sh 'mkdir -p "$REPORT_DIR"'
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh '''
          set -eux
          docker run --rm \
            -e REPORT_DIR="${REPORT_DIR}" \
            -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
              set -eux
              mkdir -p "$REPORT_DIR"
              python -V
              pip install -U pip
              # Dépendances applicatives (si présents)
              [ -f src/requirements.txt ] && pip install --no-cache-dir -r src/requirements.txt || true
              [ -f requirements.txt ]     && pip install --no-cache-dir -r requirements.txt     || true
              # Outils de qualité
              pip install --no-cache-dir flake8 bandit pytest pytest-cov

              # Lint Python (si src/ existe, sinon linter la racine)
              if [ -d src ]; then
                flake8 src || true
              else
                flake8 . || true
              fi

              # Tests (génère toujours un JUnit XML pour Jenkins)
              pytest --maxfail=0 -q \
                --cov=. --cov-report xml:"$REPORT_DIR/coverage.xml" \
                --junitxml="$REPORT_DIR/pytest-report.xml" || true

              # Si aucun test n'a tourné, assure un XML minimal pour le step JUnit
              [ -s "$REPORT_DIR/pytest-report.xml" ] || echo "<testsuite/>" > "$REPORT_DIR/pytest-report.xml"

              # Bandit (SAST Python)
              if [ -d src ]; then
                bandit -r src -f html -o "$REPORT_DIR/bandit-report.html" || true
                bandit -r src -f json -o "$REPORT_DIR/bandit-report.json" || true
              else
                bandit -r .   -f html -o "$REPORT_DIR/bandit-report.html" || true
                bandit -r .   -f json -o "$REPORT_DIR/bandit-report.json" || true
              fi
            '
        '''
      }
      post {
        always {
          script {
            if (fileExists("${REPORT_DIR}/pytest-report.xml")) {
              junit allowEmptyResults: true, testResults: "${REPORT_DIR}/pytest-report.xml"
            } else {
              writeFile file: "${REPORT_DIR}/pytest-report.xml", text: "<testsuite/>"
              junit allowEmptyResults: true, testResults: "${REPORT_DIR}/pytest-report.xml"
            }
          }
          archiveArtifacts artifacts: "${REPORT_DIR}/", allowEmptyArchive: true
        }
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { return fileExists(env.DOCKERFILE) } }
      steps {
        sh '''
          set -eux
          docker run --rm -i hadolint/hadolint < "${DOCKERFILE}" || true
        '''
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/repo zricethezav/gitleaks:latest \
            detect -v --report-format sarif --report-path /repo/"$REPORT_DIR"/gitleaks.sarif || true
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: "${REPORT_DIR}/gitleaks.sarif", allowEmptyArchive: true
        }
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/src returntocorp/semgrep:latest \
            semgrep --config p/ci --sarif --output /src/"$REPORT_DIR"/semgrep.sarif --error --timeout 0 || true
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: "${REPORT_DIR}/semgrep.sarif", allowEmptyArchive: true
        }
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -eux
            docker run --rm \
              -e SONAR_HOST_URL="${SONAR_HOST_URL}" \
              -e SONAR_TOKEN="${SONAR_TOKEN}" \
              -v "$PWD":/usr/src sonarsource/sonar-scanner-cli:latest \
              -Dsonar.organization="${SONAR_ORG}" \
              -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
              -Dsonar.projectName="${SONAR_PROJECT_KEY}" \
              -Dsonar.sources=. \
              -Dsonar.python.version=3.11 \
              -Dsonar.javascript.exclusions=/.html,/.min.js,/bundle.js \
              -Dsonar.css.exclusions=/*.html \
              -Dsonar.scm.exclusions.disabled=true \
              -Dsonar.scanner.skipJreProvisioning=true
          '''
        }
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { expression { return fileExists(env.DOCKERFILE) } }
      steps {
        sh '''
          set -eux
          docker build -f "${DOCKERFILE}" -t "${IMAGE_NAME}:${BUILD_NUMBER}" .
          echo "${IMAGE_NAME}:${BUILD_NUMBER}" > "${REPORT_DIR}/image.txt"
        '''
      }
      post {
        always {
          archiveArtifacts artifacts: "${REPORT_DIR}/image.txt", allowEmptyArchive: true
        }
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh '''
          set -eux
          docker run --rm -v "$PWD":/project aquasec/trivy:latest fs --scanners vuln,secret,config \
            --format sarif -o /project/"$REPORT_DIR"/trivy-fs.sarif /project || true

          # petit résumé HTML lisible
          docker run --rm -v "$PWD":/project aquasec/trivy:latest fs --scanners vuln,secret,config \
            -f template -t "@/contrib/html.tpl" -o /project/"$REPORT_DIR"/trivy-fs.html /project || true

          # version texte
          docker run --rm -v "$PWD":/project aquasec/trivy:latest fs --scanners vuln,secret,config \
            -q -o /project/"$REPORT_DIR"/trivy-fs.txt /project || true
        '''
      }
      post { always { archiveArtifacts artifacts: "${REPORT_DIR}/trivy-fs.*", allowEmptyArchive: true } }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { return fileExists("${env.REPORT_DIR}/image.txt") } }
      steps {
        sh '''
          set -eux
          img="$(cat "${REPORT_DIR}/image.txt")"
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image --format sarif -o /"${REPORT_DIR}"/trivy-image.sarif "$img" || true

          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/ws aquasec/trivy:latest image \
            -f template -t "@/contrib/html.tpl" -o /ws/"${REPORT_DIR}"/trivy-image.html "$img" || true

          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/ws aquasec/trivy:latest image -q -o /ws/"${REPORT_DIR}"/trivy-image.txt "$img" || true
        '''
      }
      post { always { archiveArtifacts artifacts: "${REPORT_DIR}/trivy-image.*", allowEmptyArchive: true } }
    }

    stage('DAST - ZAP Baseline') {
      when { expression { return env.DAST_TARGET?.trim() } }
      steps {
        sh '''
          set -eux
          docker pull owasp/zap2docker-stable
          docker run --rm -u root \
            owasp/zap2docker-stable zap-baseline.py \
            -t "${DAST_TARGET}" -r zap-baseline.html || true
          mv zap-baseline.html "${REPORT_DIR}/zap-baseline.html" || true
        '''
      }
      post { always { archiveArtifacts artifacts: "${REPORT_DIR}/zap-baseline.html", allowEmptyArchive: true } }
    }

    stage('Publish reports to S3') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-us', passwordVariable: 'AWS_SECRET_ACCESS_KEY', usernameVariable: 'AWS_ACCESS_KEY_ID')]) {
          sh '''
            set -eux
            docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD":/ws amazon/aws-cli s3 cp /ws/"${REPORT_DIR}"/ s3://"${S3_BUCKET}"/${JOB_NAME}/${BUILD_NUMBER}/ --recursive --only-show-errors
          '''
        }
      }
    }

    stage('Make presigned URL (1h)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-us', passwordVariable: 'AWS_SECRET_ACCESS_KEY', usernameVariable: 'AWS_ACCESS_KEY_ID')]) {
          sh '''
            set -eux
            : > presigned-urls.txt
            for f in $(ls -1 "${REPORT_DIR}"); do
              p="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/$f"
              url=$(docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" amazon/aws-cli \
                s3 presign "$p" --expires-in 3600)
              echo "${JOB_NAME}/${BUILD_NUMBER}/$f -> $url" >> presigned-urls.txt
            done
          '''
        }
      }
      post { always { archiveArtifacts artifacts: 'presigned-urls.txt', allowEmptyArchive: true } }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: "${REPORT_DIR}/", allowEmptyArchive: true
    }
  }
}
