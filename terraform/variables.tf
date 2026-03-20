variable "project" {
  description = "Project name"
  type        = string
  default     = "nexus"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Desired EKS worker nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum EKS worker nodes"
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum EKS worker nodes"
  type        = number
  default     = 3
}