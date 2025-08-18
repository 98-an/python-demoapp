pipeline {
  agent any
  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
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
  }

  post {
    always {
      sh '''
        set -eux
        BR="${BRANCH_NAME:-$(git symbolic-ref -q --short HEAD || git name-rev --name-only HEAD || echo detached)}"
        {
          echo "Branch: ${BR}"
          echo "Commit: $(git rev-parse HEAD || true)"
          echo "Is shallow: $(git rev-parse --is-shallow-repository || true)"
        } > checkout-info.txt
      '''
      archiveArtifacts artifacts: 'Jenkinsfile, checkout-info.txt', allowEmptyArchive: true
    }
  }
}
