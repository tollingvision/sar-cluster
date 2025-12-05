# GitHub Repository Setup Guide

## Repository Information

### Repository Name
```
tolling-vision-sar
```

### Description (Short - for GitHub header)
```
AWS Serverless Application Repository template for Tolling Vision ANPR/MMR infrastructure with Lambda custom resources, auto-scaling, JWT authentication, and WAF protection
```

### Description (Detailed - for About section)
```
Complete AWS SAR template for deploying secure, scalable Tolling Vision ANPR (Automatic Number Plate Recognition) and MMR (Make Model Recognition) processing infrastructure. Features include:

• Lambda custom resources for SAR compatibility
• Auto-scaling EC2 instances with ARM64/x86-64 support
• Optional JWT authentication (Cognito-based)
• WAF protection with IP allowlisting
• Enhanced monitoring with CloudWatch dashboards
• Route53 DNS management
• Private VPC architecture with public ALB entry point

Ready to deploy via AWS Serverless Application Repository, SAM CLI, or CloudFormation.
```

### Website
```
https://tollingvision.com
```

### Topics (GitHub Tags)
```
aws
serverless
cloudformation
sar
anpr
mmr
computer-vision
license-plate-recognition
vehicle-recognition
tolling
infrastructure-as-code
lambda
auto-scaling
security
jwt-authentication
waf
cloudwatch
monitoring
aws-infrastructure
serverless-application-repository
```

### Features to Enable
- [x] Issues
- [x] Wiki (optional)
- [ ] Projects
- [ ] Discussions (optional)

### Branch Protection (for main branch)
- [x] Require pull request reviews before merging
- [x] Require status checks to pass before merging

### License
```
MIT License
```

### README Badges (add to top of README.md)
```markdown
[![AWS SAR](https://img.shields.io/badge/AWS-SAR%20Compatible-orange)](https://serverlessrepo.aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CloudFormation](https://img.shields.io/badge/CloudFormation-Template-blue)](template.yaml)
[![GitHub release](https://img.shields.io/github/v/release/tollingvision/tolling-vision-sar)](https://github.com/tollingvision/tolling-vision-sar/releases)
[![GitHub stars](https://img.shields.io/github/stars/tollingvision/tolling-vision-sar?style=social)](https://github.com/tollingvision/tolling-vision-sar/stargazers)
```

## Quick Setup Commands

### Initialize Git (if not already done)
```bash
cd /home/tothl74/work/amazon/tollingvision/sar
git init
git add .
git commit -m "Initial commit: Tolling Vision SAR infrastructure template"
```

### Add Remote and Push
```bash
git remote add origin https://github.com/tollingvision/tolling-vision-sar.git
git branch -M main
git push -u origin main
```

### Create First Release
```bash
# Tag the release
git tag -a v1.0.0 -m "Release v1.0.0: Production-ready SAR template"
git push origin v1.0.0
```

## Social Media / Marketing Copy

### Twitter/LinkedIn Post
```
🚀 Launching Tolling Vision SAR Infrastructure Template! 

Deploy secure, scalable ANPR/MMR processing on AWS with:
✅ Auto-scaling & ARM64 support
✅ JWT authentication & WAF protection  
✅ CloudWatch monitoring & dashboards
✅ SAR marketplace ready

#AWS #CloudFormation #ComputerVision #ANPR
https://github.com/tollingvision/tolling-vision-sar
```

### Dev.to / Medium Article Title
```
Building Production-Ready ANPR Infrastructure on AWS with Serverless Application Repository
```

## Files to Verify Before Push

- [x] .gitignore created
- [x] README.md updated
- [x] LICENSE file present
- [x] docs/ folder clean
- [x] No sensitive data (keys, passwords)
- [x] template.yaml validated
- [x] All scripts executable (chmod +x scripts/*.sh)

## Post-Publication Tasks

1. **Create GitHub Release**
   - Go to Releases → Draft a new release
   - Tag: v1.0.0
   - Title: "Tolling Vision SAR v1.0.0"
   - Description: Copy from CHANGELOG.md

2. **Update AWS SAR Marketplace**
   - Ensure SourceCodeUrl in template.yaml points to new repo
   - Run `scripts/publish-sar.sh` with updated metadata

3. **Documentation Links**
   - Update all docs to reference new GitHub URL
   - Add "Star on GitHub" badge to README

4. **Community**
   - Enable GitHub Discussions for user questions
   - Set up issue templates for bugs/features
   - Add CONTRIBUTING.md guidelines
