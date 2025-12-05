# Tolling Vision SAR - Complete Usage Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Template Size Management](#template-size-management)
3. [Deployment Methods](#deployment-methods)
4. [Parameter Configuration](#parameter-configuration)
5. [JWT Authentication](#jwt-authentication)
6. [API Testing](#api-testing)
7. [Operations and Monitoring](#operations-and-monitoring)
8. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites Setup
```bash
# 1. Create Python virtual environment (REQUIRED)
python3 -m venv tolling-vision-env
source tolling-vision-env/bin/activate

# 2. Install dependencies
pip install boto3 botocore cryptography awscli

# 3. Configure AWS CLI
aws configure

# 4. Verify access
aws sts get-caller-identity --no-paginate
```

### Automated Deployment (Recommended)
```bash
# Deploy with automatic size detection and method selection
./scripts/deploy-template.sh tolling-vision-prod my-parameters.json

# Monitor deployment
aws cloudformation describe-stack-events \
  --stack-name tolling-vision-prod \
  --no-paginate
```

## Template Size Management

### Check Current Template Size
```bash
# Check template size and get deployment recommendations
wc -c template.yaml
ls -lh template.yaml

# Use monitoring script for detailed analysis
python3 scripts/monitor-template-size.py
```

### Size Optimization (if needed)
```bash
# Optimize template for size reduction
python3 scripts/optimize-template.py template.yaml template-optimized.yaml

# Validate optimized template
aws cloudformation validate-template \
  --template-body file://template-optimized.yaml \
  --no-paginate
```

## Deployment Methods

### Method 1: Direct Deployment (< 51KB)
```bash
# Validate template
aws cloudformation validate-template \
  --template-body file://template.yaml \
  --no-paginate

# Deploy stack
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-body file://template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate

# Monitor progress
aws cloudformation wait stack-create-complete \
  --stack-name tolling-vision-prod
```

### Method 2: S3-based Deployment (51KB - 450KB)
```bash
# Upload template to S3
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml

# Validate from S3
aws cloudformation validate-template \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --no-paginate

# Deploy from S3
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

### Method 3: SAR Marketplace (Coming Soon)
```bash
# Publish to SAR marketplace
./scripts/publish-sar.sh

# Deploy from SAR
aws serverlessrepo create-cloud-formation-template \
  --application-id arn:aws:serverlessrepo:us-east-1:123456789012:applications/tolling-vision \
  --semantic-version 1.0.0 \
  --no-paginate
```

## Parameter Configuration

### Environment-Specific Parameter Files

#### Development Environment
```bash
# Create development parameters
cat > my-dev-params.json << 'EOF'
[
  {
    "ParameterKey": "LicenseKey",
    "ParameterValue": "your-dev-license-key"
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": "api-dev.yourdomain.com"
  },
{
  "ParameterKey": "ProcessCount",
  "ParameterValue": "1"
},
{
  "ParameterKey": "MaxSize",
  "ParameterValue": "2"
}

# Deploy development stack
aws cloudformation create-stack \
  --stack-name tolling-vision-dev \
  --template-body file://template.yaml \
  --parameters file://my-dev-params.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

#### Production Environment
```bash
# Create production parameters
cat > my-prod-params.json << 'EOF'
[
  {
    "ParameterKey": "LicenseKey",
    "ParameterValue": "your-production-license-key"
  },
  {
    "ParameterKey": "DomainName",
  "ParameterValue": "api.yourdomain.com"
},
{
  "ParameterKey": "ProcessCount",
  "ParameterValue": "4"
},
{
  "ParameterKey": "MaxSize",
  "ParameterValue": "10"
},
{
  "ParameterKey": "OnDemandPercentage",
  "ParameterValue": "30"
}

# Deploy production stack
./scripts/deploy-template.sh tolling-vision-prod my-prod-params.json
```

### Parameter Validation
```bash
# Validate parameters before deployment
aws cloudformation validate-template \
  --template-body file://template.yaml \
  --parameters file://my-parameters.json \
  --no-paginate
```

## JWT Authentication

### Enable JWT Authentication
```json
{
  "ParameterKey": "EnableJwtAuth",
  "ParameterValue": "true"
},
{
  "ParameterKey": "CreateCognitoUserPool",
  "ParameterValue": "true"
},
{
  "ParameterKey": "CognitoResourceServerIdentifier",
  "ParameterValue": "api"
},
{
  "ParameterKey": "CognitoCustomScopeName",
  "ParameterValue": "m2m"
}
```

### Generate JWT Tokens
```bash
# Get authentication details from stack
USER_POOL_ID=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
  --output text --no-paginate)

CLIENT_ID=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoAppClientId`].OutputValue' \
  --output text --no-paginate)

SECRET_ARN=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoClientSecretArn`].OutputValue' \
  --output text --no-paginate)

CLIENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_ARN \
  --query 'SecretString' \
  --output text --no-paginate)

# Generate access token
TOKEN_RESPONSE=$(curl -s -X POST \
  "https://tolling-vision-prod.auth.us-east-1.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic $(echo -n "${CLIENT_ID}:${CLIENT_SECRET}" | base64)" \
  -d "grant_type=client_credentials&scope=api/m2m")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Access Token: $ACCESS_TOKEN"
```

### Test JWT Authentication
```bash
# Test with valid token
curl -X GET "https://api.yourdomain.com/health" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json"

# Test without token (should return 401)
curl -X GET "https://api.yourdomain.com/health" \
  -H "Content-Type: application/json"
```

## API Testing

### Comprehensive API Testing
```bash
# Run comprehensive test suite
python3 examples/test-api-endpoints.py tolling-vision-prod us-east-1

# Test specific endpoints
curl -X GET "https://api.yourdomain.com/health" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -X GET "https://api.yourdomain.com/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### gRPC Testing (requires grpcurl)
```bash
# Install grpcurl
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest

# Test gRPC health check
grpcurl \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -plaintext \
  api.yourdomain.com:8443 \
  grpc.health.v1.Health/Check

# List available services
grpcurl \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -plaintext \
  api.yourdomain.com:8443 \
  list
```

### Load Testing
```bash
# Simple load test with curl
for i in {1..100}; do
  curl -s -X GET "https://api.yourdomain.com/health" \
    -H "Authorization: Bearer $ACCESS_TOKEN" &
done
wait

# Using Apache Bench (if available)
ab -n 1000 -c 10 \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  https://api.yourdomain.com/health
```

## Operations and Monitoring

### Health Monitoring
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].StackStatus' \
  --output text --no-paginate

# Check Auto Scaling Group health
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --query 'AutoScalingGroups[0].Instances[*].[InstanceId,HealthStatus,LifecycleState]' \
  --output table --no-paginate

# Check VPC Link status
aws apigatewayv2 get-vpc-link \
  --vpc-link-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcLinkId`].OutputValue' \
    --output text) \
  --no-paginate
```

### Log Monitoring
```bash
# View application logs
aws logs tail /aws/ec2/tolling-vision --since 1h --no-paginate

# View Lambda custom resource logs
aws logs tail /aws/lambda/tolling-vision-custom-resource-handler \
  --since 1h --no-paginate

# View API Gateway logs
aws logs tail /aws/apigateway/tolling-vision-api --since 1h --no-paginate

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/ec2/tolling-vision \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate
```

### Scaling Operations
```bash
# Scale up
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 5 \
  --no-paginate

# Scale down
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 2 \
  --no-paginate
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Template Size Exceeds Limits
**Problem**: Template > 51KB for direct deployment
```bash
# Check template size
wc -c template.yaml

# Solution: Use S3-based deployment
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

#### 2. Lambda Custom Resource Failures
**Problem**: VPC Link, ASG, or WAF creation fails
```bash
# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/tolling-vision-custom-resource-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name tolling-vision-prod \
  --query 'StackEvents[?ResourceType==`Custom::VpcLink` || ResourceType==`Custom::AutoScaling` || ResourceType==`Custom::WAF`]' \
  --no-paginate
```

#### 3. Container Startup Failures
**Problem**: Containers fail to start or pass health checks
```bash
# Check container logs
aws logs tail /aws/ec2/tolling-vision --since 1h --no-paginate

# Check license validation
aws logs filter-log-events \
  --log-group-name /aws/ec2/tolling-vision \
  --filter-pattern "license" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Check instance health
aws elbv2 describe-target-health \
  --target-group-arn $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`HttpTargetGroupArn`].OutputValue' \
    --output text) \
  --no-paginate
```

#### 4. JWT Authentication Issues
**Problem**: 401 errors or token generation failures
```bash
# Verify Cognito configuration
aws cognito-idp describe-user-pool \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --no-paginate

# Check JWT authorizer
aws apigatewayv2 get-authorizers \
  --api-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
    --output text) \
  --no-paginate

# Test token generation
python3 examples/test-api-endpoints.py tolling-vision-prod
```

#### 5. API Gateway 5xx Errors
**Problem**: Backend connectivity issues
```bash
# Check VPC Link status
aws apigatewayv2 get-vpc-link \
  --vpc-link-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcLinkId`].OutputValue' \
    --output text) \
  --no-paginate

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`HttpTargetGroupArn`].OutputValue' \
    --output text) \
  --no-paginate

# Check API Gateway logs
aws logs filter-log-events \
  --log-group-name /aws/apigateway/tolling-vision-api \
  --filter-pattern "[timestamp, requestId, ip, user, timestamp, method, resource, protocol, status=5*, size, referer, agent, requestTime, integrationRequestTime, integrationStatus, integrationErrorMessage]" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate
```

### Recovery Procedures

#### Stack Rollback
```bash
# Cancel stuck update
aws cloudformation cancel-update-stack \
  --stack-name tolling-vision-prod \
  --no-paginate

# Delete failed stack
aws cloudformation delete-stack \
  --stack-name tolling-vision-prod \
  --no-paginate

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name tolling-vision-prod
```

#### Manual Resource Cleanup
```bash
# Clean up Lambda-created resources if needed
aws apigatewayv2 delete-vpc-link --vpc-link-id <vpc-link-id> --no-paginate
aws autoscaling delete-auto-scaling-group --auto-scaling-group-name <asg-name> --force-delete --no-paginate
aws wafv2 delete-web-acl --scope REGIONAL --id <web-acl-id> --lock-token <lock-token> --no-paginate
```

## Environment Cleanup

### Temporary Cleanup
```bash
# Deactivate virtual environment when done with session
deactivate

# Verify deactivation
which python3
```

### Complete Cleanup
```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name tolling-vision-prod \
  --no-paginate

# Clean up S3 artifacts
aws s3 rm s3://my-sar-artifacts-bucket/template.yaml

# Remove local files (optional)
rm -f test-results-*.json
rm -f my-*-params.json
```

## Best Practices

### Development Workflow
1. **Always use virtual environments**: `python3 -m venv tolling-vision-env`
2. **Test in development first**: Deploy to dev environment before production
3. **Validate templates**: Always validate before deployment
4. **Monitor deployments**: Watch CloudFormation events during deployment
5. **Check logs**: Review Lambda and application logs after deployment

### Production Deployment
1. **Use parameter files**: Don't pass sensitive data via command line
2. **Enable monitoring**: Set up CloudWatch alarms and notifications
3. **Plan for scaling**: Configure appropriate min/max capacity
4. **Security first**: Enable JWT auth and WAF for production
5. **Backup configurations**: Save parameter files and stack outputs

### Operational Excellence
1. **Regular health checks**: Monitor stack and application health
2. **Log analysis**: Regularly review logs for issues
3. **Performance monitoring**: Track API response times and error rates
4. **Capacity planning**: Monitor usage and adjust scaling policies
5. **Security updates**: Keep certificates and credentials current

## Additional Resources

### Documentation
- [Deployment Guide](DEPLOYMENT-GUIDE.md): Detailed deployment procedures
- [Operations Guide](OPERATIONS-GUIDE.md): Operational procedures and troubleshooting
- [JWT Authentication Guide](JWT-AUTHENTICATION-GUIDE.md): Complete JWT setup and testing
- [Enhanced Monitoring Guide](ENHANCED-MONITORING-GUIDE.md): Monitoring and alerting setup
- [SAR Troubleshooting Guide](SAR-TROUBLESHOOTING-GUIDE.md): SAR deployment issues

### Scripts and Tools
- `scripts/deploy-template.sh`: Automated deployment with size detection
- `scripts/monitor-template-size.py`: Template size monitoring
- `scripts/optimize-template.py`: Template size optimization
- `examples/test-api-endpoints.py`: Comprehensive API testing with JWT authentication

### Support
- **GitHub Issues**: Report bugs and feature requests
- **AWS Support**: For AWS-specific infrastructure issues
- **Documentation**: Comprehensive guides in the `docs/` directory