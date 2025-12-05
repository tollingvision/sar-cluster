# Tolling Vision SAR Infrastructure

[![AWS SAR](https://img.shields.io/badge/AWS-SAR%20Compatible-orange)](https://serverlessrepo.aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CloudFormation](https://img.shields.io/badge/CloudFormation-Template-blue)](template.yaml)

Complete AWS Serverless Application Repository (SAR) template for deploying secure, scalable **Tolling Vision ANPR/MMR** (Automatic Number Plate Recognition/Make Model Recognition) processing infrastructure.

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐    ┌─────────────────────┐
│   API Clients   │───▶│  Public ALB      │───▶│      VPC            │
│                 │     │ (HTTPS:443)      │    │                     │
└─────────────────┘     └──────────────────┘    │  ┌─────────────────┐│
                                │               │  │  Auto Scaling   ││
                       ┌────────▼────────┐      │  │     Group       ││
                       │ Optional WAF    │      │  │ (Lambda Created)││
                       │   Protection    │      │  └─────────────────┘│
                       └─────────────────┘      │           │         │
                                                │ ┌─────────▼───────┐ │
┌─────────────────┐     ┌──────────────────┐    │ │   EC2 Instances │ │
│ Optional Route53│───▶│  Custom Domain   │    │ │  (Private IPs)  │ │
│   DNS Records   │     │   (Optional)     │    │ │                 │ │
└─────────────────┘     └──────────────────┘    │ │ Container JWT   │ │
                                                │ │ Auth (Optional) │ │
                                                │ └─────────────────┘ │
                                                └─────────────────────┘
```

## ✨ Key Features

### 🔒 **Security First**
- **Private Infrastructure**: All compute resources in private subnets with no public IPs
- **Public ALB Entry Point**: Single internet-facing load balancer with HTTPS termination
- **Container JWT Authentication**: Optional Cognito-based JWT validation within containers
- **Optional WAF Protection**: Layer 7 filtering with IP allowlisting and AWS Managed Rules
- **IAM Least Privilege**: Minimal required permissions for all components

### 🚀 **Simplified Architecture**
- **Lambda Custom Resources**: Creates Auto Scaling Groups and WAF resources for SAR compatibility
- **Protocol Support**: HTTP/1.1 + gRPC-Web (port 443)
- **Optional DNS Management**: Route53 integration for custom domains

### 📈 **Scalability & Performance**
- **Auto Scaling**: Configurable capacity with On-Demand/Spot instances
- **Multi-AZ Deployment**: High availability across availability zones
- **Architecture Support**: ARM64 (default) and x86-64 containers
- **Load Balancing**: Application Load Balancer with health checks

### 💰 **Cost Optimization**
- **Spot Instances**: Configurable percentage for cost savings
- **Right-sized Instances**: Automatic selection based on ProcessCount
- **ARM64 Default**: Better price/performance ratio
- **Flexible Scaling**: Scale to zero when not in use

## 📋 Prerequisites

### Required Resources
1. **Tolling Vision License Key**: Valid license key from tollingvision.com (`LicenseKey` parameter)
2. **Maximum Instance Count**: Must specify maximum number of instances (`MaxSize` parameter)

### Optional Resources (for enhanced functionality)
1. **SSL Certificate**: ACM certificate for HTTPS (recommended for production)
2. **Custom Domain**: Domain name for Route53 DNS management
3. **Cognito User Pool**: Existing User Pool for JWT authentication
4. **Route53 Hosted Zone**: For automatic DNS record creation

### AWS Permissions
- CloudFormation stack creation
- Lambda function execution
- VPC and networking resource creation
- IAM role and policy management

## ⚙️ Configuration Parameters

### 🔑 **Required Configuration**
| Parameter | Description | Example |
|-----------|-------------|---------|
| `LicenseKey` | Tolling Vision license key | `your-license-key` |
| `MaxSize` | Maximum instance count | `10` |

### 🐳 **Container Configuration**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ConcurrentRequestCount` | `1` | Concurrent requests per process |
| `ProcessCount` | `1` | Processing threads (1-64) |
| `MaxRequestSize` | `6291456` | Max request size (6MB) |
| `ImageArchitecture` | `arm64` | Container architecture |
| `ImageTag` | `arm64` | Container Image Tag |
| `Backlog ` | `10` | Request Queue Size |
| `BacklogTimeout ` | `60` | Queue Timeout (seconds) |
| `RequestTimeout` | `30` | Request Timeout (seconds) |

### 🔧 **Auto Scaling Configuration**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `MinSize` | `0` | Minimum instances |
| `DesiredCapacity` | `0` | Initial instance count |
| `OnDemandPercentage` | `100` | On-Demand vs Spot percentage |
| `KeyPairName` | Empty  | EC2 Key Pair (optional |
| `EnableDetailedMonitoring` | `false` | Enable Detailed CloudWatch Monitoring |

### 🌐 **Network & Domain & SSL Configuration (Optional)**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `VpcCidr` | `10.0.0.0/16`| VPC CIDR Block |
| `PrivateSubnet1Cidr` | `10.0.1.0/24` | Private Subnet 1 CIDR |
| `PrivateSubnet2Cidr` | `10.0.2.0/24` | Private Subnet 2 CIDR|
| `PublicSubnet1Cidr` | `10.0.101.0/24` | Public Subnet 1 CIDR |
| `PublicSubnet2Cidr` | `10.0.102.0/24` | Public Subnet 2 CIDR|
| `DomainName` | Empty | Custom domain name |
| `CertificateArn` | Empty | ACM certificate ARN for HTTPS |
| `EnableDNS` | `false` | Create Route53 DNS records |

### 🔐 **Container JWT Authentication (Optional)**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `CognitoUserPoolId` | Empty | Existing Cognito User Pool ID |
| `CognitoRegion` | Empty | AWS region of Cognito User Pool |
| `CognitoAppClientId` | Empty | Cognito App Client ID |
| `CognitoRequiredScope` | Empty | Required JWT scope for access |

### 🛡️ **Security & Logging (Optional)**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `EnableWAF` | `false` | Enable WAF protection on ALB |
| `AllowedIpCidrs` | Empty | IP CIDR ranges for WAF rules |
| `EnableAWSManagedRules` | `true` | Enable AWS Managed Rule Groups |
| `CloudWatchLogRetentionDays` | `7`| CloudWatch Log Retention (days) |
| `EnableSNSNotifications` | `false`| Enable SNS Notifications |
| `SNSNotificationEmail` | Empty| Notification Email Address |
| `EnableCustomMetrics` | `true`| Enable Custom Application Metrics |
| `EnableALBAccessLogs` | `false` | Enable ALB access logs to S3 |
| `ALBAccessLogsBucketName` | Empty | S3 bucket for ALB logs |

## 🔌 API Endpoints

After deployment, your Tolling Vision API will be available at:

### With Custom Domain (when DNS management enabled)
```bash
# HTTP/1.1 Endpoint
https://DOMAIN_NAME/
```

### With ALB DNS Name (default)
```bash
# HTTP/1.1 Endpoint
https://GENERATED_LB_NAME-AWS_ACCOUNT_ID.REGION.elb.amazonaws.com/
```

### ℹ️ Where to find the ALB DNS name
If you did not enable DNS management with a custom domain, the Application Load Balancer (ALB) DNS name is available
in the **CloudFormation stack Outputs**. Look for the key: `ALBEndpoint`.

### Protocol Details
- **HTTP/1.1 + gRPC-Web**: Port 443 (HTTPS) → Container port 80 (HTTP)
- **Health Check**: `/` endpoint (status code: 200)

## 🔑 Authentication

### Container-Level JWT Authentication (Optional)

When JWT authentication is enabled, the container validates JWT tokens internally using the provided Cognito configuration.

#### Prerequisites
1. **Existing Cognito User Pool**: Must be created separately
2. **App Client**: Configured for client credentials flow
3. **Resource Server**: With custom scopes defined

### JWT Token Generation
```bash
# Get client credentials (from your Cognito setup)
CLIENT_ID="your-app-client-id"
CLIENT_SECRET="your-app-client-secret"
USER_POOL_DOMAIN="your-user-pool-domain"

# Generate JWT token
curl -X POST https://your-cognito-domain.auth.region.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=$CLIENT_SECRET&scope=api/m2m"
```

## 📊 Enhanced Monitoring & Observability

### 🎯 **Comprehensive Dashboard**
- **Real-time Metrics**: ALB, ASG, Lambda performance
- **Custom Application Metrics**: Container startups, license validations, processing requests/errors
- **Health Summary**: Single-value widgets for quick status overview
- **Log Analysis**: Recent errors and troubleshooting information

### 🚨 **Critical Alerts & Notifications**
- **SNS Email Notifications**: Configurable email alerts for critical issues
- **CloudWatch Alarms**: Lambda errors, ALB unhealthy targets, ASG issues, container errors
- **Escalation Paths**: Immediate notifications for production-critical failures

### 📈 **Custom Application Metrics**
- **Namespace**: `TollingVision/Application`
- **Container Lifecycle**: Startup events, license validation status
- **Processing Performance**: Request throughput, error rates, response times
- **Business Metrics**: ANPR/MMR processing statistics and success rates

### 📋 **CloudWatch Resources**
- **Container Logs**: `/aws/ec2/tolling-vision/[stack-name]`
- **Lambda Logs**: `/aws/lambda/[stack-name]-custom-resource-handler`

### 🎛️ **Monitoring Configuration**
```yaml
# Enable enhanced monitoring features
EnableSNSNotifications: 'true'
SNSNotificationEmail: 'admin@example.com'
EnableCustomMetrics: 'true'
```

### 📊 **Dashboard Access**
Access your operational dashboard at:
```
https://[region].console.aws.amazon.com/cloudwatch/home?region=[region]#dashboards:name=[stack-name]-operational-dashboard
```

For detailed monitoring setup and troubleshooting, see [Enhanced Monitoring Guide](docs/ENHANCED-MONITORING-GUIDE.md).

## 🛠️ Troubleshooting

### 🔧 **Infrastructure Issues**

#### Container Fails to Start
**Problem**: Invalid license key or insufficient resources
**Solution**: Check container logs and license validation
```bash
aws logs tail /aws/ec2/tolling-vision --follow --no-paginate
```

#### JWT Authentication Errors
**Problem**: Invalid token or scope configuration
**Solution**: Verify Cognito configuration and token generation

### 📚 **Detailed Troubleshooting**
For comprehensive troubleshooting guides, see:
- [SAR Troubleshooting Guide](docs/SAR-TROUBLESHOOTING-GUIDE.md) - SAR deployment issues
- [Enhanced Monitoring Guide](docs/ENHANCED-MONITORING-GUIDE.md) - Monitoring and alerting issues

### Support Resources
- **CloudFormation Events**: Monitor stack deployment progress
- **Lambda Logs**: Custom resource execution details
- **Container Logs**: Application-level troubleshooting
- **ALB Health Checks**: Backend connectivity status

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Important Notice

**The Docker container images launched by this template are not covered by the MIT License.**
They are commercial software provided by Smart CFloud Solutions Inc. and are subject to a separate
End User License Agreement (EULA): https://tollingvision.com/eula/

A valid Tolling Vision license key and an active registration/subscription are required
to run the container images.

## 📞 Support

For technical support and questions:
- **Issues**: GitHub Issues
- **Documentation**: This README and inline template comments
- **AWS Support**: For AWS-specific issues

---

**Note**: This template uses Lambda custom resources to overcome AWS SAR limitations while maintaining full functionality and marketplace compatibility.