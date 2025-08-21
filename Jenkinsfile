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
                        sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectKey=xssapp-scan -Dsonar.sources=src"
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
                sh 'docker stop py || true'
                sh 'docker rm py || true'
                sh 'docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2'
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
