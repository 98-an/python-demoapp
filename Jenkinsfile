pipeline {
  agent any
  options { timestamps() }

  environment {
    SNYK_ORG = '98-an'                 // ton slug d’organisation Snyk
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Java Build & Tests') {
      when { expression { fileExists('pom.xml') } }
      steps {
        sh '''
          docker run --rm -v "$PWD":/workspace -w /workspace \
            maven:3.9-eclipse-temurin-17 mvn -B -DskipTests=false clean test
        '''
        junit '**/target/surefire-reports/*.xml'
      }
    }

    stage('Python Lint & Tests & Bandit') {
      when { expression { fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          docker run --rm -v "$PWD":/workspace -w /workspace python:3.11 bash -lc "
            python -m pip install --upgrade pip &&
            if [ -f requirements.txt ]; then pip install -r src/requirements.txt; fi &&
            pip install pytest flake8 bandit &&
            flake8 || true &&
            pytest --maxfail=1 --junitxml=pytest-report.xml || true &&
            bandit -r . -f html -o bandit-report.html || true
          "
        '''
        junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        publishHTML(target: [reportDir: '.', reportFiles: 'bandit-report.html', reportName: 'Bandit - Python SAST', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
      }
    }

    // --- Snyk (SCA) : dépendances appli ---
    stage('Snyk (SCA)') {
      options { timeout(time: 5, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            mkdir -p reports
            docker run --rm -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:stable snyk test \
                --org="$SNYK_ORG" --all-projects \
                --severity-threshold=medium \
                --json-file-output=reports/snyk-sca.json || true

            docker run --rm -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v "$PWD":/project -w /project \
              snyk/snyk-cli:stable snyk monitor \
                --org="$SNYK_ORG" --all-projects || true

            docker run --rm -v "$PWD":/work \
              snyk/snyk-to-html -i /work/reports/snyk-sca.json -o /work/reports/snyk-sca.html || true
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-sca.html', reportName: 'Snyk Open Source (SCA)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      }
    }

    // --- Build de l'image Docker (si Dockerfile présent) ---
    stage('Build Image (si Dockerfile présent)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          IMAGE="demoapp:${BUILD_NUMBER}"
          docker build -t "$IMAGE" .
          echo "$IMAGE" > image.txt
        '''
        archiveArtifacts artifacts: 'image.txt', fingerprint: true
      }
    }

    // --- Snyk Container : scan de l'image (remplace Trivy) ---
    stage('Snyk Container (image)') {
      when { expression { fileExists('image.txt') } }
      options { timeout(time: 5, unit: 'MINUTES') }
      steps {
        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
          sh '''
            set -eux
            IMAGE=$(cat image.txt)
            mkdir -p reports

            # Test de l'image
            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              snyk/snyk-cli:stable snyk container test "$IMAGE" \
                --org="$SNYK_ORG" \
                --file=Dockerfile \
                --severity-threshold=medium \
                --json-file-output=/tmp/snyk-container.json || true
            docker cp $(docker ps -alq):/tmp/snyk-container.json reports/snyk-container.json || true

            # Monitor pour suivi continu dans Snyk
            docker run --rm \
              -e SNYK_TOKEN="$SNYK_TOKEN" \
              -v /var/run/docker.sock:/var/run/docker.sock \
              snyk/snyk-cli:stable snyk container monitor "$IMAGE" \
                --org="$SNYK_ORG" --file=Dockerfile || true

            # HTML
            docker run --rm -v "$PWD":/work \
              snyk/snyk-to-html -i /work/reports/snyk-container.json -o /work/reports/snyk-container.html || true
          '''
        }
        publishHTML(target: [reportDir: 'reports', reportFiles: 'snyk-container.html', reportName: 'Snyk Container (Image)', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '**/target/*.jar, **/*.log', allowEmptyArchive: true
    }
  }
}
