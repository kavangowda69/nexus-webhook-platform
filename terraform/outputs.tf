output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "ecr_api_url" {
  description = "ECR URL for API image"
  value       = module.ecr.api_repository_url
}

output "ecr_worker_url" {
  description = "ECR URL for worker image"
  value       = module.ecr.worker_repository_url
}

output "ecr_receiver_url" {
  description = "ECR URL for receiver image"
  value       = module.ecr.receiver_repository_url
}