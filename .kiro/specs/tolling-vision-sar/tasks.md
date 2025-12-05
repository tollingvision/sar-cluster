# Implementation Plan

## Core Infrastructure Tasks (Completed)

- [x] 1. Create Lambda custom resource handler foundation
  - Implement main lambda_handler function with comprehensive error handling and timeout management
  - Create resource type routing for VpcLink, AutoScaling, LaunchTemplate, and WAF resources
  - Add CloudFormation response handling with proper SUCCESS/FAILED status management
  - Implement emergency response function for critical failure scenarios
  - _Requirements: 1.1, 1.4, 1.5_

- [x] 2. Implement VPC Link custom resource handler
  - Create VpcLinkResource class for API Gateway VPC Link creation and management
  - Handle VPC Link creation with proper subnet and security group configuration
  - Implement update and delete operations with state tracking
  - Add comprehensive error handling for VPC Link-specific failures
  - _Requirements: 3.3, 2.1_

- [x] 3. Implement Auto Scaling Group custom resource handler
  - Create AutoScalingResource class for ASG, Launch Template, and Scaling Policy management
  - Handle Launch Template creation with architecture-specific AMI selection and User Data
  - Implement Auto Scaling Group creation with MixedInstancesPolicy for On-Demand/Spot instances
  - Add scaling policy creation and target group registration
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 5.1, 5.2_

- [x] 4. Implement WAF custom resource handler
  - Create WAFResource class for WAFv2 WebACL and IPSet management
  - Handle WebACL creation with IP allowlisting rules and default block action
  - Implement IPSet creation for allowed CIDR ranges
  - Add WebACL association with API Gateway custom domain
  - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 5. Create standard CloudFormation resources (SAR-compatible)
  - Implement VPC resource with configurable CIDR block and subnets
  - Create security groups for VPC Link, ALB, and EC2 with minimal permissions
  - Set up Internet Gateway, NAT Gateways, and route tables
  - Define IAM roles and policies for EC2, Lambda, and API Gateway
  - _Requirements: 2.1, 2.4, 2.5, 8.4_

- [x] 6. Implement Application Load Balancer and API Gateway (standard resources)
  - Create private ALB in private subnets with target group for HTTP
  - Implement API Gateway HTTP API with custom domain and ACM certificate
  - Configure ALB listeners and health checks for container port 80
  - Set up API Gateway route for HTTP/1.1 (443) traffic
  - _Requirements: 3.1, 3.2_

- [x] 7. Implement Cognito authentication resources (standard CloudFormation)
  - Create Cognito User Pool with conditional logic based on CreateCognitoUserPool parameter
  - Implement Resource Server with custom scope configuration for machine-to-machine auth
  - Set up App Client with client credentials flow and secret generation
  - Store client secret in AWS Secrets Manager with proper access policies
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 8. Create single SAR template with embedded Lambda function
  - Embed Lambda custom resource handler code inline in CloudFormation template
  - Create Custom::VpcLink resource using Lambda function for VPC Link creation
  - Implement Custom::AutoScaling resource for ASG and Launch Template management
  - Add Custom::WAF resource for WAF WebACL and IPSet creation
  - Configure proper DependsOn relationships between custom and standard resources
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 9. Implement JWT authorizer integration with custom VPC Link
  - Create JWT authorizer for API Gateway with Cognito User Pool integration
  - Configure API Gateway integration with custom VPC Link resource
  - Implement scope validation for custom scope enforcement
  - Set up proper error handling for invalid JWT tokens and VPC Link failures
  - _Requirements: 4.1, 4.2, 4.5, 3.3_

- [x] 10. Create comprehensive CloudFormation parameters and conditions
  - Define all Docker image parameters (LicenseKey, ProcessCount, etc.) with validation
  - Create EC2/ASG parameters with constraints and default values
  - Implement API Gateway, Cognito, and WAF parameters with conditional requirements
  - Add conditions for optional features (JWT auth, Cognito creation, WAF, etc.)
  - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 4.1, 7.1_

- [x] 11. Optimize single template for SAR compliance and size management
  - Ensure template size stays within SAR limits with embedded Lambda code (51KB direct, 450KB via S3)
  - Implement efficient Lambda code embedding using ZipFile property with code compression
  - Add proper IAM permissions for Lambda to create VPC Links, ASGs, Launch Templates, and WAF resources
  - Configure Lambda timeout (14.5 min), memory (512MB), and error handling settings
  - Implement S3-based template validation workflow for templates exceeding 51KB
  - _Requirements: 1.1, 1.4, 1.5, 1.6_

- [x] 12. Create CloudFormation mappings and conditions
  - Define mappings for instance type recommendations based on ProcessCount and architecture
  - Implement AMI ID mappings for different regions and architectures
  - Create conditions for optional features (JWT auth, Cognito creation, WAF, etc.)
  - Add condition logic for parameter validation and custom resource creation
  - _Requirements: 4.4, 5.5, 6.3_

- [x] 13. Implement comprehensive CloudFormation outputs
  - Output VPC and networking resource IDs for reference
  - Provide API Gateway endpoints and custom domain URLs from standard resources
  - Export custom resource outputs (VPC Link ID, ASG ARN, WAF WebACL ID)
  - Include Cognito User Pool ID, App Client ID, and Secrets Manager ARN (conditional)
  - _Requirements: 1.3, 1.4, 4.3_

- [x] 14. Create container configuration and User Data script
  - Write User Data script for Docker installation and Tolling Vision container startup
  - Configure container environment variables from CloudFormation parameters
  - Implement architecture-specific container image selection (ARM64/x86-64)
  - Set up CloudWatch Logs agent configuration for container log collection
  - _Requirements: 5.1, 5.2, 5.3, 8.1_

- [x] 15. Implement comprehensive error handling and logging
  - Add detailed CloudWatch logging for Lambda custom resource operations
  - Implement proper CloudFormation rollback handling for failed custom resources
  - Create operational monitoring for ALB, ASG, and API Gateway metrics
  - Set up CloudWatch alarms for critical system health indicators
  - _Requirements: 8.1, 8.3, 8.5, 1.5_

- [x] 16. Create SAR template validation and testing with size management
  - Validate CloudFormation template syntax and SAR compatibility using direct method (< 51KB)
  - Implement S3-based template validation for larger templates (51KB-450KB) using my-sar-artifacts-bucket
  - Test Lambda custom resource creation, update, and deletion operations
  - Implement integration tests for HTTP/1.1 endpoint
  - Verify JWT authentication flow and WAF IP allowlisting functionality
  - Create automated template size monitoring and S3 upload procedures
  - _Requirements: 1.4, 1.6, 3.4, 4.5, 7.5, 9.2, 9.5_

- [x] 17. Package single template for SAR publication with size optimization
  - Create SAR application metadata with proper categorization and description
  - Write comprehensive README documentation for SAR marketplace listing
  - Validate single template with embedded Lambda code meets SAR requirements (51KB direct, 450KB via S3)
  - Implement template size optimization strategies for SAR compliance
  - Add license file and usage documentation for marketplace publication
  - Document S3-based deployment procedures for large templates
  - _Requirements: 1.1, 1.3, 1.6, 9.2_

- [x] 18. Create deployment documentation and examples with template size guidance
  - Write deployment guide with parameter configuration examples
  - Create parameter file templates for different deployment scenarios
  - Document template size management and S3-based validation procedures
  - Document operational procedures and troubleshooting steps
  - Provide example JWT token generation and API testing procedures
  - Include guidance for both direct (< 51KB) and S3-based (51KB-450KB) template deployment
  - _Requirements: 1.3, 1.6, 9.2, 9.3, 9.4, 9.5_

## Cleanup and Consistency Tasks (Identified Issues)

- [x] 19. Fix documentation and script naming inconsistencies
  - Fix monitor-template-size script references (currently .py but docs reference .sh)
  - Standardize script naming conventions across all documentation
  - Update README.md and USAGE.md to match actual script names
  - Verify all script references in documentation point to existing files
  - _Requirements: 9.3, 9.4_

- [x] 20. Consolidate and organize test files
  - Remove duplicate test files (test-api-endpoints.py exists in both tests/ and examples/)
  - Standardize test file naming (test_lambda_syntax.py vs validate-lambda-syntax.py)
  - Ensure all test files are properly organized and functional
  - Update test documentation to reflect actual test file locations
  - _Requirements: 9.5_

- [x] 21. Verify template completeness and optimization
  - Validate that template.yaml contains all required resources and Lambda code
  - Ensure template-optimized.yaml is properly generated and functional
  - Verify template size is within SAR limits or properly handles S3 deployment
  - Test both direct and S3-based deployment methods
  - _Requirements: 1.1, 1.6, 9.2_

- [x] 22. Create missing utility scripts referenced in documentation
  - Create monitor-template-size.sh wrapper script if needed for consistency
  - Ensure all scripts referenced in documentation actually exist
  - Add any missing validation or utility scripts
  - Verify all scripts are executable and properly documented
  - _Requirements: 9.3, 9.4_

- [x] 23. Update project structure documentation
  - Update docs/PROJECT-STRUCTURE.md to reflect actual file organization
  - Ensure all documentation accurately describes current project state
  - Remove references to non-existent files or outdated information
  - Add any missing files or directories to documentation
  - _Requirements: 9.3, 9.4_

## Architecture Refactoring Tasks (Current Work)

- [x] 24. Add CloudWatch dashboard and enhanced monitoring
  - Create CloudWatch dashboard for operational monitoring
  - Add SNS notifications for critical alerts
  - Implement custom metrics for application-specific monitoring
  - Add automated health check and recovery procedures
  - _Requirements: 8.1, 8.3, 8.5_

- [x] 25. Refactor architecture from API Gateway + VPC Link to ALB-only
  - Remove API Gateway HTTP API and replace with public ALB as single entry point
  - Remove VPC Link custom resource (no longer needed)
  - Update ALB configuration to be internet-facing in public subnets
  - Configure ALB listeners for HTTPS (443 → 80)
  - Update security groups to allow public access to ALB on ports 443/8443
  - _Requirements: 3.1, 3.2_

- [x] 26. Remove API Gateway components and update parameters
  - Remove Cognito User Pool creation (use existing external pools)
  - Replace JWT authorizer with container-level JWT authentication
  - Update SAR parameters for optional container JWT configuration
  - Add DNS management parameters for optional Route53 integration
  - Remove API Gateway throttling and custom domain parameters
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 27. Update Lambda custom resource handler
  - Remove VPC Link handler function from Lambda code
  - Remove API Gateway permissions from Lambda IAM role
  - Update Lambda function to only handle AutoScaling and WAF resources
  - Remove API Gateway client initialization and error handling
  - _Requirements: 1.1, 1.4, 1.5_

- [x] 28. Update monitoring and outputs for new architecture
  - Remove API Gateway CloudWatch alarms and metrics
  - Update CloudWatch dashboard to remove API Gateway widgets
  - Replace API Gateway outputs with ALB DNS name and endpoints
  - Add conditional outputs for custom domain when DNS management enabled
  - Update deployment summary to reflect ALB-only architecture
  - _Requirements: 8.1, 8.3, 1.3_

- [x] 29. Update container environment variables for JWT authentication
  - Add environment variables for Cognito configuration (optional)
  - Configure container to validate JWT tokens internally when enabled
  - Update User Data script to pass JWT parameters to container
  - Test container-level authentication with existing Cognito User Pool
  - _Requirements: 4.1, 4.2, 5.1_

- [x] 30. Add optional S3 bucket for ALB access logs
  - Create conditional S3 bucket for ALB access logging
  - Configure ALB to write access logs when enabled
  - Add S3 bucket policy for ALB service access
  - Add parameter to enable/disable ALB access logging
  - _Requirements: 8.1, 8.3_

- [x] 31. Validate and test refactored template
  - Test CloudFormation template syntax and deployment
  - Verify ALB listeners and target groups work correctly
  - Test HTTPS endpoint with SSL certificates
  - Validate optional WAF integration with ALB
  - Test DNS management with Route53 when enabled
  - _Requirements: 1.4, 3.4, 7.5, 9.2_

- [x] 32. Update documentation for new architecture
  - Update README.md to reflect ALB-only architecture
  - Revise deployment guide for simplified infrastructure
  - Update parameter documentation for new JWT and DNS options
  - Create migration guide from old API Gateway architecture
  - Update cost optimization documentation (no API Gateway/VPC Link costs)
  - _Requirements: 9.3, 9.4_

## Critical Bug Fixes

- [x] 33. Fix Lambda self-deletion issue during stack cleanup
  - Prevent Lambda function from attempting to delete its own CloudWatch log group while running
  - Add logic to exclude current Lambda's log group from cleanup operations using context.function_name
  - Add proper error handling and logging for self-deletion prevention
  - Document that CloudFormation will handle current Lambda log group cleanup after function completes
  - _Requirements: 1.5, 8.1_

- [x] 34. Fix WAF managed rule configuration error
  - Remove conflicting Action field from AWS Managed Rules (only OverrideAction should be used)
  - Fix WAFInvalidParameterException for managed rule groups requiring exactly one action value
  - Ensure proper rule configuration for AWSManagedRulesAmazonIpReputationList and AWSManagedRulesAnonymousIpList
  - Validate WAF WebACL creation with correct managed rule syntax
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 35. Fix WAF deletion issues and Lambda log group management
  - Fix IP Set deletion by properly listing and finding IP Set ID instead of using name as ID
  - Add better error handling for AccessDeniedException during WAF deletion
  - Create explicit CloudWatch log group resource for Lambda function to ensure proper cleanup
  - Add DependsOn relationship between Lambda function and its log group
  - Prevent Lambda log group from surviving stack deletion
  - _Requirements: 7.1, 7.2, 1.5, 8.1_

- [x] 36. Fix ALB access logs conditional resource dependency issue
  - Remove hardcoded DependsOn reference to ApplicationLoadBalancer in Route53 DNS resource
  - Fix CloudWatch dashboard hardcoded references to ApplicationLoadBalancer.LoadBalancerFullName
  - Create separate conditional dashboard resources for ALB with and without access logs
  - Ensure proper resource dependencies when EnableALBAccessLogs is true
  - Fix "Unresolved resource dependencies" error during stack deployment
  - _Requirements: 2.1, 8.1, 8.3_

- [x] 37. Fix Lambda log group conflict in SAR deployments
  - Remove explicit CloudWatch log group resource creation to avoid conflicts with existing log groups
  - Let Lambda automatically create its log group to prevent "already exists" errors
  - Update CloudWatch dashboard references to use Lambda function name for log group path
  - Handle SAR naming conventions where stack names are prefixed with "serverlessrepo-"
  - Fix deployment failures when redeploying SAR applications with same name
  - _Requirements: 1.5, 8.1_

- [x] 38. Fix SAR publishing unresolved resource dependency error
  - Fix unresolved resource dependency ALBLoadBalancerFullName in CloudWatch dashboard
  - Correct dashboard metric references to use proper ALB resource names
  - Ensure CloudFormation can resolve all resource dependencies for SAR validation
  - Fix BadRequestException during SAR application version creation
  - _Requirements: 8.1, 8.3, 1.6_

- [x] 39. Fix S3 bucket invalid CloudWatchConfigurations property
  - Remove invalid CloudWatchConfigurations from S3 bucket NotificationConfiguration
  - Fix properties validation error for ALBAccessLogsBucket resource
  - Ensure S3 bucket configuration uses only valid properties
  - Remove unsupported CloudWatch integration from S3 bucket notifications
  - _Requirements: 8.1, 8.3_

- [x] 40. Fix EC2 User Data script runtime errors
  - Remove invalid 'path' log option from Docker json-file log driver
  - Create robust cfn-signal helper function with multiple path detection
  - Handle cfn-signal location differences between Amazon Linux versions
  - _Requirements: 5.1, 5.2, 8.1_

## Future Enhancement Tasks (Optional)

- [ ] 41. Implement CI/CD pipeline for template validation
  - Create GitHub Actions workflow for automated testing
  - Add template size monitoring and validation in CI
  - Implement automated SAR publishing pipeline
  - Add security scanning and compliance checks
  - _Requirements: 1.6, 9.2_

- [ ] 42. Add multi-region support and disaster recovery
  - Extend template to support multiple AWS regions
  - Add cross-region backup and recovery procedures
  - Implement region-specific AMI and resource mappings
  - Add documentation for multi-region deployment
  - _Requirements: 2.1, 8.4_

- [ ] 43. Add CloudFront integration for edge caching
  - Create optional CloudFront distribution for ALB
  - Configure CloudFront for HTTP protocol
  - Add custom domain support with CloudFront
  - Implement edge caching policies for static content
  - _Requirements: 3.1_