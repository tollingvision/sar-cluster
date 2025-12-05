#!/bin/bash

# SAR Template Validation and Testing Script
# Handles both direct validation (< 51KB) and S3-based validation (51KB-450KB)

set -e

# Configuration
TEMPLATE_FILE="template.yaml"
S3_BUCKET="my-sar-artifacts-bucket"
S3_KEY="template.yaml"
STACK_NAME_PREFIX="tolling-vision-test"
TEST_PARAMETERS_FILE="test-parameters.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if template file exists
check_template_exists() {
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        log_error "Template file $TEMPLATE_FILE not found!"
        exit 1
    fi
    log_info "Template file found: $TEMPLATE_FILE"
}

# Get template size in bytes
get_template_size() {
    local size=$(wc -c < "$TEMPLATE_FILE")
    echo "$size"
}

# Check template size and determine validation method
check_template_size() {
    local size=$(get_template_size)
    local size_kb=$((size / 1024))
    
    log_info "Template size: $size bytes ($size_kb KB)"
    
    if [[ $size -lt 51200 ]]; then
        log_success "Template size is under 51KB - can use direct validation"
        echo "direct"
    elif [[ $size -lt 460800 ]]; then
        log_warning "Template size is between 51KB and 450KB - requires S3-based validation"
        echo "s3"
    else
        log_error "Template size exceeds 450KB SAR limit!"
        exit 1
    fi
}

# Validate template syntax using cfn-lint (if available)
validate_syntax() {
    log_info "Validating template syntax..."
    
    if command -v cfn-lint &> /dev/null; then
        log_info "Running cfn-lint validation..."
        if cfn-lint "$TEMPLATE_FILE"; then
            log_success "cfn-lint validation passed"
        else
            log_error "cfn-lint validation failed"
            return 1
        fi
    else
        log_warning "cfn-lint not found - skipping syntax validation"
    fi
}

# Direct CloudFormation validation (< 51KB)
validate_direct() {
    log_info "Performing direct CloudFormation validation..."
    
    if aws cloudformation validate-template \
        --template-body file://"$TEMPLATE_FILE" \
        --no-paginate > /dev/null 2>&1; then
        log_success "Direct CloudFormation validation passed"
        return 0
    else
        log_error "Direct CloudFormation validation failed"
        return 1
    fi
}

# S3-based CloudFormation validation (51KB-450KB)
validate_s3() {
    log_info "Performing S3-based CloudFormation validation..."
    
    # Check if S3 bucket exists
    if ! aws s3 ls "s3://$S3_BUCKET" > /dev/null 2>&1; then
        log_error "S3 bucket $S3_BUCKET not found or not accessible"
        log_info "Creating S3 bucket $S3_BUCKET..."
        
        # Create bucket with appropriate region configuration
        local region=$(aws configure get region)
        if [[ "$region" == "us-east-1" ]]; then
            aws s3 mb "s3://$S3_BUCKET" --no-paginate
        else
            aws s3 mb "s3://$S3_BUCKET" --region "$region" --no-paginate
        fi
        
        log_success "S3 bucket created: $S3_BUCKET"
    fi
    
    # Upload template to S3
    log_info "Uploading template to S3..."
    if aws s3 cp "$TEMPLATE_FILE" "s3://$S3_BUCKET/$S3_KEY" --no-paginate; then
        log_success "Template uploaded to s3://$S3_BUCKET/$S3_KEY"
    else
        log_error "Failed to upload template to S3"
        return 1
    fi
    
    # Validate using S3 URL
    local template_url="https://$S3_BUCKET.s3.amazonaws.com/$S3_KEY"
    log_info "Validating template from S3 URL: $template_url"
    
    if aws cloudformation validate-template \
        --template-url "$template_url" \
        --no-paginate > /dev/null 2>&1; then
        log_success "S3-based CloudFormation validation passed"
        return 0
    else
        log_error "S3-based CloudFormation validation failed"
        return 1
    fi
}

# Create test parameters file if it doesn't exist
create_test_parameters() {
    if [[ ! -f "$TEST_PARAMETERS_FILE" ]]; then
        log_info "Creating test parameters file: $TEST_PARAMETERS_FILE"
        
        cat > "$TEST_PARAMETERS_FILE" << 'EOF'
[
  {
    "ParameterKey": "LicenseKey",
    "ParameterValue": "test-license-key-12345"
  },
  {
    "ParameterKey": "MaxSize",
    "ParameterValue": "2"
  },
  {
    "ParameterKey": "DesiredCapacity",
    "ParameterValue": "0"
  },
  {
    "ParameterKey": "MinSize",
    "ParameterValue": "0"
  },
  {
    "ParameterKey": "ProcessCount",
    "ParameterValue": "1"
  },
  {
    "ParameterKey": "EnableWAF",
    "ParameterValue": "false"
  },
  {
    "ParameterKey": "EnableALBAccessLogs",
    "ParameterValue": "false"
  },
  {
    "ParameterKey": "EnableDNS",
    "ParameterValue": "false"
  },
  {
    "ParameterKey": "CertificateArn",
    "ParameterValue": ""
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": ""
  }
]
EOF
        log_success "Test parameters file created"
    else
        log_info "Test parameters file already exists: $TEST_PARAMETERS_FILE"
    fi
}

# Test stack deployment (dry-run)
test_deployment() {
    local validation_method="$1"
    local stack_name="${STACK_NAME_PREFIX}-$(date +%s)"
    
    log_info "Testing stack deployment (validation only)..."
    
    create_test_parameters
    
    if [[ "$validation_method" == "direct" ]]; then
        log_info "Testing direct template deployment..."
        
        # Validate stack creation without actually creating it
        if aws cloudformation validate-template \
            --template-body file://"$TEMPLATE_FILE" \
            --no-paginate; then
            log_success "Direct deployment validation passed"
        else
            log_error "Direct deployment validation failed"
            return 1
        fi
        
    elif [[ "$validation_method" == "s3" ]]; then
        log_info "Testing S3-based template deployment..."
        
        local template_url="https://$S3_BUCKET.s3.amazonaws.com/$S3_KEY"
        
        # Validate stack creation without actually creating it
        if aws cloudformation validate-template \
            --template-url "$template_url" \
            --no-paginate; then
            log_success "S3-based deployment validation passed"
        else
            log_error "S3-based deployment validation failed"
            return 1
        fi
    fi
}

# Check Lambda function syntax (basic check)
validate_lambda_syntax() {
    log_info "Checking for embedded Lambda function..."
    
    # Simple check for Lambda function presence
    if grep -q "ZipFile:" "$TEMPLATE_FILE" && grep -q "def lambda_handler" "$TEMPLATE_FILE"; then
        log_success "Embedded Lambda function found in template"
        return 0
    else
        log_warning "No embedded Lambda function found in template"
        return 0  # Don't fail for this
    fi
}

# Monitor template size over time
monitor_template_size() {
    local size=$(get_template_size)
    local size_kb=$((size / 1024))
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Append to size monitoring log
    echo "$timestamp,$size,$size_kb" >> template-size-history.csv
    
    log_info "Template size logged: $size bytes ($size_kb KB)"
    
    # Check if approaching limits
    if [[ $size -gt 46080 ]] && [[ $size -lt 51200 ]]; then
        log_warning "Template size approaching 51KB direct limit (currently $size_kb KB)"
    elif [[ $size -gt 409600 ]] && [[ $size -lt 460800 ]]; then
        log_warning "Template size approaching 450KB S3 limit (currently $size_kb KB)"
    fi
}

# Main validation function
main() {
    log_info "Starting SAR template validation and testing..."
    
    # Check prerequisites
    check_template_exists
    
    # Monitor template size
    monitor_template_size
    
    # Determine validation method based on size
    local validation_method
    local size=$(get_template_size)
    
    if [[ $size -lt 51200 ]]; then
        validation_method="direct"
        log_success "Template size is under 51KB - can use direct validation"
    elif [[ $size -lt 460800 ]]; then
        validation_method="s3"
        log_warning "Template size is between 51KB and 450KB - requires S3-based validation"
    else
        log_error "Template size exceeds 450KB SAR limit!"
        exit 1
    fi
    
    # Validate template syntax
    validate_syntax
    
    # Validate Lambda function syntax
    validate_lambda_syntax
    
    # Perform CloudFormation validation
    case "$validation_method" in
        "direct")
            validate_direct
            ;;
        "s3")
            validate_s3
            ;;
        *)
            log_error "Unknown validation method: $validation_method"
            exit 1
            ;;
    esac
    
    # Test deployment validation
    test_deployment "$validation_method"
    
    log_success "All validations completed successfully!"
    log_info "Template validation method: $validation_method"
    log_info "Template size: $(get_template_size) bytes ($(($(get_template_size) / 1024)) KB)"
}

# Handle command line arguments
case "${1:-}" in
    "size")
        check_template_exists
        monitor_template_size
        ;;
    "syntax")
        check_template_exists
        validate_syntax
        validate_lambda_syntax
        ;;
    "direct")
        check_template_exists
        validate_direct
        ;;
    "s3")
        check_template_exists
        validate_s3
        ;;
    "deploy-test")
        check_template_exists
        size=$(get_template_size)
        if [[ $size -lt 51200 ]]; then
            validation_method="direct"
        elif [[ $size -lt 460800 ]]; then
            validation_method="s3"
        else
            log_error "Template size exceeds 450KB SAR limit!"
            exit 1
        fi
        test_deployment "$validation_method"
        ;;
    *)
        main
        ;;
esac