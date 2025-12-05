#!/bin/bash
# deploy-template.sh - Automated template deployment with size detection

set -e

# Configuration
TEMPLATE_FILE="template.yaml"
STACK_NAME="${1:-tolling-vision-prod}"
PARAMETERS_FILE="${2:-parameters/production.json}"
S3_BUCKET="${3:-my-sar-artifacts-bucket}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --no-paginate &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    # Check template file
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_error "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    # Check parameters file
    if [ ! -f "$PARAMETERS_FILE" ]; then
        log_error "Parameters file not found: $PARAMETERS_FILE"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Determine deployment method based on template size
determine_deployment_method() {
    local template_size=$(wc -c < "$TEMPLATE_FILE")
    
    log_info "Template size: $template_size bytes ($(echo "scale=2; $template_size/1024" | bc) KB)"
    
    if [ $template_size -lt 51200 ]; then
        echo "direct"
    elif [ $template_size -lt 460800 ]; then
        echo "s3"
    else
        log_error "Template size exceeds maximum limit (450KB). Optimization required."
        exit 1
    fi
}

# Validate template
validate_template() {
    local method=$1
    
    log_info "Validating template using $method method..."
    
    if [ "$method" = "direct" ]; then
        aws cloudformation validate-template \
            --template-body file://"$TEMPLATE_FILE" \
            --no-paginate
    else
        # Upload to S3 first
        log_info "Uploading template to S3..."
        aws s3 cp "$TEMPLATE_FILE" s3://"$S3_BUCKET"/"$TEMPLATE_FILE"
        
        # Validate from S3
        aws cloudformation validate-template \
            --template-url https://"$S3_BUCKET".s3.amazonaws.com/"$TEMPLATE_FILE" \
            --no-paginate
    fi
    
    log_info "Template validation passed"
}

# Deploy stack
deploy_stack() {
    local method=$1
    
    log_info "Deploying stack: $STACK_NAME using $method method..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --no-paginate &> /dev/null; then
        log_warn "Stack $STACK_NAME already exists. This will update the existing stack."
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled"
            exit 0
        fi
        OPERATION="update-stack"
    else
        OPERATION="create-stack"
    fi
    
    # Deploy based on method
    if [ "$method" = "direct" ]; then
        aws cloudformation $OPERATION \
            --stack-name "$STACK_NAME" \
            --template-body file://"$TEMPLATE_FILE" \
            --parameters file://"$PARAMETERS_FILE" \
            --capabilities CAPABILITY_IAM \
            --no-paginate
    else
        # Ensure template is uploaded to S3
        aws s3 cp "$TEMPLATE_FILE" s3://"$S3_BUCKET"/"$TEMPLATE_FILE"
        
        aws cloudformation $OPERATION \
            --stack-name "$STACK_NAME" \
            --template-url https://"$S3_BUCKET".s3.amazonaws.com/"$TEMPLATE_FILE" \
            --parameters file://"$PARAMETERS_FILE" \
            --capabilities CAPABILITY_IAM \
            --no-paginate
    fi
    
    log_info "Stack deployment initiated"
}

# Monitor deployment
monitor_deployment() {
    log_info "Monitoring deployment progress..."
    
    # Wait for stack operation to complete
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --no-paginate | grep -q "CREATE_IN_PROGRESS"; then
        aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
        FINAL_STATUS="CREATE_COMPLETE"
    elif aws cloudformation describe-stacks --stack-name "$STACK_NAME" --no-paginate | grep -q "UPDATE_IN_PROGRESS"; then
        aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME"
        FINAL_STATUS="UPDATE_COMPLETE"
    fi
    
    # Get final status
    ACTUAL_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text \
        --no-paginate)
    
    if [[ "$ACTUAL_STATUS" == *"COMPLETE" ]]; then
        log_info "Deployment completed successfully: $ACTUAL_STATUS"
        
        # Display stack outputs
        log_info "Stack outputs:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue,Description]' \
            --output table \
            --no-paginate
    else
        log_error "Deployment failed: $ACTUAL_STATUS"
        
        # Show recent stack events
        log_error "Recent stack events:"
        aws cloudformation describe-stack-events \
            --stack-name "$STACK_NAME" \
            --query 'StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
            --output table \
            --no-paginate
        
        exit 1
    fi
}

# Main execution
main() {
    log_info "Starting deployment of Tolling Vision infrastructure"
    log_info "Stack: $STACK_NAME"
    log_info "Template: $TEMPLATE_FILE"
    log_info "Parameters: $PARAMETERS_FILE"
    log_info "Region: $REGION"
    echo
    
    check_prerequisites
    
    local deployment_method=$(determine_deployment_method)
    log_info "Deployment method: $deployment_method"
    
    validate_template "$deployment_method"
    deploy_stack "$deployment_method"
    monitor_deployment
    
    log_info "Deployment process completed successfully!"
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [stack-name] [parameters-file] [s3-bucket]"
    echo
    echo "Examples:"
    echo "  $0                                          # Use defaults"
    echo "  $0 tolling-vision-dev                      # Custom stack name"
    echo "  $0 tolling-vision-dev parameters/dev.json  # Custom parameters"
    echo "  $0 tolling-vision-prod parameters/prod.json my-bucket  # All custom"
    echo
    echo "Defaults:"
    echo "  Stack name: tolling-vision-prod"
    echo "  Parameters: parameters/production.json"
    echo "  S3 bucket: my-sar-artifacts-bucket"
    exit 0
fi

# Run main function
main