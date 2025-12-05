# Technology Stack & Lambda-Based SAR Approach

## Infrastructure as Code
- **CloudFormation**: Single SAR-compliant template with embedded Lambda custom resources
- **Template Format**: YAML-based CloudFormation template (`template.yaml`)
- **SAR Publishing**: Configured for AWS Serverless Application Repository with Lambda workarounds
- **Lambda Custom Resources**: Handle AWS resource types not supported by SAR

## AWS Services Stack
- **Compute**: EC2 Auto Scaling Groups with mixed instance types (created by Lambda)
- **Networking**: VPC with private/public subnets, NAT Gateways, Application Load Balancer
- **API Management**: API Gateway with VPC Link for private backend access (VPC Link created by Lambda)
- **Authentication**: Amazon Cognito for JWT-based machine-to-machine auth
- **Security**: AWS WAF for IP allowlisting and security rules (created by Lambda)
- **Monitoring**: CloudWatch Logs, Metrics, Dashboard, SNS Notifications, Custom Metrics
- **Observability**: Enhanced monitoring
- **Container**: Docker containers from public ECR registry
- **Lambda Functions**: Custom resource handlers for unsupported SAR resource types

## Container Technology
- **Base Image**: `public.ecr.aws/smartcloud/tollingvision`
- **Architectures**: ARM64 (default) and x86-64 support
- **Protocols**: HTTP/1.1 (port 443)
- **Resource Requirements**: 3GB RAM + 1GB per additional process thread

## Lambda Custom Resource Technology
- **Runtime**: Python 3.9+ with embedded code in CloudFormation template
- **Dependencies**: boto3, botocore (available in Lambda runtime)
- **Timeout**: 15 minutes maximum execution time
- **Memory**: 512MB recommended for AWS API operations
- **Error Handling**: Comprehensive exception handling and CloudFormation response management
- **State Management**: PhysicalResourceId tracking for resource lifecycle

## Enhanced Monitoring Technology
- **CloudWatch Dashboard**: Operational monitoring with custom widgets and real-time metrics
- **SNS Notifications**: Email-based critical alerts with configurable topics and subscriptions
- **Custom Metrics**: Application-specific metrics in `TollingVision/Application` namespace
- **Metric Filters**: Log-based metric extraction for container events and processing statistics

## SAR Limitations & Lambda Workarounds
- **Unsupported Resources**: VPC Links, Auto Scaling Groups, Launch Templates, WAF resources
- **Lambda Solution**: Custom resource handler creates these resources via AWS APIs
- **Template Size**: Single template approach keeps within SAR limits
- **No External Dependencies**: All code embedded inline in template

## Development & Validation Tools
- **CloudFormation**: Native template validation and deployment
- **AWS CLI**: Direct template deployment and testing
- **Lambda Testing**: CloudWatch Logs for custom resource execution monitoring
- **SAR Validation**: Template size and complexity validation for marketplace

## Python Development Environment

**IMPORTANT**: Always use Python 3 and virtual environments when running Python scripts to avoid dependency conflicts and ensure reproducible builds.

### Virtual Environment Setup
```bash
# Create virtual environment (always use python3)
python3 -m venv tolling-vision-env

# Activate virtual environment (Linux/macOS)
source tolling-vision-env/bin/activate

# Activate virtual environment (Windows)
tolling-vision-env\Scripts\activate

# Install dependencies
pip install boto3 botocore cryptography

# Deactivate when done
deactivate
```

## Common Commands

**IMPORTANT**: Always use `--no-cli-pager` flag with AWS CLI commands to avoid interactive prompts that require pressing Q. This ensures commands run non-interactively in automated environments.

### Template Validation
```bash
# Always activate virtual environment first
source tolling-vision-env/bin/activate

# For small templates (< 51KB): Validate directly
aws cloudformation validate-template --template-body file://template.yaml --no-paginate

# For larger templates (51KB - 450KB): Upload to S3 first
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws cloudformation validate-template --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml --no-paginate

# Deploy for testing (small templates)
aws cloudformation create-stack \
  --stack-name tolling-vision-test \
  --template-body file://template.yaml \
  --parameters file://test-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate

# Deploy for testing (large templates via S3)
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws cloudformation create-stack \
  --stack-name tolling-vision-test \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters file://test-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate

# Monitor Lambda custom resource execution (avoid pagination)
aws logs tail /aws/lambda/tolling-vision-custom-resource-handler --follow --no-paginate

# Check stack status without pagination
aws cloudformation describe-stacks --stack-name tolling-vision-test --no-paginate

# List stack events without pagination
aws cloudformation describe-stack-events --stack-name tolling-vision-test --no-paginate

# Deactivate virtual environment
deactivate
```

### SAR Publishing
```bash
# Always use virtual environment for Python-based operations
source tolling-vision-env/bin/activate

# For small templates (< 51KB): Publish directly
aws serverlessrepo create-application \
  --name tolling-vision \
  --description "Tolling Vision ANPR/MMR processing infrastructure" \
  --template-body file://template.yaml \
  --no-paginate

# For larger templates (51KB - 450KB): Upload to S3 first
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws serverlessrepo create-application \
  --name tolling-vision \
  --description "Tolling Vision ANPR/MMR processing infrastructure" \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --no-paginate

# Update existing SAR application (small templates)
aws serverlessrepo update-application \
  --application-id <app-id> \
  --template-body file://template.yaml \
  --no-paginate

# Update existing SAR application (large templates via S3)
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws serverlessrepo update-application \
  --application-id <app-id> \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --no-paginate

# List SAR applications without pagination
aws serverlessrepo list-applications --no-paginate

# Get application details without pagination
aws serverlessrepo get-application --application-id <app-id> --no-paginate

# Deactivate virtual environment
deactivate
```

### Lambda Development & Testing
```bash
# Create and activate virtual environment (always use python3)
python3 -m venv lambda-dev-env
source lambda-dev-env/bin/activate

# Install Lambda dependencies for local testing
pip install boto3 botocore cryptography

# Test Lambda function locally (if using testing framework)
python3 -m pytest tests/

# Validate Lambda code syntax
python3 -m py_compile src/lambda_function.py

# Deactivate when done
deactivate
```

## Lambda Function Architecture
- **Handler**: `lambda_handler(event, context)` - Main entry point
- **Resource Routing**: Route based on `event['ResourceProperties']['ResourceType']`
- **AWS API Integration**: Use boto3 clients for resource creation/management
- **CloudFormation Integration**: Send responses via `ResponseURL` webhook
- **Error Recovery**: Graceful handling of timeouts and API failures