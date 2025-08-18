pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    // --- Project
    REPORT_DIR      = 'reports'
    IMAGE_NAME      = 'demoapp'
    DOCKERFILE      = 'container/Dockerfile'   // mets 'Dockerfile' si c’est ton cas

    // --- SonarCloud
    SONAR_HOST_URL    = 'https://sonarcloud.io'
    SONAR_ORG         = '98-an'
    SONAR_PROJECT_KEY = '98-an_python-demoapp'

    // --- S3
    AWS_REGION  = 'eu-north-1'
    S3_BUCKET   = 'cryptonext-reports-98an'    // nom exact du bucket

    // --- DAST (optionnel) : exemple http://<PUBLIC_IP>:5000
    DAST_TARGET = 'http://16.170.87.165:5000'  // renseigne une URL pour activer ZAP baseline
  }

  stages {

    stage('Checkout') {
      steps {
        checkout([$class: 'GitSCM',
          branches: [[name: '*/master']],
          doGenerateSubmoduleConfigurations: false,
          extensions: [[$class: 'CloneOption', depth: 1, noTags: false, shallow: true]],
          userRemoteConfigs: [[
            url: 'https://github.com/98-an/python-demoapp.git',
            credentialsId: 'git-cred'
          ]]
        ])
        sh "mkdir -p ${REPORT_DIR}"
      }
    }

    stage('Python Lint & Tests & Bandit') {
      steps {
        sh """#!/usr/bin/env bash
set -eux
mkdir -p ${REPORT_DIR}
# si aucun test, on crée un test smoke pour produire un rapport
[ -d tests ] || { mkdir -p tests; printf 'def test_smoke():\\n    assert True\\n' > tests/test_smoke.py; }

docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim bash -lc '
  python -V
  pip install --no-cache-dir --upgrade pip
  [ -f src/requirements.txt ] && pip install --no-cache-dir -r src/requirements.txt || true
  pip install --no-cache-dir pytest pytest-cov flake8 bandit

  # Lint (non bloquant)
  flake8 src || true

  # Tests + couverture (XML pour Sonar)
  pytest -q --disable-warnings --maxfail=1 \\
    --cov=. --cov-report=xml:${REPORT_DIR}/coverage.xml \\
    --junitxml=${REPORT_DIR}/pytest-report.xml || true

  # SAST Python (HTML)
  bandit -r src -f html -o ${REPORT_DIR}/bandit-report.html || true
'
"""
      }
      post {
        always {
          junit "${REPORT_DIR}/pytest-report.xml"
          archiveArtifacts artifacts: "${REPORT_DIR}/coverage.xml, ${REPORT_DIR}/bandit-report.html", allowEmptyArchive: true
        }
      }
    }

    stage('SonarCloud') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh """#!/usr/bin/env bash
set -eux

docker run --rm \\
  -e SONAR_HOST_URL="${SONAR_HOST_URL}" \\
  -e SONAR_TOKEN="${SONAR_TOKEN}" \\
  -e SONAR_SCANNER_OPTS="-Xmx1024m" \\
  -e NODE_OPTIONS="--max-old-space-size=2048" \\
  -v "\$PWD":/usr/src \\
  sonarsource/sonar-scanner-cli:latest \\
  -Dsonar.organization="${SONAR_ORG}" \\
  -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \\
  -Dsonar.projectName="${SONAR_PROJECT_KEY}" \\
  -Dsonar.projectVersion="${BUILD_NUMBER}" \\
  -Dsonar.sources=. \\
  -Dsonar.python.version=3.11 \\
  -Dsonar.python.coverage.reportPaths=${REPORT_DIR}/coverage.xml \\
  -Dsonar.scm.provider=git \\
  -Dsonar.exclusions="/venv/,/.venv/,/node_modules/,/dist/,/build/" \\
  -Dsonar.javascript.exclusions="/.min.js,/dist/,/build/,/public/,/static/*" \\
  -Dsonar.css.exclusions="/.min.css,/dist/,/build/,/public/,/static/*" \\
  -Dsonar.javascript.node.maxspace=2048
"""
        }
      }
    }

    stage('Hadolint (Dockerfile)') {
      when { expression { fileExists(env.DOCKERFILE) } }
      steps {
        sh """#!/usr/bin/env bash
set -eux
docker run --rm -i hadolint/hadolint < "${DOCKERFILE}" || true
"""
      }
    }

    stage('Gitleaks (Secrets)') {
      steps {
        sh """#!/usr/bin/env bash
set -eux
docker run --rm -v "\$PWD":/repo zricethezav/gitleaks:latest detect -s /repo -f sarif -o /repo/${REPORT_DIR}/gitleaks.sarif || true

# conversion SARIF -> HTML simple
docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json,sys,html,os
p="reports/gitleaks.sarif"; out="reports/gitleaks.html"
if not os.path.exists(p):
  open(out,"w").write("<h3>Gitleaks</h3><p>No SARIF found.</p>")
  raise SystemExit(0)
s=json.load(open(p))
rows=[]
for r in s.get("runs",[]):
  for res in r.get("results",[]):
    msg=res.get("message",{}).get("text","")
    rule=res.get("ruleId","")
    sev=res.get("level","")
    loc="-"
    try:
      a=res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
      l=res["locations"][0]["physicalLocation"]["region"].get("startLine",0)
      loc=f"{a}:{l}"
    except Exception: pass
    rows.append((html.escape(sev),html.escape(rule),html.escape(loc),html.escape(msg)))
out_html=["<h3>Gitleaks (résumé)</h3><table border=1 cellpadding=4><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Message</th></tr>"]
for t in rows: out_html.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"%t)
out_html.append("</table>")
open(out,"w").write("\\n".join(out_html))
PY
"""
      }
      post {
        always {
          publishHTML(target: [reportDir: "${REPORT_DIR}", reportFiles: 'gitleaks.html', reportName: 'gitleaks'])
          archiveArtifacts artifacts: "${REPORT_DIR}/gitleaks.*", allowEmptyArchive: true
        }
      }
    }

    stage('Semgrep (SAST)') {
      steps {
        sh """#!/usr/bin/env bash
set -eux
docker run --rm -v "\$PWD":/src returntocorp/semgrep:latest semgrep --config p/ci --sarif --output /src/${REPORT_DIR}/semgrep.sarif --error --timeout 0 || true

docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json,sys,html,os
p="reports/semgrep.sarif"; out="reports/semgrep.html"
if not os.path.exists(p):
  open(out,"w").write("<h3>Semgrep</h3><p>No SARIF found.</p>")
  raise SystemExit(0)
s=json.load(open(p))
rows=[]
for r in s.get("runs",[]):
  for res in r.get("results",[]):
    msg=res.get("message",{}).get("text","")
    rule=res.get("ruleId","")
    sev=res.get("level","")
    loc="-"
    try:
      a=res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
      l=res["locations"][0]["physicalLocation"]["region"].get("startLine",0)
      loc=f"{a}:{l}"
    except Exception: pass
    rows.append((html.escape(sev),html.escape(rule),html.escape(loc),html.escape(msg)))
out_html=["<h3>Semgrep (résumé)</h3><table border=1 cellpadding=4><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Message</th></tr>"]
for t in rows: out_html.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"%t)
out_html.append("</table>")
open(out,"w").write("\\n".join(out_html))
PY
"""
      }
      post {
        always {
          publishHTML(target: [reportDir: "${REPORT_DIR}", reportFiles: 'semgrep.html', reportName: 'semgrep'])
          archiveArtifacts artifacts: "${REPORT_DIR}/semgrep.*", allowEmptyArchive: true
        }
      }
    }

    stage('Build Image (si Dockerfile présent)') {
      when { expression { fileExists(env.DOCKERFILE) } }
      steps {
        sh """#!/usr/bin/env bash
set -eux
docker build -f "${DOCKERFILE}" -t ${IMAGE_NAME}:${BUILD_NUMBER} .
echo "${IMAGE_NAME}:${BUILD_NUMBER}" > image.txt
"""
        archiveArtifacts artifacts: 'image.txt', allowEmptyArchive: false
      }
    }

    stage('Trivy FS (deps & conf)') {
      steps {
        sh """#!/usr/bin/env bash
set -eux
docker run --rm -v "\$PWD":/project aquasec/trivy:latest fs --scanners vuln,secret,config -f sarif -o /project/${REPORT_DIR}/trivy-fs.sarif /project || true

docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json,sys,html,os
p="reports/trivy-fs.sarif"; out="reports/trivy-fs.html"
if not os.path.exists(p):
  open(out,"w").write("<h3>Trivy FS</h3><p>No SARIF found.</p>")
  raise SystemExit(0)
s=json.load(open(p))
rows=[]
for r in s.get("runs",[]):
  for res in r.get("results",[]):
    msg=res.get("message",{}).get("text","")
    rule=res.get("ruleId","")
    sev=res.get("level","")
    loc="-"
    try:
      a=res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
      l=res["locations"][0]["physicalLocation"]["region"].get("startLine",0)
      loc=f"{a}:{l}"
    except Exception: pass
    rows.append((html.escape(sev),html.escape(rule),html.escape(loc),html.escape(msg)))
out_html=["<h3>Trivy FS</h3><table border=1 cellpadding=4><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Message</th></tr>"]
for t in rows: out_html.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"%t)
out_html.append("</table>")
open(out,"w").write("\\n".join(out_html))
PY
"""
      }
      post {
        always {
          publishHTML(target: [reportDir: "${REPORT_DIR}", reportFiles: 'trivy-fs.html', reportName: 'trivy-fs'])
          archiveArtifacts artifacts: "${REPORT_DIR}/trivy-fs.*", allowEmptyArchive: true
        }
      }
    }

    stage('Trivy Image (si image.txt)') {
      when { expression { return fileExists('image.txt') } }
      steps {
        sh """#!/usr/bin/env bash
set -eux
IMG="\$(cat image.txt)"
docker run --rm -v "\$PWD":/project aquasec/trivy:latest image -f sarif -o /project/${REPORT_DIR}/trivy-image.sarif "\$IMG" || true

docker run --rm -v "\$PWD":/ws -w /ws python:3.11-slim python - <<'PY'
import json,sys,html,os
p="reports/trivy-image.sarif"; out="reports/trivy-image.html"
if not os.path.exists(p):
  open(out,"w").write("<h3>Trivy Image</h3><p>No SARIF found.</p>")
  raise SystemExit(0)
s=json.load(open(p))
rows=[]
for r in s.get("runs",[]):
  for res in r.get("results",[]):
    msg=res.get("message",{}).get("text","")
    rule=res.get("ruleId","")
    sev=res.get("level","")
    loc="-"
    try:
      a=res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
      l=res["locations"][0]["physicalLocation"]["region"].get("startLine",0)
      loc=f"{a}:{l}"
    except Exception: pass
    rows.append((html.escape(sev),html.escape(rule),html.escape(loc),html.escape(msg)))
out_html=["<h3>Trivy Image</h3><table border=1 cellpadding=4><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Message</th></tr>"]
for t in rows: out_html.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"%t)
out_html.append("</table>")
open(out,"w").write("\\n".join(out_html))
PY
"""
      }
      post {
        always {
          publishHTML(target: [reportDir: "${REPORT_DIR}", reportFiles: 'trivy-image.html', reportName: 'trivy-image'])
          archiveArtifacts artifacts: "${REPORT_DIR}/trivy-image.*", allowEmptyArchive: true
        }
      }
    }

    stage('DAST - ZAP Baseline') {
      when { expression { return env.DAST_TARGET?.trim() } }
      steps {
        sh """#!/usr/bin/env bash
set -eux
# peut échouer selon le contexte, on ne bloque pas
docker run --rm -u root -v "\$PWD/${REPORT_DIR}":/zap/wrk:rw owasp/zap2docker-stable zap-baseline.py \\
  -t "${DAST_TARGET}" -r /zap/wrk/zap-baseline.html -I || true
"""
      }
      post {
        always {
          publishHTML(target: [reportDir: "${REPORT_DIR}", reportFiles: 'zap-baseline.html', reportName: 'ZAP - Baseline'])
          archiveArtifacts artifacts: "${REPORT_DIR}/zap-baseline.html", allowEmptyArchive: true
        }
      }
    }

    stage('Publish reports to S3') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh """#!/usr/bin/env bash
set -eux
export AWS_DEFAULT_REGION="${AWS_REGION}"

# Upload de tous les rapports + image.txt
docker run --rm \\
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \\
  -v "\$PWD":/ws -w /ws amazon/aws-cli s3 cp ${REPORT_DIR}/ s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/ \\
  --recursive || true

[ -f image.txt ] && docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \\
  -v "\$PWD":/ws -w /ws amazon/aws-cli s3 cp image.txt s3://${S3_BUCKET}/${JOB_NAME}/${BUILD_NUMBER}/ || true
"""
        }
      }
    }

    stage('Make presigned URL (1h)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-up', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh """#!/usr/bin/env bash
set -eux
export AWS_DEFAULT_REGION="${AWS_REGION}"
OUT="presigned-urls.txt"
: > "\$OUT"

list_files() {
  for f in ${REPORT_DIR}/.html ${REPORT_DIR}/.txt image.txt; do
    [ -f "\$f" ] && echo "\$f"
  done
}

for f in \$(list_files); do
  KEY="${JOB_NAME}/${BUILD_NUMBER}/\${f##*/}"
  URL=\$(docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \\
          amazon/aws-cli s3 presign "s3://${S3_BUCKET}/\$KEY" --expires-in 3600)
  echo "\$KEY -> \$URL" >> "\$OUT"
done

cat "\$OUT"
"""
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'presigned-urls.txt', allowEmptyArchive: true
        }
      }
    }

  } // stages

  post {
    always {
      archiveArtifacts artifacts: "${REPORT_DIR}/.html, ${REPORT_DIR}/.txt, ${REPORT_DIR}/.sarif, ${REPORT_DIR}/.json, image.txt", allowEmptyArchive: true
    }
  }
}
