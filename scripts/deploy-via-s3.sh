#!/bin/bash
set -e

# Configuration
BUCKET_NAME="${SAR_BUCKET_NAME:-my-sar-artifacts-bucket}"
TEMPLATE_FILE="${TEMPLATE_FILE:-template.yaml}"
PARAMETERS_FILE="${PARAMETERS_FILE:-parameters.json}"
STACK_NAME="${STACK_NAME:-tolling-vision-prod}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root for file operations
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Tolling Vision S3-Based Deployment${NC}"
echo "=================================="
echo "Bucket: $BUCKET_NAME"
echo "Template: $TEMPLATE_FILE"
echo "Parameters: $PARAMETERS_FILE"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}Error: Template file '$TEMPLATE_FILE' not found${NC}"
    exit 1
fi

if [ ! -f "$PARAMETERS_FILE" ]; then
    echo -e "${RED}Error: Parameters file '$PARAMETERS_FILE' not found${NC}"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found${NC}"
    exit 1
fi

# Check template size
TEMPLATE_SIZE=$(wc -c < "$TEMPLATE_FILE")
TEMPLATE_SIZE_KB=$(echo "scale=1; $TEMPLATE_SIZE/1024" | bc 2>/dev/null || echo "$(($TEMPLATE_SIZE/1024))")
echo "Template size: $TEMPLATE_SIZE bytes ($TEMPLATE_SIZE_KB KB)"

if [ $TEMPLATE_SIZE -gt 460800 ]; then
    echo -e "${RED}Error: Template exceeds 450KB S3 limit${NC}"
    exit 1
elif [ $TEMPLATE_SIZE -le 51200 ]; then
    echo -e "${YELLOW}Info: Template is small enough for direct deployment${NC}"
    echo -e "${BLUE}Consider using direct deployment for faster processing${NC}"
fi

# Check if bucket exists
echo -e "${YELLOW}Checking S3 bucket access...${NC}"
if ! aws s3 ls "s3://$BUCKET_NAME" > /dev/null 2>&1; then
    echo -e "${RED}Error: S3 bucket '$BUCKET_NAME' not accessible${NC}"
    echo "Create bucket with: aws s3 mb s3://$BUCKET_NAME --region $REGION"
    exit 1
fi

# Upload template to S3
echo -e "${YELLOW}Uploading template to S3...${NC}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
S3_KEY="tolling-vision/$TIMESTAMP/template.yaml"
S3_URL="https://$BUCKET_NAME.s3.amazonaws.com/$S3_KEY"

if aws s3 cp "$TEMPLATE_FILE" "s3://$BUCKET_NAME/$S3_KEY"; then
    echo -e "${GREEN}Template uploaded successfully${NC}"
    echo "S3 URL: $S3_URL"
else
    echo -e "${RED}Failed to upload template to S3${NC}"
    exit 1
fi

# Upload parameters file for reference
PARAMS_S3_KEY="tolling-vision/$TIMESTAMP/parameters.json"
aws s3 cp "$PARAMETERS_FILE" "s3://$BUCKET_NAME/$PARAMS_S3_KEY" || echo -e "${YELLOW}Warning: Could not upload parameters file${NC}"

# Validate template
echo -e "${YELLOW}Validating template via S3...${NC}"
if aws cloudformation validate-template \
    --template-url "$S3_URL" \
    --no-paginate > /dev/null 2>&1; then
    echo -e "${GREEN}Template validation successful${NC}"
else
    echo -e "${RED}Template validation failed${NC}"
    echo "Checking template syntax..."
    aws cloudformation validate-template \
        --template-url "$S3_URL" \
        --no-paginate
    exit 1
fi

# Check if stack already exists
echo -e "${YELLOW}Checking existing stack...${NC}"
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --no-paginate > /dev/null 2>&1; then
    echo -e "${YELLOW}Stack '$STACK_NAME' already exists${NC}"
    read -p "Do you want to update the existing stack? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        OPERATION="update"
    else
        echo "Deployment cancelled"
        exit 0
    fi
else
    OPERATION="create"
fi

# Deploy or update stack
if [ "$OPERATION" = "create" ]; then
    echo -e "${YELLOW}Creating CloudFormation stack...${NC}"
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$S3_URL" \
        --parameters "file://$PARAMETERS_FILE" \
        --capabilities CAPABILITY_IAM \
        --no-paginate
    
    WAIT_COMMAND="stack-create-complete"
    SUCCESS_MESSAGE="Stack created successfully"
else
    echo -e "${YELLOW}Updating CloudFormation stack...${NC}"
    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$S3_URL" \
        --parameters "file://$PARAMETERS_FILE" \
        --capabilities CAPABILITY_IAM \
        --no-paginate
    
    WAIT_COMMAND="stack-update-complete"
    SUCCESS_MESSAGE="Stack updated successfully"
fi

echo -e "${GREEN}Stack $OPERATION initiated${NC}"
echo "Stack name: $STACK_NAME"
echo "Template URL: $S3_URL"
echo ""

# Monitor deployment
echo -e "${YELLOW}Monitoring deployment progress...${NC}"
echo "This may take 10-15 minutes for initial deployment..."
echo ""

# Show real-time events
aws cloudformation describe-stack-events \
    --stack-name "$STACK_NAME" \
    --no-paginate \
    --query 'StackEvents[0:5].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
    --output table

echo ""
echo -e "${BLUE}Waiting for stack $OPERATION to complete...${NC}"

if aws cloudformation wait "$WAIT_COMMAND" \
    --stack-name "$STACK_NAME" \
    --region "$REGION"; then
    
    echo -e "${GREEN}$SUCCESS_MESSAGE${NC}"
    echo ""
    
    # Display outputs
    echo -e "${YELLOW}Stack outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiCustomDomainEndpoint` || OutputKey==`DeploymentSummary` || OutputKey==`QuickStartInstructions`]' \
        --no-paginate \
        --output table
    
    echo ""
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Test API endpoints"
    echo "2. Configure authentication (if enabled)"
    echo "3. Set up monitoring and alerting"
    echo "4. Review CloudWatch dashboard"
    
else
    echo -e "${RED}Stack $OPERATION failed${NC}"
    echo ""
    echo -e "${YELLOW}Recent stack events:${NC}"
    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --no-paginate \
        --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId,ResourceStatusReason]' \
        --output table
    
    echo ""
    echo "Check CloudFormation console for detailed error information:"
    echo "https://console.aws.amazon.com/cloudformation/home?region=$REGION#/stacks/stackinfo?stackId=$STACK_NAME"
    exit 1
fi