pipeline {
  agent any

  options {
    skipDefaultCheckout(true)     // on contrôle le checkout nous-mêmes
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 25, unit: 'MINUTES')
  }

  stages {

    stage('Checkout') {
      steps {
        // Récupère le repo contenant ce Jenkinsfile
        checkout scm

        // Assure un historique complet (utile pour Gitleaks/Semgrep/Sonar)
        sh '''
          set -eux
          # Affiche quelques infos
          git remote -v || true
          git rev-parse HEAD

          # Si le checkout est shallow (propre à Jenkins), on "unshallow"
          if git rev-parse --is-shallow-repository >/dev/null 2>&1; then
            git fetch --unshallow --tags --prune
          fi

          # Marque le workspace comme "safe" pour Git (utile quand on lancera git dans des conteneurs root)
          git config --global --add safe.directory "$PWD" || :

          # Prépare le dossier des rapports pour les stages suivants
          rm -rf reports && mkdir -p reports
        '''

        // Expose un SHA court (pratique pour tagger des images, logs, etc.)
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          echo "Checked out commit: ${env.SHORT_SHA}"
        }
      }
    }

  }

  post {
    always {
      // (optionnel) archive le Jenkinsfile + un petit log de l’état Git
      sh '''
        set -eux
        {
          echo "Branch: $(git rev-parse --abbrev-ref HEAD || true)"
          echo "Commit: $(git rev-parse HEAD || true)"
          echo "Is shallow: $(git rev-parse --is-shallow-repository || true)"
        } > checkout-info.txt
      '''
      archiveArtifacts artifacts: 'Jenkinsfile, checkout-info.txt', allowEmptyArchive: true
    }
  }
}
