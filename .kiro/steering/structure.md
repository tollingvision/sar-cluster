# Project Structure & Organization

## Root Level Files
- `template.yaml`: Single SAR-compliant CloudFormation template with embedded Lambda custom resources
- `README.md`: Project documentation and deployment guide (updated for Lambda-based approach)
- `LICENSE`: MIT license file
- `CHANGELOG.md`: Version history and release notes
- `USAGE.md`: Usage instructions and examples

## Documentation Structure
```
docs/
├── DEPLOYMENT-GUIDE.md              # Deployment instructions and best practices
├── ENHANCED-MONITORING-GUIDE.md     # Enhanced monitoring features guide
├── JWT-AUTHENTICATION-GUIDE.md     # Authentication setup and configuration
├── OPERATIONS-GUIDE.md              # Operations and maintenance guide
├── PROJECT-AUDIT-SUMMARY.md        # Project audit and analysis summary
├── PROJECT-STRUCTURE.md             # Project organization documentation
├── S3-DEPLOYMENT-GUIDE.md           # S3-based deployment guide
├── SAR_OPTIMIZATION_SUMMARY.md     # SAR optimization details
├── SAR-PACKAGING-SUMMARY.md        # SAR packaging information
├── TEMPLATE-SIZE-MANAGEMENT.md     # Template size management guide
└── TESTING_README.md                # Testing documentation
```

## Testing Structure
```
tests/
├── lambda_test.py                   # Lambda function testing
├── run-all-tests.py                 # Test suite runner
├── template-size-history.csv       # Template size tracking
├── template-size-log.json          # Template size history log
├── test-jwt-auth.py                 # JWT authentication testing
├── test-lambda-resources.py        # Lambda custom resource testing
├── test-monitoring-features.py     # Enhanced monitoring features testing
├── test-parameters.json             # Test parameter configurations
├── test-report.json                 # Test execution reports
└── validate-lambda-syntax.py       # Lambda code syntax validation
```

## Parameter Configuration
```
parameters/
├── development.json                 # Development environment parameters
├── staging.json                     # Staging environment parameters
└── production.json                  # Production environment parameters
```

## Lambda Reference Code
```
src/
├── lambda_function.py               # Reference Lambda handler implementation
├── cloudfront_manager.py            # Reference custom resource manager (from WordPress Guardian)
└── requirements.txt                 # Lambda dependencies (boto3, botocore, cryptography)
```

## Single Template Architecture
The project uses a **single SAR template** with embedded Lambda custom resources to overcome SAR resource type limitations:

```
template.yaml (SAR-compliant single file)
├── Standard CloudFormation Resources:
│   ├── VPC, Subnets, Security Groups
│   ├── IAM Roles and Policies  
│   ├── Application Load Balancer
│   ├── API Gateway HTTP API
│   ├── Cognito User Pool (optional)
│   └── CloudWatch Logs and Alarms
├── Lambda Custom Resource Handler (embedded inline)
└── Custom Resources (Lambda-created):
    ├── Custom::VpcLink → AWS::ApiGatewayV2::VpcLink
    ├── Custom::AutoScaling → AWS::AutoScaling::AutoScalingGroup
    ├── Custom::LaunchTemplate → AWS::EC2::LaunchTemplate  
    ├── Custom::ScalingPolicy → AWS::AutoScaling::ScalingPolicy
    └── Custom::WAF → AWS::WAFv2::WebACL + AWS::WAFv2::IPSet
```

## Kiro Configuration
```
.kiro/
├── settings/                        # Kiro IDE settings
│   └── mcp.json                     # Model Context Protocol configuration
├── steering/                        # AI assistant guidance rules
│   ├── product.md                   # Product overview and use cases
│   ├── tech.md                      # Technology stack and Lambda approach
│   └── structure.md                 # Project organization (this file)
└── specs/                          # Feature specifications
    └── tolling-vision-sar/
        ├── requirements.md          # Lambda-based SAR requirements
        ├── design.md               # Lambda custom resource design
        └── tasks.md                # Implementation tasks
```

## Development Environment
- `.vscode/`: VS Code configuration with Kiro settings
- `tolling-vision-env/`: Python virtual environment for development

## Lambda-Based SAR Architecture

### Single Template Structure (`template.yaml`)
- **Metadata**: SAR publishing configuration and parameter grouping
- **Parameters**: Comprehensive parameter set for all configuration options
- **Conditions**: Complex conditional logic for optional features (JWT, WAF, etc.)
- **Resources**: Mix of standard CloudFormation and Lambda custom resources
- **Lambda Function**: Embedded inline code for custom resource handling
- **Outputs**: Comprehensive outputs from both standard and custom resources

### Lambda Custom Resource Strategy
1. **VPC Link Creation**: Lambda creates `AWS::ApiGatewayV2::VpcLink` (not supported by SAR)
2. **Auto Scaling Management**: Lambda creates `AWS::AutoScaling::AutoScalingGroup` and `AWS::EC2::LaunchTemplate`
3. **WAF Protection**: Lambda creates `AWS::WAFv2::WebACL` and `AWS::WAFv2::IPSet`
4. **Scaling Policies**: Lambda creates `AWS::AutoScaling::ScalingPolicy`
5. **Error Handling**: Comprehensive timeout and failure management

### Enhanced Monitoring Architecture
1. **SNS Notifications**: Critical alerts via email for infrastructure issues
2. **Custom Metrics**: Application-specific metrics in `TollingVision/Application` namespace
3. **Enhanced Dashboard**: Comprehensive CloudWatch dashboard with custom widgets
4. **Metric Filters**: Log-based metrics for container events and processing statistics

### Parameter Grouping
1. Docker Image Configuration (LicenseKey, ProcessCount, ImageArchitecture)
2. EC2 and Auto Scaling Configuration (DesiredCapacity, MaxSize, OnDemandPercentage)
3. API Gateway and Domain Configuration (ApiCustomDomainName, CertificateArn)
4. Authentication Configuration (EnableJwtAuth, CognitoUserPoolId)
5. Security Configuration (EnableWAF, AllowedIpCidrs)
6. Network Configuration (VpcCidr, subnet configurations)
7. Observability Configuration (EnableSNSNotifications, EnableCustomMetrics)

### Benefits of Lambda-Based Architecture
- **SAR Compatibility**: Single template maintains marketplace presence
- **Complete Functionality**: All AWS resource types supported via Lambda
- **No External Dependencies**: Everything embedded in single template
- **Proven Pattern**: Based on successful WordPress Static Site Guardian implementation
- **Robust Error Handling**: Comprehensive timeout and failure management
- **Enhanced Monitoring**: Built-in observability with custom metrics
- **Production Ready**: Enterprise-grade monitoring and alerting capabilities

## Naming Conventions
- **CloudFormation Resources**: PascalCase (`VPC`, `PrivateSubnet1`)
- **Custom Resources**: `Custom::ResourceType` format (`Custom::VpcLink`, `Custom::AutoScaling`)
- **Parameters**: PascalCase with descriptive names (`ApiCustomDomainName`)
- **Outputs**: PascalCase matching resource purpose (`ApiGatewayEndpoint`, `VpcLinkId`)
- **Lambda Functions**: Descriptive names with resource type (`TollingVisionCustomResourceHandler`)
- **Tags**: Consistent tagging with `Name` and `Application` keys

## Development Workflow
1. **Environment Setup**: Create and activate Python 3 virtual environment (`python3 -m venv tolling-vision-env && source tolling-vision-env/bin/activate`)
2. **Template Changes**: Modify single `template.yaml` with embedded Lambda code
3. **Lambda Development**: Update embedded Lambda function code for custom resources
4. **Validation**: Test CloudFormation template syntax and Lambda code (within virtual environment)
   - Small templates (< 51KB): Use `--template-body file://template.yaml`
   - Large templates (51KB - 450KB): Upload to S3 and use `--template-url`
5. **Testing**: Run comprehensive test suite
   - `python tests/run-all-tests.py` - Full test suite
   - `python tests/test-monitoring-features.py` - Monitoring features validation
   - `python tests/validate-lambda-syntax.py` - Lambda code syntax validation
6. **Documentation**: Update README.md, docs/, and spec files
7. **SAR Publishing**: Ensure template meets SAR size limits (450KB max via S3)
8. **Environment Cleanup**: Deactivate virtual environment when done (`deactivate`)

## Lambda Custom Resource Development

**CRITICAL**: Always use Python virtual environments for development and testing to ensure consistent dependencies and avoid conflicts.

**AWS CLI IMPORTANT**: Always use `--no-paginate` flag with AWS CLI commands to prevent interactive prompts that require pressing Enter. This ensures commands run smoothly in automated environments and scripts.

### Development Steps:
1. **Virtual Environment**: Create and activate isolated Python environment
2. **Handler Function**: Main `lambda_handler` with comprehensive error handling
3. **Resource Routing**: Route requests based on `ResourceType` parameter
4. **AWS API Calls**: Use boto3 to create/update/delete AWS resources
5. **CloudFormation Response**: Send proper SUCCESS/FAILED responses
6. **Timeout Management**: Handle 15-minute Lambda timeout gracefully
7. **State Management**: Track resource IDs for updates and deletions
8. **Local Testing**: Test Lambda code in virtual environment before embedding
9. **Environment Cleanup**: Deactivate virtual environment when development session ends

### Virtual Environment Commands:
```bash
# Create virtual environment (always use python3)
python3 -m venv tolling-vision-env

# Activate (Linux/macOS)
source tolling-vision-env/bin/activate

# Install dependencies
pip install boto3 botocore cryptography

# Work on Lambda code...

# Validate template (small < 51KB) - always use --no-paginate
aws cloudformation validate-template --template-body file://template.yaml --no-paginate

# Validate template (large 51KB-450KB via S3) - always use --no-paginate
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml
aws cloudformation validate-template --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml --no-paginate

# Check stack status without pagination
aws cloudformation describe-stacks --stack-name my-stack --no-paginate

# List stack resources without pagination
aws cloudformation list-stack-resources --stack-name my-stack --no-paginate

# Deactivate when done
deactivate
```