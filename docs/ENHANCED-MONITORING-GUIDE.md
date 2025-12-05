# Enhanced Monitoring Guide

This guide covers the enhanced monitoring features added to the Tolling Vision SAR template, including CloudWatch dashboards, SNS notifications, and custom metrics.

## Overview

The enhanced monitoring system provides comprehensive observability for the Tolling Vision infrastructure:

- **CloudWatch Dashboard**: Operational monitoring with custom widgets
- **SNS Notifications**: Critical alerts via email
- **Custom Metrics**: Application-specific monitoring

## Configuration Parameters

### SNS Notifications

```yaml
EnableSNSNotifications: 'true'  # Enable SNS notifications
SNSNotificationEmail: 'admin@example.com'  # Email for alerts
```

### Custom Metrics

```yaml
EnableCustomMetrics: 'true'  # Enable application metrics
```

## Features

### 1. CloudWatch Dashboard

The operational dashboard provides real-time visibility into:

**API Gateway Metrics**
- Request count, 4XX/5XX errors, latency
- HTTP/1.1 and gRPC endpoint performance

**Application Load Balancer Metrics**
- Request count, response times, HTTP status codes
- Target health and availability

**Auto Scaling Group Metrics**
- Instance counts (desired, min, max, in-service)
- Scaling activity and health

**Lambda Custom Resource Metrics**
- Duration, errors, invocations, throttles
- Custom resource operation status

**Custom Application Metrics**
- Container startups and license validations
- Processing requests and errors
- Application-specific performance indicators

**Health Summary Widgets**
- Healthy target count (single value)
- Instances in service (single value)
- Processing requests (last 5 minutes)
- Processing errors (last 5 minutes)

**Log Analysis**
- Recent container errors (table view)
- Lambda custom resource errors (table view)

### 2. SNS Notifications

Critical alerts are sent via SNS to the configured email address:

**Notification Topics**
- Lambda custom resource errors
- Lambda function timeouts
- ALB unhealthy targets
- Auto Scaling Group issues
- Container error patterns

**Email Format**
```
Subject: Tolling Vision Critical Alerts - [Stack Name]
Message: [Alarm description and details]
```

### 3. Custom Application Metrics

Application-specific metrics in the `TollingVision/Application` namespace:

**Container Lifecycle Metrics**
- `ContainerStartups`: Successful container initializations
- `LicenseValidations`: License validation events

**Processing Metrics**
- `ProcessingRequests`: Total processing requests
- `ProcessingErrors`: Processing failures and errors

**Metric Filters**
- Container startup: `[timestamp, level="INFO", message="Container started successfully"]`
- License validation: `[timestamp, level="INFO", message="License validation successful"]`
- Processing requests: `[timestamp, level="INFO", message="Processing request", requestId]`
- Processing errors: `[timestamp, level="ERROR", message="Processing failed", requestId]`

## Deployment

### Standard Deployment (Template < 51KB)

```bash
aws cloudformation create-stack \
  --stack-name tolling-vision-monitoring \
  --template-body file://template.yaml \
  --parameters ParameterKey=EnableSNSNotifications,ParameterValue=true \
               ParameterKey=SNSNotificationEmail,ParameterValue=admin@example.com \
               ParameterKey=EnableCustomMetrics,ParameterValue=true \
  --capabilities CAPABILITY_IAM
```

### S3-Based Deployment (Template > 51KB)

```bash
# Upload template to S3
aws s3 cp template.yaml s3://my-sar-artifacts-bucket/template.yaml

# Deploy using S3 URL
aws cloudformation create-stack \
  --stack-name tolling-vision-monitoring \
  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/template.yaml \
  --parameters ParameterKey=EnableSNSNotifications,ParameterValue=true \
               ParameterKey=SNSNotificationEmail,ParameterValue=admin@example.com \
               ParameterKey=EnableCustomMetrics,ParameterValue=true \
  --capabilities CAPABILITY_IAM
```

## Accessing Monitoring Resources

### CloudWatch Dashboard

```bash
# Get dashboard URL from stack outputs
aws cloudformation describe-stacks \
  --stack-name tolling-vision-monitoring \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchDashboardURL`].OutputValue' \
  --output text
```

### SNS Topic

```bash
# Get SNS topic ARN
aws cloudformation describe-stacks \
  --stack-name tolling-vision-monitoring \
  --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
  --output text
```

### Custom Metrics

```bash
# View custom metrics
aws cloudwatch list-metrics \
  --namespace TollingVision/Application
```

## Monitoring Best Practices

### 1. Alert Thresholds

**Lambda Errors**: Immediate notification (threshold: 1 error)
**Lambda Duration**: Near timeout warning (threshold: 800 seconds)
**ALB Unhealthy Targets**: 2 evaluation periods (threshold: 1 unhealthy)
**ASG No Instances**: 3 evaluation periods (threshold: < 1 instance)
**Container Errors**: Pattern-based (threshold: 5 errors in 5 minutes)

### 2. Dashboard Usage

- Monitor the dashboard during peak traffic periods
- Set up automated screenshots for reporting
- Use log widgets for troubleshooting
- Review custom metrics for application insights

### 3. SNS Notifications

- Use distribution lists for team notifications
- Set up SMS for critical alerts
- Configure notification filtering based on severity
- Test notification delivery regularly

## Troubleshooting

### Common Issues

**SNS Notifications Not Received**
- Verify email subscription confirmation
- Check SNS topic permissions
- Review CloudWatch alarm configuration

**Custom Metrics Not Appearing**
- Verify log group permissions
- Check metric filter patterns
- Ensure container logging is enabled

**Dashboard Not Loading**
- Verify CloudWatch permissions
- Check metric availability
- Review dashboard JSON syntax

### Debugging Commands

```bash
# Check alarm states
aws cloudwatch describe-alarms --state-value ALARM

# View metric filter statistics
aws logs describe-metric-filters --log-group-name /aws/ec2/tolling-vision/[stack-name]

# Test SNS topic
aws sns publish --topic-arn [topic-arn] --message "Test notification"
```

## Cost Considerations

### CloudWatch Costs
- Dashboard: $3/month per dashboard
- Custom metrics: $0.30 per metric per month
- Log ingestion: $0.50 per GB
- Alarm evaluations: $0.10 per alarm per month

### SNS Costs
- Email notifications: $0.75 per 1M notifications
- SMS notifications: $0.75 per 100 SMS (US)

### Lambda Costs
- Typical cost: < $1/month for normal operations

### Optimization Tips
- Use log retention policies to control storage costs
- Set appropriate alarm evaluation periods
- Monitor custom metric usage
- Review and remove unused alarms

## Security Considerations

### IAM Permissions
- SNS topic access is restricted to CloudWatch alarms
- Custom metrics use existing EC2 instance role

### Data Protection
- SNS messages contain operational data only
- No sensitive information in custom metrics
- CloudWatch logs follow existing retention policies

### Access Control
- Dashboard access controlled by IAM policies
- SNS subscriptions require confirmation

## Integration with External Systems

### Third-Party Monitoring
- Export CloudWatch metrics to external systems
- Use SNS webhooks for integration
- Stream logs to external log aggregators

### Automation Platforms
- Trigger external workflows from SNS
- Use CloudWatch Events for advanced automation
- Integrate with CI/CD pipelines for deployment monitoring

### Reporting Systems
- Generate automated reports from dashboard data
- Export metrics for capacity planning
- Create SLA reports from availability metrics