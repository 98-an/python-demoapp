pipeline {
  agent any
  options { skipDefaultCheckout(true); timestamps() }

  environment {
    // Si tu veux pousser l'image sur GHCR, change 98-an par ton user GitHub
    REGISTRY       = "ghcr.io"
    REGISTRY_IMAGE = "ghcr.io/98-an/python-demoapp"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout([$class: 'GitSCM',
          branches: [[name: '*/master']],
          userRemoteConfigs: [[url: 'https://github.com/98-an/python-demoapp.git', credentialsId: 'git-cred']]
        ])
        script {
          env.SHORT_COMMIT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.LOCAL_IMAGE  = "demoapp:${env.SHORT_COMMIT}"
          env.PUSH_IMAGE   = "${REGISTRY_IMAGE}:${env.SHORT_COMMIT}"
        }
      }
    }

    stage('Setup Python') {
      steps {
        sh '''
          sudo apt-get update -y
          sudo apt-get install -y python3-venv python3-pip
          python3 -m venv .venv
          . .venv/bin/activate
          pip install -U pip
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            pip install flask gunicorn pytest
          fi
        '''
      }
    }

    stage('Tests & Bandit') {
      steps {
        sh '''
          . .venv/bin/activate
          pytest -q || true
          pip install bandit
          bandit -q -r . || true
        '''
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh 'docker run --rm -v $PWD:/workspace hadolint/hadolint hadolint /workspace/Dockerfile || true'
      }
    }

    stage('Build Docker image') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh 'docker build -t $LOCAL_IMAGE .'
      }
    }

    stage('Push image to GHCR (optionnel)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'ghcr-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_PAT')]) {
          sh '''
            echo "$GH_PAT" | docker login ghcr.io -u "$GH_USER" --password-stdin
            docker tag $LOCAL_IMAGE $PUSH_IMAGE
            docker push $PUSH_IMAGE
          '''
        }
      }
    }

    stage('Deploy local (EC2)') {
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          docker rm -f demoapp || true
          docker run -d --name demoapp -p 5000:5000 $LOCAL_IMAGE
        '''
      }
    }
  }
}
