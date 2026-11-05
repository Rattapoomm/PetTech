pipeline {
  agent { label 'docker-agent' }
  triggers { pollSCM('H/2 * * * *') }
  options { timeout(time: 15, unit: 'MINUTES'); disableConcurrentBuilds() }
  environment { COMPOSE_PROJECT_NAME = 'pettech' }
  stages {
    stage('Build')      { steps { sh 'docker build -t pettech-app:${BUILD_NUMBER} .' } }
    stage('Unit Test')  { steps { sh 'docker run --rm pettech-app:${BUILD_NUMBER} python -m pytest -q' } }
    stage('Deploy')     { steps { sh 'cp -n .env.example .env || true; docker compose up -d --build --wait' } }
    stage('Smoke Test') { steps { sh 'docker compose exec -T app python scripts/smoke.py http://localhost:8000' } }
  }
  post {
    success { echo 'Deployed: เปิดแอปที่ http://<IP-ของ-server>:8081' }
    failure { sh 'docker compose logs --tail=50 || true; docker compose down || true' }
  }
}