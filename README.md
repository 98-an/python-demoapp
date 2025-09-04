# DevSecOps CI/CD Pipeline with GitOps – Secure Python App Deployment

![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-blue)

---

## Introduction

This project demonstrates the design and deployment of a fully automated DevSecOps CI/CD pipeline for a Python application running on Kubernetes (Amazon EKS).  
It integrates continuous security checks, container image scanning, GitOps-based deployment, and real-time monitoring to ensure reliable, secure, and traceable software delivery.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)  
- [Installation & Prerequisites](#installation--prerequisites)  
- [CI/CD Pipeline Details](#cicd-pipeline-details)  
- [Security Integrations](#security-integrations)  
- [Monitoring Setup](#monitoring-setup)  
- [Features & Results](#features--results)  
- [Contributing](#contributing)  
- [License](#license)  

---

## Architecture Overview

![Pipeline Architecture](https://github.com/user-attachments/assets/dba94644-c3a4-4a37-8b87-b8a966b4f247)

*Figure 1: Overview of the DevSecOps CI/CD pipeline integrating Jenkins, SonarQube, Docker, ArgoCD, Prometheus, and Grafana.*

The pipeline automates from code commit to deployment, incorporating static and dynamic security testing, container scanning, and continuous monitoring.

---

## Installation & Prerequisites

- Docker >= 20.x  
- Jenkins >= 2.x  
- Kubernetes cluster (Amazon EKS)  
- Helm >= 3.x  
- Tools: SonarQube, OWASP ZAP, Trivy, Prometheus, Grafana  
- Access to GitHub repository with pipeline manifests  

*Insert setup commands or scripts here if applicable.*

---

## CI/CD Pipeline Details

### CI Steps

[SonarQube Scan](https://github.com/user-attachments/assets/6e6c574c-25dd-4063-8821-0a55e9f91893)
*Static code analysis and secrets detection with SonarQube.*

- Code quality and security analysis triggered on each push  
- Block pipeline on Quality Gate failure ensuring code compliance

### Build & Push Docker Images

![Docker Build](docs/images/docker-build.png)  
*Automated Docker image build and vulnerability scanning with Trivy.*

- Build of Docker containers after code validation  
- Scanning images to detect vulnerabilities prior to deployment

### GitOps Deployment

![ArgoCD Sync](docs/images/argocd-sync.png)  
*Automated synchronization and deployment of Kubernetes manifests via ArgoCD.*

- Git repository serves as single source of truth  
- Ensures state consistency and enables easy rollback

---

## Security Integrations

- Static Application Security Testing (SAST) with SonarQube  
- Dynamic Application Security Testing (DAST) using OWASP ZAP  
- Dependency scanning using OWASP Dependency-Check and Trivy  
- Enforced Quality Gates to prevent insecure code release  

*Add screenshots of scan results, alerts, or Quality Gate dashboards.*

---

## Monitoring Setup

![Grafana Dashboard](docs/images/grafana-dashboard.png)  
*Real-time monitoring dashboards displaying application and cluster metrics.*

- Metrics collected via Prometheus and Node Exporter  
- Alerts configured for key performance and security indicators  

---

## Features & Results

- End-to-end pipeline automating secure deployments with traceability  
- Early detection of vulnerabilities reducing production risks  
- Real-time observability improving operational response  
- Ready for scaling with multi-environment support  

---

## Contributing

Contributions are welcome! Please fork the repository, open issues for bugs or feature requests, and submit pull requests with your improvements.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

*For any questions or feedback, feel free to open an issue or contact me directly.*

