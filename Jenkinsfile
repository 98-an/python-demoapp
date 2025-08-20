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
                        sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectKey=xssapp-scan"
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
                sh 'docker build -t yasdevsec/python-demoapp:v2 .'
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
                withCredentials([string(credentialsId: 'dockerhub-pwd', variable: 'dockerhubpwd')]) {
                    sh 'docker login -u yasdevsec -p ${dockerhubpwd}'
                    sh 'docker push yasdevsec/python-demoapp:v2'
                }
            }
        }
        stage('Deploy Container') {
            steps {
                sh 'docker stop vulnlab'
                sh 'docker rm vulnlab'
                sh 'docker run -d --name vulnlab -p 5000:80 yasdevsec/python-demoapp:v2'
            }
        }
        stage('OWASP ZAP Scan') {
            steps {
                script {
                    try {
                        sh "docker run --rm -v \${pwd}:/zap/wrk -i owasp/zap2docker-stable zap-baseline.py -t http://13.50.222.204:5000"
