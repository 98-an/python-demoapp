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

Each code commit triggers a complete CI/CD pipeline, checked at every stage for quality and security:

![Jenkins Pipeline Stages](https://github.com/user-attachments/assets/008b4e74-0b58-4467-82ac-c024c73fe1d6)  
*Jenkins pipeline triggered for each commit, with all build, scan, and deployment stages visible.*

The pipeline runs:

- Static analysis and secrets detection (SonarQube)
- Code Quality Gate validation
- Dependency and image scan (OWASP Dependency-Check, Trivy)
- Container build and push
- Automated deployment to Kubernetes via ArgoCD
- Runtime vulnerability scan (OWASP ZAP)

### GitOps Deployment

![ArgoCD Sync](https://github.com/user-attachments/assets/484925e6-7be3-40e2-85e0-e3f1b78b9e31)  
*Automated synchronization and deployment of Kubernetes manifests via ArgoCD.*

- Git repository serves as single source of truth  
- Ensures state consistency and enables easy rollback

---

## Security Integrations

- Static Application Security Testing (SAST) with SonarQube
![SonarQube Scan](https://github.com/user-attachments/assets/6e6c574c-25dd-4063-8821-0a55e9f91893)
*Static code analysis and secrets detection with SonarQube.*

   - Code quality and security analysis triggered on each push  
   - Block pipeline on Quality Gate failure ensuring code compliance
 
- Dynamic Application Security Testing (DAST) using OWASP ZAP
![OWASP ZAP Scan Report](https://github.com/user-attachments/assets/7c01ef3e-692d-45c0-abb2-f1c44a5c91b7)  
*Figure: Example OWASP ZAP report — vulnerabilities detected in the deployed app.*
- Dependency scanning using OWASP Dependency-Check and Trivy  
- Enforced Quality Gates to prevent insecure code release  

---

## Monitoring Setup

![Grafana Dashboard](https://github.com/user-attachments/assets/c84156d6-e44f-43e6-a449-892341b67499)
*Real-time monitoring dashboards displaying application and cluster metrics.*

![Prometheus Configuration](https://github.com/user-attachments/assets/c3d1297f-6190-4a60-87d1-3facc13219d1)
*Figure: Prometheus collecting metrics from Jenkins, Kubernetes, and system exporters.*
- Metrics collected via Prometheus and Node Exporter  
- Alerts configured for key performance and security indicators  

---

## Monitoring SonarQube in Grafana

SonarQube exposes detailed code quality metrics via its Prometheus exporter (see below).  
These metrics are scraped by Prometheus and visualized in Grafana, making it easy to monitor bugs, vulnerabilities, coverage, and technical debt in real time throughout the CI/CD workflow.

![SonarQube Prometheus Exporter](https://github.com/user-attachments/assets/b0e757e4-89f7-4fda-b57d-2faa9fcabe5f)
*Configuring SonarQube's Prometheus exporter to expose code quality metrics.*

![Prometheus SonarQube Job](https://github.com/user-attachments/assets/71e7226f-ee77-4652-bb6c-e2818b0082d6)
*Prometheus configuration to scrape SonarQube metrics.*

Grafana dashboards provide a unified view of infrastructure and code health, supporting proactivity and fast remediation.


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

