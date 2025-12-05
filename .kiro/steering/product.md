# Product Overview

## Tolling Vision SAR Application

A complete AWS Serverless Application Repository (SAR) template for deploying secure, scalable Tolling Vision ANPR/MMR (Automatic Number Plate Recognition/Make Model Recognition) processing infrastructure using **Lambda custom resources** to overcome SAR limitations.

## Core Functionality

- **Computer Vision Processing**: ANPR and MMR capabilities for tolling and traffic management
- **Secure Private Infrastructure**: VPC-based deployment with private subnets and controlled access
- **API Gateway Integration**: HTTPS endpoints for both HTTP/1.1 protocol with VPC Links (Lambda-created)
- **Auto Scaling**: Flexible EC2 Auto Scaling with On-Demand and Spot instance support (Lambda-created)
- **Optional Authentication**: Cognito-based JWT machine-to-machine authentication
- **Security Controls**: Optional WAF protection with IP allowlisting (Lambda-created)
- **Enhanced Monitoring**: Comprehensive CloudWatch dashboard with custom metrics and SNS notifications
- **SAR Compatibility**: Single template deployment from AWS marketplace

## Lambda Custom Resource Strategy

- **SAR Limitations**: AWS SAR doesn't support VPC Links, Auto Scaling Groups, Launch Templates, or WAF resources
- **Lambda Solution**: Custom resource handler creates unsupported resources via AWS APIs
- **Proven Pattern**: Based on successful WordPress Static Site Guardian implementation
- **Complete Functionality**: All required AWS resources supported through Lambda functions
- **Marketplace Presence**: Maintains SAR discoverability and one-click deployment

## Architecture Principles

- **Security First**: All compute resources in private subnets, API Gateway as sole public entry point
- **High Availability**: Multi-AZ deployment with load balancing
- **Cost Optimization**: Configurable Spot instance usage and right-sized instance selection
- **Scalability**: Auto Scaling based on demand with configurable capacity limits
- **SAR Compliance**: Single template approach with embedded Lambda custom resources
- **Robust Error Handling**: Comprehensive timeout and failure management for Lambda operations
- **Observability First**: Built-in monitoring and alerting
- **Self-Healing**: Automated response to common infrastructure failures and issues

## Target Use Cases

- Tolling systems requiring license plate recognition
- Traffic monitoring and analytics
- Parking management systems
- Security and access control applications
- Any application requiring automated vehicle identification

## Competitive Advantages

- **SAR Marketplace**: One-click deployment from AWS Serverless Application Repository
- **Complete Feature Set**: All AWS resource types supported via Lambda custom resources
- **No External Dependencies**: Everything embedded in single template
- **Production Ready**: Based on proven Lambda custom resource patterns with enterprise-grade monitoring
- **Cost Effective**: Optimized for Spot instances and ARM64 architecture
- **Comprehensive Observability**: Built-in monitoring eliminates need for external monitoring solutions