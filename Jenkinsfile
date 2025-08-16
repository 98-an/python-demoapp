pipeline {
  agent any
  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 15, unit: 'MINUTES') // garde une limite globale
  }
  environment {
    GH_USER = '98-an'
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script { env.GIT_SHORT = sh(returnStdout:true, script:'git rev-parse --short HEAD').trim() }
      }
    }

    stage('Setup Python + Tests + Bandit') {
      options { timeout(time: 4, unit: 'MINUTES') }
      agent { docker { image 'python:3.11-slim'; args '-v $WORKSPACE/.pip-cache:/root/.cache/pip' } }
      steps {
        sh '''
          python --version
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest bandit
          pytest -q || true
          bandit -q -r .
        '''
      }
    }

    stage('Hadolint (Dockerfile)') {
      options { timeout(time: 2, unit: 'MINUTES') }
      agent { docker { image 'hadolint/hadolint:latest' } }
      when { expression { fileExists('Dockerfile') } }
      steps { sh 'hadolint -t warning Dockerfile || true' }
    }

    stage('Snyk (SCA)') {
      options { timeout(time: 4, unit: 'MINUTES') }
      environment { SNYK_TOKEN = credentials('snyk-token') } // crée ce credential "Secret text"
      steps {
        sh '''
          docker run --rm -v "$PWD":/app -w /app -e SNYK_TOKEN snyk/snyk:docker \
            snyk test --package-manager=pip --severity-threshold=high --prune-repeated-subdependencies || true
        '''
      }
    }

    stage('Build Docker image') {
      options { timeout(time: 5, unit: 'MINUTES') }
      when { expression { fileExists('Dockerfile') } }
      steps {
        sh '''
          IMG="ghcr.io/${GH_USER}/python-demoapp:${GIT_SHORT}"
          docker build -t "$IMG" .
          echo "Built $IMG"
        '''
      }
    }
  }
}
