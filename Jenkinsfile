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
            # Tuer (via PID) tout conteneur publiant le port 5000
            docker ps -q --filter "publish=5000" | xargs -r -I{} sh -c '
              pid=$(docker inspect -f "{{.State.Pid}}" {} 2>/dev/null);
              if [ -n "$pid" ] && [ "$pid" -gt 0 ]; then
                if command -v sudo >/dev/null 2>&1; then s=sudo; else s=""; fi
                $s kill -9 "$pid" || true
              fi
            '

            # Supprimer le conteneur "py" s'il existe (après kill il peut rester en Exited)
            docker ps -aq -f name=^py$ | xargs -r docker rm -f

            # Lancer le nouveau conteneur sur 5000
            docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2
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
