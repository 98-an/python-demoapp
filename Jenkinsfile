pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 20, unit: 'MINUTES')
  }

  environment {
    SNYK_ORG  = '98-an'
    S3_BUCKET = 'cryptonext-reports-98an'
    AWS_REGION = 'eu-north-1'
    // IMAGE_NAME sera défini dynamiquement dans le stage Build
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.SHORT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        }
      }
    }

    stage('Java Build & Tests') {
      when { expression { return fileExists('pom.xml') } }
      steps {
        sh '''
          docker run --rm -v "$PWD":/ws -w /ws \
            maven:3.9-eclipse-temurin-17 mvn -B -DskipTests=false clean test
        '''
        junit '**/target/surefire-reports/*.xml'
      }
    }

    stage('Python Lint & Tests & Bandit') {
      when {
        expression {
          return fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pyproject.toml')
        }
      }
      steps {
        sh '''
          set -eux
          mkdir -p reports
          if   [ -f src/requirements.txt ]; then REQ=src/requirements.txt
          elif [ -f requirements.txt ];    then REQ=requirements.txt
          else REQ=""; fi

          docker run --rm -v "$PWD":/ws -w /ws python:3.8-slim bash -lc "
            python -m pip install --upgrade pip &&
            if [ -n \\"$REQ\\" ]; then pip install --prefer-binary -r \\"$REQ\\"; fi &&
            pip install pytest flake8 bandit &&
            flake8 || true &&
            pytest --maxfail=1 --junitxml=pytest-report.xml || true &&
            bandit -r . -f html -o reports/bandit-report.html || true
          "
        '''
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { return fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF="Dockerfile"; [ -f "$DF" ] || DF="container/Dockerfile"
          docker run --rm -i hadolint/hadolint < "$DF" || true
        '''
      }
    }

    stage('Snyk (SCA)') {
      options { timeout(time: 5, unit: 'MINUTES') }
      when {
        expression {
          return fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pom.xml') || fileExists('pyproject.toml')
        }
      }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            mkdir -p reports

            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:stable snyk test \
                --org="$SNYK_ORG" --all-projects \
                --severity-threshold=medium \
                --json-file-output=reports/snyk-sca.json || true

            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:stable snyk monitor \
                --org="$SNYK_ORG" --all-projects || true

            docker run --rm -v "$PWD":/work \
              snyk/snyk-to-html -i /work/reports/snyk-sca.json -o /work/reports/snyk-sca.html || true
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-sca.html',
          reportName: 'Snyk Open Source (SCA)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { expression { return fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        script { env.IMAGE_NAME = "demoapp:${BUILD_NUMBER}" }
        sh '''
          set -eux
          DF="Dockerfile"; [ -f "$DF" ] || DF="container/Dockerfile"
          docker build -f "$DF" -t "$IMAGE_NAME" .
          echo "$IMAGE_NAME" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    stage('Snyk Container (image)') {
      when { expression { return fileExists('image.txt') } }
      options { timeout(time: 5, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            mkdir -p reports
            IMAGE=$(cat image.txt)

            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:stable snyk container test "$IMAGE" \
                --org="$SNYK_ORG" \
                --severity-threshold=medium \
                --json-file-output=reports/snyk-container.json || true

            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              snyk/snyk-cli:stable snyk container monitor "$IMAGE" \
                --org="$SNYK_ORG" || true

            docker run --rm -v "$PWD":/work \
              snyk/snyk-to-html -i /work/reports/snyk-container.json -o /work/reports/snyk-container.html || true
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-container.html',
          reportName: 'Snyk Container (Image)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      }
    }

    // -------------------- S3 --------------------
    stage('Publish reports to S3') {
      when {
        expression {
          return fileExists('reports/snyk-sca.json') ||
                 fileExists('reports/snyk-container.json') ||
                 fileExists('reports/bandit-report.html')
        }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                         usernameVariable: 'AWS_ACCESS_KEY_ID',
                         passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eux
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"

            docker run --rm \
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD/reports:/reports" amazon/aws-cli \
              s3 cp /reports "${DEST}" --recursive --sse AES256

            if [ -f image.txt ]; then
              docker run --rm \
                -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
                -v "$PWD:/w" amazon/aws-cli \
                s3 cp /w/image.txt "${DEST}"
            fi
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
            DEST="s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/"
            docker run --rm \
              -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
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
            set -euo pipefail
            DEST_PREFIX="${JOB_NAME}/${BUILD_NUMBER}"
            BUCKET="${S3_BUCKET}"
            : > presigned-urls.txt

            # Récupère la liste des objets déjà uploadés dans s3://BUCKET/DEST_PREFIX/
            docker run --rm \
            -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
            amazon/aws-cli s3api list-objects-v2 \
              --bucket "$BUCKET" --prefix "$DEST_PREFIX/" \
              --query "Contents[].Key" --output text | tr '\\t' '\\n' > keys.txt

            # Présigne chaque objet pour 1h
            while read -r key; do
              [ -z "$key" ] && continue
              url=$(docker run --rm \
                -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION="${AWS_REGION}" \
                amazon/aws-cli s3 presign "s3://${BUCKET}/${key}" --expires-in 3600)
              echo "${key} -> ${url}" | tee -a presigned-urls.txt
            done < keys.txt
          '''
    }
    archiveArtifacts artifacts: 'presigned-urls.txt', allowEmptyArchive: true
  }
}
