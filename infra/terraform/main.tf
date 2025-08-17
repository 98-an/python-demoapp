terraform {
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.region
}

# Exemple ultra-minimal : un Security Group pour la démo
resource "aws_security_group" "demo" {
  name        = "demoapp-sg"
  description = "Allow 5000 from your IP"
  vpc_id      = var.vpc_id

  ingress {
    description = "Flask"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
