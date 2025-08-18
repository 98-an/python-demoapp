pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }
  environment {
    IMAGE_NAME        = "demoapp:${env.BUILD_NUMBER}"
    S3_BUCKET         = 'cryptonext-reports-98an'
    AWS_REGION        = 'eu-north-1'
    DAST_TARGET       = 'http://16.170.87.165:5000'

    // SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'
  }


  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          set -eux
          git remote -v || true
          git rev-parse HEAD
          if git rev-parse --is-shallow-repository >/dev/null 2>&1; then
            git fetch --unshallow --tags --prune
          fi
          git config --global --add safe.directory "$PWD" || :
          rm -rf reports && mkdir -p reports
        '''
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          echo "Checked out commit: ${env.SHORT_SHA}"
        }
      }
    }

    stage('Python Lint & Tests & Bandit') {
      // on déclenche si au moins un des fichiers de conf existe
      when { expression { fileExists('src/app/requirements.txt') || fileExists('src/requirements.txt') || fileExists('requirements.txt') || fileExists('pyproject.toml') } }
      steps {
        sh '''
          set -eux

          docker run --rm -v "$PWD":/ws -w /ws python:3.11-slim bash -lc '
            set -eux
            python -m pip install --upgrade pip

            # === Dépendances selon ton arbo ===
            if   [ -f src/app/requirements.txt ]; then
                 pip install --prefer-binary -r src/app/requirements.txt
            elif [ -f src/requirements.txt ]; then
                 pip install --prefer-binary -r src/requirements.txt
            elif [ -f requirements.txt ]; then
                 pip install --prefer-binary -r requirements.txt
            fi

            # Outils qualité
            pip install --prefer-binary pytest pytest-cov flake8 bandit

            # Lint (ne casse pas le build)
            flake8 || :

            # Tests (écrit tout dans /ws/reports)
            pytest --maxfail=1 \
              --cov=. \
              --cov-report=xml:/ws/reports/coverage.xml \
              --junitxml=/ws/reports/pytest-report.xml || :

            # SAST Python
            bandit -r . -f html -o /ws/reports/bandit-report.html || :
          '

          # Fallback si aucun test n’a tourné (pour que 'junit' ait un fichier)
          test -f reports/pytest-report.xml || echo "<testsuite tests=\\"0\\"></testsuite>" > reports/pytest-report.xml
        '''

        // Publier les rapports
        junit allowEmptyResults: true, testResults: 'reports/pytest-report.xml'
        publishHTML(target: [
          reportDir: 'reports',
          reportFiles: 'bandit-report.html',
          reportName: 'Bandit - Python SAST',
          keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
        ])
      }
    }

  }

  post {
    always {
      // petit récap checkout
      sh '''
        set -eux
        BR="${BRANCH_NAME:-$(git symbolic-ref -q --short HEAD || git name-rev --name-only HEAD || echo detached)}"
        {
          echo "Branch: ${BR}"
          echo "Commit: $(git rev-parse HEAD || true)"
          echo "Is shallow: $(git rev-parse --is-shallow-repository || true)"
        } > checkout-info.txt
      '''
      archiveArtifacts artifacts: 'Jenkinsfile, checkout-info.txt, reports/', allowEmptyArchive: true
    }
  }
}
