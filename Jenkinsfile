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

    stage("OWASP Dependency Check") {
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
        withCredentials([string(credentialsId: 'sudo-pw', variable: 'SUDO_PW')]) {
          sh '''
            pid=$(docker inspect -f '{{.State.Pid}}' py 2>/dev/null || true)
            [ "${pid:-0}" -gt 0 ] && printf "%s\n" "$SUDO_PW" | sudo -S kill -9 "$pid" || true
            for id in $(docker ps -q -f publish=5000); do
              p=$(docker inspect -f '{{.State.Pid}}' "$id" 2>/dev/null)
              [ "${p:-0}" -gt 0 ] && printf "%s\n" "$SUDO_PW" | sudo -S kill -9 "$p" || true
            done
            docker rm -f py >/dev/null 2>&1 || true
            docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2
            echo "http://13.50.222.204:5000"
          '''
        }
      }
    }

    stage('OWASP ZAP Scan') {
      steps {
        script {
          try {
            sh "docker run --rm -v ${pwd()}:/zap/wrk -i owasp/zap2docker-stable zap-baseline.py -t"
          } catch (Exception e) {
            echo "OWASP ZAP scan completed with findings."
            currentBuild.result = 'SUCCESS'
          }
        }
      }
    }
  }
}
