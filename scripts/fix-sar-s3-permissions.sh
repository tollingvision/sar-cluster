#!/bin/bash

# Fix SAR S3 Permissions Script
# This script helps resolve S3 bucket policy issues for AWS Serverless Application Repository

set -e

# Configuration
BUCKET_NAME="${1:-my-sar-artifacts-bucket}"
REGION="${2:-us-east-1}"
TEMPLATE_FILE="template.yaml"

echo "🔧 Fixing SAR S3 Permissions for bucket: $BUCKET_NAME"
echo "📍 Region: $REGION"
echo ""

# Check if bucket exists
echo "1️⃣ Checking if S3 bucket exists..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo "   ✅ Bucket $BUCKET_NAME exists"
else
    echo "   ❌ Bucket $BUCKET_NAME does not exist or is not accessible"
    echo "   Creating bucket..."
    
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$BUCKET_NAME"
    else
        aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    echo "   ✅ Bucket created successfully"
fi

# Enable versioning (recommended for SAR)
echo ""
echo "2️⃣ Enabling S3 bucket versioning..."
aws s3api put-bucket-versioning --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled
echo "   ✅ Versioning enabled"

# Apply bucket policy for SAR access
echo ""
echo "3️⃣ Applying S3 bucket policy for SAR access..."

# Create temporary policy file with correct bucket name
cat > /tmp/sar-bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowServerlessRepoReadAccess",
      "Effect": "Allow",
      "Principal": {
        "Service": "serverlessrepo.amazonaws.com"
      },
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    },
    {
      "Sid": "AllowServerlessRepoListBucket",
      "Effect": "Allow",
      "Principal": {
        "Service": "serverlessrepo.amazonaws.com"
      },
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::$BUCKET_NAME"
    }
  ]
}
EOF

aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy file:///tmp/sar-bucket-policy.json
echo "   ✅ Bucket policy applied successfully"

# Upload template to S3
echo ""
echo "4️⃣ Uploading template to S3..."
if [ -f "$TEMPLATE_FILE" ]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    S3_KEY="sar/$TIMESTAMP/template.yaml"
    
    aws s3 cp "$TEMPLATE_FILE" "s3://$BUCKET_NAME/$S3_KEY"
    
    TEMPLATE_URL="https://$BUCKET_NAME.s3.amazonaws.com/$S3_KEY"
    echo "   ✅ Template uploaded successfully"
    echo "   📄 Template URL: $TEMPLATE_URL"
    
    # Test template access
    echo ""
    echo "5️⃣ Testing template accessibility..."
    if aws cloudformation validate-template --template-url "$TEMPLATE_URL" --no-paginate > /dev/null 2>&1; then
        echo "   ✅ Template is accessible and valid"
    else
        echo "   ❌ Template validation failed"
        echo "   Please check the template syntax and S3 permissions"
        exit 1
    fi
    
    # Provide SAR creation command
    echo ""
    echo "🚀 Ready for SAR deployment!"
    echo ""
    echo "Use this command to create your SAR application:"
    echo ""
    echo "aws serverlessrepo create-application \\"
    echo "  --name tolling-vision \\"
    echo "  --description 'Tolling Vision ANPR/MMR processing infrastructure with Lambda custom resources' \\"
    echo "  --template-url '$TEMPLATE_URL' \\"
    echo "  --capabilities CAPABILITY_IAM \\"
    echo "  --no-paginate"
    echo ""
    echo "Or to update an existing application:"
    echo ""
    echo "aws serverlessrepo update-application \\"
    echo "  --application-id <your-app-id> \\"
    echo "  --template-url '$TEMPLATE_URL' \\"
    echo "  --no-paginate"
    
else
    echo "   ❌ Template file $TEMPLATE_FILE not found"
    echo "   Please ensure the template file exists in the current directory"
    exit 1
fi

# Clean up temporary files
rm -f /tmp/sar-bucket-policy.json

echo ""
echo "✅ SAR S3 permissions setup completed successfully!"
echo ""
echo "📋 Summary:"
echo "   • Bucket: $BUCKET_NAME"
echo "   • Region: $REGION"
echo "   • Versioning: Enabled"
echo "   • SAR Policy: Applied"
echo "   • Template: Uploaded and validated"
echo ""
echo "🎯 Next steps:"
echo "   1. Run the SAR creation command shown above"
echo "   2. Monitor the application creation in the AWS console"
echo "   3. Test deployment from the SAR marketplace"