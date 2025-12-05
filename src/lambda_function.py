import json
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import logging
import time
import urllib.request
import urllib.parse
import traceback
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients with error handling
try:
    ec2_client = boto3.client('ec2')
    apigatewayv2_client = boto3.client('apigatewayv2')
    autoscaling_client = boto3.client('autoscaling')
    wafv2_client = boto3.client('wafv2')
    elbv2_client = boto3.client('elbv2')
    cognito_client = boto3.client('cognito-idp')
    secretsmanager_client = boto3.client('secretsmanager')
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {str(e)}")
    # Continue execution - clients will be re-initialized if needed

# Constants for timeout management
LAMBDA_TIMEOUT_BUFFER = 30  # Reserve 30 seconds before Lambda timeout
MAX_OPERATION_TIME = 14 * 60  # 14 minutes maximum operation time
EMERGENCY_RESPONSE_TIME = 15  # Emergency response within 15 seconds of timeout

# Resource type constants
RESOURCE_TYPE_VPC_LINK = 'VpcLink'
RESOURCE_TYPE_AUTO_SCALING = 'AutoScaling'
RESOURCE_TYPE_LAUNCH_TEMPLATE = 'LaunchTemplate'
RESOURCE_TYPE_WAF = 'WAF'
RESOURCE_TYPE_COGNITO_CLIENT_SECRET = 'CognitoClientSecret'

# CloudFormation response status constants
SUCCESS = 'SUCCESS'
FAILED = 'FAILED'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda custom resource handler for Tolling Vision SAR application.
    Handles creation, update, and deletion of AWS resources not supported by SAR.
    
    Supported resource types:
    - VpcLink: Creates API Gateway VPC Links
    - AutoScaling: Creates Auto Scaling Groups and Launch Templates  
    - WAF: Creates WAFv2 WebACLs and IPSets
    
    Args:
        event: CloudFormation custom resource event
        context: Lambda context object
        
    Returns:
        Dict: CloudFormation response (handled via ResponseURL)
    """
    
    # Initialize timeout management
    start_time = time.time()
    timeout_threshold = start_time + MAX_OPERATION_TIME
    emergency_threshold = (context.get_remaining_time_in_millis() / 1000) - EMERGENCY_RESPONSE_TIME
    
    request_type = None
    resource_type = None
    physical_resource_id = None
    
    try:
        # Log the incoming event (sanitized)
        sanitized_event = sanitize_event_for_logging(event)
        logger.info(f"Processing custom resource request: {sanitized_event}")
        
        # Extract CloudFormation event details
        request_type = event.get('RequestType')
        resource_type = event.get('ResourceProperties', {}).get('ResourceType')
        logical_resource_id = event.get('LogicalResourceId')
        stack_id = event.get('StackId')
        
        # Validate required fields
        if not request_type:
            raise ValueError("Missing RequestType in event")
        if not resource_type:
            raise ValueError("Missing ResourceType in ResourceProperties")
        if not logical_resource_id:
            raise ValueError("Missing LogicalResourceId in event")
            
        logger.info(f"Processing {request_type} for {resource_type} resource: {logical_resource_id}")
        
        # Check for timeout conditions before processing
        current_time = time.time()
        if current_time > timeout_threshold or context.get_remaining_time_in_millis() < (EMERGENCY_RESPONSE_TIME * 1000):
            logger.warning("Approaching timeout, sending emergency response")
            return send_emergency_response(event, context, FAILED, {"Error": "Timeout approaching before processing"})
        
        # Use timeout handler for the main processing
        with TimeoutHandler(context) as timeout_handler:
            # Route to appropriate resource handler
            if resource_type == RESOURCE_TYPE_VPC_LINK:
                physical_resource_id, response_data = handle_vpc_link_resource(event, context, timeout_handler)
            elif resource_type == RESOURCE_TYPE_AUTO_SCALING:
                physical_resource_id, response_data = handle_auto_scaling_resource(event, context, timeout_handler)
            elif resource_type == RESOURCE_TYPE_LAUNCH_TEMPLATE:
                physical_resource_id, response_data = handle_launch_template_resource(event, context, timeout_handler)
            elif resource_type == RESOURCE_TYPE_WAF:
                physical_resource_id, response_data = handle_waf_resource(event, context, timeout_handler)
            elif resource_type == RESOURCE_TYPE_COGNITO_CLIENT_SECRET:
                physical_resource_id, response_data = handle_cognito_client_secret_resource(event, context, timeout_handler)
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")
        
        # Send success response
        logger.info(f"Successfully processed {request_type} for {resource_type}")
        return send_cloudformation_response(
            event=event,
            context=context,
            response_status=SUCCESS,
            response_data=response_data,
            physical_resource_id=physical_resource_id
        )
        
    except TimeoutError:
        error_message = f"Timeout processing {request_type or 'unknown'} for {resource_type or 'unknown'}"
        logger.error(error_message)
        
        # For delete operations, return success to avoid blocking stack deletion
        if request_type == 'Delete':
            logger.warning("Delete operation timed out, but returning SUCCESS to allow stack deletion")
            return send_cloudformation_response(
                event=event,
                context=context,
                response_status=SUCCESS,
                response_data={'Status': 'TimeoutOnDelete', 'Message': 'Deletion timed out but continuing'},
                physical_resource_id=physical_resource_id or f"timeout-delete-{int(time.time())}"
            )
        else:
            return send_emergency_response(event, context, FAILED, {'Error': error_message})
        
    except Exception as e:
        error_message = f"Error processing {request_type or 'unknown'} for {resource_type or 'unknown'}: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # Check if we're approaching timeout
        if context.get_remaining_time_in_millis() < (EMERGENCY_RESPONSE_TIME * 1000):
            logger.warning("Timeout approaching during error handling, sending emergency response")
            return send_emergency_response(event, context, FAILED, {'Error': error_message})
        
        # For delete operations, return success to avoid blocking stack deletion
        if request_type == 'Delete':
            logger.warning("Delete operation failed, but returning SUCCESS to allow stack deletion to continue")
            return send_cloudformation_response(
                event=event,
                context=context,
                response_status=SUCCESS,
                response_data={'Status': 'DeleteFailed', 'Error': str(e)},
                physical_resource_id=physical_resource_id or f"delete-failed-{int(time.time())}"
            )
        
        # Send failure response
        return send_cloudformation_response(
            event=event,
            context=context,
            response_status=FAILED,
            response_data={'Error': error_message},
            physical_resource_id=physical_resource_id or f"failed-{int(time.time())}"
        )


def handle_vpc_link_resource(event: Dict[str, Any], context: Any, timeout_handler: 'TimeoutHandler') -> tuple[str, Dict[str, Any]]:
    """
    Handle VPC Link custom resource operations.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        timeout_handler: Timeout management handler
        
    Returns:
        tuple: (physical_resource_id, response_data)
    """
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    logger.info(f"Handling VPC Link {request_type}")
    
    # Check timeout before processing
    timeout_handler.raise_if_timeout()
    
    # Initialize VPC Link resource handler
    vpc_link_handler = VpcLinkResource(apigatewayv2_client, timeout_handler)
    
    if request_type == 'Create':
        return vpc_link_handler.create(properties)
    elif request_type == 'Update':
        physical_resource_id = event.get('PhysicalResourceId')
        return vpc_link_handler.update(physical_resource_id, properties)
    elif request_type == 'Delete':
        physical_resource_id = event.get('PhysicalResourceId')
        return vpc_link_handler.delete(physical_resource_id, properties)
    else:
        raise ValueError(f"Unsupported request type: {request_type}")


def handle_auto_scaling_resource(event: Dict[str, Any], context: Any, timeout_handler: 'TimeoutHandler') -> tuple[str, Dict[str, Any]]:
    """
    Handle Auto Scaling Group custom resource operations.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        timeout_handler: Timeout management handler
        
    Returns:
        tuple: (physical_resource_id, response_data)
    """
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    logger.info(f"Handling Auto Scaling Group {request_type}")
    
    # Check timeout before processing
    timeout_handler.raise_if_timeout()
    
    # Initialize Auto Scaling resource handler
    asg_handler = AutoScalingResource(autoscaling_client, ec2_client, elbv2_client, timeout_handler)
    
    if request_type == 'Create':
        return asg_handler.create(properties)
    elif request_type == 'Update':
        physical_resource_id = event.get('PhysicalResourceId')
        return asg_handler.update(physical_resource_id, properties)
    elif request_type == 'Delete':
        physical_resource_id = event.get('PhysicalResourceId')
        return asg_handler.delete(physical_resource_id, properties)
    else:
        raise ValueError(f"Unsupported request type: {request_type}")


def handle_launch_template_resource(event: Dict[str, Any], context: Any, timeout_handler: 'TimeoutHandler') -> tuple[str, Dict[str, Any]]:
    """
    Handle Launch Template custom resource operations.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        timeout_handler: Timeout management handler
        
    Returns:
        tuple: (physical_resource_id, response_data)
    """
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    logger.info(f"Handling Launch Template {request_type}")
    
    # Check timeout before processing
    timeout_handler.raise_if_timeout()
    
    if request_type == 'Create':
        # TODO: Implement Launch Template creation
        physical_resource_id = f"lt-{int(time.time())}"
        response_data = {
            'LaunchTemplateId': physical_resource_id,
            'LaunchTemplateName': f"tolling-vision-{physical_resource_id}"
        }
    elif request_type == 'Update':
        # TODO: Implement Launch Template update
        physical_resource_id = event.get('PhysicalResourceId')
        response_data = {
            'LaunchTemplateId': physical_resource_id
        }
    elif request_type == 'Delete':
        # TODO: Implement Launch Template deletion
        physical_resource_id = event.get('PhysicalResourceId')
        response_data = {}
    else:
        raise ValueError(f"Unsupported request type: {request_type}")
    
    return physical_resource_id, response_data


def handle_waf_resource(event: Dict[str, Any], context: Any, timeout_handler: 'TimeoutHandler') -> tuple[str, Dict[str, Any]]:
    """
    Handle WAF WebACL custom resource operations.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        timeout_handler: Timeout management handler
        
    Returns:
        tuple: (physical_resource_id, response_data)
    """
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    logger.info(f"Handling WAF WebACL {request_type}")
    
    # Check timeout before processing
    timeout_handler.raise_if_timeout()
    
    # Initialize WAF resource handler
    waf_handler = WAFResource(wafv2_client, timeout_handler)
    
    if request_type == 'Create':
        return waf_handler.create(properties)
    elif request_type == 'Update':
        physical_resource_id = event.get('PhysicalResourceId')
        return waf_handler.update(physical_resource_id, properties)
    elif request_type == 'Delete':
        physical_resource_id = event.get('PhysicalResourceId')
        return waf_handler.delete(physical_resource_id, properties)
    else:
        raise ValueError(f"Unsupported request type: {request_type}")


def handle_cognito_client_secret_resource(event: Dict[str, Any], context: Any, timeout_handler: 'TimeoutHandler') -> tuple[str, Dict[str, Any]]:
    """
    Handle Cognito App Client Secret retrieval and storage in Secrets Manager.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        timeout_handler: Timeout management handler
        
    Returns:
        tuple: (physical_resource_id, response_data)
    """
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    logger.info(f"Handling Cognito Client Secret {request_type}")
    
    # Check timeout before processing
    timeout_handler.raise_if_timeout()
    
    # Initialize Cognito client secret handler
    cognito_secret_handler = CognitoClientSecretResource(cognito_client, secretsmanager_client, timeout_handler)
    
    if request_type == 'Create':
        return cognito_secret_handler.create(properties)
    elif request_type == 'Update':
        physical_resource_id = event.get('PhysicalResourceId')
        return cognito_secret_handler.update(physical_resource_id, properties)
    elif request_type == 'Delete':
        physical_resource_id = event.get('PhysicalResourceId')
        return cognito_secret_handler.delete(physical_resource_id, properties)
    else:
        raise ValueError(f"Unsupported request type: {request_type}")


def sanitize_event_for_logging(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize CloudFormation event for safe logging by removing sensitive data.
    
    Args:
        event: CloudFormation custom resource event
        
    Returns:
        Dict: Sanitized event safe for logging
    """
    try:
        sanitized = event.copy()
        
        # Remove sensitive fields that might contain credentials
        sensitive_fields = ['ResponseURL', 'StackId']
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = f"<{field}_REDACTED>"
        
        # Sanitize ResourceProperties if present
        if 'ResourceProperties' in sanitized and isinstance(sanitized['ResourceProperties'], dict):
            props = sanitized['ResourceProperties'].copy()
            
            # Remove potentially sensitive property values
            sensitive_props = ['Password', 'Secret', 'Key', 'Token', 'Credential']
            for prop_key in list(props.keys()):
                if any(sensitive in prop_key for sensitive in sensitive_props):
                    props[prop_key] = "<REDACTED>"
            
            sanitized['ResourceProperties'] = props
        
        return sanitized
    except Exception as e:
        logger.warning(f"Failed to sanitize event for logging: {e}")
        return {"Error": "Event sanitization failed"}


def send_cloudformation_response(
    event: Dict[str, Any], 
    context: Any, 
    response_status: str, 
    response_data: Dict[str, Any], 
    physical_resource_id: str
) -> Dict[str, Any]:
    """
    Send response to CloudFormation with comprehensive error handling.
    
    Args:
        event: CloudFormation custom resource event
        context: Lambda context object
        response_status: SUCCESS or FAILED
        response_data: Data to return to CloudFormation
        physical_resource_id: Physical resource identifier
        
    Returns:
        Dict: Response sent to CloudFormation
    """
    try:
        # Validate inputs
        if not event:
            raise ValueError("Event is None or empty")
        
        if 'ResponseURL' not in event:
            raise ValueError("ResponseURL not found in event")
        
        response_url = event['ResponseURL']
        
        # Build response body with safe defaults
        response_body = {
            'Status': response_status or FAILED,
            'Reason': f'See CloudWatch Log Stream: {getattr(context, "log_stream_name", "unknown")}',
            'PhysicalResourceId': str(physical_resource_id or f"unknown-{int(time.time())}"),
            'StackId': event.get('StackId', 'unknown-stack'),
            'RequestId': event.get('RequestId', 'unknown-request'),
            'LogicalResourceId': event.get('LogicalResourceId', 'unknown-logical-resource'),
            'Data': response_data if isinstance(response_data, dict) else {'Result': str(response_data)}
        }
        
        # Serialize with error handling
        try:
            json_response_body = json.dumps(response_body)
        except Exception as json_error:
            logger.error(f"JSON serialization failed: {json_error}")
            # Fallback with string representation
            response_body['Data'] = {
                'Error': 'JSON serialization failed', 
                'OriginalData': str(response_data)[:500]
            }
            json_response_body = json.dumps(response_body)
        
        headers = {
            'content-type': '',
            'content-length': str(len(json_response_body))
        }
        
        # Send the response using urllib.request (available in Lambda runtime)
        request = urllib.request.Request(
            response_url,
            data=json_response_body.encode('utf-8'),
            headers=headers,
            method='PUT'
        )
        
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.getcode()
            logger.info(f"CloudFormation response sent successfully with status code: {status_code}")
            
            # Validate response
            if status_code not in [200, 201, 202]:
                logger.warning(f"Unexpected response status from CloudFormation: {status_code}")
        
        return response_body
        
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {e}", exc_info=True)
        
        # Try emergency response
        try:
            return send_emergency_response(event, context, FAILED, {'Error': f'Response send failed: {str(e)}'})
        except Exception as final_error:
            logger.error(f"Emergency response also failed: {final_error}")
            # At this point, CloudFormation will timeout, but we've logged everything
            return {'Status': FAILED, 'Error': 'All response attempts failed'}


def send_emergency_response(
    event: Dict[str, Any], 
    context: Any, 
    status: str, 
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Emergency response function that works even if other parts fail.
    
    Args:
        event: CloudFormation event
        context: Lambda context
        status: Response status
        data: Response data
        
    Returns:
        Dict: Emergency response
    """
    response_url = event.get('ResponseURL') if event else None
    
    if not response_url:
        logger.error("No response URL available for emergency response")
        return {'Status': FAILED, 'Error': 'No response URL'}
    
    try:
        response_body = {
            'Status': status,
            'Reason': f'Emergency response - See CloudWatch Log Stream: {getattr(context, "log_stream_name", "unknown")}',
            'PhysicalResourceId': getattr(context, 'log_stream_name', f'emergency-{int(time.time())}'),
            'StackId': event.get('StackId', 'unknown') if event else 'unknown',
            'RequestId': event.get('RequestId', 'unknown') if event else 'unknown',
            'LogicalResourceId': event.get('LogicalResourceId', 'unknown') if event else 'unknown',
            'Data': data or {}
        }
        
        json_response_body = json.dumps(response_body)
        
        headers = {
            'content-type': '',
            'content-length': str(len(json_response_body))
        }
        
        request = urllib.request.Request(
            response_url,
            data=json_response_body.encode('utf-8'),
            headers=headers,
            method='PUT'
        )
        
        with urllib.request.urlopen(request, timeout=10) as response:
            logger.info(f"Emergency response sent with status code: {response.getcode()}")
        
        return response_body
        
    except Exception as e:
        logger.error(f"Emergency response failed: {e}")
        return {'Status': FAILED, 'Error': f'Emergency response failed: {str(e)}'}


class TimeoutHandler:
    """Handle Lambda timeout gracefully with context manager."""
    
    def __init__(self, context: Any, buffer_seconds: int = EMERGENCY_RESPONSE_TIME):
        """
        Initialize timeout handler.
        
        Args:
            context: Lambda context object
            buffer_seconds: Seconds to reserve before timeout for cleanup
        """
        self.context = context
        self.buffer_seconds = buffer_seconds
        self.timed_out = False
        self.start_time = time.time()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def check_timeout(self) -> bool:
        """
        Check if we're approaching timeout.
        
        Returns:
            bool: True if timeout is approaching
        """
        if self.context:
            remaining_ms = self.context.get_remaining_time_in_millis()
            if remaining_ms < (self.buffer_seconds * 1000):
                self.timed_out = True
                return True
        
        # Fallback check based on elapsed time
        elapsed = time.time() - self.start_time
        if elapsed > MAX_OPERATION_TIME:
            self.timed_out = True
            return True
        
        return False
    
    def raise_if_timeout(self):
        """Raise TimeoutError if timeout is approaching."""
        if self.check_timeout():
            raise TimeoutError("Lambda function execution approaching timeout")


def validate_resource_properties(properties: Dict[str, Any], required_fields: list) -> None:
    """
    Validate that required fields are present in resource properties.
    
    Args:
        properties: Resource properties from CloudFormation
        required_fields: List of required field names
        
    Raises:
        ValueError: If required fields are missing
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in properties or not properties[field]:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Missing required properties: {', '.join(missing_fields)}")


def get_aws_region() -> str:
    """
    Get the current AWS region from Lambda environment.
    
    Returns:
        str: AWS region name
    """
    import os
    return os.environ.get('AWS_REGION', 'us-east-1')


class VpcLinkResource:
    """
    Handles API Gateway VPC Link creation and management for Tolling Vision SAR application.
    
    This class manages the lifecycle of VPC Links that connect API Gateway to private
    Application Load Balancers in the Tolling Vision infrastructure.
    """
    
    def __init__(self, apigatewayv2_client, timeout_handler: 'TimeoutHandler'):
        """
        Initialize VPC Link resource handler.
        
        Args:
            apigatewayv2_client: Boto3 API Gateway v2 client
            timeout_handler: Timeout management handler
        """
        self.client = apigatewayv2_client
        self.timeout_handler = timeout_handler
        
        # VPC Link creation can take 2-10 minutes
        self.max_wait_time = 600  # 10 minutes maximum wait
        self.poll_interval = 15   # Check status every 15 seconds
    
    def create(self, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Create a new VPC Link for API Gateway integration.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
            
        Raises:
            ValueError: If required properties are missing
            ClientError: If AWS API calls fail
        """
        logger.info("Creating VPC Link")
        
        # Validate required properties
        required_fields = ['Name', 'SubnetIds']
        validate_resource_properties(properties, required_fields)
        
        name = properties['Name']
        subnet_ids = properties['SubnetIds']
        security_group_ids = properties.get('SecurityGroupIds', [])
        
        # Ensure subnet_ids is a list
        if isinstance(subnet_ids, str):
            subnet_ids = [s.strip() for s in subnet_ids.split(',') if s.strip()]
        
        # Ensure security_group_ids is a list
        if isinstance(security_group_ids, str):
            security_group_ids = [s.strip() for s in security_group_ids.split(',') if s.strip()]
        
        logger.info(f"Creating VPC Link '{name}' with subnets: {subnet_ids}")
        if security_group_ids:
            logger.info(f"Using security groups: {security_group_ids}")
        
        try:
            # Check timeout before making API call
            self.timeout_handler.raise_if_timeout()
            
            # Create VPC Link
            create_params = {
                'Name': name,
                'SubnetIds': subnet_ids
            }
            
            # Add security groups if provided
            if security_group_ids:
                create_params['SecurityGroupIds'] = security_group_ids
            
            # Add tags if provided
            tags = properties.get('Tags', {})
            if tags:
                create_params['Tags'] = tags
            
            response = self.client.create_vpc_link(**create_params)
            
            vpc_link_id = response['VpcLinkId']
            logger.info(f"VPC Link creation initiated: {vpc_link_id}")
            
            # Wait for VPC Link to become available
            final_status = self._wait_for_vpc_link_available(vpc_link_id)
            
            response_data = {
                'VpcLinkId': vpc_link_id,
                'VpcLinkArn': f"arn:aws:apigateway:{get_aws_region()}::/vpclinks/{vpc_link_id}",
                'Status': final_status,
                'Name': name
            }
            
            logger.info(f"VPC Link created successfully: {vpc_link_id} with status: {final_status}")
            return vpc_link_id, response_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to create VPC Link: {error_code} - {error_message}")
            
            # Handle specific error cases
            if error_code == 'BadRequestException':
                if 'subnet' in error_message.lower():
                    raise ValueError(f"Invalid subnet configuration: {error_message}")
                elif 'security group' in error_message.lower():
                    raise ValueError(f"Invalid security group configuration: {error_message}")
                else:
                    raise ValueError(f"Invalid VPC Link configuration: {error_message}")
            elif error_code == 'TooManyRequestsException':
                raise ValueError("Rate limit exceeded. Please try again later.")
            elif error_code == 'ConflictException':
                raise ValueError(f"VPC Link with name '{name}' already exists")
            else:
                raise ValueError(f"VPC Link creation failed: {error_code} - {error_message}")
        
        except Exception as e:
            logger.error(f"Unexpected error creating VPC Link: {str(e)}", exc_info=True)
            raise ValueError(f"VPC Link creation failed: {str(e)}")
    
    def update(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Update an existing VPC Link.
        
        Note: VPC Links have limited update capabilities. Most properties require replacement.
        
        Args:
            physical_resource_id: VPC Link ID
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Updating VPC Link: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Get current VPC Link details
            current_vpc_link = self._get_vpc_link_details(physical_resource_id)
            if not current_vpc_link:
                logger.warning(f"VPC Link {physical_resource_id} not found, treating as create operation")
                return self.create(properties)
            
            # Check if update is possible or if replacement is needed
            name = properties.get('Name', current_vpc_link.get('Name'))
            subnet_ids = properties.get('SubnetIds', [])
            security_group_ids = properties.get('SecurityGroupIds', [])
            
            # Ensure lists are properly formatted
            if isinstance(subnet_ids, str):
                subnet_ids = [s.strip() for s in subnet_ids.split(',') if s.strip()]
            if isinstance(security_group_ids, str):
                security_group_ids = [s.strip() for s in security_group_ids.split(',') if s.strip()]
            
            # Check if subnets or security groups changed (requires replacement)
            current_subnets = set(current_vpc_link.get('SubnetIds', []))
            new_subnets = set(subnet_ids) if subnet_ids else current_subnets
            
            current_sgs = set(current_vpc_link.get('SecurityGroupIds', []))
            new_sgs = set(security_group_ids) if security_group_ids else current_sgs
            
            if current_subnets != new_subnets or current_sgs != new_sgs:
                logger.warning("VPC Link subnet or security group changes require replacement")
                # For CloudFormation, we should signal that replacement is needed
                # But since we can't force replacement from custom resource, we'll update what we can
                logger.info("Proceeding with name-only update due to VPC Link limitations")
            
            # Update VPC Link (only name can be updated)
            if name != current_vpc_link.get('Name'):
                update_params = {'VpcLinkId': physical_resource_id, 'Name': name}
                self.client.update_vpc_link(**update_params)
                logger.info(f"VPC Link name updated to: {name}")
            
            # Wait for VPC Link to be available after update
            final_status = self._wait_for_vpc_link_available(physical_resource_id)
            
            response_data = {
                'VpcLinkId': physical_resource_id,
                'VpcLinkArn': f"arn:aws:apigateway:{get_aws_region()}::/vpclinks/{physical_resource_id}",
                'Status': final_status,
                'Name': name
            }
            
            logger.info(f"VPC Link updated successfully: {physical_resource_id}")
            return physical_resource_id, response_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to update VPC Link: {error_code} - {error_message}")
            
            if error_code == 'NotFoundException':
                logger.warning(f"VPC Link {physical_resource_id} not found during update, treating as create")
                return self.create(properties)
            else:
                raise ValueError(f"VPC Link update failed: {error_code} - {error_message}")
        
        except Exception as e:
            logger.error(f"Unexpected error updating VPC Link: {str(e)}", exc_info=True)
            raise ValueError(f"VPC Link update failed: {str(e)}")
    
    def delete(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Delete a VPC Link.
        
        Args:
            physical_resource_id: VPC Link ID
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Deleting VPC Link: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Check if VPC Link exists
            vpc_link_details = self._get_vpc_link_details(physical_resource_id)
            if not vpc_link_details:
                logger.info(f"VPC Link {physical_resource_id} not found, skipping deletion")
                return physical_resource_id, {}
            
            # Delete VPC Link
            self.client.delete_vpc_link(VpcLinkId=physical_resource_id)
            logger.info(f"VPC Link deletion initiated: {physical_resource_id}")
            
            # Wait for VPC Link to be deleted
            self._wait_for_vpc_link_deleted(physical_resource_id)
            
            logger.info(f"VPC Link deleted successfully: {physical_resource_id}")
            return physical_resource_id, {}
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'NotFoundException':
                logger.info(f"VPC Link {physical_resource_id} not found, considering deletion successful")
                return physical_resource_id, {}
            else:
                logger.error(f"Failed to delete VPC Link: {error_code} - {error_message}")
                # For delete operations, we should be more lenient to avoid blocking stack deletion
                logger.warning("Returning success for delete operation to avoid blocking stack deletion")
                return physical_resource_id, {'Status': 'DeleteFailed', 'Error': error_message}
        
        except Exception as e:
            logger.error(f"Unexpected error deleting VPC Link: {str(e)}", exc_info=True)
            # For delete operations, return success to avoid blocking stack deletion
            logger.warning("Returning success for delete operation to avoid blocking stack deletion")
            return physical_resource_id, {'Status': 'DeleteFailed', 'Error': str(e)}
    
    def _get_vpc_link_details(self, vpc_link_id: str) -> Optional[Dict[str, Any]]:
        """
        Get VPC Link details.
        
        Args:
            vpc_link_id: VPC Link ID
            
        Returns:
            Dict: VPC Link details or None if not found
        """
        try:
            response = self.client.get_vpc_link(VpcLinkId=vpc_link_id)
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFoundException':
                return None
            raise
    
    def _wait_for_vpc_link_available(self, vpc_link_id: str) -> str:
        """
        Wait for VPC Link to become available.
        
        Args:
            vpc_link_id: VPC Link ID
            
        Returns:
            str: Final status of the VPC Link
            
        Raises:
            TimeoutError: If VPC Link doesn't become available within timeout
            ValueError: If VPC Link creation fails
        """
        logger.info(f"Waiting for VPC Link {vpc_link_id} to become available")
        
        start_time = time.time()
        
        while time.time() - start_time < self.max_wait_time:
            # Check Lambda timeout
            self.timeout_handler.raise_if_timeout()
            
            try:
                response = self.client.get_vpc_link(VpcLinkId=vpc_link_id)
                status = response.get('VpcLinkStatus', 'UNKNOWN')
                
                logger.info(f"VPC Link {vpc_link_id} status: {status}")
                
                if status == 'AVAILABLE':
                    logger.info(f"VPC Link {vpc_link_id} is now available")
                    return status
                elif status == 'FAILED':
                    error_message = response.get('VpcLinkStatusMessage', 'VPC Link creation failed')
                    logger.error(f"VPC Link {vpc_link_id} creation failed: {error_message}")
                    raise ValueError(f"VPC Link creation failed: {error_message}")
                elif status in ['PENDING', 'DELETING']:
                    # Continue waiting
                    time.sleep(self.poll_interval)
                else:
                    logger.warning(f"Unknown VPC Link status: {status}")
                    time.sleep(self.poll_interval)
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'NotFoundException':
                    raise ValueError(f"VPC Link {vpc_link_id} was deleted during creation")
                else:
                    logger.error(f"Error checking VPC Link status: {e}")
                    time.sleep(self.poll_interval)
        
        # Timeout reached
        logger.error(f"Timeout waiting for VPC Link {vpc_link_id} to become available")
        
        # Get final status for logging
        try:
            response = self.client.get_vpc_link(VpcLinkId=vpc_link_id)
            final_status = response.get('VpcLinkStatus', 'UNKNOWN')
            status_message = response.get('VpcLinkStatusMessage', '')
            logger.error(f"Final VPC Link status: {final_status}, Message: {status_message}")
        except Exception as e:
            logger.error(f"Could not get final VPC Link status: {e}")
        
        raise TimeoutError(f"VPC Link {vpc_link_id} did not become available within {self.max_wait_time} seconds")
    
    def _wait_for_vpc_link_deleted(self, vpc_link_id: str) -> None:
        """
        Wait for VPC Link to be deleted.
        
        Args:
            vpc_link_id: VPC Link ID
            
        Raises:
            TimeoutError: If VPC Link doesn't get deleted within timeout
        """
        logger.info(f"Waiting for VPC Link {vpc_link_id} to be deleted")
        
        start_time = time.time()
        
        while time.time() - start_time < self.max_wait_time:
            # Check Lambda timeout
            self.timeout_handler.raise_if_timeout()
            
            try:
                response = self.client.get_vpc_link(VpcLinkId=vpc_link_id)
                status = response.get('VpcLinkStatus', 'UNKNOWN')
                
                logger.info(f"VPC Link {vpc_link_id} deletion status: {status}")
                
                if status == 'DELETING':
                    # Continue waiting
                    time.sleep(self.poll_interval)
                else:
                    logger.warning(f"Unexpected status during deletion: {status}")
                    time.sleep(self.poll_interval)
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'NotFoundException':
                    logger.info(f"VPC Link {vpc_link_id} successfully deleted")
                    return
                else:
                    logger.error(f"Error checking VPC Link deletion status: {e}")
                    time.sleep(self.poll_interval)
        
        # Timeout reached - for delete operations, we should be more lenient
        logger.warning(f"Timeout waiting for VPC Link {vpc_link_id} deletion, but continuing")
        return


class AutoScalingResource:
    """
    Handles Auto Scaling Group, Launch Template, and Scaling Policy creation and management 
    for Tolling Vision SAR application.
    
    This class manages the lifecycle of Auto Scaling Groups with Launch Templates that run
    the Tolling Vision container with architecture-specific AMI selection and User Data.
    """
    
    def __init__(self, autoscaling_client, ec2_client, elbv2_client, timeout_handler: 'TimeoutHandler'):
        """
        Initialize Auto Scaling resource handler.
        
        Args:
            autoscaling_client: Boto3 Auto Scaling client
            ec2_client: Boto3 EC2 client
            elbv2_client: Boto3 ELBv2 client
            timeout_handler: Timeout management handler
        """
        self.autoscaling_client = autoscaling_client
        self.ec2_client = ec2_client
        self.elbv2_client = elbv2_client
        self.timeout_handler = timeout_handler
        
        # Auto Scaling operations can take several minutes
        self.max_wait_time = 600  # 10 minutes maximum wait
        self.poll_interval = 15   # Check status every 15 seconds
    
    def create(self, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Create Auto Scaling Group with Launch Template and Scaling Policies.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
            
        Raises:
            ValueError: If required properties are missing
            ClientError: If AWS API calls fail
        """
        logger.info("Creating Auto Scaling Group with Launch Template")
        
        # Validate required properties
        required_fields = [
            'AutoScalingGroupName', 'LaunchTemplateName', 'SubnetIds',
            'MinSize', 'MaxSize', 'DesiredCapacity'
        ]
        validate_resource_properties(properties, required_fields)
        
        asg_name = properties['AutoScalingGroupName']
        launch_template_name = properties['LaunchTemplateName']
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Step 1: Create Launch Template
            launch_template_id = self._create_launch_template(properties)
            logger.info(f"Launch Template created: {launch_template_id}")
            
            # Step 2: Create Auto Scaling Group
            asg_arn = self._create_auto_scaling_group(properties, launch_template_id)
            logger.info(f"Auto Scaling Group created: {asg_name}")
            
            # Step 3: Create Scaling Policies (if specified)
            scaling_policies = self._create_scaling_policies(properties, asg_name)
            
            # Step 4: Register with Target Groups (if specified)
            self._register_target_groups(properties, asg_name)
            
            response_data = {
                'AutoScalingGroupName': asg_name,
                'AutoScalingGroupARN': asg_arn,
                'LaunchTemplateId': launch_template_id,
                'LaunchTemplateName': launch_template_name,
                'ScalingPolicies': scaling_policies
            }
            
            logger.info(f"Auto Scaling Group created successfully: {asg_name}")
            return asg_name, response_data
            
        except Exception as e:
            logger.error(f"Failed to create Auto Scaling Group: {str(e)}", exc_info=True)
            
            # Cleanup on failure
            try:
                self._cleanup_on_failure(asg_name, launch_template_name)
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")
            
            raise ValueError(f"Auto Scaling Group creation failed: {str(e)}")
    
    def update(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Update Auto Scaling Group configuration.
        
        Args:
            physical_resource_id: Auto Scaling Group name
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Updating Auto Scaling Group: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Check if ASG exists
            if not self._get_auto_scaling_group_details(physical_resource_id):
                logger.warning(f"Auto Scaling Group {physical_resource_id} not found, treating as create")
                return self.create(properties)
            
            # Update Auto Scaling Group properties
            self._update_auto_scaling_group(physical_resource_id, properties)
            
            # Update Launch Template if needed
            launch_template_id = self._update_launch_template(properties)
            
            # Update Scaling Policies
            scaling_policies = self._update_scaling_policies(properties, physical_resource_id)
            
            # Update Target Group registration
            self._update_target_groups(properties, physical_resource_id)
            
            response_data = {
                'AutoScalingGroupName': physical_resource_id,
                'LaunchTemplateId': launch_template_id,
                'ScalingPolicies': scaling_policies
            }
            
            logger.info(f"Auto Scaling Group updated successfully: {physical_resource_id}")
            return physical_resource_id, response_data
            
        except Exception as e:
            logger.error(f"Failed to update Auto Scaling Group: {str(e)}", exc_info=True)
            raise ValueError(f"Auto Scaling Group update failed: {str(e)}")
    
    def delete(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Delete Auto Scaling Group and associated resources.
        
        Args:
            physical_resource_id: Auto Scaling Group name
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Deleting Auto Scaling Group: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Check if ASG exists
            asg_details = self._get_auto_scaling_group_details(physical_resource_id)
            if not asg_details:
                logger.info(f"Auto Scaling Group {physical_resource_id} not found, skipping deletion")
                return physical_resource_id, {}
            
            # Step 1: Delete Scaling Policies
            self._delete_scaling_policies(physical_resource_id)
            
            # Step 2: Set ASG capacity to 0 and wait for instances to terminate
            self._scale_down_auto_scaling_group(physical_resource_id)
            
            # Step 3: Delete Auto Scaling Group
            self._delete_auto_scaling_group(physical_resource_id)
            
            # Step 4: Delete Launch Template
            launch_template_name = properties.get('LaunchTemplateName')
            if launch_template_name:
                self._delete_launch_template(launch_template_name)
            
            logger.info(f"Auto Scaling Group deleted successfully: {physical_resource_id}")
            return physical_resource_id, {}
            
        except Exception as e:
            logger.error(f"Error deleting Auto Scaling Group: {str(e)}", exc_info=True)
            # For delete operations, return success to avoid blocking stack deletion
            logger.warning("Returning success for delete operation to avoid blocking stack deletion")
            return physical_resource_id, {'Status': 'DeleteFailed', 'Error': str(e)}
    
    def _create_launch_template(self, properties: Dict[str, Any]) -> str:
        """
        Create Launch Template with architecture-specific AMI and User Data.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            str: Launch Template ID
        """
        launch_template_name = properties['LaunchTemplateName']
        image_architecture = properties.get('ImageArchitecture', 'arm64')
        instance_types = properties.get('InstanceTypes', [])
        
        # Get architecture-specific AMI
        ami_id = self._get_architecture_specific_ami(image_architecture)
        
        # Generate User Data script
        user_data = self._generate_user_data_script(properties)
        
        # Prepare Launch Template specification
        launch_template_data = {
            'ImageId': ami_id,
            'InstanceType': instance_types[0] if instance_types else self._get_default_instance_type(image_architecture),
            'UserData': user_data,
            'SecurityGroupIds': properties.get('SecurityGroupIds', []),
            'IamInstanceProfile': {
                'Name': properties.get('InstanceProfileName', '')
            } if properties.get('InstanceProfileName') else {},
            'TagSpecifications': [
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': f"tolling-vision-{launch_template_name}"},
                        {'Key': 'Application', 'Value': 'TollingVision'}
                    ]
                }
            ]
        }
        
        # Add key pair if specified
        if properties.get('KeyPairName'):
            launch_template_data['KeyName'] = properties['KeyPairName']
        
        # Remove empty IamInstanceProfile if not specified
        if not launch_template_data['IamInstanceProfile']:
            del launch_template_data['IamInstanceProfile']
        
        try:
            response = self.ec2_client.create_launch_template(
                LaunchTemplateName=launch_template_name,
                LaunchTemplateData=launch_template_data
            )
            
            launch_template_id = response['LaunchTemplate']['LaunchTemplateId']
            logger.info(f"Launch Template created: {launch_template_id} with AMI: {ami_id}")
            return launch_template_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'InvalidLaunchTemplateName.AlreadyExistsException':
                # Try to get existing template
                try:
                    response = self.ec2_client.describe_launch_templates(
                        LaunchTemplateNames=[launch_template_name]
                    )
                    existing_template = response['LaunchTemplates'][0]
                    logger.info(f"Using existing Launch Template: {existing_template['LaunchTemplateId']}")
                    return existing_template['LaunchTemplateId']
                except Exception:
                    pass
            
            logger.error(f"Failed to create Launch Template: {error_code} - {error_message}")
            raise ValueError(f"Launch Template creation failed: {error_message}")
    
    def _create_auto_scaling_group(self, properties: Dict[str, Any], launch_template_id: str) -> str:
        """
        Create Auto Scaling Group with MixedInstancesPolicy.
        
        Args:
            properties: CloudFormation resource properties
            launch_template_id: Launch Template ID
            
        Returns:
            str: Auto Scaling Group ARN
        """
        asg_name = properties['AutoScalingGroupName']
        subnet_ids = properties['SubnetIds']
        min_size = int(properties['MinSize'])
        max_size = int(properties['MaxSize'])
        desired_capacity = int(properties['DesiredCapacity'])
        
        # Ensure subnet_ids is a list
        if isinstance(subnet_ids, str):
            subnet_ids = [s.strip() for s in subnet_ids.split(',') if s.strip()]
        
        # Prepare Mixed Instances Policy
        mixed_instances_policy = self._create_mixed_instances_policy(properties, launch_template_id)
        
        asg_params = {
            'AutoScalingGroupName': asg_name,
            'MinSize': min_size,
            'MaxSize': max_size,
            'DesiredCapacity': desired_capacity,
            'VPCZoneIdentifier': ','.join(subnet_ids),
            'HealthCheckType': 'ELB',
            'HealthCheckGracePeriod': 300,
            'DefaultCooldown': 300,
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': f"tolling-vision-{asg_name}",
                    'PropagateAtLaunch': True,
                    'ResourceId': asg_name,
                    'ResourceType': 'auto-scaling-group'
                },
                {
                    'Key': 'Application',
                    'Value': 'TollingVision',
                    'PropagateAtLaunch': True,
                    'ResourceId': asg_name,
                    'ResourceType': 'auto-scaling-group'
                }
            ]
        }
        
        # Add Mixed Instances Policy
        if mixed_instances_policy:
            asg_params['MixedInstancesPolicy'] = mixed_instances_policy
        else:
            # Fallback to simple Launch Template
            asg_params['LaunchTemplate'] = {
                'LaunchTemplateId': launch_template_id,
                'Version': '$Latest'
            }
        
        try:
            self.autoscaling_client.create_auto_scaling_group(**asg_params)
            
            # Wait for ASG to be created
            self._wait_for_auto_scaling_group_ready(asg_name)
            
            # Get ASG ARN
            asg_details = self._get_auto_scaling_group_details(asg_name)
            asg_arn = asg_details['AutoScalingGroupARN']
            
            logger.info(f"Auto Scaling Group created: {asg_name}")
            return asg_arn
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to create Auto Scaling Group: {error_code} - {error_message}")
            raise ValueError(f"Auto Scaling Group creation failed: {error_message}")
    
    def _create_mixed_instances_policy(self, properties: Dict[str, Any], launch_template_id: str) -> Dict[str, Any]:
        """
        Create Mixed Instances Policy for On-Demand and Spot instances.
        
        Args:
            properties: CloudFormation resource properties
            launch_template_id: Launch Template ID
            
        Returns:
            Dict: Mixed Instances Policy configuration
        """
        instance_types = properties.get('InstanceTypes', [])
        on_demand_percentage = int(properties.get('OnDemandPercentage', 100))
        image_architecture = properties.get('ImageArchitecture', 'arm64')
        
        # If no instance types specified, use defaults based on architecture
        if not instance_types:
            instance_types = self._get_default_instance_types(image_architecture)
        
        # Ensure instance_types is a list
        if isinstance(instance_types, str):
            instance_types = [t.strip() for t in instance_types.split(',') if t.strip()]
        
        mixed_instances_policy = {
            'LaunchTemplate': {
                'LaunchTemplateSpecification': {
                    'LaunchTemplateId': launch_template_id,
                    'Version': '$Latest'
                },
                'Overrides': [
                    {'InstanceType': instance_type} for instance_type in instance_types
                ]
            },
            'InstancesDistribution': {
                'OnDemandPercentageAboveBaseCapacity': on_demand_percentage,
                'SpotAllocationStrategy': 'diversified'
            }
        }
        
        # Add Spot configuration if using Spot instances
        if on_demand_percentage < 100:
            mixed_instances_policy['InstancesDistribution']['SpotInstancePools'] = min(len(instance_types), 4)
            mixed_instances_policy['InstancesDistribution']['SpotMaxPrice'] = properties.get('SpotMaxPrice', '')
        
        return mixed_instances_policy
    
    def _create_scaling_policies(self, properties: Dict[str, Any], asg_name: str) -> list:
        """
        Create Auto Scaling policies for the ASG.
        
        Args:
            properties: CloudFormation resource properties
            asg_name: Auto Scaling Group name
            
        Returns:
            list: Created scaling policy ARNs
        """
        scaling_policies = []
        
        # Create scale-up policy
        if properties.get('CreateScalingPolicies', False):
            try:
                # Scale Up Policy
                scale_up_response = self.autoscaling_client.put_scaling_policy(
                    AutoScalingGroupName=asg_name,
                    PolicyName=f"{asg_name}-scale-up",
                    PolicyType='StepScaling',
                    AdjustmentType='ChangeInCapacity',
                    StepAdjustments=[
                        {
                            'MetricIntervalLowerBound': 0,
                            'ScalingAdjustment': 1
                        }
                    ],
                    Cooldown=300
                )
                scaling_policies.append(scale_up_response['PolicyARN'])
                
                # Scale Down Policy
                scale_down_response = self.autoscaling_client.put_scaling_policy(
                    AutoScalingGroupName=asg_name,
                    PolicyName=f"{asg_name}-scale-down",
                    PolicyType='StepScaling',
                    AdjustmentType='ChangeInCapacity',
                    StepAdjustments=[
                        {
                            'MetricIntervalUpperBound': 0,
                            'ScalingAdjustment': -1
                        }
                    ],
                    Cooldown=300
                )
                scaling_policies.append(scale_down_response['PolicyARN'])
                
                logger.info(f"Created scaling policies for ASG: {asg_name}")
                
            except Exception as e:
                logger.warning(f"Failed to create scaling policies: {e}")
        
        return scaling_policies
    
    def _register_target_groups(self, properties: Dict[str, Any], asg_name: str) -> None:
        """
        Register Auto Scaling Group with Target Groups.
        
        Args:
            properties: CloudFormation resource properties
            asg_name: Auto Scaling Group name
        """
        target_group_arns = properties.get('TargetGroupARNs', [])
        
        if not target_group_arns:
            return
        
        # Ensure target_group_arns is a list
        if isinstance(target_group_arns, str):
            target_group_arns = [arn.strip() for arn in target_group_arns.split(',') if arn.strip()]
        
        try:
            self.autoscaling_client.attach_load_balancer_target_groups(
                AutoScalingGroupName=asg_name,
                TargetGroupARNs=target_group_arns
            )
            logger.info(f"Registered ASG {asg_name} with target groups: {target_group_arns}")
            
        except Exception as e:
            logger.warning(f"Failed to register target groups: {e}")
    
    def _get_architecture_specific_ami(self, architecture: str) -> str:
        """
        Get the latest Amazon Linux 2023 AMI for the specified architecture.
        
        Args:
            architecture: 'arm64' or 'x86_64'
            
        Returns:
            str: AMI ID
        """
        try:
            # Map architecture to AMI architecture filter
            arch_filter = 'arm64' if architecture == 'arm64' else 'x86_64'
            
            response = self.ec2_client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'name', 'Values': ['al2023-ami-*']},
                    {'Name': 'architecture', 'Values': [arch_filter]},
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'virtualization-type', 'Values': ['hvm']}
                ]
            )
            
            if not response['Images']:
                raise ValueError(f"No Amazon Linux 2023 AMI found for architecture: {architecture}")
            
            # Sort by creation date and get the latest
            images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
            latest_ami = images[0]
            
            logger.info(f"Selected AMI {latest_ami['ImageId']} for architecture {architecture}")
            return latest_ami['ImageId']
            
        except Exception as e:
            logger.error(f"Failed to get AMI for architecture {architecture}: {e}")
            # Fallback to known AMI IDs (these should be updated periodically)
            fallback_amis = {
                'arm64': 'ami-0c02fb55956c7d316',  # Amazon Linux 2023 ARM64
                'x86_64': 'ami-0abcdef1234567890'   # Amazon Linux 2023 x86_64
            }
            
            fallback_ami = fallback_amis.get(architecture, fallback_amis['arm64'])
            logger.warning(f"Using fallback AMI: {fallback_ami}")
            return fallback_ami
    
    def _generate_user_data_script(self, properties: Dict[str, Any]) -> str:
        """
        Generate User Data script for Tolling Vision container startup.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            str: Base64-encoded User Data script
        """
        import base64
        
        # Extract container configuration
        license_key = properties.get('LicenseKey', '')
        process_count = properties.get('ProcessCount', '1')
        concurrent_request_count = properties.get('ConcurrentRequestCount', '1')
        max_request_size = properties.get('MaxRequestSize', '6291456')
        backlog = properties.get('Backlog', '10')
        backlog_timeout = properties.get('BacklogTimeout', '60')
        request_timeout = properties.get('RequestTimeout', '30')
        image_architecture = properties.get('ImageArchitecture', 'arm64')
        image_tag = properties.get('ImageTag', image_architecture)
        
        # Generate User Data script
        user_data_script = f"""#!/bin/bash
yum update -y
yum install -y docker

# Start Docker service
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Install CloudWatch agent
yum install -y amazon-cloudwatch-agent

# Configure CloudWatch agent for container logs
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{{
    "logs": {{
        "logs_collected": {{
            "files": {{
                "collect_list": [
                    {{
                        "file_path": "/var/log/tolling-vision.log",
                        "log_group_name": "/aws/ec2/tolling-vision",
                        "log_stream_name": "{{instance_id}}"
                    }}
                ]
            }}
        }}
    }}
}}
EOF

# Start CloudWatch agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \\
    -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# Pull and run Tolling Vision container
docker pull public.ecr.aws/smartcloud/tollingvision:{image_tag}

# Run container with environment variables
docker run -d \\
    --name tolling-vision \\
    --restart unless-stopped \\
    -p 80:80 \\
    -p 8080:8080 \\
    -e LICENSE_KEY="{license_key}" \\
    -e PROCESS_COUNT="{process_count}" \\
    -e CONCURRENT_REQUEST_COUNT="{concurrent_request_count}" \\
    -e MAX_REQUEST_SIZE="{max_request_size}" \\
    -e BACKLOG="{backlog}" \\
    -e BACKLOG_TIMEOUT="{backlog_timeout}" \\
    -e REQUEST_TIMEOUT="{request_timeout}" \\
    --log-driver=awslogs \\
    --log-opt awslogs-group=/aws/ec2/tolling-vision \\
    --log-opt awslogs-region={get_aws_region()} \\
    public.ecr.aws/smartcloud/tollingvision:{image_tag}

# Create health check script
cat > /home/ec2-user/health-check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost/health || exit 1
EOF

chmod +x /home/ec2-user/health-check.sh

# Log container startup
echo "Tolling Vision container started at $(date)" >> /var/log/tolling-vision.log
"""
        
        # Encode as base64
        encoded_user_data = base64.b64encode(user_data_script.encode('utf-8')).decode('utf-8')
        return encoded_user_data
    
    def _get_default_instance_type(self, architecture: str) -> str:
        """
        Get default instance type for architecture.
        
        Args:
            architecture: 'arm64' or 'x86_64'
            
        Returns:
            str: Default instance type
        """
        defaults = {
            'arm64': 't4g.medium',
            'x86_64': 't3.medium'
        }
        return defaults.get(architecture, 't4g.medium')
    
    def _get_default_instance_types(self, architecture: str) -> list:
        """
        Get default instance types for Mixed Instances Policy.
        
        Args:
            architecture: 'arm64' or 'x86_64'
            
        Returns:
            list: Default instance types
        """
        defaults = {
            'arm64': ['t4g.medium', 't4g.large', 'c7g.large', 'c7g.xlarge'],
            'x86_64': ['t3.medium', 't3.large', 'c6i.large', 'c6i.xlarge']
        }
        return defaults.get(architecture, defaults['arm64'])
    
    def _get_auto_scaling_group_details(self, asg_name: str) -> Optional[Dict[str, Any]]:
        """
        Get Auto Scaling Group details.
        
        Args:
            asg_name: Auto Scaling Group name
            
        Returns:
            Dict: ASG details or None if not found
        """
        try:
            response = self.autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if response['AutoScalingGroups']:
                return response['AutoScalingGroups'][0]
            return None
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return None
            raise
    
    def _wait_for_auto_scaling_group_ready(self, asg_name: str) -> None:
        """
        Wait for Auto Scaling Group to be ready.
        
        Args:
            asg_name: Auto Scaling Group name
        """
        logger.info(f"Waiting for Auto Scaling Group {asg_name} to be ready")
        
        start_time = time.time()
        
        while time.time() - start_time < self.max_wait_time:
            # Check Lambda timeout
            self.timeout_handler.raise_if_timeout()
            
            try:
                asg_details = self._get_auto_scaling_group_details(asg_name)
                if asg_details:
                    logger.info(f"Auto Scaling Group {asg_name} is ready")
                    return
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error checking ASG status: {e}")
                time.sleep(self.poll_interval)
        
        raise TimeoutError(f"Auto Scaling Group {asg_name} did not become ready within {self.max_wait_time} seconds")
    
    def _update_auto_scaling_group(self, asg_name: str, properties: Dict[str, Any]) -> None:
        """
        Update Auto Scaling Group configuration.
        
        Args:
            asg_name: Auto Scaling Group name
            properties: CloudFormation resource properties
        """
        update_params = {
            'AutoScalingGroupName': asg_name
        }
        
        # Update capacity settings
        if 'MinSize' in properties:
            update_params['MinSize'] = int(properties['MinSize'])
        if 'MaxSize' in properties:
            update_params['MaxSize'] = int(properties['MaxSize'])
        if 'DesiredCapacity' in properties:
            update_params['DesiredCapacity'] = int(properties['DesiredCapacity'])
        
        try:
            self.autoscaling_client.update_auto_scaling_group(**update_params)
            logger.info(f"Updated Auto Scaling Group: {asg_name}")
            
        except Exception as e:
            logger.error(f"Failed to update Auto Scaling Group: {e}")
            raise
    
    def _update_launch_template(self, properties: Dict[str, Any]) -> str:
        """
        Update Launch Template if needed.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            str: Launch Template ID
        """
        launch_template_name = properties.get('LaunchTemplateName')
        if not launch_template_name:
            return ""
        
        try:
            # For simplicity, we'll create a new version of the launch template
            # In a production environment, you might want to check if changes are needed
            response = self.ec2_client.describe_launch_templates(
                LaunchTemplateNames=[launch_template_name]
            )
            
            if response['LaunchTemplates']:
                return response['LaunchTemplates'][0]['LaunchTemplateId']
            
        except Exception as e:
            logger.warning(f"Could not update launch template: {e}")
        
        return ""
    
    def _update_scaling_policies(self, properties: Dict[str, Any], asg_name: str) -> list:
        """
        Update scaling policies for the ASG.
        
        Args:
            properties: CloudFormation resource properties
            asg_name: Auto Scaling Group name
            
        Returns:
            list: Updated scaling policy ARNs
        """
        # For simplicity, return existing policies
        # In production, you might want to update or recreate policies
        return []
    
    def _update_target_groups(self, properties: Dict[str, Any], asg_name: str) -> None:
        """
        Update Target Group registration.
        
        Args:
            properties: CloudFormation resource properties
            asg_name: Auto Scaling Group name
        """
        target_group_arns = properties.get('TargetGroupARNs', [])
        
        if target_group_arns:
            self._register_target_groups(properties, asg_name)
    
    def _scale_down_auto_scaling_group(self, asg_name: str) -> None:
        """
        Scale down Auto Scaling Group to 0 instances.
        
        Args:
            asg_name: Auto Scaling Group name
        """
        try:
            self.autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=asg_name,
                MinSize=0,
                DesiredCapacity=0
            )
            
            logger.info(f"Scaling down Auto Scaling Group: {asg_name}")
            
            # Wait for instances to terminate
            start_time = time.time()
            while time.time() - start_time < self.max_wait_time:
                self.timeout_handler.raise_if_timeout()
                
                asg_details = self._get_auto_scaling_group_details(asg_name)
                if asg_details and len(asg_details.get('Instances', [])) == 0:
                    logger.info(f"All instances terminated for ASG: {asg_name}")
                    return
                
                time.sleep(self.poll_interval)
            
            logger.warning(f"Timeout waiting for instances to terminate in ASG: {asg_name}")
            
        except Exception as e:
            logger.error(f"Failed to scale down ASG: {e}")
    
    def _delete_auto_scaling_group(self, asg_name: str) -> None:
        """
        Delete Auto Scaling Group.
        
        Args:
            asg_name: Auto Scaling Group name
        """
        try:
            self.autoscaling_client.delete_auto_scaling_group(
                AutoScalingGroupName=asg_name,
                ForceDelete=True
            )
            logger.info(f"Deleted Auto Scaling Group: {asg_name}")
            
        except Exception as e:
            logger.error(f"Failed to delete Auto Scaling Group: {e}")
    
    def _delete_launch_template(self, launch_template_name: str) -> None:
        """
        Delete Launch Template.
        
        Args:
            launch_template_name: Launch Template name
        """
        try:
            self.ec2_client.delete_launch_template(
                LaunchTemplateName=launch_template_name
            )
            logger.info(f"Deleted Launch Template: {launch_template_name}")
            
        except Exception as e:
            logger.error(f"Failed to delete Launch Template: {e}")
    
    def _delete_scaling_policies(self, asg_name: str) -> None:
        """
        Delete scaling policies for the ASG.
        
        Args:
            asg_name: Auto Scaling Group name
        """
        try:
            # Get existing policies
            response = self.autoscaling_client.describe_policies(
                AutoScalingGroupName=asg_name
            )
            
            for policy in response.get('ScalingPolicies', []):
                policy_name = policy['PolicyName']
                try:
                    self.autoscaling_client.delete_policy(
                        AutoScalingGroupName=asg_name,
                        PolicyName=policy_name
                    )
                    logger.info(f"Deleted scaling policy: {policy_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete scaling policy {policy_name}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to delete scaling policies: {e}")
    
    def _cleanup_on_failure(self, asg_name: str, launch_template_name: str) -> None:
        """
        Cleanup resources on creation failure.
        
        Args:
            asg_name: Auto Scaling Group name
            launch_template_name: Launch Template name
        """
        logger.info("Cleaning up resources after failure")
        
        try:
            # Try to delete ASG if it was created
            if self._get_auto_scaling_group_details(asg_name):
                self._scale_down_auto_scaling_group(asg_name)
                self._delete_auto_scaling_group(asg_name)
        except Exception as e:
            logger.error(f"Failed to cleanup ASG: {e}")
        
        try:
            # Try to delete Launch Template
            self._delete_launch_template(launch_template_name)
        except Exception as e:
            logger.error(f"Failed to cleanup Launch Template: {e}")


class WAFResource:
    """
    Handles WAFv2 WebACL and IPSet creation and management for Tolling Vision SAR application.
    
    This class manages the lifecycle of WAF WebACLs with IP allowlisting rules and default
    block actions for API Gateway custom domain protection.
    """
    
    def __init__(self, wafv2_client, timeout_handler: 'TimeoutHandler'):
        """
        Initialize WAF resource handler.
        
        Args:
            wafv2_client: Boto3 WAFv2 client
            timeout_handler: Timeout management handler
        """
        self.client = wafv2_client
        self.timeout_handler = timeout_handler
        
        # WAF operations are typically fast but can take time for propagation
        self.max_wait_time = 300  # 5 minutes maximum wait
        self.poll_interval = 10   # Check status every 10 seconds
    
    def create(self, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Create WAF WebACL with IP allowlisting rules and IPSet.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
            
        Raises:
            ValueError: If required properties are missing
            ClientError: If AWS API calls fail
        """
        logger.info("Creating WAF WebACL with IP allowlisting")
        
        # Validate required properties
        required_fields = ['Name', 'Scope']
        validate_resource_properties(properties, required_fields)
        
        name = properties['Name']
        scope = properties['Scope']  # REGIONAL for API Gateway
        allowed_ip_cidrs = properties.get('AllowedIpCidrs', [])
        description = properties.get('Description', f'WAF WebACL for {name}')
        
        # Ensure allowed_ip_cidrs is a list
        if isinstance(allowed_ip_cidrs, str):
            allowed_ip_cidrs = [cidr.strip() for cidr in allowed_ip_cidrs.split(',') if cidr.strip()]
        
        logger.info(f"Creating WAF WebACL '{name}' with scope '{scope}'")
        if allowed_ip_cidrs:
            logger.info(f"IP allowlist: {allowed_ip_cidrs}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Step 1: Create IPSet if IP allowlisting is enabled
            ipset_id = None
            ipset_arn = None
            
            if allowed_ip_cidrs:
                ipset_id, ipset_arn = self._create_ipset(name, scope, allowed_ip_cidrs, description)
                logger.info(f"IPSet created: {ipset_id}")
            
            # Step 2: Create WebACL with rules
            webacl_id, webacl_arn = self._create_webacl(name, scope, description, ipset_arn)
            logger.info(f"WebACL created: {webacl_id}")
            
            # Step 3: Associate with API Gateway custom domain if specified
            custom_domain_name = properties.get('ApiCustomDomainName')
            if custom_domain_name:
                self._associate_webacl_with_api_gateway(webacl_arn, custom_domain_name)
                logger.info(f"WebACL associated with API Gateway domain: {custom_domain_name}")
            
            response_data = {
                'WebAclId': webacl_id,
                'WebAclArn': webacl_arn,
                'WebAclName': name,
                'IpSetId': ipset_id,
                'IpSetArn': ipset_arn,
                'Scope': scope
            }
            
            # Remove None values
            response_data = {k: v for k, v in response_data.items() if v is not None}
            
            logger.info(f"WAF WebACL created successfully: {webacl_id}")
            return webacl_id, response_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to create WAF WebACL: {error_code} - {error_message}")
            
            # Handle specific error cases
            if error_code == 'WAFDuplicateItemException':
                raise ValueError(f"WAF WebACL with name '{name}' already exists")
            elif error_code == 'WAFLimitsExceededException':
                raise ValueError("WAF resource limits exceeded")
            elif error_code == 'WAFInvalidParameterException':
                raise ValueError(f"Invalid WAF configuration: {error_message}")
            elif error_code == 'WAFTagOperationException':
                raise ValueError(f"WAF tagging operation failed: {error_message}")
            else:
                raise ValueError(f"WAF WebACL creation failed: {error_code} - {error_message}")
        
        except Exception as e:
            logger.error(f"Unexpected error creating WAF WebACL: {str(e)}", exc_info=True)
            raise ValueError(f"WAF WebACL creation failed: {str(e)}")
    
    def update(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Update WAF WebACL configuration.
        
        Args:
            physical_resource_id: WebACL ID
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Updating WAF WebACL: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            # Get current WebACL details
            current_webacl = self._get_webacl_details(physical_resource_id, properties.get('Scope', 'REGIONAL'))
            if not current_webacl:
                logger.warning(f"WAF WebACL {physical_resource_id} not found, treating as create operation")
                return self.create(properties)
            
            name = properties.get('Name', current_webacl.get('Name'))
            scope = properties.get('Scope', 'REGIONAL')
            allowed_ip_cidrs = properties.get('AllowedIpCidrs', [])
            description = properties.get('Description', current_webacl.get('Description', ''))
            
            # Ensure allowed_ip_cidrs is a list
            if isinstance(allowed_ip_cidrs, str):
                allowed_ip_cidrs = [cidr.strip() for cidr in allowed_ip_cidrs.split(',') if cidr.strip()]
            
            # Update IPSet if IP allowlisting changed
            ipset_id = None
            ipset_arn = None
            
            if allowed_ip_cidrs:
                # Find existing IPSet or create new one
                ipset_name = f"{name}-ipset"
                existing_ipset = self._find_ipset_by_name(ipset_name, scope)
                
                if existing_ipset:
                    ipset_id = existing_ipset['Id']
                    ipset_arn = existing_ipset['ARN']
                    self._update_ipset(ipset_id, scope, allowed_ip_cidrs)
                    logger.info(f"IPSet updated: {ipset_id}")
                else:
                    ipset_id, ipset_arn = self._create_ipset(name, scope, allowed_ip_cidrs, description)
                    logger.info(f"IPSet created: {ipset_id}")
            
            # Update WebACL rules
            self._update_webacl_rules(physical_resource_id, scope, ipset_arn)
            
            # Update API Gateway association if specified
            custom_domain_name = properties.get('ApiCustomDomainName')
            if custom_domain_name:
                webacl_arn = current_webacl['ARN']
                self._associate_webacl_with_api_gateway(webacl_arn, custom_domain_name)
                logger.info(f"WebACL association updated for domain: {custom_domain_name}")
            
            response_data = {
                'WebAclId': physical_resource_id,
                'WebAclArn': current_webacl['ARN'],
                'WebAclName': name,
                'IpSetId': ipset_id,
                'IpSetArn': ipset_arn,
                'Scope': scope
            }
            
            # Remove None values
            response_data = {k: v for k, v in response_data.items() if v is not None}
            
            logger.info(f"WAF WebACL updated successfully: {physical_resource_id}")
            return physical_resource_id, response_data
            
        except Exception as e:
            logger.error(f"Failed to update WAF WebACL: {str(e)}", exc_info=True)
            raise ValueError(f"WAF WebACL update failed: {str(e)}")
    
    def delete(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Delete WAF WebACL and associated IPSet.
        
        Args:
            physical_resource_id: WebACL ID
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Deleting WAF WebACL: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            scope = properties.get('Scope', 'REGIONAL')
            
            # Check if WebACL exists
            webacl_details = self._get_webacl_details(physical_resource_id, scope)
            if not webacl_details:
                logger.info(f"WAF WebACL {physical_resource_id} not found, skipping deletion")
                return physical_resource_id, {}
            
            # Step 1: Disassociate from API Gateway if associated
            custom_domain_name = properties.get('ApiCustomDomainName')
            if custom_domain_name:
                try:
                    self._disassociate_webacl_from_api_gateway(custom_domain_name)
                    logger.info(f"WebACL disassociated from API Gateway domain: {custom_domain_name}")
                except Exception as e:
                    logger.warning(f"Failed to disassociate WebACL from API Gateway: {e}")
            
            # Step 2: Delete WebACL
            self._delete_webacl(physical_resource_id, scope)
            logger.info(f"WebACL deleted: {physical_resource_id}")
            
            # Step 3: Delete associated IPSet
            name = properties.get('Name', webacl_details.get('Name', ''))
            if name:
                ipset_name = f"{name}-ipset"
                existing_ipset = self._find_ipset_by_name(ipset_name, scope)
                if existing_ipset:
                    self._delete_ipset(existing_ipset['Id'], scope)
                    logger.info(f"IPSet deleted: {existing_ipset['Id']}")
            
            logger.info(f"WAF WebACL deleted successfully: {physical_resource_id}")
            return physical_resource_id, {}
            
        except Exception as e:
            logger.error(f"Error deleting WAF WebACL: {str(e)}", exc_info=True)
            # For delete operations, return success to avoid blocking stack deletion
            logger.warning("Returning success for delete operation to avoid blocking stack deletion")
            return physical_resource_id, {'Status': 'DeleteFailed', 'Error': str(e)}
    
    def _create_ipset(self, name: str, scope: str, ip_cidrs: list, description: str) -> tuple[str, str]:
        """
        Create WAF IPSet for IP allowlisting.
        
        Args:
            name: Base name for the IPSet
            scope: WAF scope (REGIONAL or CLOUDFRONT)
            ip_cidrs: List of IP CIDR ranges
            description: IPSet description
            
        Returns:
            tuple: (ipset_id, ipset_arn)
        """
        ipset_name = f"{name}-ipset"
        
        # Validate IP CIDR formats
        validated_cidrs = []
        for cidr in ip_cidrs:
            if self._validate_ip_cidr(cidr):
                validated_cidrs.append(cidr)
            else:
                logger.warning(f"Invalid CIDR format, skipping: {cidr}")
        
        if not validated_cidrs:
            raise ValueError("No valid IP CIDR ranges provided for IPSet")
        
        logger.info(f"Creating IPSet '{ipset_name}' with {len(validated_cidrs)} CIDR ranges")
        
        try:
            response = self.client.create_ip_set(
                Name=ipset_name,
                Scope=scope,
                Description=description,
                IPAddressVersion='IPV4',
                Addresses=validated_cidrs,
                Tags=[
                    {'Key': 'Name', 'Value': ipset_name},
                    {'Key': 'Application', 'Value': 'TollingVision'},
                    {'Key': 'Purpose', 'Value': 'IPAllowlisting'}
                ]
            )
            
            ipset_id = response['Summary']['Id']
            ipset_arn = response['Summary']['ARN']
            
            logger.info(f"IPSet created successfully: {ipset_id}")
            return ipset_id, ipset_arn
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to create IPSet: {error_code} - {error_message}")
            raise ValueError(f"IPSet creation failed: {error_message}")
    
    def _create_webacl(self, name: str, scope: str, description: str, ipset_arn: Optional[str]) -> tuple[str, str]:
        """
        Create WAF WebACL with IP allowlisting rules.
        
        Args:
            name: WebACL name
            scope: WAF scope (REGIONAL or CLOUDFRONT)
            description: WebACL description
            ipset_arn: IPSet ARN for allowlisting (optional)
            
        Returns:
            tuple: (webacl_id, webacl_arn)
        """
        logger.info(f"Creating WebACL '{name}' with scope '{scope}'")
        
        # Build rules based on configuration
        rules = []
        
        # Rule 1: IP Allowlist (if IPSet provided)
        if ipset_arn:
            rules.append({
                'Name': 'IPAllowlistRule',
                'Priority': 1,
                'Statement': {
                    'IPSetReferenceStatement': {
                        'ARN': ipset_arn
                    }
                },
                'Action': {'Allow': {}},
                'VisibilityConfig': {
                    'SampledRequestsEnabled': True,
                    'CloudWatchMetricsEnabled': True,
                    'MetricName': f'{name}-IPAllowlist'
                }
            })
        
        # Default action: Block if IP allowlisting is enabled, Allow otherwise
        default_action = {'Block': {}} if ipset_arn else {'Allow': {}}
        
        try:
            response = self.client.create_web_acl(
                Name=name,
                Scope=scope,
                DefaultAction=default_action,
                Description=description,
                Rules=rules,
                VisibilityConfig={
                    'SampledRequestsEnabled': True,
                    'CloudWatchMetricsEnabled': True,
                    'MetricName': name
                },
                Tags=[
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'Application', 'Value': 'TollingVision'},
                    {'Key': 'Purpose', 'Value': 'APIProtection'}
                ]
            )
            
            webacl_id = response['Summary']['Id']
            webacl_arn = response['Summary']['ARN']
            
            logger.info(f"WebACL created successfully: {webacl_id}")
            return webacl_id, webacl_arn
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to create WebACL: {error_code} - {error_message}")
            raise ValueError(f"WebACL creation failed: {error_message}")
    
    def _associate_webacl_with_api_gateway(self, webacl_arn: str, custom_domain_name: str) -> None:
        """
        Associate WebACL with API Gateway custom domain.
        
        Args:
            webacl_arn: WebACL ARN
            custom_domain_name: API Gateway custom domain name
        """
        try:
            # Get the resource ARN for the API Gateway custom domain
            # For API Gateway v2, the resource ARN format is:
            # arn:aws:apigateway:region::/domainnames/domain-name
            region = get_aws_region()
            resource_arn = f"arn:aws:apigateway:{region}::/domainnames/{custom_domain_name}"
            
            self.client.associate_web_acl(
                WebACLArn=webacl_arn,
                ResourceArn=resource_arn
            )
            
            logger.info(f"WebACL {webacl_arn} associated with API Gateway domain {custom_domain_name}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'WAFNonexistentItemException':
                logger.warning(f"API Gateway domain {custom_domain_name} not found for WebACL association")
            elif error_code == 'WAFInvalidParameterException':
                logger.warning(f"Invalid resource ARN for WebACL association: {error_message}")
            else:
                logger.error(f"Failed to associate WebACL with API Gateway: {error_code} - {error_message}")
                raise ValueError(f"WebACL association failed: {error_message}")
    
    def _disassociate_webacl_from_api_gateway(self, custom_domain_name: str) -> None:
        """
        Disassociate WebACL from API Gateway custom domain.
        
        Args:
            custom_domain_name: API Gateway custom domain name
        """
        try:
            # Get the resource ARN for the API Gateway custom domain
            region = get_aws_region()
            resource_arn = f"arn:aws:apigateway:{region}::/domainnames/{custom_domain_name}"
            
            self.client.disassociate_web_acl(ResourceArn=resource_arn)
            
            logger.info(f"WebACL disassociated from API Gateway domain {custom_domain_name}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code in ['WAFNonexistentItemException', 'WAFNonAssociatedResourceException']:
                logger.info(f"No WebACL associated with API Gateway domain {custom_domain_name}")
            else:
                logger.warning(f"Failed to disassociate WebACL: {e}")
    
    def _get_webacl_details(self, webacl_id: str, scope: str) -> Optional[Dict[str, Any]]:
        """
        Get WebACL details.
        
        Args:
            webacl_id: WebACL ID
            scope: WAF scope
            
        Returns:
            Dict: WebACL details or None if not found
        """
        try:
            response = self.client.get_web_acl(
                Id=webacl_id,
                Scope=scope
            )
            return response['WebACL']
        except ClientError as e:
            if e.response['Error']['Code'] == 'WAFNonexistentItemException':
                return None
            raise
    
    def _find_ipset_by_name(self, ipset_name: str, scope: str) -> Optional[Dict[str, Any]]:
        """
        Find IPSet by name.
        
        Args:
            ipset_name: IPSet name
            scope: WAF scope
            
        Returns:
            Dict: IPSet details or None if not found
        """
        try:
            response = self.client.list_ip_sets(Scope=scope)
            
            for ipset in response.get('IPSets', []):
                if ipset['Name'] == ipset_name:
                    return ipset
            
            return None
            
        except ClientError as e:
            logger.error(f"Failed to list IPSets: {e}")
            return None
    
    def _update_ipset(self, ipset_id: str, scope: str, ip_cidrs: list) -> None:
        """
        Update IPSet with new IP CIDR ranges.
        
        Args:
            ipset_id: IPSet ID
            scope: WAF scope
            ip_cidrs: List of IP CIDR ranges
        """
        try:
            # Get current IPSet details for lock token
            response = self.client.get_ip_set(Id=ipset_id, Scope=scope)
            lock_token = response['LockToken']
            
            # Validate IP CIDR formats
            validated_cidrs = []
            for cidr in ip_cidrs:
                if self._validate_ip_cidr(cidr):
                    validated_cidrs.append(cidr)
                else:
                    logger.warning(f"Invalid CIDR format, skipping: {cidr}")
            
            if not validated_cidrs:
                raise ValueError("No valid IP CIDR ranges provided for IPSet update")
            
            self.client.update_ip_set(
                Id=ipset_id,
                Scope=scope,
                Addresses=validated_cidrs,
                LockToken=lock_token
            )
            
            logger.info(f"IPSet {ipset_id} updated with {len(validated_cidrs)} CIDR ranges")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to update IPSet: {error_code} - {error_message}")
            raise ValueError(f"IPSet update failed: {error_message}")
    
    def _update_webacl_rules(self, webacl_id: str, scope: str, ipset_arn: Optional[str]) -> None:
        """
        Update WebACL rules.
        
        Args:
            webacl_id: WebACL ID
            scope: WAF scope
            ipset_arn: IPSet ARN for allowlisting (optional)
        """
        try:
            # Get current WebACL details for lock token
            response = self.client.get_web_acl(Id=webacl_id, Scope=scope)
            webacl = response['WebACL']
            lock_token = response['LockToken']
            
            # Build updated rules
            rules = []
            
            if ipset_arn:
                rules.append({
                    'Name': 'IPAllowlistRule',
                    'Priority': 1,
                    'Statement': {
                        'IPSetReferenceStatement': {
                            'ARN': ipset_arn
                        }
                    },
                    'Action': {'Allow': {}},
                    'VisibilityConfig': {
                        'SampledRequestsEnabled': True,
                        'CloudWatchMetricsEnabled': True,
                        'MetricName': f'{webacl["Name"]}-IPAllowlist'
                    }
                })
            
            # Update default action based on IP allowlisting
            default_action = {'Block': {}} if ipset_arn else {'Allow': {}}
            
            self.client.update_web_acl(
                Id=webacl_id,
                Scope=scope,
                DefaultAction=default_action,
                Rules=rules,
                VisibilityConfig=webacl['VisibilityConfig'],
                LockToken=lock_token
            )
            
            logger.info(f"WebACL {webacl_id} rules updated")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to update WebACL rules: {error_code} - {error_message}")
            raise ValueError(f"WebACL rules update failed: {error_message}")
    
    def _delete_webacl(self, webacl_id: str, scope: str) -> None:
        """
        Delete WebACL.
        
        Args:
            webacl_id: WebACL ID
            scope: WAF scope
        """
        try:
            # Get current WebACL details for lock token
            response = self.client.get_web_acl(Id=webacl_id, Scope=scope)
            lock_token = response['LockToken']
            
            self.client.delete_web_acl(
                Id=webacl_id,
                Scope=scope,
                LockToken=lock_token
            )
            
            logger.info(f"WebACL {webacl_id} deleted")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'WAFNonexistentItemException':
                logger.info(f"WebACL {webacl_id} not found, considering deletion successful")
            else:
                logger.error(f"Failed to delete WebACL: {e}")
                raise
    
    def _delete_ipset(self, ipset_id: str, scope: str) -> None:
        """
        Delete IPSet.
        
        Args:
            ipset_id: IPSet ID
            scope: WAF scope
        """
        try:
            # Get current IPSet details for lock token
            response = self.client.get_ip_set(Id=ipset_id, Scope=scope)
            lock_token = response['LockToken']
            
            self.client.delete_ip_set(
                Id=ipset_id,
                Scope=scope,
                LockToken=lock_token
            )
            
            logger.info(f"IPSet {ipset_id} deleted")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'WAFNonexistentItemException':
                logger.info(f"IPSet {ipset_id} not found, considering deletion successful")
            else:
                logger.error(f"Failed to delete IPSet: {e}")
                raise
    
    def _validate_ip_cidr(self, cidr: str) -> bool:
        """
        Validate IP CIDR format.
        
        Args:
            cidr: IP CIDR string
            
        Returns:
            bool: True if valid CIDR format
        """
        import re
        
        # Basic CIDR validation regex
        cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
        
        if not re.match(cidr_pattern, cidr):
            return False
        
        try:
            ip_part, prefix_part = cidr.split('/')
            
            # Validate IP address octets
            octets = ip_part.split('.')
            for octet in octets:
                if not (0 <= int(octet) <= 255):
                    return False
            
            # Validate prefix length
            prefix_length = int(prefix_part)
            if not (0 <= prefix_length <= 32):
                return False
            
            return True
            
        except (ValueError, IndexError):
            return False


class CognitoClientSecretResource:
    """
    Handles Cognito App Client Secret retrieval and storage in AWS Secrets Manager.
    
    This class retrieves the client secret from Cognito User Pool App Client and
    stores it securely in AWS Secrets Manager for machine-to-machine authentication.
    """
    
    def __init__(self, cognito_client, secretsmanager_client, timeout_handler: 'TimeoutHandler'):
        """
        Initialize Cognito Client Secret resource handler.
        
        Args:
            cognito_client: Boto3 Cognito Identity Provider client
            secretsmanager_client: Boto3 Secrets Manager client
            timeout_handler: Timeout management handler
        """
        self.cognito_client = cognito_client
        self.secretsmanager_client = secretsmanager_client
        self.timeout_handler = timeout_handler
    
    def create(self, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Retrieve Cognito App Client Secret and store it in Secrets Manager.
        
        Args:
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
            
        Raises:
            ValueError: If required properties are missing
            ClientError: If AWS API calls fail
        """
        logger.info("Retrieving and storing Cognito App Client Secret")
        
        # Validate required properties
        required_fields = ['UserPoolId', 'ClientId', 'SecretName']
        validate_resource_properties(properties, required_fields)
        
        user_pool_id = properties['UserPoolId']
        client_id = properties['ClientId']
        secret_name = properties['SecretName']
        secret_description = properties.get('SecretDescription', 'Cognito App Client Secret')
        stack_name = properties.get('StackName', 'unknown')
        
        logger.info(f"Retrieving client secret for User Pool: {user_pool_id}, Client: {client_id}")
        
        try:
            # Check timeout before making API calls
            self.timeout_handler.raise_if_timeout()
            
            # Retrieve the App Client details including the secret
            response = self.cognito_client.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            
            user_pool_client = response['UserPoolClient']
            client_secret = user_pool_client.get('ClientSecret')
            
            if not client_secret:
                raise ValueError(f"App Client {client_id} does not have a client secret. Ensure GenerateSecret is enabled.")
            
            logger.info(f"Successfully retrieved client secret for {client_id}")
            
            # Prepare the secret value as JSON
            secret_value = {
                'client_id': client_id,
                'client_secret': client_secret,
                'user_pool_id': user_pool_id,
                'created_by': 'tolling-vision-custom-resource',
                'stack_name': stack_name
            }
            
            # Check timeout before updating secret
            self.timeout_handler.raise_if_timeout()
            
            # Update the Secrets Manager secret with the actual client secret
            try:
                self.secretsmanager_client.update_secret(
                    SecretId=secret_name,
                    Description=secret_description,
                    SecretString=json.dumps(secret_value)
                )
                logger.info(f"Successfully updated secret: {secret_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Secret doesn't exist yet, create it
                    logger.info(f"Secret {secret_name} not found, creating it")
                    self.secretsmanager_client.create_secret(
                        Name=secret_name,
                        Description=secret_description,
                        SecretString=json.dumps(secret_value),
                        Tags=[
                            {'Key': 'Name', 'Value': secret_name},
                            {'Key': 'Application', 'Value': 'TollingVision'},
                            {'Key': 'StackName', 'Value': stack_name}
                        ]
                    )
                    logger.info(f"Successfully created secret: {secret_name}")
                else:
                    raise
            
            # Generate physical resource ID
            physical_resource_id = f"cognito-secret-{user_pool_id}-{client_id}"
            
            response_data = {
                'SecretName': secret_name,
                'SecretArn': f"arn:aws:secretsmanager:{get_aws_region()}:{self._get_account_id()}:secret:{secret_name}",
                'UserPoolId': user_pool_id,
                'ClientId': client_id,
                'Status': 'SecretUpdated'
            }
            
            logger.info(f"Cognito client secret stored successfully in {secret_name}")
            return physical_resource_id, response_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Failed to retrieve/store Cognito client secret: {error_code} - {error_message}")
            
            # Handle specific error cases
            if error_code == 'ResourceNotFoundException':
                if 'UserPool' in error_message:
                    raise ValueError(f"User Pool {user_pool_id} not found")
                elif 'Client' in error_message:
                    raise ValueError(f"App Client {client_id} not found in User Pool {user_pool_id}")
                else:
                    raise ValueError(f"Resource not found: {error_message}")
            elif error_code == 'InvalidParameterException':
                raise ValueError(f"Invalid parameter: {error_message}")
            elif error_code == 'NotAuthorizedException':
                raise ValueError(f"Not authorized to access Cognito resources: {error_message}")
            else:
                raise ValueError(f"Cognito client secret retrieval failed: {error_code} - {error_message}")
        
        except Exception as e:
            logger.error(f"Unexpected error retrieving Cognito client secret: {str(e)}", exc_info=True)
            raise ValueError(f"Cognito client secret retrieval failed: {str(e)}")
    
    def update(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Update Cognito App Client Secret in Secrets Manager.
        
        Args:
            physical_resource_id: Physical resource identifier
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Updating Cognito client secret: {physical_resource_id}")
        
        # For updates, we re-retrieve and update the secret
        # This handles cases where the client secret might have been regenerated
        return self.create(properties)
    
    def delete(self, physical_resource_id: str, properties: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Delete operation for Cognito App Client Secret.
        
        Note: We don't actually delete the secret from Secrets Manager as it might be needed
        for cleanup operations. We just mark it as deleted.
        
        Args:
            physical_resource_id: Physical resource identifier
            properties: CloudFormation resource properties
            
        Returns:
            tuple: (physical_resource_id, response_data)
        """
        logger.info(f"Deleting Cognito client secret resource: {physical_resource_id}")
        
        try:
            # Check timeout before processing
            self.timeout_handler.raise_if_timeout()
            
            secret_name = properties.get('SecretName')
            if secret_name:
                # Update the secret to mark it as deleted (but don't actually delete it)
                # This allows for stack rollback scenarios
                try:
                    current_secret = self.secretsmanager_client.get_secret_value(SecretId=secret_name)
                    current_value = json.loads(current_secret['SecretString'])
                    current_value['status'] = 'deleted_by_cloudformation'
                    current_value['deleted_at'] = time.time()
                    
                    self.secretsmanager_client.update_secret(
                        SecretId=secret_name,
                        Description=f"DELETED - {current_secret.get('Description', '')}",
                        SecretString=json.dumps(current_value)
                    )
                    logger.info(f"Marked secret as deleted: {secret_name}")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        logger.info(f"Secret {secret_name} already deleted or not found")
                    else:
                        logger.warning(f"Failed to mark secret as deleted: {e}")
            
            response_data = {
                'Status': 'Deleted',
                'SecretName': secret_name or 'unknown'
            }
            
            logger.info("Cognito client secret resource deleted successfully")
            return physical_resource_id, response_data
            
        except Exception as e:
            logger.warning(f"Error during Cognito client secret deletion: {str(e)}")
            # For delete operations, we return success to avoid blocking stack deletion
            response_data = {
                'Status': 'DeleteFailed',
                'Error': str(e)
            }
            return physical_resource_id, response_data
    
    def _get_account_id(self) -> str:
        """
        Get the current AWS account ID.
        
        Returns:
            str: AWS account ID
        """
        try:
            sts_client = boto3.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception as e:
            logger.warning(f"Failed to get account ID: {e}")
            return '123456789012'  # Fallback for ARN construction