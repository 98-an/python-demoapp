pipeline {
  agent any

  parameters {
    choice(name: 'SCAN_TYPE', choices: ['Baseline', 'APIS', 'Full'], description: 'Type de scan OWASP ZAP')
    string(name: 'TARGET', defaultValue: 'http://13.50.222.204:5000', description: 'URL cible à scanner')
    string(name: 'USERNAME', defaultValue: '', description: 'Utilisateur pour authentification')
    string(name: 'PASSWORD', defaultValue: '', description: 'Mot de passe pour authentification')
    booleanParam(name: 'GENERATE_REPORT', defaultValue: true, description: 'Générer un rapport HTML')
  }

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
          sudo docker ps -aq --filter "ancestor=yasdevsec/python-demoapp:v2" | xargs -r sudo docker rm -f
          sudo docker run -d --name py -p 5000:5000 yasdevsec/python-demoapp:v2
          echo "Application démarrée sur http://13.50.222.204:5000"
        '''
      }
    }

    stage('Prepare OWASP ZAP Container') {
      steps {
        sh '''
          sudo docker pull zaproxy/zap-stable
          sudo docker rm -f owasp || true
          sudo docker run -d --name owasp -v /tmp/jenkins_zap_home:/home/zap zaproxy/zap-stable tail -f /dev/null
        '''
      }
    }

    stage('Prepare Work Directory') {
      when {
        expression { return params.GENERATE_REPORT }
      }
      steps {
        sh 'sudo docker exec owasp mkdir -p /zap/wrk'
      }
    }

    stage('Setup Authentication Script') {
      when {
        expression { return params.USERNAME != "" && params.PASSWORD != "" }
      }
      steps {
        script {
          def authScript = '''function authenticate(helper, paramsValues, credentials) {
            var requestUri = new URI(paramsValues.get("loginUrl"), false);
            var requestMethod = "POST";
            var requestBody = "username=" + credentials.get("username") + "&password=" + credentials.get("password");
            var requestMessage = helper.prepareMessage();
            requestMessage.getRequestHeader().setURI(requestUri);
            requestMessage.getRequestHeader().setMethod(requestMethod);
            requestMessage.setRequestBody(requestBody);
            helper.sendAndReceive(requestMessage);
            var responseMessage = requestMessage.getResponseBody().toString();
            return responseMessage.contains("Login Successful");
          }'''
          writeFile file: 'auth-script.js', text: authScript
          sh 'sudo docker cp auth-script.js owasp:/zap/scripts/'
        }
      }
    }

    stage('Run OWASP ZAP Scan') {
      steps {
        script {
          def scanCmd = ''
          if (params.SCAN_TYPE == 'Baseline') {
            scanCmd = "zap-baseline.py -t ${params.TARGET} -r /zap/wrk/report.html"
          } else if (params.SCAN_TYPE == 'APIS') {
            scanCmd = "zap-api-scan.py -t ${params.TARGET} -r /zap/wrk/report.html"
          } else if (params.SCAN_TYPE == 'Full') {
            scanCmd = "zap-full-scan.py -t ${params.TARGET} -r /zap/wrk/report.html"
          }
          sh "sudo docker exec owasp ${scanCmd}"
        }
      }
    }

    stage('Copy Report to Workspace') {
      when {
        expression { return params.GENERATE_REPORT }
      }
      steps {
        sh 'sudo docker cp owasp:/zap/wrk/report.html ./'
      }
    }

    stage('Publish ZAP Report') {
      when {
        expression { return params.GENERATE_REPORT }
      }
      steps {
        publishHTML(target: [
          reportName: 'OWASP ZAP Scan Report',
          reportDir: '.',
          reportFiles: 'report.html',
          keepAll: true,
          alwaysLinkToLastBuild: true
        ])
      }
    }
  }

  post {
    always {
      sh '''
        sudo docker stop owasp || true
        sudo docker rm owasp || true
      '''
      cleanWs()
    }
  }
}
