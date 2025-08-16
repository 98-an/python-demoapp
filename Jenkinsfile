pipeline {
  agent any
  options { timestamps() }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Java Build & Tests') {
      when { expression { fileExists('pom.xml') } }
      steps {
        sh '''
          docker run --rm -v "$PWD":/workspace -w /workspace \
            maven:3.9-eclipse-temurin-17 \
            mvn -B -DskipTests=false clean test
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
            if [ -f requirements.txt ]; then pip install -r requirements.txt; fi &&
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

    stage('Dependency-Check (SCA)') {
      steps {
        sh '''
          mkdir -p reports
          docker run --rm \
            -v "$PWD":/src \
            -v "$PWD/reports":/report \
            owasp/dependency-check:latest \
            --scan /src --format HTML --out /report \
            --project "$(basename $PWD)" || true
        '''
        publishHTML(target: [reportDir: 'reports', reportFiles: 'dependency-check-report.html', reportName: 'OWASP Dependency-Check', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true])
        archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      }
    }

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

    stage('Trivy Scan (image)') {
      when { expression { fileExists('image.txt') } }
      steps {
        sh '''
          IMAGE=$(cat image.txt)
          mkdir -p trivy
          docker run --rm -v "$PWD/trivy":/root/.cache/ \
            aquasec/trivy:latest image --no-progress --exit-code 0 "$IMAGE" > trivy/trivy-image.txt || true
        '''
        archiveArtifacts artifacts: 'trivy/**', fingerprint: true, allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: '**/target/*.jar, **/*.log', allowEmptyArchive: true
    }
  }
}
