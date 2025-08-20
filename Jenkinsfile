pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                echo 'Step 1: Build started'
                sleep 2
            }
        }
        stage('Test') {
            steps {
                echo 'Step 2: Running tests'
                sleep 2
            }
        }
        stage('Deploy') {
            steps {
                echo 'Step 3: Deploying application'
                sleep 2
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
