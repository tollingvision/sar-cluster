# JWT Authentication Guide

## Overview

This guide covers JWT authentication setup, token generation, and API testing for the Tolling Vision infrastructure when JWT authentication is enabled.

## Prerequisites

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv tolling-vision-env
source tolling-vision-env/bin/activate

# Install required tools
pip install boto3 botocore requests cryptography pyjwt

# Verify AWS access
aws sts get-caller-identity --no-paginate
```

## JWT Authentication Architecture

When `EnableJwtAuth` is set to `true`, the system creates:
- Cognito User Pool for JWT token issuing
- Resource Server with custom scopes
- App Client configured for client credentials flow
- JWT Authorizer on API Gateway
- Client secret stored in AWS Secrets Manager

## Retrieving Authentication Details

### Get Cognito Configuration
```bash
# Get User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
  --output text \
  --no-paginate)

echo "User Pool ID: $USER_POOL_ID"

# Get App Client ID
CLIENT_ID=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoAppClientId`].OutputValue' \
  --output text \
  --no-paginate)

echo "Client ID: $CLIENT_ID"

# Get Client Secret from Secrets Manager
SECRET_ARN=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoClientSecretArn`].OutputValue' \
  --output text \
  --no-paginate)

CLIENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_ARN \
  --query 'SecretString' \
  --output text \
  --no-paginate)

echo "Client Secret: $CLIENT_SECRET"

# Get Cognito Domain (for token endpoint)
COGNITO_DOMAIN=$(aws cognito-idp describe-user-pool \
  --user-pool-id $USER_POOL_ID \
  --query 'UserPool.Domain' \
  --output text \
  --no-paginate)

echo "Cognito Domain: $COGNITO_DOMAIN"
```

### Get API Gateway Details
```bash
# Get API Gateway endpoint
API_ENDPOINT=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayEndpoint`].OutputValue' \
  --output text \
  --no-paginate)

echo "API Endpoint: $API_ENDPOINT"

# Get custom domain (if configured)
CUSTOM_DOMAIN=$(aws cloudformation describe-stack-outputs \
  --stack-name tolling-vision-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CustomDomainName`].OutputValue' \
  --output text \
  --no-paginate)

echo "Custom Domain: $CUSTOM_DOMAIN"
```

## JWT Token Generation

### Method 1: Using AWS CLI and curl
```bash
# Set variables (replace with your actual values)
USER_POOL_ID="us-east-1_XXXXXXXXX"
CLIENT_ID="your-client-id"
CLIENT_SECRET="your-client-secret"
REGION="us-east-1"

# Generate access token using client credentials flow
TOKEN_RESPONSE=$(curl -s -X POST \
  "https://tolling-vision-prod.auth.${REGION}.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic $(echo -n "${CLIENT_ID}:${CLIENT_SECRET}" | base64)" \
  -d "grant_type=client_credentials&scope=api/m2m")

# Extract access token
ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Access Token: $ACCESS_TOKEN"

# Verify token expiration
echo $TOKEN_RESPONSE | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Token expires in: {data[\"expires_in\"]} seconds')"
```

### Method 2: Using Python Script
```python
#!/usr/bin/env python3
import boto3
import requests
import base64
import json
from datetime import datetime, timedelta

def get_jwt_token(user_pool_id, client_id, client_secret, region='us-east-1'):
    """Generate JWT token using Cognito client credentials flow"""
    
    # Cognito token endpoint
    token_url = f"https://tolling-vision-prod.auth.{region}.amazoncognito.com/oauth2/token"
    
    # Prepare credentials
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    # Request headers
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {encoded_credentials}'
    }
    
    # Request body
    data = {
        'grant_type': 'client_credentials',
        'scope': 'api/m2m'
    }
    
    # Make request
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        return token_data['access_token'], token_data['expires_in']
    else:
        raise Exception(f"Token request failed: {response.status_code} - {response.text}")

def get_cognito_config_from_stack(stack_name):
    """Retrieve Cognito configuration from CloudFormation stack"""
    cf = boto3.client('cloudformation')
    
    # Get stack outputs
    response = cf.describe_stacks(StackName=stack_name)
    outputs = response['Stacks'][0]['Outputs']
    
    config = {}
    for output in outputs:
        if output['OutputKey'] == 'CognitoUserPoolId':
            config['user_pool_id'] = output['OutputValue']
        elif output['OutputKey'] == 'CognitoAppClientId':
            config['client_id'] = output['OutputValue']
        elif output['OutputKey'] == 'CognitoClientSecretArn':
            config['secret_arn'] = output['OutputValue']
    
    # Get client secret from Secrets Manager
    secrets = boto3.client('secretsmanager')
    secret_response = secrets.get_secret_value(SecretId=config['secret_arn'])
    config['client_secret'] = secret_response['SecretString']
    
    return config

if __name__ == "__main__":
    # Get configuration from CloudFormation stack
    stack_name = "tolling-vision-prod"
    config = get_cognito_config_from_stack(stack_name)
    
    # Generate token
    try:
        access_token, expires_in = get_jwt_token(
            config['user_pool_id'],
            config['client_id'], 
            config['client_secret']
        )
        
        print(f"Access Token: {access_token}")
        print(f"Expires in: {expires_in} seconds")
        print(f"Expires at: {datetime.now() + timedelta(seconds=expires_in)}")
        
    except Exception as e:
        print(f"Error generating token: {e}")
```

Save this as `generate_jwt_token.py` and run:
```bash
python3 generate_jwt_token.py
```

## API Testing with JWT

### Test HTTP/1.1 Endpoint
```bash
# Set your access token
ACCESS_TOKEN="your-jwt-token-here"

# Test health endpoint
curl -X GET "https://api.yourdomain.com/health" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -v

# Test with invalid token (should return 401)
curl -X GET "https://api.yourdomain.com/health" \
  -H "Authorization: Bearer invalid-token" \
  -H "Content-Type: application/json" \
  -v

# Test without token (should return 401)
curl -X GET "https://api.yourdomain.com/health" \
  -H "Content-Type: application/json" \
  -v
```

### Test gRPC Endpoint
```bash
# Using grpcurl with JWT token
grpcurl \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -plaintext \
  api.yourdomain.com:8443 \
  grpc.health.v1.Health/Check

# Test with invalid token
grpcurl \
  -H "Authorization: Bearer invalid-token" \
  -plaintext \
  api.yourdomain.com:8443 \
  grpc.health.v1.Health/Check
```

### Automated API Testing Script
```python
#!/usr/bin/env python3
import requests
import json
import sys
from datetime import datetime

def test_api_with_jwt(api_endpoint, access_token):
    """Test API endpoints with JWT authentication"""
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Test endpoints
    endpoints = [
        '/health',
        '/status',
        '/api/v1/process'  # Example processing endpoint
    ]
    
    results = []
    
    for endpoint in endpoints:
        url = f"{api_endpoint}{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            result = {
                'endpoint': endpoint,
                'status_code': response.status_code,
                'success': response.status_code < 400,
                'response_time': response.elapsed.total_seconds(),
                'timestamp': datetime.now().isoformat()
            }
            
            if response.status_code < 400:
                print(f"✅ {endpoint}: {response.status_code} ({result['response_time']:.3f}s)")
            else:
                print(f"❌ {endpoint}: {response.status_code} ({result['response_time']:.3f}s)")
                
            results.append(result)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint}: Request failed - {e}")
            results.append({
                'endpoint': endpoint,
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            })
    
    return results

def test_unauthorized_access(api_endpoint):
    """Test that unauthorized requests are properly rejected"""
    
    print("\nTesting unauthorized access...")
    
    # Test without token
    response = requests.get(f"{api_endpoint}/health", timeout=30)
    if response.status_code == 401:
        print("✅ No token: Correctly rejected (401)")
    else:
        print(f"❌ No token: Expected 401, got {response.status_code}")
    
    # Test with invalid token
    headers = {'Authorization': 'Bearer invalid-token'}
    response = requests.get(f"{api_endpoint}/health", headers=headers, timeout=30)
    if response.status_code == 401:
        print("✅ Invalid token: Correctly rejected (401)")
    else:
        print(f"❌ Invalid token: Expected 401, got {response.status_code}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 test_api.py <api_endpoint> <access_token>")
        sys.exit(1)
    
    api_endpoint = sys.argv[1]
    access_token = sys.argv[2]
    
    print(f"Testing API: {api_endpoint}")
    print(f"Token: {access_token[:20]}...")
    print("-" * 50)
    
    # Test with valid token
    results = test_api_with_jwt(api_endpoint, access_token)
    
    # Test unauthorized access
    test_unauthorized_access(api_endpoint)
    
    # Summary
    successful_tests = sum(1 for r in results if r.get('success', False))
    total_tests = len(results)
    
    print(f"\nSummary: {successful_tests}/{total_tests} tests passed")
```

Save as `test_api.py` and run:
```bash
python3 test_api.py "https://api.yourdomain.com" "$ACCESS_TOKEN"
```

## JWT Token Validation

### Decode JWT Token (for debugging)
```python
#!/usr/bin/env python3
import jwt
import json
import sys
from datetime import datetime

def decode_jwt_token(token, verify=False):
    """Decode JWT token without verification (for debugging)"""
    
    try:
        # Decode without verification (for inspection only)
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        print("JWT Token Contents:")
        print(json.dumps(decoded, indent=2))
        
        # Check expiration
        if 'exp' in decoded:
            exp_time = datetime.fromtimestamp(decoded['exp'])
            now = datetime.now()
            
            print(f"\nToken expires at: {exp_time}")
            print(f"Current time: {now}")
            
            if exp_time > now:
                remaining = exp_time - now
                print(f"Time remaining: {remaining}")
            else:
                print("⚠️  Token has expired!")
        
        # Check scope
        if 'scope' in decoded:
            print(f"Scopes: {decoded['scope']}")
        
        return decoded
        
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 decode_jwt.py <jwt_token>")
        sys.exit(1)
    
    token = sys.argv[1]
    decode_jwt_token(token)
```

Save as `decode_jwt.py` and run:
```bash
python3 decode_jwt.py "$ACCESS_TOKEN"
```

## Token Management

### Token Refresh Strategy
```python
#!/usr/bin/env python3
import boto3
import requests
import base64
import json
import time
from datetime import datetime, timedelta

class JWTTokenManager:
    def __init__(self, user_pool_id, client_id, client_secret, region='us-east-1'):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.token_url = f"https://tolling-vision-prod.auth.{region}.amazoncognito.com/oauth2/token"
        
        self.access_token = None
        self.token_expires_at = None
        
    def get_token(self, force_refresh=False):
        """Get valid access token, refreshing if necessary"""
        
        # Check if we need to refresh
        if (force_refresh or 
            self.access_token is None or 
            self.token_expires_at is None or 
            datetime.now() >= self.token_expires_at - timedelta(minutes=5)):
            
            self._refresh_token()
        
        return self.access_token
    
    def _refresh_token(self):
        """Refresh the access token"""
        
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded_credentials}'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'scope': 'api/m2m'
        }
        
        response = requests.post(self.token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data['expires_in']
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            print(f"Token refreshed. Expires at: {self.token_expires_at}")
        else:
            raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")
    
    def make_authenticated_request(self, method, url, **kwargs):
        """Make HTTP request with automatic token management"""
        
        token = self.get_token()
        
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        kwargs['headers']['Authorization'] = f'Bearer {token}'
        
        return requests.request(method, url, **kwargs)

# Example usage
if __name__ == "__main__":
    # Initialize token manager
    token_manager = JWTTokenManager(
        user_pool_id="us-east-1_XXXXXXXXX",
        client_id="your-client-id",
        client_secret="your-client-secret"
    )
    
    # Make authenticated requests
    response = token_manager.make_authenticated_request(
        'GET', 
        'https://api.yourdomain.com/health'
    )
    
    print(f"Response: {response.status_code}")
    print(f"Body: {response.text}")
```

## Troubleshooting JWT Authentication

### Common Issues and Solutions

#### 1. 401 Unauthorized Errors
```bash
# Check if JWT auth is enabled
aws cloudformation describe-stack-parameters \
  --stack-name tolling-vision-prod \
  --query 'Parameters[?ParameterKey==`EnableJwtAuth`].ParameterValue' \
  --output text \
  --no-paginate

# Verify JWT authorizer configuration
aws apigatewayv2 get-authorizers \
  --api-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
    --output text) \
  --no-paginate
```

#### 2. Token Generation Failures
```bash
# Check Cognito User Pool status
aws cognito-idp describe-user-pool \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --no-paginate

# Verify App Client configuration
aws cognito-idp describe-user-pool-client \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --client-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoAppClientId`].OutputValue' \
    --output text) \
  --no-paginate
```

#### 3. Scope Validation Issues
```bash
# Check Resource Server configuration
aws cognito-idp describe-resource-server \
  --user-pool-id $(aws cloudformation describe-stack-outputs \
    --stack-name tolling-vision-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
    --output text) \
  --identifier api \
  --no-paginate
```

## Environment Cleanup

### Deactivate Virtual Environment
```bash
# Always deactivate when done
deactivate

# Verify deactivation
which python3
```

## Security Best Practices

1. **Token Storage**: Never store JWT tokens in plain text files or version control
2. **Token Rotation**: Implement automatic token refresh before expiration
3. **Scope Validation**: Use minimal required scopes for each client
4. **Client Secret Management**: Rotate client secrets regularly
5. **Network Security**: Use HTTPS only for all API communications
6. **Monitoring**: Monitor failed authentication attempts and unusual patterns

## Integration Examples

For complete integration examples and production-ready code, see the `examples/` directory in the project repository.