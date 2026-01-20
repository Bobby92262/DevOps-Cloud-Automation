# DevOps-Cloud-Automation
This project automates the creation, configuration, and monitoring of a public- facing web server in AWS using Python 3, Boto 3, and a custom monitoring script.

# Project OverView
The automation script (devops1.py) provisions cloud resources, configures a running web server, and performs remote monitoring on the instance.

The system performs the following high‑level tasks:

Launches an EC2 instance (Amazon Linux 2023) with a User Data script that installs Apache, applies updates, and generates a dynamic index page containing instance metadata.

Creates an S3 bucket with a unique name, configures it for static website hosting, and uploads both an image (downloaded dynamically) and a generated HTML page.

Injects S3 content into the EC2‑hosted webpage, ensuring both sites display shared assets.

Writes the EC2 and S3 website URLs to a local output file for easy access.

Transfers and executes a monitoring script (monitoring.sh) on the EC2 instance using SSH, collecting system metrics and service status.

Creates an AMI from the running instance using a timestamped naming convention.

This project demonstrates cloud automation, infrastructure provisioning, remote execution, and monitoring within AWS, following DevOps best practices for reproducibility and automation.
