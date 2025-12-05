# SAR Troubleshooting Guide

This guide helps resolve common issues when deploying to AWS Serverless Application Repository (SAR).

## Common Issues and Solutions

### 1. S3 Bucket Policy Error

**Error Message:**
```
An error occurred (BadRequestException) when calling the CreateApplication operation: 
The AWS Serverless Application Repository does not have read access to bucket 'my-sar-artifacts-bucket', 
key 'sar/20250919-215550/template.yaml'. Please update your Amazon S3 bucket policy to grant 
the service read permissions to the application artifacts you have uploaded to your S3 bucket.
```

**Root Cause:** SAR service doesn't have permission to read your S3 bucket.

**Solution:**

#### Quick Fix (Automated)
```bash
# Run the automated fix script
./scripts/fix-sar-s3-permissions.sh my-sar-artifacts-bucket us-east-1
```

#### Manual Fix
1. **Apply S3 Bucket Policy:**
```bash
# Use the provided policy file
aws s3api put-bucket-policy --bucket my-sar-artifacts-bucket --policy file://s3-bucket-policy-for-sar.json
```

2. **Verify Policy Applied:**
```bash
aws s3api get-bucket-policy --bucket my-sar-artifacts-bucket
```

3. **Test Template Access:**
```bash
aws cloudformation validate-template --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml --no-paginate
```

### 2. Template Size Exceeds Limits

**Error Message:**
```
Member must have length less than or equal to 51200
```

**Root Cause:** Template is larger than 51KB direct upload limit.

**Solution:**
Always use S3-based deployment for large templates:

```bash
# Upload to S3 first
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/sar/$(date +%Y%m%d-%H%M%S)/template.yaml

# Use template-url instead of template-body
aws serverlessrepo create-application \
  --name tolling-vision \
  --description "Tolling Vision ANPR/MMR processing infrastructure" \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/sar/20250919-215550/template.yaml \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

### 3. Template Validation Errors

**Error Messages:**
```
Template format error: Mappings attribute name 'x86-64' must contain only alphanumeric characters
Template format error: Mappings attribute name 'ProcessCount1-2' must contain only alphanumeric characters
```

**Root Cause:** CloudFormation mapping keys cannot contain hyphens or special characters.

**Solution:**
These issues have been fixed in the template:
- `x86-64` mapping keys converted to `x8664`
- `ProcessCount1-2` mapping keys converted to `ProcessCount1to2`
- User-facing parameter values preserved for clarity

**CloudFormation Function Parameter Limits:**
```
Template error: every Fn::Or object requires a list of at least 2 and at most 10 boolean parameters
```

**Root Cause:** CloudFormation `!Or` and `!And` functions support maximum 10 parameters.

**Solution:**
Fixed by splitting large conditions:
- `ProcessCount17to32` split into `ProcessCount17to24` and `ProcessCount25to32`
- Combined using nested conditions to stay within limits

### 4. Circular Dependency Errors

**Error Message:**
```
Circular dependency between resources: [GRPCListener, HttpApiRoute, VpcLinkSecurityGroup, 
TollingVisionDashboard, GrpcApiIntegration, ALBResponseTimeAlarm, CustomVpcLink, ALBSecurityGroup, 
HTTPListener, EC2SecurityGroup, HttpApiIntegration, CustomAutoScalingGroup, GrpcApiRoute, 
ALBUnhealthyTargetsAlarm, ApplicationLoadBalancer]
```

**Root Cause:** Resources reference each other in a way that creates a dependency loop.

**Common Causes:**
- Dashboard references Lambda functions that have alarm actions referencing other resources
- Custom resources depend on resources that reference the custom resource outputs
- Cross-references between API Gateway, ALB, and monitoring resources

**Solution:**
Fixed by breaking the dependency chain:
- Dashboard uses function name string instead of `!Ref AutomatedRecoveryFunction`
- Removed unnecessary cross-references between monitoring and infrastructure resources
- Used static names instead of dynamic references where possible

**Prevention:**
- Use `tests/test-circular-dependencies.py` to detect potential cycles
- Minimize cross-references between resource groups
- Use static names for monitoring resources when possible

### 5. Unresolved Resource Dependencies

**Error Message:**
```
Unresolved resource dependencies [PublicSubnet1] in the Outputs block of the template
```

**Root Cause:** Template outputs reference resources that don't exist.

**Common Causes:**
- Outputs section references resources that were removed or renamed
- Missing infrastructure components (public subnets, NAT gateways, etc.)
- Incomplete VPC architecture implementation

**Solution:**
Fixed by completing the VPC architecture:
- Added missing public subnets (`PublicSubnet1`, `PublicSubnet2`)
- Added NAT gateways (`NATGateway1`, `NATGateway2`) with Elastic IPs
- Added route tables and associations for proper networking
- Used parameter references instead of hardcoded CIDR blocks

**Prevention:**
- Ensure all referenced resources exist before adding outputs
- Complete infrastructure architectures (don't leave components half-implemented)
- Use consistent naming conventions between resources and outputs

**Other Template Validation Errors:**
```
Template format error: unsupported structure
```

**Root Cause:** Template syntax or structure issues.

**Solution:**
1. **Validate Template Locally:**
```bash
# For S3-based templates
aws cloudformation validate-template --template-url https://my-bucket.s3.amazonaws.com/template.yaml --no-paginate

# Check template size
wc -c template.yaml
```

2. **Common Template Issues:**
- Missing required parameters
- Invalid CloudFormation syntax
- Unsupported resource types in SAR
- Circular dependencies
- Invalid mapping key names (must be alphanumeric only)
- CloudFormation intrinsic function parameter limits exceeded
- Circular dependencies between resources

### 4. IAM Permissions Issues

**Error Message:**
```
User is not authorized to perform: serverlessrepo:CreateApplication
```

**Root Cause:** Insufficient IAM permissions.

**Solution:**
Ensure your IAM user/role has these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "serverlessrepo:CreateApplication",
        "serverlessrepo:UpdateApplication",
        "serverlessrepo:GetApplication",
        "serverlessrepo:ListApplications",
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "cloudformation:ValidateTemplate"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5. Application Already Exists

**Error Message:**
```
An application with the provided name already exists
```

**Root Cause:** Application name conflict.

**Solution:**
1. **Update Existing Application:**
```bash
# Get application ID
aws serverlessrepo list-applications --no-paginate | grep -A 5 "tolling-vision"

# Update existing application
aws serverlessrepo update-application \
  --application-id arn:aws:serverlessrepo:us-east-1:123456789012:applications/tolling-vision \
  --template-url https://my-bucket.s3.amazonaws.com/template.yaml \
  --no-paginate
```

2. **Use Different Name:**
```bash
aws serverlessrepo create-application \
  --name tolling-vision-v2 \
  --description "Tolling Vision ANPR/MMR processing infrastructure" \
  --template-url https://my-bucket.s3.amazonaws.com/template.yaml \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

### 6. Region-Specific Issues

**Error Message:**
```
The bucket you are attempting to access must be addressed using the specified endpoint
```

**Root Cause:** S3 bucket and SAR service in different regions.

**Solution:**
1. **Use Region-Specific S3 URLs:**
```bash
# For us-west-2
https://my-bucket.s3.us-west-2.amazonaws.com/template.yaml

# For eu-west-1  
https://my-bucket.s3.eu-west-1.amazonaws.com/template.yaml
```

2. **Create SAR Application in Same Region:**
```bash
aws serverlessrepo create-application \
  --region us-west-2 \
  --name tolling-vision \
  --template-url https://my-bucket.s3.us-west-2.amazonaws.com/template.yaml \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

## Diagnostic Commands

### Check Template Status
```bash
# Validate template
aws cloudformation validate-template --template-url https://my-bucket.s3.amazonaws.com/template.yaml --no-paginate

# Check template size
curl -I https://my-bucket.s3.amazonaws.com/template.yaml | grep -i content-length
```

### Check S3 Permissions
```bash
# Test S3 access
aws s3api head-object --bucket my-bucket --key template.yaml

# Check bucket policy
aws s3api get-bucket-policy --bucket my-bucket
```

### Check SAR Applications
```bash
# List your applications
aws serverlessrepo list-applications --no-paginate

# Get specific application details
aws serverlessrepo get-application --application-id <app-id> --no-paginate
```

### Check IAM Permissions
```bash
# Test SAR permissions
aws serverlessrepo list-applications --no-paginate

# Check current user/role
aws sts get-caller-identity
```

## Best Practices

### 1. Template Management
- Always use versioned S3 keys (include timestamp)
- Keep template size under 450KB for S3 deployment
- Validate templates before uploading to S3
- Use consistent naming conventions

### 2. S3 Bucket Setup
- Enable versioning on SAR artifacts bucket
- Apply proper bucket policy for SAR access
- Use lifecycle policies to manage old versions
- Consider cross-region replication for multi-region deployments

### 3. SAR Application Management
- Use descriptive application names and descriptions
- Include proper labels and categories
- Maintain semantic versioning
- Document parameter requirements clearly

### 4. Security Considerations
- Limit S3 bucket policy to minimum required permissions
- Use IAM roles instead of users when possible
- Regularly audit SAR application permissions
- Monitor SAR application usage and deployments

## Emergency Recovery

### If SAR Application is Corrupted
1. **Delete Application:**
```bash
aws serverlessrepo delete-application --application-id <app-id>
```

2. **Recreate with New Version:**
```bash
# Upload new template version
aws s3 cp template.yaml s3://my-bucket/sar/$(date +%Y%m%d-%H%M%S)/template.yaml

# Create new application
aws serverlessrepo create-application \
  --name tolling-vision \
  --template-url https://my-bucket.s3.amazonaws.com/sar/$(date +%Y%m%d-%H%M%S)/template.yaml \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

### If S3 Bucket is Inaccessible
1. **Create New Bucket:**
```bash
aws s3api create-bucket --bucket my-sar-backup-bucket --region us-east-1
```

2. **Apply Bucket Policy:**
```bash
aws s3api put-bucket-policy --bucket my-sar-backup-bucket --policy file://s3-bucket-policy-for-sar.json
```

3. **Upload Template:**
```bash
aws s3 cp template.yaml s3://my-sar-backup-bucket/template.yaml
```

## Getting Help

### AWS Support Resources
- [SAR Developer Guide](https://docs.aws.amazon.com/serverlessrepo/latest/devguide/)
- [CloudFormation User Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/)
- [AWS Support Center](https://console.aws.amazon.com/support/)

### Community Resources
- [AWS re:Post](https://repost.aws/)
- [Stack Overflow - AWS SAR](https://stackoverflow.com/questions/tagged/aws-serverless-application-repository)
- [AWS GitHub Issues](https://github.com/aws/serverless-application-model/issues)

### Logging and Monitoring
- CloudTrail logs for SAR API calls
- CloudFormation events for deployment issues
- S3 access logs for template download issues