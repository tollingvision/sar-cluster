# Tolling Vision SAR Deployment Guide

## Overview

This guide covers deploying the Tolling Vision infrastructure using AWS Serverless Application Repository (SAR) with Lambda custom resources. The template supports both direct deployment (< 51KB) and S3-based deployment (51KB-450KB) depending on template size.

## Template Size Management

### Size Constraints
- **Direct Template Body**: 51KB maximum (51,200 bytes)
- **S3-based Templates**: 450KB maximum (460,800 bytes)
- **SAR Publishing**: Supports both deployment methods

### Check Template Size
```bash
# Check current template size
wc -c template.yaml

# Human-readable format
ls -lh template.yaml
```

### Deployment Method Selection
- **< 51KB**: Use direct deployment with `--template-body`
- **51KB - 450KB**: Use S3-based deployment with `--template-url`
- **> 450KB**: Template optimization required

## Prerequisites

### AWS CLI Setup
```bash
# Configure AWS CLI with appropriate credentials
aws configure

# Verify access
aws sts get-caller-identity --no-paginate
```

### Python Virtual Environment (Required)
```bash
# Create virtual environment (always use python3)
python3 -m venv tolling-vision-env

# Activate virtual environment
source tolling-vision-env/bin/activate

# Install dependencies
pip install boto3 botocore cryptography

# Verify installation
python3 -c "import boto3; print('AWS SDK ready')"
```

### S3 Bucket for Large Templates
```bash
# Create S3 bucket for templates > 51KB
aws s3 mb s3://my-sar-artifacts-bucket --no-paginate

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket my-sar-artifacts-bucket \
  --versioning-configuration Status=Enabled \
  --no-paginate
```

## Deployment Methods

### Method 1: Direct Deployment (< 51KB)

#### Template Validation
```bash
# Activate virtual environment
source tolling-vision-env/bin/activate

# Validate template syntax
aws cloudformation validate-template \
  --template-body file://template.yaml \
  --no-paginate
```

#### SAR Deployment
```bash
# Deploy from SAR marketplace (one-click)
aws serverlessrepo create-cloud-formation-template \
  --application-id arn:aws:serverlessrepo:us-east-1:123456789012:applications/tolling-vision \
  --semantic-version 1.0.0 \
  --no-paginate

# Deploy using CloudFormation directly
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-body file://template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

### Method 2: S3-based Deployment (51KB - 450KB)

#### Upload Template to S3
```bash
# Activate virtual environment
source tolling-vision-env/bin/activate

# Upload template to S3
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml

# Verify upload
aws s3 ls s3://my-sar-artifacts-bucket/ --no-paginate
```

#### Template Validation via S3
```bash
# Validate template from S3
aws cloudformation validate-template \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --no-paginate
```

#### S3-based Deployment
```bash
# Deploy using S3 template URL
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate

# Monitor deployment progress
aws cloudformation describe-stack-events \
  --stack-name tolling-vision-prod \
  --no-paginate
```

## Parameter Configuration

### Required Parameters
```json
{
  "ParameterKey": "LicenseKey",
  "ParameterValue": "your-license-key-here"
},
{
  "ParameterKey": "DomainName", 
  "ParameterValue": "api.yourdomain.com"
},
{
  "ParameterKey": "CertificateArn",
  "ParameterValue": "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012"
},
{
  "ParameterKey": "MaxSize",
  "ParameterValue": "10"
}
```

### Common Configuration Scenarios

#### Minimal Development Setup
```json
[
  {
    "ParameterKey": "LicenseKey",
    "ParameterValue": "dev-license-key"
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": "api-dev.yourdomain.com"
  },
  {
    "ParameterKey": "CertificateArn", 
    "ParameterValue": "arn:aws:acm:us-east-1:123456789012:certificate/dev-cert"
  },
  {
    "ParameterKey": "ProcessCount",
    "ParameterValue": "1"
  },
  {
    "ParameterKey": "DesiredCapacity",
    "ParameterValue": "1"
  },
  {
    "ParameterKey": "MaxSize",
    "ParameterValue": "2"
  },
  {
    "ParameterKey": "EnableWAF",
    "ParameterValue": "false"
  }
]
```

#### Production Setup with Security
```json
[
  {
    "ParameterKey": "LicenseKey",
    "ParameterValue": "prod-license-key"
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": "api.yourdomain.com"
  },
  {
    "ParameterKey": "CertificateArn",
    "ParameterValue": "arn:aws:acm:us-east-1:123456789012:certificate/prod-cert"
  },
  {
    "ParameterKey": "ProcessCount",
    "ParameterValue": "4"
  },
  {
    "ParameterKey": "DesiredCapacity", 
    "ParameterValue": "2"
  },
  {
    "ParameterKey": "MaxSize",
    "ParameterValue": "10"
  },
  {
    "ParameterKey": "OnDemandPercentage",
    "ParameterValue": "50"
  },
  {
    "ParameterKey": "CognitoUserPoolId",
    "ParameterValue": "us-east-1_ABC123456"
  },
  {
    "ParameterKey": "EnableWAF",
    "ParameterValue": "true"
  },
  {
    "ParameterKey": "AllowedIpCidrs",
    "ParameterValue": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
  }
]
```

## Monitoring Deployment

### Stack Status Monitoring
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --no-paginate

# Monitor stack events
aws cloudformation describe-stack-events \
  --stack-name tolling-vision-prod \
  --no-paginate

# Watch for completion
aws cloudformation wait stack-create-complete \
  --stack-name tolling-vision-prod
```

### Lambda Custom Resource Monitoring
```bash
# Monitor Lambda custom resource execution
aws logs tail /aws/lambda/tolling-vision-custom-resource-handler \
  --follow \
  --no-paginate

# Check specific log group
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/tolling-vision" \
  --no-paginate
```

## Post-Deployment Verification

### Infrastructure Verification
```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs' \
  --no-paginate

# Verify VPC Link status (Lambda-created)
aws apigatewayv2 get-vpc-link \
  --vpc-link-id <vpc-link-id> \
  --no-paginate

# Check Auto Scaling Group (Lambda-created)
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names <asg-name> \
  --no-paginate
```

### API Endpoint Testing
```bash
# Test HTTP/1.1 endpoint
curl -X GET https://api.yourdomain.com/health \
  -H "Content-Type: application/json"

# Test gRPC endpoint (requires grpcurl)
grpcurl -plaintext api.yourdomain.com:8443 list
```

## Template Size Optimization

### Size Reduction Strategies
1. **Lambda Code Compression**: Minimize embedded Python code
2. **Mapping Reduction**: Streamline instance type mappings
3. **Comment Removal**: Strip non-essential documentation
4. **Parameter Consolidation**: Group related parameters

### Optimization Commands
```bash
# Remove comments and extra whitespace
sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' template.yaml > template-optimized.yaml

# Check size reduction
wc -c template.yaml template-optimized.yaml

# Validate optimized template
aws cloudformation validate-template \
  --template-body file://template-optimized.yaml \
  --no-paginate
```

## Troubleshooting

### Common Issues

#### Template Size Exceeded
```bash
# Check template size
ls -lh template.yaml

# If > 51KB, use S3 method
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml

# Deploy via S3
aws cloudformation create-stack \
  --stack-name tolling-vision-prod \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

#### Lambda Custom Resource Failures
```bash
# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/tolling-vision-custom-resource-handler \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Check CloudFormation events for custom resource failures
aws cloudformation describe-stack-events \
  --stack-name tolling-vision-prod \
  --query 'StackEvents[?ResourceType==`Custom::VpcLink` || ResourceType==`Custom::AutoScaling` || ResourceType==`Custom::WAF`]' \
  --no-paginate
```

#### Certificate Issues
```bash
# Verify certificate exists and is valid
aws acm describe-certificate \
  --certificate-arn <certificate-arn> \
  --no-paginate

# Check certificate domain validation
aws acm list-certificates \
  --certificate-statuses ISSUED \
  --no-paginate
```

### Recovery Procedures

#### Stack Rollback
```bash
# Cancel stack update if stuck
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
# List resources that may need manual cleanup
aws cloudformation list-stack-resources \
  --stack-name tolling-vision-prod \
  --no-paginate

# Clean up Lambda-created resources if needed
aws apigatewayv2 delete-vpc-link --vpc-link-id <vpc-link-id> --no-paginate
aws autoscaling delete-auto-scaling-group --auto-scaling-group-name <asg-name> --force-delete --no-paginate
aws wafv2 delete-web-acl --scope REGIONAL --id <web-acl-id> --lock-token <lock-token> --no-paginate
```

## Environment Cleanup

### Deactivate Virtual Environment
```bash
# Always deactivate when done
deactivate

# Verify deactivation
which python3
```

### Stack Cleanup
```bash
# Delete stack when no longer needed
aws cloudformation delete-stack \
  --stack-name tolling-vision-prod \
  --no-paginate

# Clean up S3 artifacts (if used)
aws s3 rm s3://my-sar-artifacts-bucket/template.yaml
```

## Next Steps

After successful deployment:
1. Configure DNS records for custom domain
2. Set up monitoring and alerting
3. Configure backup procedures
4. Review security settings
5. Test JWT authentication (if enabled)
6. Validate WAF rules (if enabled)

For operational procedures, see [OPERATIONS-GUIDE.md](OPERATIONS-GUIDE.md).
For JWT authentication setup, see [JWT-AUTHENTICATION-GUIDE.md](JWT-AUTHENTICATION-GUIDE.md).