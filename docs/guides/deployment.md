# Deployment Guide

This guide covers deploying Civium to production environments.

## Deployment Options

1. **Kubernetes (Recommended)** - For production workloads
2. **Docker Compose** - For staging/small deployments
3. **Manual** - For development/testing

## Prerequisites

- AWS account with appropriate permissions
- kubectl configured
- Terraform installed
- Docker & Docker Compose

## Kubernetes Deployment

### 1. Infrastructure Setup (Terraform)

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var-file=environments/production.tfvars

# Apply infrastructure
terraform apply -var-file=environments/production.tfvars
```

This provisions:
- VPC with public/private subnets
- EKS cluster
- RDS (PostgreSQL)
- ElastiCache (Redis)
- DocumentDB (MongoDB-compatible)
- MSK (Kafka)

### 2. Configure kubectl

```bash
aws eks update-kubeconfig --name civium-production-eks --region us-east-1
```

### 3. Deploy to Kubernetes

```bash
cd infrastructure/k8s

# Create namespace and base resources
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml

# Create secrets (replace values first!)
kubectl apply -f secrets.yaml

# Deploy services
kubectl apply -f services/

# Configure ingress
kubectl apply -f ingress.yaml
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n civium

# Check services
kubectl get svc -n civium

# Check ingress
kubectl get ingress -n civium

# View logs
kubectl logs -f deployment/regulatory-intelligence -n civium
```

## Docker Compose Deployment

For staging or smaller deployments:

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Configuration

### Required Secrets

Update `infrastructure/k8s/secrets.yaml` with production values:

- `SECRET_KEY` - Application secret (32+ chars)
- `POSTGRES_PASSWORD` - Database password
- `NEO4J_PASSWORD` - Graph database password
- `MONGODB_PASSWORD` - Document store password
- `REDIS_PASSWORD` - Cache password
- `ANTHROPIC_API_KEY` - Claude API key
- `JWT_SECRET_KEY` - JWT signing key (32+ chars)
- `ALCHEMY_API_KEY` - Blockchain RPC (if using)

### Environment-Specific Settings

Edit `infrastructure/k8s/configmap.yaml`:

```yaml
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  DEBUG: "false"
  CORS_ORIGINS: "https://app.civium.io"
```

## Scaling

### Horizontal Pod Autoscaler

HPAs are configured for each service:

```bash
# View HPA status
kubectl get hpa -n civium

# Manually scale
kubectl scale deployment regulatory-intelligence --replicas=5 -n civium
```

### Database Scaling

For RDS/DocumentDB scaling, update Terraform variables and apply:

```bash
terraform apply -var-file=environments/production.tfvars \
  -var="rds_instance_class=db.r6g.xlarge"
```

## Monitoring

### Health Checks

Each service exposes `/health`:

```bash
curl https://api.civium.io/api/v1/regulations/health
```

### Prometheus Metrics

Services expose Prometheus metrics. Configure scraping in your monitoring stack.

### Logging

Logs are structured JSON in production. Configure your log aggregator (CloudWatch, Datadog, etc.).

## SSL/TLS

The ingress is configured for TLS with cert-manager:

```yaml
annotations:
  cert-manager.io/cluster-issuer: letsencrypt-prod
```

Ensure cert-manager is installed:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

## Database Migrations

Run migrations before deploying new versions:

```bash
kubectl exec -it deployment/regulatory-intelligence -n civium -- \
  python scripts/init_databases.py
```

## Rollback

### Kubernetes

```bash
# View rollout history
kubectl rollout history deployment/regulatory-intelligence -n civium

# Rollback to previous version
kubectl rollout undo deployment/regulatory-intelligence -n civium

# Rollback to specific revision
kubectl rollout undo deployment/regulatory-intelligence --to-revision=2 -n civium
```

### Terraform

```bash
# View state
terraform state list

# Import/modify as needed
terraform import ...
```

## Security Checklist

- [ ] All secrets rotated from defaults
- [ ] TLS enabled for all endpoints
- [ ] Network policies configured
- [ ] Database backups enabled
- [ ] Monitoring and alerting configured
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Security scanning in CI/CD

## Troubleshooting

### Pods Not Starting

```bash
kubectl describe pod <pod-name> -n civium
kubectl logs <pod-name> -n civium
```

### Database Connection Issues

```bash
# Check security groups allow traffic
# Verify secrets are mounted correctly
kubectl exec -it <pod> -n civium -- env | grep POSTGRES
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -n civium

# Review HPA status
kubectl describe hpa -n civium
```

## Backup & Recovery

### Database Backups

RDS automated backups are enabled. For manual backup:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier civium-production \
  --db-snapshot-identifier civium-manual-backup
```

### Disaster Recovery

1. Infrastructure is codified in Terraform
2. Database snapshots in AWS
3. Container images in ECR
4. Secrets in AWS Secrets Manager (recommended)

