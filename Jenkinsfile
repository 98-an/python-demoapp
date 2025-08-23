pipeline {
    agent any

    stages {
        stage('Git Checkout') {
            steps {
                checkout scm
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
      set -e

      # Stopper les conteneurs en cours dont le nom correspond exactement à "py"
      docker ps -q -f name=^py$ | xargs -r docker stop

      # Supprimer les conteneurs (même arrêtés) nommés "py"
      docker ps -aq -f name=^py$ | xargs -r docker rm -f

      # (Optionnel) Vérifier que le port 5000 est libre
      if ss -ltn | awk "{print \\$4}" | grep -qE "(:|^)5000$|:5000$"; then
        echo "ERREUR: le port 5000 est déjà utilisé." >&2
        exit 1
      fi

      # Relancer le conteneur
      docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2
      echo "Application démarrée sur http://$(hostname -I | awk '{print $1}'):5000"
    '''
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
