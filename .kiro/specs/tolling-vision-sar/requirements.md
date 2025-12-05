# Requirements Document

## Introduction

**SIMPLIFIED ARCHITECTURE**: The Tolling Vision infrastructure uses a **streamlined Lambda-based Custom Resource Strategy** with the Application Load Balancer as the single public entry point. This approach eliminates API Gateway complexity while maintaining SAR marketplace compatibility and supporting all required AWS resource types through Lambda custom resources.

The architecture focuses on simplicity and direct access patterns, with optional WAF protection, container-based JWT authentication, and optional DNS management through Route53.

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want to deploy a complete Tolling Vision infrastructure stack through SAR using Lambda-based custom resources, so that I can access all AWS resource types while maintaining SAR marketplace compatibility.

#### Acceptance Criteria

1. WHEN the SAR template is deployed THEN the system SHALL use Lambda custom resources to create Auto Scaling Groups, Launch Templates, WAF resources, and Route53 records
2. WHEN Lambda functions execute THEN the system SHALL handle resource creation, updates, and deletion with proper CloudFormation integration
3. WHEN unsupported resources are created THEN the system SHALL provide comprehensive error handling and timeout management
4. WHEN the deployment completes THEN the system SHALL return proper CloudFormation outputs for all created resources
5. WHEN template size exceeds 51KB THEN the system SHALL support S3-based template validation and deployment up to 450KB limit
6. IF Lambda functions fail THEN the system SHALL provide detailed error messages and clean rollback without hanging CloudFormation

### Requirement 2

**User Story:** As a system administrator, I want the Tolling Vision container to run in a private network with controlled public access, so that the system remains secure while being accessible through a public load balancer.

#### Acceptance Criteria

1. WHEN the infrastructure is deployed THEN the system SHALL place all EC2 instances in private subnets only
2. WHEN traffic flows to the application THEN the system SHALL route all requests through a public Application Load Balancer as the sole entry point
3. WHEN security groups are configured THEN the system SHALL allow only necessary port (80) between ALB and EC2 instances
4. WHEN NAT Gateway is provisioned THEN the system SHALL allow EC2 instances outbound internet access for license validation and image pulls
5. IF direct access to EC2 instances is attempted THEN the system SHALL block such access through security group rules

### Requirement 3

**User Story:** As an API consumer, I want to access Tolling Vision services through HTTPS endpoints on specific ports, so that I can integrate HTTP/1.1 protocol securely.

#### Acceptance Criteria

1. WHEN ALB is configured THEN the system SHALL expose port 443 for HTTPS traffic routing to container port 80
2. WHEN custom domain and certificate are provided THEN the system SHALL terminate TLS at the ALB using the provided ACM certificate
3. WHEN no certificate is provided THEN the system SHALL serve HTTP traffic on port 80
4. WHEN Route53 DNS is enabled THEN the system SHALL create DNS records pointing to the ALB
5. IF invalid protocols are used THEN the system SHALL reject requests with appropriate error responses

### Requirement 4

**User Story:** As a security administrator, I want optional container-based JWT authentication with Cognito integration, so that I can control API access through machine-to-machine authentication when required.

#### Acceptance Criteria

1. WHEN EnableJwtAuth is true THEN the system SHALL configure the container with Cognito User Pool parameters for JWT validation
2. WHEN JWT authentication is enabled THEN the system SHALL pass CognitoUserPoolId, CognitoRegion, CognitoAppClientId, and CognitoRequiredScope as environment variables
3. WHEN JWT tokens are received THEN the container SHALL validate tokens against the Cognito JWKS endpoint
4. WHEN EnableJwtAuth is false THEN the system SHALL allow unauthenticated access relying on network and WAF controls
5. IF invalid JWT tokens are presented THEN the container SHALL return 401 Unauthorized responses

### Requirement 5

**User Story:** As a DevOps engineer, I want configurable container parameters for Tolling Vision, so that I can optimize performance based on expected workload and hardware specifications.

#### Acceptance Criteria

1. WHEN ProcessCount is specified THEN the system SHALL configure the container with the appropriate number of processing threads
2. WHEN ImageArchitecture is set THEN the system SHALL select compatible ECR image tags and instance types
3. WHEN memory requirements are calculated THEN the system SHALL ensure at least 3GB for first process plus 1GB per additional process
4. WHEN license key is provided THEN the system SHALL configure container environment to validate against tollingvision.com
5. IF insufficient resources are allocated THEN the system SHALL prevent deployment with validation errors

### Requirement 6

**User Story:** As a cost-conscious administrator, I want flexible instance purchasing options, so that I can balance cost and availability using On-Demand and Spot instances.

#### Acceptance Criteria

1. WHEN OnDemandPercentage is configured THEN the system SHALL provision the specified percentage as On-Demand instances
2. WHEN Spot instances are used THEN the system SHALL configure the remaining percentage as Spot instances
3. WHEN instance types are not specified THEN the system SHALL recommend appropriate types based on ProcessCount and architecture
4. WHEN MixedInstancesPolicy is applied THEN the system SHALL distribute instances according to the specified strategy
5. IF Spot instances are interrupted THEN the system SHALL automatically replace them according to ASG configuration

### Requirement 7

**User Story:** As a security administrator, I want optional WAF protection with IP filtering and managed rules, so that I can restrict ALB access and protect against common threats.

#### Acceptance Criteria

1. WHEN EnableWAF is true THEN the system SHALL attach a WAFv2 WebACL to the Application Load Balancer
2. WHEN AllowedIpCidrs is provided THEN the system SHALL create an IPSet with configurable allow/deny rules for specified CIDR ranges
3. WHEN EnableAWSManagedRules is true THEN the system SHALL include free AWS Managed Rule Groups (Common, Known Bad Inputs, Linux, IP Reputation)
4. WHEN WAF is disabled THEN the system SHALL rely on security groups and other network controls for access restriction
5. WHEN IPSetAction is ALLOW THEN the system SHALL create an allowlist pattern, WHEN IPSetAction is BLOCK THEN the system SHALL create a denylist pattern
6. IF malicious traffic patterns are detected THEN the system SHALL block requests according to WAF rules and managed rule groups

### Requirement 8

**User Story:** As a DNS administrator, I want optional Route53 DNS record management, so that I can automatically configure domain names to point to the load balancer.

#### Acceptance Criteria

1. WHEN EnableDNS is true AND DomainName is provided AND HostedZoneId is provided THEN the system SHALL create Route53 A/AAAA records pointing to the ALB
2. WHEN EnableDNS is false THEN the system SHALL skip DNS record creation and rely on manual DNS configuration
3. WHEN DNS records are created THEN the system SHALL use Lambda custom resources to manage Route53 records
4. WHEN the stack is deleted THEN the system SHALL automatically remove created DNS records
5. IF DNS record creation fails THEN the system SHALL provide detailed error messages but continue with ALB deployment

### Requirement 9

**User Story:** As a system operator, I want comprehensive observability and logging, so that I can monitor system health and troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN the system is running THEN the system SHALL send container logs to CloudWatch Logs
2. WHEN ALB is configured THEN the system SHALL optionally store access logs in S3
3. WHEN WAF is enabled THEN the system SHALL optionally log WAF requests to CloudWatch
4. WHEN IAM roles are created THEN the system SHALL provide minimum necessary permissions for logging and ECR access
5. IF logging fails THEN the system SHALL continue operating but alert administrators of the logging issue

### Requirement 10

**User Story:** As a solution architect, I want to understand SAR limitations and template size constraints, so that I can make informed decisions about infrastructure deployment approaches and validation strategies.

#### Acceptance Criteria

1. WHEN SAR resource type restrictions are encountered THEN the system SHALL document all unsupported resource types with impact analysis
2. WHEN template size exceeds 51KB THEN the system SHALL support S3-based validation using `--template-url` parameter with 450KB maximum limit
3. WHEN comparing distribution methods THEN the system SHALL provide clear comparison between SAR vs Direct CloudFormation capabilities
4. WHEN alternative strategies are evaluated THEN the system SHALL recommend optimal distribution approaches (S3, GitHub, AWS Solutions Library)
5. WHEN template validation is required THEN the system SHALL provide both direct validation (< 51KB) and S3-based validation (51KB-450KB) procedures
6. IF users ask about SAR compatibility THEN the system SHALL clearly communicate limitations and recommend better alternatives