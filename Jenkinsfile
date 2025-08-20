pipeline {
    agent any

    stages {
        stage('Test') {
            steps {
                echo 'Hello, Jenkins pipeline is working!'
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
