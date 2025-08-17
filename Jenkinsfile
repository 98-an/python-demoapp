pipeline {
  agent any

  parameters {
    string(
      name: 'DAST_TARGET',
      defaultValue: '',
      description: 'URL cible pour ZAP. Laisse vide pour scanner le conteneur déployé localement (http://demoapp-ansible:5000 via réseau Docker).'
    )
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    ansiColor('xterm')
    timeout(time: 30, unit: 'MINUTES')
    skipDefaultCheckout(false)
  }

  environment {
    // --- Vars globales ---
    SNYK_ORG      = '98-an'
    SNYK_FAIL_SEV = 'high'                 // échoue si vuln >= ce seuil
    IMAGE_NAME    = "demoapp:${env.BUILD_NUMBER}"
    PY_IMAGE      = 'python:3.8-slim'      // 3.8 pour éviter les wheels manquants (psutil==5.8.0)
    S3_BUCKET     = 'cryptonext-reports-98an'
    AWS_REGION    = 'eu-north-1'
    DAST_TARGET = 'http://13.62.105.249:5000'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
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
        sh """
          docker run --rm -v "$PWD":/ws -w /ws ${PY_IMAGE} bash -lc '
            set -eux
            mkdir -p reports
            REQ=""
            if [ -f src/requirements.txt ]; then REQ=src/requirements.txt; elif [ -f requirements.txt ]; then REQ=requirements.txt; fi
            python -m pip install --upgrade pip
            if [ -n "$REQ" ]; then pip install --prefer-binary -r "$REQ"; fi
            pip install pytest flake8 bandit
            flake8 || true
            pytest --maxfail=1 --junitxml=pytest-report.xml || true
            bandit -q -r . -f html -o reports/bandit-report.html || true
          '
        """
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: 'reports', reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    stage('SAST - Semgrep & Secrets') {
      steps {
        sh '''
          set -eux
          mkdir -p reports
          CFG="p/ci"; [ -f security/semgrep-rules.yml ] && CFG="security/semgrep-rules.yml"
          docker run --rm -v "$PWD":/work -w /work semgrep/semgrep:latest \
            semgrep ci --config "$CFG" --sarif --output reports/semgrep.sarif || true

          docker run --rm -v "$PWD":/repo -w /repo gitleaks/gitleaks:latest detect \
            -s /repo -f sarif -r /repo/reports/gitleaks.sarif --no-git || true
        '''
        archiveArtifacts artifacts: 'reports/*.sarif', fingerprint: true, allowEmptyArchive: true
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

    stage('Build Image') {
      when { expression { fileExists('Dockerfile') || fileExists('container/Dockerfile') } }
      steps {
        sh '''
          set -eux
          DF="Dockerfile"; [ -f "$DF" ] || DF="container/Dockerfile"
          docker build -t "$IMAGE_NAME" -f "$DF" .
          echo "$IMAGE_NAME" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    // ---------- Déploiement local via ANSIBLE (gère conteneur sur l’EC2) ----------
    stage('Deploy (Ansible - local Docker)') {
      when { expression { return fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          mkdir -p ansible

          # inventaire minimal
          if [ ! -f ansible/inventory.ini ]; then
            cat > ansible/inventory.ini <<'INV'
[local]
localhost ansible_connection=local
INV
          fi

          # playbook minimal (utilise CLI Docker pour éviter les dépendances)
          if [ ! -f ansible/playbook.yml ]; then
            cat > ansible/playbook.yml <<'YML'
- hosts: local
  gather_facts: false
  vars:
    container_name: demoapp-ansible
    app_port: 5000
  tasks:
    - name: Create user-defined network (for ZAP to reach container by name)
      shell: docker network create appnet || true

    - name: Stop previous container
      shell: docker rm -f {{ container_name }} || true

    - name: Run new container on appnet
      shell: docker run -d --name {{ container_name }} --network appnet -p {{ app_port }}:5000 {{ image_name }}
YML
          fi

          IMAGE=$(cat image.txt)
          docker run --rm -v "$PWD/ansible:/ansible" -v /var/run/docker.sock:/var/run/docker.sock -w /ansible \
            cytopia/ansible:latest ansible-playbook -i inventory.ini playbook.yml --extra-vars "image_name=$IMAGE"
        '''
      }
    }

    // ---------- Snyk SCA avec gate ----------
    stage('Snyk (SCA) + Gate') {
      when { expression { fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pom.xml') || fileExists('pyproject.toml') } }
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            mkdir -p reports
            EXIT=0
            docker run --rm -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:linux snyk test \
                --org="$SNYK_ORG" --all-projects \
                --severity-threshold='"${SNYK_FAIL_SEV}"' \
                --json-file-output=reports/snyk-sca.json || EXIT=$?

            docker run --rm -v "$PWD":/work snyk/snyk-to-html \
              -i /work/reports/snyk-sca.json -o /work/reports/snyk-sca.html || true

            echo $EXIT > reports/snyk-sca.exit
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-sca.html',
          reportName: 'Snyk Open Source (SCA)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/snyk-sca.*', fingerprint: true, allowEmptyArchive: true
      }
      post {
        always {
          script {
            if (fileExists('reports/snyk-sca.exit')) {
              def code = readFile('reports/snyk-sca.exit').trim()
              if (code != '0') { error "Snyk SCA gate failed (>= ${env.SNYK_FAIL_SEV})" }
            }
          }
        }
      }
    }

    // ---------- DAST : ZAP Baseline ----------
    stage('DAST - OWASP ZAP (baseline)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          set -eux
          mkdir -p reports

          TARGET="${DAST_TARGET}"
          ZAP_NET=""
          if [ -z "$TARGET" ]; then
            # si pas de cible fournie, on scanne le conteneur déployé via Ansible
            TARGET="http://demoapp-ansible:5000"
            ZAP_NET="--network appnet"
          fi

          docker run --rm $ZAP_NET -v "$PWD/reports:/zap/wrk" owasp/zap2docker-stable \
            zap-baseline.py -t "$TARGET" -r zap-baseline.html -x zap-baseline.xml -m 5 -d || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'zap-baseline.html',
          reportName: 'OWASP ZAP Baseline (DAST)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/zap-baseline.*', fingerprint: true, allowEmptyArchive: true
      }
    }

    // ---------- Snyk Container sur l'image ----------
    stage('Snyk Container (image) + Gate') {
      when { expression { fileExists('image.txt') } }
      options { timeout(time: 8, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            mkdir -p reports
            IMAGE=$(cat image.txt)
            EXIT=0

            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              snyk/snyk-cli:docker snyk container test "$IMAGE" \
                --org="$SNYK_ORG" \
                --severity-threshold='"${SNYK_FAIL_SEV}"' \
                --json-file-output=/tmp/snyk-container.json || EXIT=$?

            CID=$(docker ps -alq || true)
            [ -n "$CID" ] && docker cp "$CID":/tmp/snyk-container.json reports/snyk-container.json || true

            docker run --rm -v "$PWD":/work snyk/snyk-to-html \
              -i /work/reports/snyk-container.json -o /work/reports/snyk-container.html || true

            echo $EXIT > reports/snyk-container.exit
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-container.html',
          reportName: 'Snyk Container (Image)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/snyk-container.*', fingerprint: true, allowEmptyArchive: true
      }
      post {
        always {
          script {
            if (fileExists('reports/snyk-container.exit')) {
              def code = readFile('reports/snyk-container.exit').trim()
              if (code != '0') { error "Snyk Container gate failed (>= ${env.SNYK_FAIL_SEV})" }
            }
          }
        }
      }
    }

    // ---------- Publication S3 ----------
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
              -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
              -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
              -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD/reports:/reports" amazon/aws-cli \
              s3 cp /reports "${DEST}" --recursive --sse AES256
            [ -f image.txt ] && docker run --rm \
              -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
              -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
              -e AWS_DEFAULT_REGION="${AWS_REGION}" \
              -v "$PWD:/w" amazon/aws-cli \
              s3 cp /w/image.txt "${DEST}" || true
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
            set -eu
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
      when { expression { fileExists('reports') } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -eu
            PREFIX="${JOB_NAME}/${BUILD_NUMBER}"
            : > presigned-urls.txt
            for f in reports/*; do
              key="${PREFIX}/$(basename "$f")"
              url=$(docker run --rm \
                -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
                -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
                -e AWS_DEFAULT_REGION="${AWS_REGION}" \
                amazon/aws-cli \
                aws s3 presign "s3://${S3_BUCKET}/${key}" --expires-in 3600)
              echo "${key} -> ${url}" | tee -a presigned-urls.txt
            done
          '''
        }
        archiveArtifacts artifacts: 'presigned-urls.txt', allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '/target/.jar, **/.log, reports//.html, reports//.json, reports/*.sarif, image.txt', allowEmptyArchive: true
    }
  }
}
