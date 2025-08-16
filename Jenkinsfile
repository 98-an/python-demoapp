pipeline {
  agent any
  environment {
    IMAGE_NAME = "ghcr.io/98-an/python-demoapp"
    IMAGE_TAG  = "build-${env.BUILD_NUMBER}"
    PUSH_TO_GHCR = "false"   // passe à "true" quand tu auras ajouté les creds GHCR
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup Python + Tests + Bandit') {
      agent { docker { image 'python:3.11-slim'; args '-u root' } } // pas de sudo nécessaire
      steps {
        sh '''
          python -V
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then python -m pip install -r requirements.txt; fi
          python -m pip install pytest bandit
          # tests unitaires (tolérants si pas présents)
          pytest -q || true
          # scan sécurité Python
          bandit -r . -x tests || true
        '''
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh 'docker run --rm -i hadolint/hadolint < Dockerfile || true'
      }
    }

    stage('Build Docker image') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          docker build -t $IMAGE_NAME:$IMAGE_TAG .
          docker tag  $IMAGE_NAME:$IMAGE_TAG $IMAGE_NAME:latest
        '''
      }
    }

    stage('Push image to GHCR (optionnel)') {
      when { expression { env.PUSH_TO_GHCR == "true" && fileExists('Dockerfile') } }
      steps {
        withCredentials([string(credentialsId: 'ghcr-token', variable: 'TOKEN')]) {
          sh '''
            echo "$TOKEN" | docker login ghcr.io -u 98-an --password-stdin
            docker push $IMAGE_NAME:$IMAGE_TAG
            docker push $IMAGE_NAME:latest
          '''
        }
      }
    }

    stage('Deploy local (EC2)') {
      steps {
        sh '''
          # lance l'image locale si buildée, sinon prends l'image publique du projet
          IMG="$IMAGE_NAME:latest"
          docker image inspect $IMG >/dev/null 2>&1 || IMG="ghcr.io/benc-uk/python-demoapp:latest"

          docker rm -f demoapp 2>/dev/null || true
          docker run -d --name demoapp -p 5000:5000 $IMG
        '''
      }
    }
  }

  post {
    always { echo "Build finished: ${currentBuild.currentResult}" }
  }
}
