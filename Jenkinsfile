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
    sh '''
      set -euo pipefail

      IMAGE="yasdevsec/python-demoapp:v2"
      NAME="py-${BUILD_NUMBER}"
      LABELS="--label app=python-demoapp --label owner=jenkins --label job=${JOB_NAME:-unknown} --label build=${BUILD_NUMBER}"

      # Choisir un port libre en partant de 5000
      PORT=5000
      while ss -ltn | awk '{print $4}' | grep -qE "(:|^)${PORT}$|:${PORT}$"; do
        PORT=$((PORT+1))
      done

      # Lancer SANS arrêter les autres conteneurs
      docker run -d --name "${NAME}" ${LABELS} -p ${PORT}:5000 ${IMAGE}

      # IP publique EC2 (IMDSv2). Si indispo, on met ton IP connue.
      TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
      PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || echo "13.50.222.204")

      echo "Application démarrée sur http://${PUBLIC_IP}:${PORT}"
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
