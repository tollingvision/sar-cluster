# Tolling Vision Operations Guide

## Overview

This guide covers operational procedures, monitoring, and troubleshooting for the Tolling Vision infrastructure deployed via SAR with Lambda custom resources.

## Prerequisites

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv tolling-vision-env
source tolling-vision-env/bin/activate

# Install required tools
pip install boto3 botocore cryptography awscli

# Verify AWS access
aws sts get-caller-identity --no-paginate
```

## Daily Operations

### Health Monitoring

#### Infrastructure Health Checks
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --no-paginate

# Verify Auto Scaling Group health (Lambda-created)
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --query 'AutoScalingGroups[0].Instances[*].[InstanceId,HealthStatus,LifecycleState]' \
  --output table \
  --no-paginate

# Check VPC Link status (Lambda-created)
aws apigatewayv2 get-vpc-link \
  --vpc-link-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcLinkId`].OutputValue' \
    --output text) \
  --query 'VpcLinkStatus' \
  --output text \
  --no-paginate
```

#### Application Health Checks
```bash
# Test HTTP/1.1 endpoint
curl -f -s -o /dev/null -w "%{http_code}" https://api.yourdomain.com/health

# Test gRPC endpoint (if grpcurl is available)
grpcurl -plaintext api.yourdomain.com:8443 grpc.health.v1.Health/Check

# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=tolling-vision-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --no-paginate
```

### Log Monitoring

#### Application Logs
```bash
# View recent container logs
aws logs tail /aws/ec2/tolling-vision \
  --since 1h \
  --no-paginate

# Search for errors in application logs
aws logs filter-log-events \
  --log-group-name /aws/ec2/tolling-vision \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Monitor license validation issues
aws logs filter-log-events \
  --log-group-name /aws/ec2/tolling-vision \
  --filter-pattern "license" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate
```

#### Lambda Custom Resource Logs
```bash
# Monitor Lambda custom resource handler
aws logs tail /aws/lambda/tolling-vision-custom-resource-handler \
  --since 1h \
  --no-paginate

# Check for Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/tolling-vision-custom-resource-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --no-paginate
```

#### API Gateway Logs
```bash
# View API Gateway access logs
aws logs tail /aws/apigateway/tolling-vision-api \
  --since 1h \
  --no-paginate

# Check for 4xx/5xx errors
aws logs filter-log-events \
  --log-group-name /aws/apigateway/tolling-vision-api \
  --filter-pattern "[timestamp, requestId, ip, user, timestamp, method, resource, protocol, status=4*, size, referer, agent, requestTime, integrationRequestTime, integrationStatus, integrationErrorMessage]" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate
```

### Performance Monitoring

#### Auto Scaling Metrics
```bash
# Check CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value=$(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --no-paginate

# Check memory utilization (if CloudWatch agent is configured)
aws cloudwatch get-metric-statistics \
  --namespace CWAgent \
  --metric-name mem_used_percent \
  --dimensions Name=AutoScalingGroupName,Value=$(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --no-paginate
```

#### Load Balancer Metrics
```bash
# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`HttpTargetGroupArn`].OutputValue' \
    --output text) \
  --no-paginate

# Check ALB request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancer,Value=$(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerFullName`].OutputValue' \
    --output text) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --no-paginate
```

## Scaling Operations

### Manual Scaling
```bash
# Scale up Auto Scaling Group
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 5 \
  --no-paginate

# Scale down Auto Scaling Group
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 2 \
  --no-paginate

# Check scaling activity
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --max-items 10 \
  --no-paginate
```

### Instance Management
```bash
# List instances in Auto Scaling Group
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --query 'AutoScalingGroups[0].Instances[*].[InstanceId,AvailabilityZone,HealthStatus,LifecycleState]' \
  --output table \
  --no-paginate

# Terminate unhealthy instance (will be replaced automatically)
aws autoscaling terminate-instance-in-auto-scaling-group \
  --instance-id i-1234567890abcdef0 \
  --should-decrement-desired-capacity \
  --no-paginate
```

## Security Operations

### JWT Token Management
```bash
# Get Cognito client credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoClientSecretArn`].OutputValue' \
    --output text) \
  --query 'SecretString' \
  --output text \
  --no-paginate

# Rotate client secret (if needed)
aws cognito-idp update-user-pool-client \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --client-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoAppClientId`].OutputValue' \
    --output text) \
  --generate-secret \
  --no-paginate
```

### WAF Management
```bash
# Check WAF WebACL status (Lambda-created)
aws wafv2 get-web-acl \
  --scope REGIONAL \
  --id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`WAFWebACLId`].OutputValue' \
    --output text) \
  --no-paginate

# View WAF metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name AllowedRequests \
  --dimensions Name=WebACL,Value=$(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`WAFWebACLId`].OutputValue' \
    --output text) Name=Region,Value=us-east-1 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --no-paginate
```

## Troubleshooting

### Common Issues

#### High CPU Usage
```bash
# Check CPU metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value=$(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --no-paginate

# Scale up if needed
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 5 \
  --no-paginate
```

#### License Validation Failures
```bash
# Check license-related logs
aws logs filter-log-events \
  --log-group-name /aws/ec2/tolling-vision \
  --filter-pattern "license" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Verify outbound connectivity (NAT Gateway)
aws ec2 describe-nat-gateways \
  --filter Name=vpc-id,Values=$(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
    --output text) \
  --query 'NatGateways[*].[NatGatewayId,State]' \
  --output table \
  --no-paginate
```

#### API Gateway 5xx Errors
```bash
# Check API Gateway integration errors
aws logs filter-log-events \
  --log-group-name /aws/apigateway/tolling-vision-api \
  --filter-pattern "[timestamp, requestId, ip, user, timestamp, method, resource, protocol, status=5*, size, referer, agent, requestTime, integrationRequestTime, integrationStatus, integrationErrorMessage]" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --no-paginate

# Check VPC Link connectivity
aws apigatewayv2 get-vpc-link \
  --vpc-link-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcLinkId`].OutputValue' \
    --output text) \
  --no-paginate
```

#### Lambda Custom Resource Issues
```bash
# Check Lambda function errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/tolling-vision-custom-resource-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --no-paginate

# Check Lambda function configuration
aws lambda get-function \
  --function-name tolling-vision-custom-resource-handler \
  --no-paginate

# Check Lambda function metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=tolling-vision-custom-resource-handler \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --no-paginate
```

### Emergency Procedures

#### Complete Service Restart
```bash
# Terminate all instances (will be replaced)
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 0 \
  --no-paginate

# Wait for termination
sleep 60

# Scale back up
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(aws cloudformation describe-stack-resources \
    --stack-name tolling-vision-prod \
    --logical-resource-id AutoScalingCustomResource \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text) \
  --desired-capacity 3 \
  --no-paginate
```

#### Stack Recovery
```bash
# Check stack drift
aws cloudformation detect-stack-drift \
  --stack-name tolling-vision-prod \
  --no-paginate

# Get drift detection results
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id <detection-id> \
  --no-paginate

# Update stack if needed
aws cloudformation update-stack \
  --stack-name tolling-vision-prod \
  --template-body file://template.yaml \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_IAM \
  --no-paginate
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### Weekly Tasks
1. Review CloudWatch alarms and metrics
2. Check Auto Scaling Group health and capacity
3. Verify certificate expiration dates
4. Review security group rules and WAF logs
5. Check for AWS service updates and patches

#### Monthly Tasks
1. Review and rotate access keys if needed
2. Update instance AMIs if new versions available
3. Review cost optimization opportunities
4. Test disaster recovery procedures
5. Update documentation and runbooks

#### Quarterly Tasks
1. Review and update security policies
2. Conduct security audit and penetration testing
3. Review capacity planning and scaling policies
4. Update disaster recovery and business continuity plans
5. Review and update monitoring and alerting thresholds

### Backup and Recovery

#### Configuration Backup
```bash
# Export CloudFormation template
aws cloudformation get-template \
  --stack-name tolling-vision-prod \
  --template-stage Processed \
  --no-paginate > backup-template.yaml

# Export stack parameters
aws cloudformation describe-stacks \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Parameters' \
  --no-paginate > backup-parameters.json

# Backup Cognito User Pool configuration
aws cognito-idp describe-user-pool \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --no-paginate > backup-cognito-config.json
```

## Environment Cleanup

### Deactivate Virtual Environment
```bash
# Always deactivate when done
deactivate

# Verify deactivation
which python3
```

## Monitoring and Alerting Setup

For comprehensive monitoring setup, see the CloudWatch alarms and SNS topics created by the CloudFormation template. Key metrics to monitor:

- API Gateway 4xx/5xx error rates
- ALB target health and response times
- Auto Scaling Group instance health
- Lambda custom resource execution errors
- VPC Link connectivity status
- WAF blocked request rates (if enabled)

## Support and Escalation

For issues requiring escalation:
1. Collect relevant logs and metrics
2. Document steps taken to resolve
3. Include stack outputs and resource IDs
4. Provide timeline of issue occurrence
5. Contact AWS Support with case details