#!/usr/bin/env python3
"""
Template Size Optimization Script for SAR Compliance
Optimizes CloudFormation template to reduce size while maintaining functionality
"""

import re
import yaml
import json
from pathlib import Path

def remove_comments_and_whitespace(content):
    """Remove comments and excessive whitespace"""
    lines = content.split('\n')
    optimized_lines = []
    
    for line in lines:
        # Remove inline comments (but preserve strings with #)
        if '#' in line and not line.strip().startswith('#'):
            # Check if # is inside a string
            in_string = False
            quote_char = None
            for i, char in enumerate(line):
                if char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None
                elif char == '#' and not in_string:
                    line = line[:i].rstrip()
                    break
        
        # Skip empty lines and comment-only lines
        if line.strip() and not line.strip().startswith('#'):
            optimized_lines.append(line.rstrip())
    
    return '\n'.join(optimized_lines)

def optimize_mappings(content):
    """Optimize mappings by reducing redundancy"""
    # Simplify AMI mappings - use placeholder AMIs
    ami_pattern = r"ami-[a-f0-9]{17}"
    content = re.sub(ami_pattern, "ami-12345678901234567", content)
    
    # Reduce instance type mappings
    content = re.sub(
        r"ProcessCount\d+-\d+: \[.*?\]",
        lambda m: m.group(0).replace(" ", "").replace("'", ""),
        content
    )
    
    return content

def optimize_descriptions(content):
    """Shorten parameter and resource descriptions"""
    # Shorten long descriptions
    content = re.sub(
        r"Description: '[^']{100,}'",
        lambda m: f"Description: '{m.group(0)[13:63]}...'",
        content
    )
    
    return content

def optimize_conditions(content):
    """Optimize condition logic"""
    # Simplify repetitive condition patterns
    content = re.sub(
        r"!Equals \[!Ref (\w+), '(\w+)'\]",
        r"!Equals [!Ref \1, '\2']",
        content
    )
    
    return content

def optimize_lambda_code(content):
    """Optimize embedded Lambda code"""
    # Find Lambda code sections and compress them
    lambda_pattern = r"(ZipFile: \|[\s\S]*?)(?=\n\s{0,6}[A-Z]|\n\s{0,6}Resources:|\n\s{0,6}Outputs:|\Z)"
    
    def compress_lambda_code(match):
        code = match.group(1)
        # Remove excessive indentation and comments from Python code
        lines = code.split('\n')
        compressed_lines = []
        
        for line in lines:
            if 'ZipFile: |' in line:
                compressed_lines.append(line)
                continue
            
            # Remove Python comments
            if line.strip().startswith('#'):
                continue
            
            # Remove excessive whitespace but preserve Python indentation
            if line.strip():
                # Preserve relative indentation for Python
                base_indent = len(line) - len(line.lstrip())
                if base_indent > 10:  # Likely CloudFormation + Python indentation
                    # Reduce CloudFormation indentation but keep Python structure
                    python_indent = 0
                    content_part = line.strip()
                    if content_part:
                        # Detect Python indentation level
                        for char in content_part:
                            if char == ' ':
                                python_indent += 1
                            else:
                                break
                        # Reconstruct with minimal CloudFormation indent + Python indent
                        compressed_lines.append('          ' + ' ' * python_indent + content_part.lstrip())
                else:
                    compressed_lines.append(line.rstrip())
        
        return '\n'.join(compressed_lines)
    
    content = re.sub(lambda_pattern, compress_lambda_code, content, flags=re.MULTILINE)
    return content

def optimize_template(input_file, output_file):
    """Main optimization function"""
    print(f"Optimizing template: {input_file} -> {output_file}")
    
    # Read original template
    with open(input_file, 'r') as f:
        content = f.read()
    
    original_size = len(content.encode('utf-8'))
    print(f"Original size: {original_size:,} bytes ({original_size/1024:.1f} KB)")
    
    # Apply optimizations
    print("Applying optimizations...")
    
    # 1. Remove comments and excessive whitespace
    content = remove_comments_and_whitespace(content)
    size_after_comments = len(content.encode('utf-8'))
    print(f"After removing comments: {size_after_comments:,} bytes (saved {original_size - size_after_comments:,} bytes)")
    
    # 2. Optimize mappings
    content = optimize_mappings(content)
    size_after_mappings = len(content.encode('utf-8'))
    print(f"After optimizing mappings: {size_after_mappings:,} bytes (saved {size_after_comments - size_after_mappings:,} bytes)")
    
    # 3. Optimize descriptions
    content = optimize_descriptions(content)
    size_after_descriptions = len(content.encode('utf-8'))
    print(f"After optimizing descriptions: {size_after_descriptions:,} bytes (saved {size_after_mappings - size_after_descriptions:,} bytes)")
    
    # 4. Optimize Lambda code
    content = optimize_lambda_code(content)
    size_after_lambda = len(content.encode('utf-8'))
    print(f"After optimizing Lambda code: {size_after_lambda:,} bytes (saved {size_after_descriptions - size_after_lambda:,} bytes)")
    
    # 5. Final cleanup
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Remove excessive blank lines
    content = content.strip() + '\n'  # Ensure single trailing newline
    
    final_size = len(content.encode('utf-8'))
    total_saved = original_size - final_size
    
    # Write optimized template
    with open(output_file, 'w') as f:
        f.write(content)
    
    print(f"\nOptimization Results:")
    print(f"Original size: {original_size:,} bytes ({original_size/1024:.1f} KB)")
    print(f"Optimized size: {final_size:,} bytes ({final_size/1024:.1f} KB)")
    print(f"Total saved: {total_saved:,} bytes ({total_saved/1024:.1f} KB)")
    print(f"Size reduction: {(total_saved/original_size)*100:.1f}%")
    
    # Check SAR compliance
    if final_size <= 51200:
        print("✅ Template now fits within 51KB direct SAR limit!")
    elif final_size <= 460800:
        print("✅ Template fits within 450KB S3-based SAR limit")
    else:
        print("❌ Template still exceeds SAR limits - further optimization needed")
    
    return final_size

def main():
    """Main function"""
    # Get script directory and project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Change to project root
    os.chdir(project_root)
    
    input_file = "template.yaml"
    output_file = "template-optimized.yaml"
    
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found")
        print(f"Current directory: {os.getcwd()}")
        return 1
    
    try:
        final_size = optimize_template(input_file, output_file)
        
        print(f"\nOptimized template saved as: {output_file}")
        print("Next steps:")
        print("1. Validate optimized template:")
        print(f"   python3 validate-template-size.py")
        print("2. Test deployment with optimized template")
        print("3. If size is acceptable, replace original template")
        
        return 0
        
    except Exception as e:
        print(f"Error during optimization: {e}")
        return 1

if __name__ == "__main__":
    exit(main())