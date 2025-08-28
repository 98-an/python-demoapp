pipeline {
  agent any

  stages {

    stage('Git Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Run SonarQube Analysis') {
      steps {
        script {
          def scannerHome = tool name: 'sonar-qube', type: 'hudson.plugins.sonar.SonarRunnerInstallation'
          withSonarQubeEnv('sonar-server') {
            sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectKey=pythonapp -Dsonar.sources=src"
          }
        }
      }
    }

    stage('Code Quality Gate') {
      steps {
        script {
          waitForQualityGate abortPipeline: false, credentialsId: 'sonar-token'
        }
      }
    }

    stage('OWASP Dependency Check') {
      steps {
        dependencyCheck additionalArguments: '--scan ./ --format XML --enableExperimental', odcInstallation: 'DC'
        dependencyCheckPublisher pattern: 'dependency-check-report.xml'
      }
    }

    stage('Docker Build') {
      steps {
        sh 'docker build -f container/Dockerfile -t yasdevsec/python-demoapp:v4 .'
      }
    }

    stage('Trivy Scan') {
      steps {
        script {
          def dockerImage = "yasdevsec/python-demoapp:v4"
          sh "trivy image ${dockerImage} --no-progress --severity HIGH,CRITICAL"
        }
      }
    }

    stage('Docker Push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub', passwordVariable: 'PASS', usernameVariable: 'USER')]) {
          sh '''
            echo "$PASS" | docker login -u "$USER" --password-stdin
            docker images | grep yasdevsec/python-demoapp || true
            docker push yasdevsec/python-demoapp:v4
          '''
        }
      }
    }

    stage('Deploy Container') {
      steps {
        sh '''
          # Supprime tous les conteneurs basés sur l'image poussée
          sudo docker ps -aq --filter "ancestor=yasdevsec/python-demoapp:v4" | xargs -r sudo docker rm -f

          # Lance le nouveau conteneur
          sudo docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v4
          echo "Application démarrée sur http://13.50.222.204:5000"
        '''
      }
    }

    stage('OWASP ZAP Baseline') {
      steps {
        script {
          sh '''
            set -e
            VOL="zap-wrk-${JOB_NAME}-${BUILD_NUMBER}"
            sudo docker volume create "$VOL" >/dev/null
            sudo docker rm -f zap-scan >/dev/null 2>&1 || true

            # Lancer ZAP, écrire le rapport dans /zap/wrk (nom de fichier RELATIF)
            sudo docker run --name zap-scan --network=host \
              --user 0:0 -v "$VOL":/zap/wrk:rw \
              zaproxy/zap-stable zap-baseline.py \
              -t http://13.50.222.204:5000 \
              -r scan-report.html -a || true

            # Récupérer le rapport
            sudo docker cp zap-scan:/zap/wrk/scan-report.html .

            # Nettoyage
            sudo docker rm -f zap-scan >/dev/null 2>&1 || true
            sudo docker volume rm "$VOL" >/dev/null 2>&1 || true
          '''
        }
        publishHTML(target: [
          allowMissing: false,
          alwaysLinkToLastBuild: true,
          keepAll: true,
          reportDir: '.',
          reportFiles: 'scan-report.html',
          reportName: 'OWASP ZAP Baseline Scan Report'
        ])
      }
    }

  }
}
