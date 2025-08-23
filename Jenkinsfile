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

    stage('OWASP Dependency Check') {
      steps {
        dependencyCheck additionalArguments: '--scan ./ --format XML --enableExperimental', odcInstallation: 'DC'
        dependencyCheckPublisher pattern: 'dependency-check-report.xml'
      }
    }

    stage('Docker Build') {
      steps {
        sh 'docker build -f container/Dockerfile -t yasdevsec/python-demoapp:v2 .'
      }
    }

    stage('Trivy Scan') {
      steps {
        script {
          def dockerImage = "yasdevsec/python-demoapp:v2"
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
            docker push yasdevsec/python-demoapp:v2
          '''
        }
      }
    }

    stage('Deploy Container') {
      steps {
        sh '''
          # Supprime tous les conteneurs basés sur l'image poussée
          sudo docker ps -aq --filter "ancestor=yasdevsec/python-demoapp:v2" | xargs -r sudo docker rm -f

          # Lance le nouveau conteneur
          sudo docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2
          echo "Application démarrée sur http://13.50.222.204:5000"
        '''
      }
    }

    stage('OWASP ZAP Full Scan') {
      steps {
        script {
          def target_url = "http://13.50.222.204:5000"
          sh """
            sudo docker run --rm -v \$PWD:/zap/wrk:rw zaproxy/zap-stable zap-full-scan.py \\
              -t ${target_url} -r zap-full-report.html -a
          """
        }
        publishHTML(target: [
          allowMissing: false,
          alwaysLinkToLastBuild: true,
          keepAll: true,
          reportDir: '.',
          reportFiles: 'zap-full-report.html',
          reportName: 'OWASP ZAP Full Scan Report'
        ])
      }
    }
  }
}
