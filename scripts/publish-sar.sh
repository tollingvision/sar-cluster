#!/bin/bash
set -e

# Configuration
BUCKET_NAME="${SAR_BUCKET_NAME:-my-sar-artifacts-bucket}"
TEMPLATE_FILE="${TEMPLATE_FILE:-template.yaml}"
APP_NAME="tolling-vision"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
DEFAULT_VERSION="1.0.0"

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

# Show usage if help requested
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Tolling Vision SAR Publishing Script"
    echo "===================================="
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Environment Variables:"
    echo "  SAR_BUCKET_NAME       S3 bucket for large templates (default: my-sar-artifacts-bucket)"
    echo "  TEMPLATE_FILE         Template file path (default: template.yaml)"
    echo "  AWS_DEFAULT_REGION    AWS region (default: us-east-1)"
    echo ""
    echo "Operations:"
    echo "  - Create new SAR application (if doesn't exist)"
    echo "  - Create new application version (recommended for template changes)"
    echo "  - Update application metadata only"
    echo ""
    echo "Template Size Limits:"
    echo "  - Direct: < 51KB"
    echo "  - S3-based: 51KB - 450KB"
    echo "  - Over 450KB: Not supported by SAR"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Interactive mode"
    echo "  SAR_BUCKET_NAME=my-bucket $0          # Use custom bucket"
    echo "  TEMPLATE_FILE=custom.yaml $0          # Use custom template"
    echo ""
    exit 0
fi

echo -e "${GREEN}Tolling Vision SAR Publishing${NC}"
echo "============================="
echo "Application: $APP_NAME"
echo "Template: $TEMPLATE_FILE"
echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check required tools
for tool in aws jq bc; do
    if ! command -v "$tool" &> /dev/null; then
        echo -e "${RED}Error: Required tool '$tool' not found${NC}"
        echo "Please install $tool and try again"
        exit 1
    fi
done

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Please configure AWS credentials and try again"
    exit 1
fi

# Check required files
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}Error: Template file '$TEMPLATE_FILE' not found${NC}"
    exit 1
fi

if [ ! -f "README.md" ]; then
    echo -e "${RED}Error: README.md not found${NC}"
    exit 1
fi

if [ ! -f "LICENSE" ]; then
    echo -e "${RED}Error: LICENSE file not found${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites check passed${NC}"

# Check template size
TEMPLATE_SIZE=$(wc -c < "$TEMPLATE_FILE")
TEMPLATE_SIZE_KB=$(echo "scale=1; $TEMPLATE_SIZE/1024" | bc 2>/dev/null || echo "$(($TEMPLATE_SIZE/1024))")
echo "Template size: $TEMPLATE_SIZE bytes ($TEMPLATE_SIZE_KB KB)"

# Determine deployment method
if [ $TEMPLATE_SIZE -le 51200 ]; then
    DEPLOYMENT_METHOD="direct"
    echo -e "${GREEN}Using direct SAR deployment (< 51KB)${NC}"
elif [ $TEMPLATE_SIZE -le 460800 ]; then
    DEPLOYMENT_METHOD="s3"
    echo -e "${YELLOW}Using S3-based SAR deployment (51KB-450KB)${NC}"
else
    echo -e "${RED}Error: Template exceeds 450KB SAR limit${NC}"
    echo "Consider template optimization or alternative distribution"
    exit 1
fi

# Validate template
echo -e "${YELLOW}Validating template...${NC}"
if [ "$DEPLOYMENT_METHOD" = "direct" ]; then
    if aws cloudformation validate-template \
        --template-body "file://$TEMPLATE_FILE" \
        --no-cli-pager > /dev/null 2>&1; then
        echo -e "${GREEN}Template validation successful${NC}"
    else
        echo -e "${RED}Template validation failed${NC}"
        aws cloudformation validate-template \
            --template-body "file://$TEMPLATE_FILE" \
            --no-cli-pager
        exit 1
    fi
else
    # S3-based validation
    echo -e "${YELLOW}Uploading template to S3 for validation...${NC}"
    
    # Check if bucket exists
    if ! aws s3 ls "s3://$BUCKET_NAME" > /dev/null 2>&1; then
        echo -e "${RED}Error: S3 bucket '$BUCKET_NAME' not accessible${NC}"
        echo "Create bucket with: aws s3 mb s3://$BUCKET_NAME --region $REGION"
        exit 1
    fi
    
    # Upload template and supporting files
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    S3_PREFIX="sar/$TIMESTAMP"
    
    aws s3 cp "$TEMPLATE_FILE" "s3://$BUCKET_NAME/$S3_PREFIX/template.yaml"
    aws s3 cp "README.md" "s3://$BUCKET_NAME/$S3_PREFIX/README.md"
    aws s3 cp "LICENSE" "s3://$BUCKET_NAME/$S3_PREFIX/LICENSE"
    
    TEMPLATE_URL="https://$BUCKET_NAME.s3.amazonaws.com/$S3_PREFIX/template.yaml"
    README_URL="https://$BUCKET_NAME.s3.amazonaws.com/$S3_PREFIX/README.md"
    LICENSE_URL="https://$BUCKET_NAME.s3.amazonaws.com/$S3_PREFIX/LICENSE"
    
    echo "Template URL: $TEMPLATE_URL"
    
    # Validate via S3
    if aws cloudformation validate-template \
        --template-url "$TEMPLATE_URL" \
        --no-cli-pager > /dev/null 2>&1; then
        echo -e "${GREEN}Template validation successful${NC}"
    else
        echo -e "${RED}Template validation failed${NC}"
        aws cloudformation validate-template \
            --template-url "$TEMPLATE_URL" \
            --no-cli-pager
        exit 1
    fi
fi

# Function to get next semantic version
get_next_version() {
    local app_id="$1"
    local highest_version="$DEFAULT_VERSION"
    
    # Get all versions and find the highest semantic version
    local versions=$(aws serverlessrepo list-application-versions \
        --application-id "$app_id" \
        --query 'Versions[].SemanticVersion' \
        --output text 2>/dev/null)
    
    if [ -n "$versions" ]; then
        # Sort versions using semantic version comparison
        highest_version=$(echo "$versions" | tr '\t' '\n' | sort -V | tail -n1)
    fi
    
    if [ "$highest_version" = "None" ] || [ -z "$highest_version" ]; then
        highest_version="$DEFAULT_VERSION"
    fi
    
    # Parse version and increment patch number
    IFS='.' read -r major minor patch <<< "$highest_version"
    patch=$((patch + 1))
    echo "$major.$minor.$patch"
}

# Check if SAR application already exists
echo -e "${YELLOW}Checking existing SAR application...${NC}"
APP_ID=""
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FULL_APP_ID="arn:aws:serverlessrepo:$REGION:$ACCOUNT_ID:applications/$APP_NAME"

if aws serverlessrepo get-application \
    --application-id "$FULL_APP_ID" > /dev/null 2>&1; then
    
    APP_ID="$FULL_APP_ID"
    echo -e "${YELLOW}Application '$APP_NAME' already exists${NC}"
    echo "Application ID: $APP_ID"
    
    # Get current default version and highest version
    DEFAULT_VERSION_SHOWN=$(aws serverlessrepo get-application \
        --application-id "$APP_ID" \
        --query 'Version.SemanticVersion' \
        --output text  2>/dev/null || echo "$DEFAULT_VERSION")
    
    # Get all versions to find the highest
    ALL_VERSIONS=$(aws serverlessrepo list-application-versions \
        --application-id "$APP_ID" \
        --query 'Versions[].SemanticVersion' \
        --output text  2>/dev/null)
    
    HIGHEST_VERSION=$(echo "$ALL_VERSIONS" | tr '\t' '\n' | sort -V | tail -n1)
    
    NEXT_VERSION=$(get_next_version "$APP_ID")
    echo "Default version (shown in marketplace): $DEFAULT_VERSION_SHOWN"
    echo "Highest version (by semantic versioning): $HIGHEST_VERSION"
    echo "Suggested next version: $NEXT_VERSION"
    
    echo ""
    echo "Choose operation:"
    echo "1) Create new version (recommended for template changes)"
    echo "2) Update application metadata only"
    echo "3) Cancel"
    read -p "Enter choice (1-3): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            OPERATION="create-version"
            # Try to extract version from template
            TEMPLATE_VERSION=$(grep -A 10 "AWS::ServerlessRepo::Application" "$TEMPLATE_FILE" | grep "SemanticVersion:" | sed 's/.*SemanticVersion: *\([0-9.]*\).*/\1/' | head -1)
            
            if [ -n "$TEMPLATE_VERSION" ] && [ "$TEMPLATE_VERSION" != "$NEXT_VERSION" ]; then
                echo "Template contains version: $TEMPLATE_VERSION"
                echo "Suggested next version: $NEXT_VERSION"
                read -p "Enter semantic version [$TEMPLATE_VERSION]: " USER_VERSION
                SEMANTIC_VERSION="${USER_VERSION:-$TEMPLATE_VERSION}"
            else
                read -p "Enter semantic version [$NEXT_VERSION]: " USER_VERSION
                SEMANTIC_VERSION="${USER_VERSION:-$NEXT_VERSION}"
            fi
            
            # Validate semantic version format
            if [[ ! $SEMANTIC_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                echo -e "${RED}Error: Invalid semantic version format. Use MAJOR.MINOR.PATCH (e.g., 1.0.1)${NC}"
                exit 1
            fi
            
            # Check if version already exists
            if aws serverlessrepo get-application \
                --application-id "$APP_ID" \
                --semantic-version "$SEMANTIC_VERSION" > /dev/null 2>&1; then
                echo -e "${RED}Error: Version $SEMANTIC_VERSION already exists${NC}"
                exit 1
            fi
            ;;
        2)
            OPERATION="update-metadata"
            SEMANTIC_VERSION="$CURRENT_VERSION"
            ;;
        *)
            echo "Publishing cancelled"
            exit 0
            ;;
    esac
else
    OPERATION="create"
    SEMANTIC_VERSION="$DEFAULT_VERSION"
fi

# Create or update SAR application
if [ "$OPERATION" = "create" ]; then
    echo -e "${YELLOW}Creating SAR application...${NC}"
    echo "Version: $SEMANTIC_VERSION"
    
    if [ "$DEPLOYMENT_METHOD" = "direct" ]; then
        RESULT=$(aws serverlessrepo create-application \
            --name "$APP_NAME" \
            --description "Complete Tolling Vision ANPR/MMR infrastructure. Deploys secure, scalable computer vision processing with optional WAF/JWT protection." \
            --author "Smart Cloud Solutions" \
            --spdx-license-id "MIT" \
            --license-url "LICENSE" \
            --readme-url "README.md" \
            --labels "tolling" "image-review" "anpr" "mmr" "computer-vision" "infrastructure" "security" \
            --home-page-url "https://tollingvision.com" \
            --source-code-url "https://github.com/tollingvision/sar-cluster" \
            --semantic-version "$SEMANTIC_VERSION" \
            --template-body "file://$TEMPLATE_FILE")
    else
        RESULT=$(aws serverlessrepo create-application \
            --name "$APP_NAME" \
            --description "Complete Tolling Vision ANPR/MMR infrastructure. Deploys secure, scalable computer vision processing with optional WAF/JWT protection." \
            --author "Smart Cloud Solutions" \
            --spdx-license-id "MIT" \
            --license-url "$LICENSE_URL" \
            --readme-url "$README_URL" \
            --labels "tolling" "image-review" "anpr" "mmr" "computer-vision" "infrastructure" "security" \
            --home-page-url "https://tollingvision.com" \
            --source-code-url "https://github.com/tollingvision/sar-cluster" \
            --semantic-version "$SEMANTIC_VERSION" \
            --template-url "$TEMPLATE_URL")
    fi
    
    APP_ID=$(echo "$RESULT" | jq -r '.ApplicationId')
    echo -e "${GREEN}SAR application created successfully${NC}"
    
elif [ "$OPERATION" = "create-version" ]; then
    echo -e "${YELLOW}Creating new application version...${NC}"
    echo "Version: $SEMANTIC_VERSION"
    
    # Update template version to match CLI version
    if grep -q "SemanticVersion:" "$TEMPLATE_FILE"; then
        echo -e "${YELLOW}Updating template version to match...${NC}"
        sed -i.bak "s/SemanticVersion: [0-9.]*/SemanticVersion: $SEMANTIC_VERSION/" "$TEMPLATE_FILE"
        echo "Template version updated to: $SEMANTIC_VERSION"
    fi
    
    # Additional validation for version creation
    echo -e "${YELLOW}Performing additional template validation...${NC}"
    
    if [ "$DEPLOYMENT_METHOD" = "direct" ]; then
        # Run our custom validation tests if they exist
        if [ -f "tests/test-outputs-validation.py" ]; then
            echo "Running output validation tests..."
            python3 tests/test-outputs-validation.py || echo -e "${YELLOW}Warning: Output validation tests failed${NC}"
        fi
        
        RESULT=$(aws serverlessrepo create-application-version \
            --application-id "$APP_ID" \
            --semantic-version "$SEMANTIC_VERSION" \
            --source-code-url "https://github.com/smartcloudsol/tolling-vision-sar" \
            --template-body "file://$TEMPLATE_FILE")
    else
        # Run our custom validation tests if they exist
        if [ -f "tests/test-outputs-validation.py" ]; then
            echo "Running output validation tests..."
            python3 tests/test-outputs-validation.py || echo -e "${YELLOW}Warning: Output validation tests failed${NC}"
        fi
        
        RESULT=$(aws serverlessrepo create-application-version \
            --application-id "$APP_ID" \
            --semantic-version "$SEMANTIC_VERSION" \
            --source-code-url "https://github.com/smartcloudsol/tolling-vision-sar" \
            --template-url "$TEMPLATE_URL")
    fi
    
    # Extract and display version information
    VERSION_INFO=$(echo "$RESULT" | jq -r '.SemanticVersion')
    TEMPLATE_URL_RESULT=$(echo "$RESULT" | jq -r '.TemplateUrl // "N/A"')
    
    echo -e "${GREEN}SAR application version created successfully${NC}"
    echo "Created version: $VERSION_INFO"
    if [ "$TEMPLATE_URL_RESULT" != "N/A" ]; then
        echo "Template URL: $TEMPLATE_URL_RESULT"
    fi
    
else
    echo -e "${YELLOW}Updating SAR application metadata...${NC}"
    echo "Note: This only updates metadata, not the template"
    
    if [ "$DEPLOYMENT_METHOD" = "direct" ]; then
        aws serverlessrepo update-application \
            --application-id "$APP_ID" \
            --description "Complete Tolling Vision ANPR/MMR infrastructure. Deploys secure, scalable computer vision processing with optional WAF/JWT protection." \
            --author "Smart Cloud Solutions" \
            --readme-url "README.md" \
            --labels "tolling" "image-review" "anpr" "mmr" "computer-vision" "infrastructure" "security" \
            --home-page-url "https://github.com/smartcloudsol/tolling-vision-sar"
    else
        aws serverlessrepo update-application \
            --application-id "$APP_ID" \
            --description "Complete Tolling Vision ANPR/MMR infrastructure. Deploys secure, scalable computer vision processing with optional WAF/JWT protection." \
            --author "Smart Cloud Solutions" \
            --readme-url "$README_URL" \
            --labels "tolling" "image-review" "anpr" "mmr" "computer-vision" "infrastructure" "security" \
            --home-page-url "https://github.com/smartcloudsol/tolling-vision-sar"
    fi
    
    echo -e "${GREEN}SAR application metadata updated successfully${NC}"
fi

echo ""
echo -e "${GREEN}SAR Publishing Complete!${NC}"
echo "========================"
echo "Application ID: $APP_ID"
echo "Application Name: $APP_NAME"
echo "Operation: $OPERATION"
echo "Version: $SEMANTIC_VERSION"
echo "Deployment Method: $DEPLOYMENT_METHOD"

if [ "$DEPLOYMENT_METHOD" = "s3" ]; then
    echo "Template URL: $TEMPLATE_URL"
    echo "README URL: $README_URL"
    echo "License URL: $LICENSE_URL"
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
if [ "$OPERATION" = "create-version" ]; then
    echo "1. Test deployment of new version from SAR marketplace"
    echo "2. Verify all template changes work correctly"
    echo "3. Update application description if needed"
    echo "4. Monitor version adoption and feedback"
elif [ "$OPERATION" = "create" ]; then
    echo "1. Test deployment from SAR marketplace"
    echo "2. Verify all parameters work correctly"
    echo "3. Update application visibility settings if needed"
    echo "4. Monitor application usage and feedback"
else
    echo "1. Verify metadata changes in SAR console"
    echo "2. Consider creating new version for template changes"
    echo "3. Update application visibility settings if needed"
    echo "4. Monitor application usage and feedback"
fi

echo ""
echo -e "${YELLOW}SAR Console URLs:${NC}"
echo "Application: https://console.aws.amazon.com/serverlessrepo/home?region=$REGION#/applications/$APP_ID"
echo "Marketplace: https://serverlessrepo.aws.amazon.com/applications"

if [ "$OPERATION" = "create-version" ]; then
    echo ""
    echo -e "${BLUE}Version Management:${NC}"
    echo "- Current version: $SEMANTIC_VERSION"
    echo "- To create another version, run this script again"
    echo "- Version format: MAJOR.MINOR.PATCH (semantic versioning)"
fi

echo ""
echo -e "${GREEN}Publishing completed successfully!${NC}"