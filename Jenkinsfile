pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    // ---- Project
    REPORT_DIR = 'reports'
    IMAGE_NAME = 'demoapp'
    DOCKERFILE = 'container/Dockerfile' // mets 'Dockerfile' si c’est ton cas
    // ---- SonarCloud
    SONAR_HOST_URL   = 'https://sonarcloud.io'
    SONAR_ORG        = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
    // ---- S3
    AWS_REGION = 'eu-north-1'
    S3_BUCKET  = 'cryptonext-reports-98an'   // nom exact du bucket
    // ---- DAST (optionnel) : exemple http://<PUBLIC_IP>:5000
    DAST_TARGET = 'http://16.170.87.165:5000' // renseigne une URL pour activer ZAP baseline
  }

  stages {

    stage('Checkout') {
      steps {
        checkout([$class: 'GitSCM',
          branches: [[name: '*/master']],
          doGenerateSubmoduleConfigurations: false,
          extensions: [[$class: 'CloneOption', depth: 1, noTags: false, shallow: true]],
          userRemoteConfigs: [[
            url: 'https://github.com/98-an/python-demoapp.git',
            credentialsId: 'git-cred'
          ]]
        ])
        sh "rm -rf ${REPORT_DIR} && mkdir -p ${REPORT_DIR}"
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh """
          set -eux
          docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -eux
            python -m pip install --upgrade pip
            if [ -f src/requirements.txt ]; then pip install --prefer-binary -r src/requirements.txt;
            elif [ -f requirements.txt ]; then pip install --prefer-binary -r requirements.txt; fi
            pip install pytest flake8 bandit pytest-cov
            # Lint (ne casse pas le build)
            flake8 || true
            # Tests + coverage (XML pour Sonar)
            pytest --maxfail=1 --junitxml=/ws/${REPORT_DIR}/pytest-report.xml \\
                   --cov=. --cov-report=xml:/ws/${REPORT_DIR}/coverage.xml || true
            # SAST Python
            bandit -r . -f html -o /ws/${REPORT_DIR}/bandit-report.html || true
          '
        """
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: "${REPORT_DIR}/pytest-report.xml"
          publishHTML target: [
            allowMissing: true,
            keepAll: true,
            alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}",
            reportFiles: 'bandit-report.html',
            reportName: 'Bandit (Python)'
          ]
        }
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh """
          set -eux
          docker run --rm -v "\$PWD":/repo -w /repo zricethezav/gitleaks:latest \\
            detect --no-git --source /repo --report-format sarif --report-path /repo/${REPORT_DIR}/gitleaks.sarif || true

          # Résumé HTML
          count=\$(jq '[.runs[].results|length] | add // 0' ${REPORT_DIR}/gitleaks.sarif 2>/dev/null || echo 0)
          cat > ${REPORT_DIR}/gitleaks.html <<EOF
          <html><body><h2>Gitleaks (résumé)</h2><p>Findings: \$count</p></body></html>
          EOF
        """
      }
      post {
        always {
          publishHTML target: [
            allowMissing: true, keepAll: true, alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}", reportFiles: 'gitleaks.html', reportName: 'Gitleaks (Secrets)'
          ]
        }
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh """
          set -eux
          docker run --rm -v "\$PWD":/src returntocorp/semgrep:latest \\
            semgrep --config p/ci /src --sarif --output /src/${REPORT_DIR}/semgrep.sarif --error --timeout 0 || true

          count=\$(jq '[.runs[].results|length] | add // 0' ${REPORT_DIR}/semgrep.sarif 2>/dev/null || echo 0)
          cat > ${REPORT_DIR}/semgrep.html <<EOF
          <html><body><h2>Semgrep (résumé)</h2><p>Findings: \$count</p></body></html>
          EOF
        """
      }
      post {
        always {
          publishHTML target: [
            allowMissing: true, keepAll: true, alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}", reportFiles: 'semgrep.html', reportName: 'Semgrep (SAST)'
          ]
        }
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh """
            set -eux
            docker run --rm \\
              -e SONAR_HOST_URL="${SONAR_HOST_URL}" \\
              -e SONAR_TOKEN="\$SONAR_TOKEN" \\
              -v "\$PWD":/usr/src sonarsource/sonar-scanner-cli:latest \\
              -Dsonar.organization="${SONAR_ORG}" \\
              -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \\
              -Dsonar.projectName="${SONAR_PROJECT_KEY}" \\
              -Dsonar.projectVersion="${BUILD_NUMBER}" \\
              -Dsonar.sources=. \\
              -Dsonar.python.version=3.11 \\
              -Dsonar.scanner.skipJreProvisioning=true \\
              -Dsonar.scm.exclusions.disabled=true
          """
        }
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { expression { return fileExists(env.DOCKERFILE) || fileExists('Dockerfile') } }
      steps {
        script {
          def df = fileExists(env.DOCKERFILE) ? env.DOCKERFILE : 'Dockerfile'
          sh """
            set -eux
            docker build -f ${df} -t ${IMAGE_NAME}:${BUILD_NUMBER} .
            echo ${IMAGE_NAME}:${BUILD_NUMBER} > image.txt
          """
        }
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh """
          set -eux
          docker run --rm -v "\$PWD":/project aquasec/trivy:latest \\
            fs --scanners vuln,secret,config --format sarif -o /project/${REPORT_DIR}/trivy-fs.sarif /project || true

          # Résumé HTML
          count=\$(jq '[.runs[].results|length] | add // 0' ${REPORT_DIR}/trivy-fs.sarif 2>/dev/null || echo 0)
          cat > ${REPORT_DIR}/trivy-fs.html <<EOF
          <html><body><h2>Trivy FS (résumé)</h2><p>Findings: \$count</p></body></html>
          EOF
          # Copie brute pour consultation rapide aussi
          cp ${REPORT_DIR}/trivy-fs.sarif ${REPORT_DIR}/trivy-fs.txt || true
        """
      }
      post {
        always {
          publishHTML target: [
            allowMissing: true, keepAll: true, alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}", reportFiles: 'trivy-fs.html', reportName: 'Trivy FS'
          ]
        }
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { return fileExists('image.txt') } }
      steps {
        sh """
          set -eux
          IMAGE=\$(cat image.txt)
          docker run --rm -v "\$PWD":/project aquasec/trivy:latest \\
            image --format sarif -o /project/${REPORT_DIR}/trivy-image.sarif "\$IMAGE" || true

          count=\$(jq '[.runs[].results|length] | add // 0' ${REPORT_DIR}/trivy-image.sarif 2>/dev/null || echo 0)
          cat > ${REPORT_DIR}/trivy-image.html <<EOF
          <html><body><h2>Trivy Image (résumé)</h2><p>Findings: \$count</p></body></html>
          EOF
          cp ${REPORT_DIR}/trivy-image.sarif ${REPORT_DIR}/trivy-image.txt || true
        """
      }
      post {
        always {
          publishHTML target: [
            allowMissing: true, keepAll: true, alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}", reportFiles: 'trivy-image.html', reportName: 'Trivy Image'
          ]
        }
      }
    }

    stage('DAST - ZAP Baseline (optionnel)') {
      when { expression { return env.DAST_TARGET?.trim() } }
      steps {
        sh """
          set -eux
          docker pull owasp/zap2docker-stable || true
          docker run --rm owasp/zap2docker-stable zap-baseline.py \\
            -t "${DAST_TARGET}" -r zap-baseline.html -m 1 || true
          mv -f zap-baseline.html ${REPORT_DIR}/ || true
        """
      }
      post {
        always {
          publishHTML target: [
            allowMissing: true, keepAll: true, alwaysLinkToLastBuild: true,
            reportDir: "${REPORT_DIR}", reportFiles: 'zap-baseline.html', reportName: 'ZAP Baseline'
          ]
        }
      }
    }

    stage('Publish reports to S3') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                        passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh """
            set -eux
            # 1) Sanity STS: échoue si clé invalide
            docker run --rm \\
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=${AWS_REGION} \\
              amazon/aws-cli sts get-caller-identity

            # 2) Upload de tous les rapports
            docker run --rm -v "\$PWD/${REPORT_DIR}":/r -w /r \\
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=${AWS_REGION} \\
              amazon/aws-cli s3 cp . s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/ --recursive --only-show-errors
          """
        }
      }
    }

    stage('Make presigned URLs (1h)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                        passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh """
            set -eux
            : > presigned-urls.txt
            for f in ${REPORT_DIR}/.html ${REPORT_DIR}/.txt ${REPORT_DIR}/*.sarif 2>/dev/null; do
              [ -f "\$f" ] || continue
              key="${JOB_NAME}/${BUILD_NUMBER}/\$(basename "\$f")"
              url=\$(docker run --rm \\
                -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=${AWS_REGION} \\
                amazon/aws-cli s3 presign s3://${S3_BUCKET}/"\$key" --expires-in 3600)
              echo "\$key -> \$url" >> presigned-urls.txt
            done
          """
        }
      }
    }
  } // stages

  post {
    always {
      archiveArtifacts artifacts: "${REPORT_DIR}/,image.txt,presigned-urls.txt", allowEmptyArchive: true
      echo "Done. Ouvre 'presigned-urls.txt' dans les artifacts pour accéder aux rapports S3."
    }
  }
}
