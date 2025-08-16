pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
    buildDiscarder(logRotator(numToKeepStr: '20'))
    disableConcurrentBuilds()
    timeout(time: 20, unit: 'MINUTES')   // timeout global
  }

  environment {
    // Chemin du Dockerfile (change si besoin)
    DOCKERFILE_PATH = 'Dockerfile'
    // Nom image (tag final construit plus bas)
    DOCKER_IMAGE    = 'python-demoapp'
    // (Optionnel) ton org Snyk
    SNYK_ORG        = '98-an'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout([$class: 'GitSCM',
          branches: [[name: '*/master']],
          userRemoteConfigs: [[url: 'https://github.com/98-an/python-demoapp.git', credentialsId: 'git-cred']],
          extensions: [[$class: 'CloneOption', shallow: true, depth: 1, noTags: true]]
        ])
        script {
          env.GIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        }
      }
    }

    stage('Setup Python + Tests + Bandit') {
      options { timeout(time: 5, unit: 'MINUTES') }
      agent {
        docker {
          image 'python:3.11-slim'
          // cache pip + accès Docker du host (pour les étapes suivantes)
          args "-u 0:0 -v $WORKSPACE/.pip-cache:/root/.cache/pip -v /var/run/docker.sock:/var/run/docker.sock"
        }
      }
      steps {
        sh '''
          set -eux
          echo "WD: $(pwd)"
          # trouver un requirements*.txt (à n'importe quel niveau <= 3)
          REQ=$(find . -maxdepth 3 -type f -iname "requirements*.txt" -print -quit || true)
          if [ -z "$REQ" ]; then echo "❌ Aucun requirements*.txt trouvé"; exit 1; fi

          python --version
          pip install --upgrade pip

          # 1ère tentative : wheels binaires (rapide)
          if ! pip install --prefer-binary -r "$REQ"; then
            # fallback si une lib (ex: psutil) exige une compilation
            apt-get update
            apt-get install -y --no-install-recommends gcc python3-dev
            pip install --no-cache-dir -r "$REQ"
          fi

          pip install pytest bandit
          pytest -q || true
          bandit -q -r .
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: '**/pytest*.xml, **/junit*.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: '.bandit*, bandit*.txt'
        }
      }
    }

    stage('Hadolint (Dockerfile)') {
      options { timeout(time: 2, unit: 'MINUTES') }
      when { expression { fileExists(env.DOCKERFILE_PATH) } }
      steps {
        sh '''
          set -e
          docker run --rm -i hadolint/hadolint < "$DOCKERFILE_PATH" | tee hadolint.txt || true
        '''
      }
      post { always { archiveArtifacts artifacts: 'hadolint.txt', allowEmptyArchive: true } }
    }

    stage('Snyk (SCA)') {
      options { timeout(time: 5, unit: 'MINUTES') }
      steps {
        script {
          // essaie de récupérer le token 'snyk-token' (Secret text). Si absent, on skippe proprement.
          def hasSnyk = false
          try {
            withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
              hasSnyk = (env.SNYK_TOKEN?.trim())
              if (hasSnyk) {
                sh """
                  set -eux
                  curl -fsSL https://static.snyk.io/cli/latest/snyk-linux -o /usr/local/bin/snyk
                  chmod +x /usr/local/bin/snyk
                  REQ=\$(find . -maxdepth 3 -type f -iname "requirements*.txt" -print -quit)
                  snyk auth "\$SNYK_TOKEN"
                  snyk test --org="${SNYK_ORG}" --file="\$REQ" --package-manager=pip || true
                """
              }
            }
          } catch (ignored) { hasSnyk = false }
          if (!hasSnyk) { echo 'Snyk non configuré (credential "snyk-token" manquant) → étape ignorée.' }
        }
      }
    }

    stage('Build Docker image') {
      options { timeout(time: 5, unit: 'MINUTES') }
      when { expression { fileExists(env.DOCKERFILE_PATH) } }
      steps {
        script {
          // nom par défaut local si pas de GHCR_USER défini via credentials à l’étape suivante
          env.IMAGE_TAG = "ghcr.io/${env.GHCR_USER ?: 'local'}/${env.DOCKER_IMAGE}:${env.GIT_SHORT}"
        }
        sh '''
          set -eux
          docker build -t "$IMAGE_TAG" -f "$DOCKERFILE_PATH" .
        '''
      }
    }

    stage('Push image to GHCR (optionnel)') {
      options { timeout(time: 3, unit: 'MINUTES') }
      steps {
        script {
          def pushed = false
          try {
            withCredentials([usernamePassword(credentialsId: 'ghcr-creds', usernameVariable: 'GHCR_USER', passwordVariable: 'GHCR_TOKEN')]) {
              sh '''
                set -eux
                echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
                docker push "$IMAGE_TAG"
              '''
            }
            pushed = true
          } catch (ignored) {
            echo 'GHCR non configuré (credential "ghcr-creds" absent) → on ne pousse pas.'
          }
          if (!pushed) { echo "Image construite localement: ${env.IMAGE_TAG}" }
        }
      }
    }

    stage('Deploy local (EC2)') {
      options { timeout(time: 2, unit: 'MINUTES') }
      steps {
        sh '''
          set -eux
          docker rm -f demoapp || true
          # utilise l'image buildée, sinon l'officielle publique
          IMG="${IMAGE_TAG:-ghcr.io/benc-uk/python-demoapp:latest}"
          docker run -d --name demoapp -p 5000:5000 "$IMG"
        '''
      }
    }
  }

  post {
    always {
      cleanWs(deleteDirs: true)
    }
  }
}
