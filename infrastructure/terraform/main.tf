# ==============================================================================
# Civium Infrastructure - Main Terraform Configuration
# ==============================================================================
# This configuration provisions the core infrastructure for Civium on AWS.
#
# Usage:
#   terraform init
#   terraform plan -var-file=environments/dev.tfvars
#   terraform apply -var-file=environments/dev.tfvars
# ==============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }

  backend "s3" {
    # Configure in backend.hcl or via CLI
    # bucket         = "civium-terraform-state"
    # key            = "infrastructure/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "civium-terraform-locks"
    # encrypt        = true
  }
}

# ==============================================================================
# Provider Configuration
# ==============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Civium"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# ==============================================================================
# Data Sources
# ==============================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ==============================================================================
# Local Values
# ==============================================================================

locals {
  name_prefix = "civium-${var.environment}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)

  common_tags = {
    Project     = "Civium"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ==============================================================================
# VPC Module
# ==============================================================================

module "vpc" {
  source = "./modules/vpc"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  azs         = local.azs

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"

  tags = local.common_tags
}

# ==============================================================================
# EKS Module
# ==============================================================================

module "eks" {
  source = "./modules/eks"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  kubernetes_version = var.kubernetes_version
  node_instance_type = var.eks_node_instance_type
  node_min_size      = var.eks_node_min_size
  node_max_size      = var.eks_node_max_size
  node_desired_size  = var.eks_node_desired_size

  tags = local.common_tags
}

# ==============================================================================
# RDS (PostgreSQL) Module
# ==============================================================================

module "rds" {
  source = "./modules/rds"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  engine_version    = "16.1"
  instance_class    = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage

  database_name = "civium"
  username      = "civium"

  # Allow access from EKS
  allowed_security_groups = [module.eks.node_security_group_id]

  multi_az               = var.environment == "production"
  backup_retention_period = var.environment == "production" ? 30 : 7

  tags = local.common_tags
}

# ==============================================================================
# ElastiCache (Redis) Module
# ==============================================================================

module "redis" {
  source = "./modules/redis"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  node_type       = var.redis_node_type
  num_cache_nodes = var.environment == "production" ? 3 : 1

  allowed_security_groups = [module.eks.node_security_group_id]

  tags = local.common_tags
}

# ==============================================================================
# DocumentDB (MongoDB-compatible) Module
# ==============================================================================

module "documentdb" {
  source = "./modules/documentdb"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  instance_class  = var.documentdb_instance_class
  instance_count  = var.environment == "production" ? 3 : 1

  master_username = "civium"

  allowed_security_groups = [module.eks.node_security_group_id]

  tags = local.common_tags
}

# ==============================================================================
# MSK (Kafka) Module
# ==============================================================================

module "msk" {
  source = "./modules/msk"

  name_prefix = local.name_prefix
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids

  kafka_version    = "3.5.1"
  broker_node_type = var.msk_broker_node_type
  broker_count     = var.environment == "production" ? 3 : 1

  allowed_security_groups = [module.eks.node_security_group_id]

  tags = local.common_tags
}

# ==============================================================================
# S3 Buckets
# ==============================================================================

module "s3" {
  source = "./modules/s3"

  name_prefix = local.name_prefix
  environment = var.environment

  tags = local.common_tags
}

# ==============================================================================
# Outputs
# ==============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.endpoint
}

output "documentdb_endpoint" {
  description = "DocumentDB endpoint"
  value       = module.documentdb.endpoint
}

output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  value       = module.msk.bootstrap_brokers
}

