#!/usr/bin/env python3
"""
Template Size Validation Script for SAR Compliance
Validates CloudFormation template size and provides deployment guidance
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def get_file_size(file_path):
    """Get file size in bytes"""
    return os.path.getsize(file_path)

def format_size(size_bytes):
    """Format size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def validate_template_syntax(template_path):
    """Validate CloudFormation template syntax using AWS CLI"""
    try:
        # Try direct validation first (will fail if > 51KB)
        result = subprocess.run([
            'aws', 'cloudformation', 'validate-template',
            '--template-body', f'file://{template_path}',
            '--no-paginate'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return True, "Direct validation successful"
        else:
            # Check if it's a size error
            if "Member must have length less than or equal to 51200" in result.stderr:
                return False, "Template exceeds 51KB direct limit - requires S3-based validation"
            else:
                return False, f"Validation error: {result.stderr}"
    
    except subprocess.TimeoutExpired:
        return False, "Validation timeout"
    except Exception as e:
        return False, f"Validation exception: {str(e)}"

def check_sar_compliance(template_path):
    """Check SAR compliance and provide recommendations"""
    size = get_file_size(template_path)
    
    # SAR size limits
    DIRECT_LIMIT = 51200  # 51KB
    S3_LIMIT = 460800     # 450KB
    
    print(f"Template Size Analysis:")
    print(f"File: {template_path}")
    print(f"Size: {format_size(size)} ({size:,} bytes)")
    print()
    
    if size <= DIRECT_LIMIT:
        print("✅ SAR Direct Deployment: SUPPORTED")
        print("   - Can deploy directly from SAR marketplace")
        print("   - Use --template-body parameter")
        print()
        deployment_method = "direct"
    elif size <= S3_LIMIT:
        print("⚠️  SAR Direct Deployment: NOT SUPPORTED (exceeds 51KB)")
        print("✅ SAR S3-based Deployment: SUPPORTED")
        print("   - Requires S3 bucket upload")
        print("   - Use --template-url parameter")
        print("   - Still SAR marketplace compatible")
        print()
        deployment_method = "s3"
    else:
        print("❌ SAR Direct Deployment: NOT SUPPORTED (exceeds 51KB)")
        print("❌ SAR S3-based Deployment: NOT SUPPORTED (exceeds 450KB)")
        print("   - Template too large for SAR")
        print("   - Consider template optimization")
        print("   - Alternative: Direct CloudFormation deployment")
        print()
        deployment_method = "none"
    
    return deployment_method, size

def generate_deployment_commands(template_path, deployment_method, size):
    """Generate deployment commands based on template size"""
    
    print("Deployment Commands:")
    print("=" * 50)
    
    if deployment_method == "direct":
        print("Direct SAR Deployment (< 51KB):")
        print(f"aws cloudformation validate-template \\")
        print(f"  --template-body file://{template_path} \\")
        print(f"  --no-paginate")
        print()
        print(f"aws cloudformation create-stack \\")
        print(f"  --stack-name tolling-vision-prod \\")
        print(f"  --template-body file://{template_path} \\")
        print(f"  --parameters file://parameters.json \\")
        print(f"  --capabilities CAPABILITY_IAM \\")
        print(f"  --no-paginate")
        
    elif deployment_method == "s3":
        print("S3-based SAR Deployment (51KB-450KB):")
        print("# 1. Upload template to S3")
        print(f"aws s3 cp {template_path} s3://my-sar-artifacts-bucket/{template_path}")
        print()
        print("# 2. Validate using S3 URL")
        print(f"aws cloudformation validate-template \\")
        print(f"  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/{template_path} \\")
        print(f"  --no-paginate")
        print()
        print("# 3. Deploy using S3 URL")
        print(f"aws cloudformation create-stack \\")
        print(f"  --stack-name tolling-vision-prod \\")
        print(f"  --template-url https://my-sar-artifacts-bucket.s3.amazonaws.com/{template_path} \\")
        print(f"  --parameters file://parameters.json \\")
        print(f"  --capabilities CAPABILITY_IAM \\")
        print(f"  --no-paginate")
        
    else:
        print("Template Optimization Required:")
        print("- Current size exceeds SAR limits")
        print("- Consider removing comments and whitespace")
        print("- Optimize Lambda function code")
        print("- Reduce mapping complexity")
        print("- Alternative: Use direct CloudFormation (no SAR)")
    
    print()

def main():
    """Main function"""
    # Get script directory and project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Change to project root
    os.chdir(project_root)
    
    template_path = sys.argv[1] if len(sys.argv) > 1 else "template.yaml"
    
    if not os.path.exists(template_path):
        print(f"Error: Template file '{template_path}' not found")
        print(f"Current directory: {os.getcwd()}")
        sys.exit(1)
    
    print("Tolling Vision SAR Template Size Validation")
    print("=" * 50)
    print()
    
    # Check SAR compliance
    deployment_method, size = check_sar_compliance(template_path)
    
    # Validate template syntax
    print("Template Syntax Validation:")
    print("-" * 30)
    is_valid, message = validate_template_syntax(template_path)
    
    if is_valid:
        print("✅ Template syntax is valid")
    else:
        print(f"⚠️  {message}")
    
    print()
    
    # Generate deployment commands
    generate_deployment_commands(template_path, deployment_method, size)
    
    # Summary and recommendations
    print()
    print("Summary and Recommendations:")
    print("=" * 50)
    
    if deployment_method == "direct":
        print("✅ Ready for direct SAR marketplace deployment")
        print("✅ Optimal size for fast deployment")
        
    elif deployment_method == "s3":
        print("✅ Ready for S3-based SAR marketplace deployment")
        print("⚠️  Requires S3 bucket for template storage")
        print("💡 Consider template optimization for direct deployment")
        
    else:
        print("❌ Template requires optimization for SAR compliance")
        print("💡 Consider alternative distribution methods")
    
    print()
    print("Template Size Breakdown:")
    print(f"- Current: {format_size(size)}")
    print(f"- Direct SAR Limit: {format_size(51200)}")
    print(f"- S3-based SAR Limit: {format_size(460800)}")
    
    # Exit code based on SAR compliance
    if deployment_method in ["direct", "s3"]:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Needs optimization

if __name__ == "__main__":
    main()