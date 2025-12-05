#!/usr/bin/env python3
"""
Comprehensive API testing script for Tolling Vision infrastructure
Tests both HTTP/1.1 and gRPC endpoints with JWT authentication
"""

import requests
import json
import sys
import time
import boto3
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class TollingVisionAPITester:
    def __init__(self, stack_name: str, region: str = 'us-east-1'):
        self.stack_name = stack_name
        self.region = region
        self.cf_client = boto3.client('cloudformation', region_name=region)
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        
        # Get stack outputs
        self.stack_outputs = self._get_stack_outputs()
        
        # Initialize authentication
        self.access_token = None
        self.token_expires_at = None
        
    def _get_stack_outputs(self) -> Dict[str, str]:
        """Retrieve CloudFormation stack outputs"""
        try:
            response = self.cf_client.describe_stacks(StackName=self.stack_name)
            outputs = response['Stacks'][0]['Outputs']
            
            output_dict = {}
            for output in outputs:
                output_dict[output['OutputKey']] = output['OutputValue']
            
            return output_dict
            
        except Exception as e:
            print(f"❌ Error retrieving stack outputs: {e}")
            sys.exit(1)
    
    def _get_jwt_token(self) -> str:
        """Generate JWT token using Cognito client credentials flow"""
        
        # Check if we have a valid token
        if (self.access_token and 
            self.token_expires_at and 
            datetime.now() < self.token_expires_at - timedelta(minutes=5)):
            return self.access_token
        
        try:
            # Get client credentials
            user_pool_id = self.stack_outputs.get('CognitoUserPoolId')
            client_id = self.stack_outputs.get('CognitoAppClientId')
            secret_arn = self.stack_outputs.get('CognitoClientSecretArn')
            
            if not all([user_pool_id, client_id, secret_arn]):
                raise Exception("JWT authentication not enabled or configured")
            
            # Get client secret from Secrets Manager
            secret_response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            client_secret = secret_response['SecretString']
            
            # Construct token endpoint URL
            token_url = f"https://{self.stack_name}.auth.{self.region}.amazoncognito.com/oauth2/token"
            
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
            
            # Make token request
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                expires_in = token_data['expires_in']
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                print(f"✅ JWT token generated (expires in {expires_in} seconds)")
                return self.access_token
            else:
                raise Exception(f"Token request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ JWT token generation failed: {e}")
            return None
    
    def test_http_endpoints(self, use_jwt: bool = True) -> List[Dict]:
        """Test HTTP/1.1 endpoints"""
        
        print("\n🌐 Testing HTTP/1.1 Endpoints")
        print("-" * 40)
        
        # Get API endpoint
        api_endpoint = self.stack_outputs.get('ApiGatewayEndpoint')
        custom_domain = self.stack_outputs.get('ApiCustomDomainName')
        
        base_url = f"https://{custom_domain}" if custom_domain else api_endpoint
        
        if not base_url:
            print("❌ No API endpoint found in stack outputs")
            return []
        
        # Prepare headers
        headers = {'Content-Type': 'application/json'}
        
        if use_jwt:
            token = self._get_jwt_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'
            else:
                print("⚠️  Proceeding without JWT authentication")
        
        # Test endpoints
        endpoints = [
            {'path': '/health', 'method': 'GET', 'description': 'Health check'},
            {'path': '/status', 'method': 'GET', 'description': 'Status endpoint'},
            {'path': '/api/v1/info', 'method': 'GET', 'description': 'API information'},
            {'path': '/metrics', 'method': 'GET', 'description': 'Metrics endpoint'},
        ]
        
        results = []
        
        for endpoint in endpoints:
            url = f"{base_url}{endpoint['path']}"
            
            try:
                start_time = time.time()
                
                if endpoint['method'] == 'GET':
                    response = requests.get(url, headers=headers, timeout=30)
                elif endpoint['method'] == 'POST':
                    response = requests.post(url, headers=headers, json={}, timeout=30)
                
                response_time = time.time() - start_time
                
                result = {
                    'endpoint': endpoint['path'],
                    'method': endpoint['method'],
                    'description': endpoint['description'],
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'success': response.status_code < 400,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Add response details for successful requests
                if response.status_code < 400:
                    try:
                        result['response_body'] = response.json()
                    except:
                        result['response_body'] = response.text[:200]
                
                status_icon = "✅" if result['success'] else "❌"
                print(f"{status_icon} {endpoint['method']} {endpoint['path']}: "
                      f"{response.status_code} ({response_time:.3f}s) - {endpoint['description']}")
                
                results.append(result)
                
            except requests.exceptions.RequestException as e:
                result = {
                    'endpoint': endpoint['path'],
                    'method': endpoint['method'],
                    'description': endpoint['description'],
                    'error': str(e),
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"❌ {endpoint['method']} {endpoint['path']}: Request failed - {e}")
                results.append(result)
        
        return results
    
    def test_grpc_endpoints(self, use_jwt: bool = True) -> List[Dict]:
        """Test gRPC endpoints (requires grpcurl)"""
        
        print("\n🔌 Testing gRPC Endpoints")
        print("-" * 40)
        
        # Check if grpcurl is available
        import subprocess
        try:
            subprocess.run(['grpcurl', '--version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  grpcurl not found. Skipping gRPC tests.")
            print("   Install grpcurl: https://github.com/fullstorydev/grpcurl")
            return []
        
        # Get gRPC endpoint
        custom_domain = self.stack_outputs.get('ApiCustomDomainName')
        
        if not custom_domain:
            print("❌ No custom domain found for gRPC testing")
            return []
        
        grpc_endpoint = f"{custom_domain}:8443"
        
        # Prepare authentication
        auth_args = []
        if use_jwt:
            token = self._get_jwt_token()
            if token:
                auth_args = ['-H', f'Authorization: Bearer {token}']
        
        # Test gRPC services
        grpc_tests = [
            {
                'service': 'grpc.health.v1.Health/Check',
                'description': 'Health check service'
            },
            {
                'service': 'grpc.reflection.v1alpha.ServerReflection/ServerReflectionInfo',
                'description': 'Reflection service'
            }
        ]
        
        results = []
        
        for test in grpc_tests:
            try:
                start_time = time.time()
                
                cmd = ['grpcurl', '-plaintext'] + auth_args + [grpc_endpoint, test['service']]
                
                result_proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                response_time = time.time() - start_time
                
                result = {
                    'service': test['service'],
                    'description': test['description'],
                    'success': result_proc.returncode == 0,
                    'response_time': response_time,
                    'stdout': result_proc.stdout,
                    'stderr': result_proc.stderr,
                    'timestamp': datetime.now().isoformat()
                }
                
                status_icon = "✅" if result['success'] else "❌"
                print(f"{status_icon} {test['service']}: "
                      f"{'Success' if result['success'] else 'Failed'} "
                      f"({response_time:.3f}s) - {test['description']}")
                
                results.append(result)
                
            except subprocess.TimeoutExpired:
                result = {
                    'service': test['service'],
                    'description': test['description'],
                    'error': 'Timeout',
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"❌ {test['service']}: Timeout - {test['description']}")
                results.append(result)
            
            except Exception as e:
                result = {
                    'service': test['service'],
                    'description': test['description'],
                    'error': str(e),
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"❌ {test['service']}: Error - {e}")
                results.append(result)
        
        return results
    
    def test_unauthorized_access(self) -> List[Dict]:
        """Test that unauthorized requests are properly rejected"""
        
        print("\n🔒 Testing Unauthorized Access")
        print("-" * 40)
        
        # Get API endpoint
        api_endpoint = self.stack_outputs.get('ApiGatewayEndpoint')
        custom_domain = self.stack_outputs.get('ApiCustomDomainName')
        
        base_url = f"https://{custom_domain}" if custom_domain else api_endpoint
        
        if not base_url:
            print("❌ No API endpoint found")
            return []
        
        test_cases = [
            {
                'name': 'No Authorization Header',
                'headers': {'Content-Type': 'application/json'},
                'expected_status': 401
            },
            {
                'name': 'Invalid Bearer Token',
                'headers': {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer invalid-token-12345'
                },
                'expected_status': 401
            },
            {
                'name': 'Malformed Authorization Header',
                'headers': {
                    'Content-Type': 'application/json',
                    'Authorization': 'InvalidFormat token'
                },
                'expected_status': 401
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            try:
                response = requests.get(
                    f"{base_url}/health",
                    headers=test_case['headers'],
                    timeout=30
                )
                
                result = {
                    'test_case': test_case['name'],
                    'status_code': response.status_code,
                    'expected_status': test_case['expected_status'],
                    'success': response.status_code == test_case['expected_status'],
                    'timestamp': datetime.now().isoformat()
                }
                
                status_icon = "✅" if result['success'] else "❌"
                print(f"{status_icon} {test_case['name']}: "
                      f"Got {response.status_code}, expected {test_case['expected_status']}")
                
                results.append(result)
                
            except Exception as e:
                result = {
                    'test_case': test_case['name'],
                    'error': str(e),
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"❌ {test_case['name']}: Error - {e}")
                results.append(result)
        
        return results
    
    def run_comprehensive_tests(self) -> Dict:
        """Run all tests and return comprehensive results"""
        
        print(f"🧪 Starting Comprehensive API Tests for Stack: {self.stack_name}")
        print(f"📍 Region: {self.region}")
        print(f"⏰ Timestamp: {datetime.now().isoformat()}")
        print("=" * 60)
        
        # Check if JWT is enabled
        jwt_enabled = 'CognitoUserPoolId' in self.stack_outputs
        print(f"🔐 JWT Authentication: {'Enabled' if jwt_enabled else 'Disabled'}")
        
        # Run tests
        http_results = self.test_http_endpoints(use_jwt=jwt_enabled)
        grpc_results = self.test_grpc_endpoints(use_jwt=jwt_enabled)
        
        # Only test unauthorized access if JWT is enabled
        unauthorized_results = []
        if jwt_enabled:
            unauthorized_results = self.test_unauthorized_access()
        
        # Compile results
        all_results = {
            'stack_name': self.stack_name,
            'region': self.region,
            'jwt_enabled': jwt_enabled,
            'timestamp': datetime.now().isoformat(),
            'stack_outputs': self.stack_outputs,
            'http_tests': http_results,
            'grpc_tests': grpc_results,
            'unauthorized_tests': unauthorized_results
        }
        
        # Summary
        total_tests = len(http_results) + len(grpc_results) + len(unauthorized_results)
        successful_tests = sum(1 for r in http_results + grpc_results + unauthorized_results 
                             if r.get('success', False))
        
        print(f"\n📊 Test Summary")
        print("-" * 40)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        
        if successful_tests == total_tests:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed. Check the detailed results above.")
        
        return all_results

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test-api-endpoints.py <stack-name> [region]")
        print("\nExample:")
        print("  python3 test-api-endpoints.py tolling-vision-prod us-east-1")
        sys.exit(1)
    
    stack_name = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else 'us-east-1'
    
    # Initialize tester
    tester = TollingVisionAPITester(stack_name, region)
    
    # Run tests
    results = tester.run_comprehensive_tests()
    
    # Save results to file
    output_file = f"test-results-{stack_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == "__main__":
    main()