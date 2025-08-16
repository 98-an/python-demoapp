pipeline {
  agent any
  options { timestamps(); ansiColor('xterm') }

  environment {
    IMAGE_NAME = "demoapp:ci"
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Python tests + SCA (pip-audit)') {
      steps {
        script {
          // On exécute dans un conteneur Python → pas besoin que Python soit installé dans Jenkins
          docker.image('python:3.11-slim').inside {
            sh '''
              python -V
              pip install --no-input --upgrade pip
              if [ -f requirements.txt ]; then pip install --no-input -r requirements.txt; fi
              pip install --no-input pytest pytest-cov pip-audit
              pytest -q || true
              pip-audit -f cyclonedx -o pip-audit.json || true
            '''
            archiveArtifacts artifacts: 'pip-audit.json', allowEmptyArchive: true
            junit allowEmptyResults: true, testResults: '**/pytest*.xml'
          }
        }
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh 'docker run --rm -i hadolint/hadolint < Dockerfile || true'
      }
    }

    stage('Build image') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh 'docker build -t ${IMAGE_NAME} .'
      }
    }

    stage('Trivy scan (image)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:latest image --no-progress --format table ${IMAGE_NAME} || true
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts allowEmptyArchive: true, artifacts: '**/bandit.txt,**/pip-audit.json'
    }
  }
}
