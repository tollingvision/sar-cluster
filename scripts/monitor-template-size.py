#!/usr/bin/env python3

"""
Template Size Monitoring Script
Monitors CloudFormation template size and provides S3 upload procedures
"""

import os
import sys
import json
import time
import boto3
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from botocore.exceptions import ClientError, NoCredentialsError

class TemplateSizeMonitor:
    """Monitor CloudFormation template size and manage S3 uploads"""
    
    def __init__(self, template_file: str = "template.yaml", s3_bucket: str = "my-sar-artifacts-bucket"):
        """Initialize the monitor"""
        self.template_file = template_file
        self.s3_bucket = s3_bucket
        self.size_history_file = "template-size-history.csv"
        self.size_log_file = "template-size-log.json"
        
        # Size limits (in bytes)
        self.DIRECT_LIMIT = 51200      # 51KB
        self.S3_LIMIT = 460800         # 450KB
        self.WARNING_THRESHOLD = 0.9   # Warn at 90% of limit
        
        try:
            self.s3_client = boto3.client('s3')
            self.cloudformation = boto3.client('cloudformation')
        except NoCredentialsError:
            print("❌ AWS credentials not configured")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error initializing AWS clients: {e}")
            sys.exit(1)
    
    def log_info(self, message: str):
        """Log info message"""
        print(f"ℹ️  {message}")
    
    def log_success(self, message: str):
        """Log success message"""
        print(f"✅ {message}")
    
    def log_warning(self, message: str):
        """Log warning message"""
        print(f"⚠️  {message}")
    
    def log_error(self, message: str):
        """Log error message"""
        print(f"❌ {message}")
    
    def get_template_size(self) -> int:
        """Get template file size in bytes"""
        if not os.path.exists(self.template_file):
            raise FileNotFoundError(f"Template file not found: {self.template_file}")
        
        return os.path.getsize(self.template_file)
    
    def get_template_hash(self) -> str:
        """Get MD5 hash of template file"""
        with open(self.template_file, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def get_size_category(self, size_bytes: int) -> Tuple[str, str]:
        """Get size category and deployment method"""
        if size_bytes < self.DIRECT_LIMIT:
            return "SMALL", "direct"
        elif size_bytes < self.S3_LIMIT:
            return "LARGE", "s3"
        else:
            return "OVERSIZED", "unsupported"
    
    def check_size_warnings(self, size_bytes: int) -> List[str]:
        """Check for size warnings"""
        warnings = []
        
        # Check direct limit warning
        direct_warning_threshold = self.DIRECT_LIMIT * self.WARNING_THRESHOLD
        if size_bytes > direct_warning_threshold and size_bytes < self.DIRECT_LIMIT:
            warnings.append(f"Approaching direct template limit ({self.format_size(size_bytes)} / {self.format_size(self.DIRECT_LIMIT)})")
        
        # Check S3 limit warning
        s3_warning_threshold = self.S3_LIMIT * self.WARNING_THRESHOLD
        if size_bytes > s3_warning_threshold and size_bytes < self.S3_LIMIT:
            warnings.append(f"Approaching S3 template limit ({self.format_size(size_bytes)} / {self.format_size(self.S3_LIMIT)})")
        
        # Check if exceeded limits
        if size_bytes >= self.DIRECT_LIMIT and size_bytes < self.S3_LIMIT:
            warnings.append("Template exceeds direct limit - S3 deployment required")
        elif size_bytes >= self.S3_LIMIT:
            warnings.append("Template exceeds SAR size limits - optimization required")
        
        return warnings
    
    def log_size_history(self, size_bytes: int, file_hash: str):
        """Log size to CSV history file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        size_kb = size_bytes / 1024
        category, method = self.get_size_category(size_bytes)
        
        # Create CSV header if file doesn't exist
        if not os.path.exists(self.size_history_file):
            with open(self.size_history_file, 'w') as f:
                f.write("timestamp,size_bytes,size_kb,category,deployment_method,file_hash\n")
        
        # Append size data
        with open(self.size_history_file, 'a') as f:
            f.write(f"{timestamp},{size_bytes},{size_kb:.1f},{category},{method},{file_hash}\n")
    
    def log_size_json(self, size_bytes: int, file_hash: str):
        """Log size to JSON log file"""
        timestamp = datetime.now().isoformat()
        category, method = self.get_size_category(size_bytes)
        warnings = self.check_size_warnings(size_bytes)
        
        log_entry = {
            "timestamp": timestamp,
            "size_bytes": size_bytes,
            "size_formatted": self.format_size(size_bytes),
            "category": category,
            "deployment_method": method,
            "file_hash": file_hash,
            "warnings": warnings,
            "limits": {
                "direct_limit": self.DIRECT_LIMIT,
                "s3_limit": self.S3_LIMIT
            }
        }
        
        # Load existing log or create new
        log_data = []
        if os.path.exists(self.size_log_file):
            try:
                with open(self.size_log_file, 'r') as f:
                    log_data = json.load(f)
            except:
                log_data = []
        
        # Add new entry
        log_data.append(log_entry)
        
        # Keep only last 100 entries
        if len(log_data) > 100:
            log_data = log_data[-100:]
        
        # Save log
        with open(self.size_log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def ensure_s3_bucket_exists(self) -> bool:
        """Ensure S3 bucket exists for template uploads"""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            self.log_success(f"S3 bucket exists: {self.s3_bucket}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == '404':
                # Bucket doesn't exist, create it
                self.log_info(f"Creating S3 bucket: {self.s3_bucket}")
                try:
                    region = boto3.Session().region_name or 'us-east-1'
                    
                    if region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.s3_bucket)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.s3_bucket,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    
                    self.log_success(f"S3 bucket created: {self.s3_bucket}")
                    return True
                except ClientError as create_error:
                    self.log_error(f"Failed to create S3 bucket: {create_error}")
                    return False
            else:
                self.log_error(f"Error accessing S3 bucket: {e}")
                return False
    
    def upload_template_to_s3(self, s3_key: str = "template.yaml") -> Optional[str]:
        """Upload template to S3 and return URL"""
        if not self.ensure_s3_bucket_exists():
            return None
        
        try:
            # Upload template
            self.s3_client.upload_file(
                self.template_file,
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': 'text/yaml'}
            )
            
            # Generate URL
            template_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            self.log_success(f"Template uploaded to S3: {template_url}")
            return template_url
            
        except ClientError as e:
            self.log_error(f"Failed to upload template to S3: {e}")
            return None
    
    def validate_template_direct(self) -> bool:
        """Validate template using direct method"""
        try:
            with open(self.template_file, 'r') as f:
                template_body = f.read()
            
            self.cloudformation.validate_template(TemplateBody=template_body)
            self.log_success("Direct template validation successful")
            return True
        except ClientError as e:
            self.log_error(f"Direct template validation failed: {e}")
            return False
    
    def validate_template_s3(self, template_url: str) -> bool:
        """Validate template using S3 URL"""
        try:
            self.cloudformation.validate_template(TemplateURL=template_url)
            self.log_success("S3 template validation successful")
            return True
        except ClientError as e:
            self.log_error(f"S3 template validation failed: {e}")
            return False
    
    def generate_deployment_commands(self, size_bytes: int) -> Dict[str, List[str]]:
        """Generate deployment commands based on template size"""
        category, method = self.get_size_category(size_bytes)
        
        commands = {
            "validation": [],
            "deployment": [],
            "sar_publish": []
        }
        
        if method == "direct":
            # Direct deployment commands
            commands["validation"] = [
                "# Direct template validation (< 51KB)",
                "aws cloudformation validate-template --template-body file://template.yaml --no-paginate"
            ]
            
            commands["deployment"] = [
                "# Direct template deployment",
                "aws cloudformation create-stack \\",
                "  --stack-name tolling-vision-test \\",
                "  --template-body file://template.yaml \\",
                "  --parameters file://test-parameters.json \\",
                "  --capabilities CAPABILITY_IAM \\",
                "  --no-paginate"
            ]
            
            commands["sar_publish"] = [
                "# Direct SAR publishing",
                "aws serverlessrepo create-application \\",
                "  --name tolling-vision \\",
                "  --description 'Tolling Vision ANPR/MMR processing infrastructure' \\",
                "  --template-body file://template.yaml \\",
                "  --no-paginate"
            ]
            
        elif method == "s3":
            # S3-based deployment commands
            commands["validation"] = [
                "# S3-based template validation (51KB-450KB)",
                f"aws s3 cp template.yaml s3://{self.s3_bucket}/template.yaml",
                f"aws cloudformation validate-template --template-url https://{self.s3_bucket}.s3.amazonaws.com/template.yaml --no-paginate"
            ]
            
            commands["deployment"] = [
                "# S3-based template deployment",
                f"aws s3 cp template.yaml s3://{self.s3_bucket}/template.yaml",
                "aws cloudformation create-stack \\",
                "  --stack-name tolling-vision-test \\",
                f"  --template-url https://{self.s3_bucket}.s3.amazonaws.com/template.yaml \\",
                "  --parameters file://test-parameters.json \\",
                "  --capabilities CAPABILITY_IAM \\",
                "  --no-paginate"
            ]
            
            commands["sar_publish"] = [
                "# S3-based SAR publishing",
                f"aws s3 cp template.yaml s3://{self.s3_bucket}/template.yaml",
                "aws serverlessrepo create-application \\",
                "  --name tolling-vision \\",
                "  --description 'Tolling Vision ANPR/MMR processing infrastructure' \\",
                f"  --template-url https://{self.s3_bucket}.s3.amazonaws.com/template.yaml \\",
                "  --no-paginate"
            ]
        
        else:  # oversized
            commands["validation"] = [
                "# Template exceeds SAR limits - optimization required",
                "# Consider reducing embedded Lambda code or using external references"
            ]
            
            commands["deployment"] = [
                "# Template too large for SAR - use direct CloudFormation instead",
                "# Or optimize template size to fit within 450KB limit"
            ]
            
            commands["sar_publish"] = [
                "# Template exceeds SAR size limits",
                "# Optimization required before SAR publishing"
            ]
        
        return commands
    
    def monitor_template(self) -> Dict[str, Any]:
        """Monitor template size and generate report"""
        if not os.path.exists(self.template_file):
            raise FileNotFoundError(f"Template file not found: {self.template_file}")
        
        # Get template info
        size_bytes = self.get_template_size()
        file_hash = self.get_template_hash()
        category, method = self.get_size_category(size_bytes)
        warnings = self.check_size_warnings(size_bytes)
        
        # Log size data
        self.log_size_history(size_bytes, file_hash)
        self.log_size_json(size_bytes, file_hash)
        
        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "template_file": self.template_file,
            "size_bytes": size_bytes,
            "size_formatted": self.format_size(size_bytes),
            "category": category,
            "deployment_method": method,
            "file_hash": file_hash,
            "warnings": warnings,
            "limits": {
                "direct_limit": self.DIRECT_LIMIT,
                "direct_limit_formatted": self.format_size(self.DIRECT_LIMIT),
                "s3_limit": self.S3_LIMIT,
                "s3_limit_formatted": self.format_size(self.S3_LIMIT)
            },
            "deployment_commands": self.generate_deployment_commands(size_bytes)
        }
        
        return report
    
    def print_report(self, report: Dict[str, Any]):
        """Print monitoring report"""
        print(f"📊 Template Size Monitoring Report")
        print("=" * 60)
        print(f"Template: {report['template_file']}")
        print(f"Size: {report['size_formatted']} ({report['size_bytes']} bytes)")
        print(f"Category: {report['category']}")
        print(f"Deployment Method: {report['deployment_method']}")
        print(f"File Hash: {report['file_hash']}")
        
        # Print limits
        print(f"\n📏 Size Limits:")
        print(f"Direct Template: {report['limits']['direct_limit_formatted']}")
        print(f"S3-based Template: {report['limits']['s3_limit_formatted']}")
        
        # Print warnings
        if report['warnings']:
            print(f"\n⚠️  Warnings:")
            for warning in report['warnings']:
                print(f"  • {warning}")
        else:
            print(f"\n✅ No size warnings")
        
        # Print deployment commands
        print(f"\n🚀 Deployment Commands:")
        commands = report['deployment_commands']
        
        for section, cmd_list in commands.items():
            if cmd_list:
                print(f"\n{section.title()}:")
                for cmd in cmd_list:
                    print(f"  {cmd}")
    
    def run_continuous_monitoring(self, interval_seconds: int = 60):
        """Run continuous template monitoring"""
        self.log_info(f"Starting continuous monitoring (interval: {interval_seconds}s)")
        self.log_info("Press Ctrl+C to stop")
        
        try:
            while True:
                report = self.monitor_template()
                self.print_report(report)
                print(f"\n⏰ Next check in {interval_seconds} seconds...")
                print("-" * 80)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            self.log_info("Monitoring stopped by user")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 monitor-template-size.py <command> [options]")
        print("Commands:")
        print("  check                    - Check template size once")
        print("  monitor [interval]       - Continuous monitoring (default: 60s)")
        print("  upload                   - Upload template to S3")
        print("  validate                 - Validate template (auto-detect method)")
        print("  commands                 - Generate deployment commands")
        print("  history                  - Show size history")
        sys.exit(1)
    
    command = sys.argv[1]
    monitor = TemplateSizeMonitor()
    
    try:
        if command == "check":
            report = monitor.monitor_template()
            monitor.print_report(report)
            
        elif command == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            monitor.run_continuous_monitoring(interval)
            
        elif command == "upload":
            size_bytes = monitor.get_template_size()
            category, method = monitor.get_size_category(size_bytes)
            
            if method in ["s3", "oversized"]:
                template_url = monitor.upload_template_to_s3()
                if template_url:
                    print(f"Template URL: {template_url}")
            else:
                print("Template is small enough for direct deployment")
                
        elif command == "validate":
            size_bytes = monitor.get_template_size()
            category, method = monitor.get_size_category(size_bytes)
            
            if method == "direct":
                monitor.validate_template_direct()
            elif method == "s3":
                template_url = monitor.upload_template_to_s3()
                if template_url:
                    monitor.validate_template_s3(template_url)
            else:
                print("Template exceeds SAR size limits")
                
        elif command == "commands":
            report = monitor.monitor_template()
            commands = report['deployment_commands']
            
            for section, cmd_list in commands.items():
                if cmd_list:
                    print(f"\n{section.title()}:")
                    for cmd in cmd_list:
                        print(cmd)
                        
        elif command == "history":
            if os.path.exists(monitor.size_history_file):
                with open(monitor.size_history_file, 'r') as f:
                    print(f.read())
            else:
                print("No size history found")
                
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()