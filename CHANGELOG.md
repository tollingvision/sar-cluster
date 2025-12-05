# Changelog

All notable changes to the Tolling Vision SAR application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-05

### Added
- Initial SAR application release
- Complete VPC infrastructure with private/public subnets across multiple AZs
- Auto Scaling Group with mixed instance types (On-Demand + Spot)
- Application Load Balancer with health checks for HTTP and gRPC traffic
- API Gateway with custom domain and VPC Link integration
- Optional Cognito User Pool with JWT authentication
- Optional WAF protection with IP allowlisting
- CloudWatch Logs integration for container output
- Support for both ARM64 and x86-64 architectures
- Configurable container parameters (ProcessCount, ConcurrentRequestCount, etc.)
- Cost optimization through Spot instance usage
- Comprehensive parameter validation and constraints
- Security groups with least privilege access
- IAM roles following security best practices
- Optional ALB access logging to S3
- Comprehensive CloudFormation outputs
- Complete validation test suite
- SAR marketplace documentation

### Infrastructure Components
- **Networking**: VPC, Internet Gateway, NAT Gateways, Route Tables, Security Groups
- **Compute**: EC2 Launch Template, Auto Scaling Group with MixedInstancesPolicy
- **Load Balancing**: Application Load Balancer, Target Groups, Listeners
- **API Management**: API Gateway HTTP API, Custom Domain, VPC Link
- **Authentication**: Cognito User Pool, Resource Server, App Client, JWT Authorizer
- **Security**: WAF WebACL, IPSet for allowlisting, Secrets Manager
- **Monitoring**: CloudWatch Logs, S3 bucket for ALB logs

### Configuration Options
- **Container Configuration**: 9 parameters for Tolling Vision container setup
- **Infrastructure Configuration**: 6 parameters for EC2 and Auto Scaling
- **API Configuration**: 2 parameters for custom domain setup
- **Authentication Configuration**: 8 parameters for Cognito and JWT setup
- **Security Configuration**: 2 parameters for WAF and IP allowlisting
- **Network Configuration**: 1 parameter for VPC CIDR customization

### Documentation
- Comprehensive README with deployment instructions
- Detailed parameter documentation with examples
- Security considerations and best practices
- Troubleshooting guide with common issues
- API usage examples for HTTP/1.1 and gRPC
- Cost optimization recommendations
- SAR packaging and publishing guide
- Usage examples for different deployment scenarios

### Validation and Testing
- CloudFormation template validation with cfn-lint
- Parameter constraint testing
- Conditional resource creation testing
- Template size validation for SAR compliance
- Automated validation test suite
- Build automation with Makefile

### Security Features
- Private subnet deployment for all compute resources
- Security groups with minimal required permissions
- Optional JWT authentication with custom scopes
- Optional WAF protection with IP allowlisting
- TLS encryption for all API traffic
- Secrets stored in AWS Secrets Manager
- IAM roles with least privilege principle
- Network isolation and controlled egress

### Cost Optimization
- Support for Spot instances with configurable percentage
- ARM64 instance support for cost savings
- Right-sized instance recommendations based on ProcessCount
- Configurable Auto Scaling parameters
- Optional components to reduce costs when not needed

### Monitoring and Observability
- CloudWatch Logs for container output
- API Gateway access and execution logging
- Optional ALB access logs to S3
- CloudWatch metrics for all AWS services
- Comprehensive tagging for cost tracking
- Health checks and monitoring integration

## [Unreleased]

### Planned Features
- CloudWatch dashboards for operational monitoring
- SNS notifications for operational alerts
- Enhanced auto scaling policies based on custom metrics
- Support for additional AWS regions
- Integration with AWS X-Ray for distributed tracing
- Enhanced security with AWS Config rules
- Cost optimization recommendations dashboard
- Automated backup and disaster recovery procedures

### Known Issues
- None currently identified

### Breaking Changes
- None planned for v1.x series

---

## Version Support

- **v1.0.x**: Current stable release, actively maintained
- **v0.x**: Pre-release versions, no longer supported

## Migration Guide

### From Pre-Release to v1.0.0
This is the initial stable release. No migration required.

## Support and Maintenance

- **Security Updates**: Applied as patch releases (1.0.x)
- **Feature Updates**: Applied as minor releases (1.x.0)
- **Breaking Changes**: Applied as major releases (x.0.0)

For support and questions:
- **Infrastructure Issues**: AWS Support or GitHub Issues
- **Tolling Vision Issues**: [tollingvision.com/support](https://tollingvision.com/support)
- **Documentation**: [tollingvision.com/docs](https://tollingvision.com/docs)