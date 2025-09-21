#!/usr/bin/env -S uv run --script
"""
terraform.py - Cross-platform Python script for Terraform with preprocessing

Usage: uv run terraform.py [terraform_arguments...]

IMPORTANT: This script can only be run from 'preview' or 'production' directories

This script performs the following preprocessing before running terraform:
1. Validates current directory is 'preview' or 'production'
2. Consolidates all .tf files from subdirectories into a single temporary file
3. Passes all arguments to terraform command

Examples:
  cd preview
  uv run ../src/terraform.py --help
  uv run  ../src/terraform.py version
  uv run ../src/terraform.py init
  uv run ../src/terraform.py plan -var-file=terraform.tfvars.json
  uv run ../src/terraform.py apply -var-file=terraform.tfvars.json

The script will:
- Verify you're in preview/ or production/ directory
- Find all .tf files in subdirectories (like apps/*.tf, group/*.tf)
- Append them all into a single consolidated temporary file
- Run the actual terraform command with all provided arguments
- Clean up the temporary file when done

Note: This script prevents infinite recursion by detecting if it's already running
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Global constants
CONSOLIDATED_FILE = "_consolidated.tf"
ALLOWED_DIRECTORIES = ["preview", "production"]

def log_info(message):
    """Print an info message"""
    print(f"[INFO] {message}")

def log_error(message):
    """Print an error message"""
    print(f"[ERROR] {message}")

def check_infinite_recursion():
    """Prevent infinite recursion by checking environment variable"""
    if os.environ.get("TERRAFORM_WRAPPER_RUNNING"):
        log_error("Terraform wrapper is already running. Infinite recursion detected.")
        sys.exit(1)
    os.environ["TERRAFORM_WRAPPER_RUNNING"] = "1"

def validate_current_directory():
    """Check if current directory contains a .tf file with a terraform {} block"""
    cwd = Path.cwd()
    allowed = False
    for tf_file in cwd.glob("*.tf"):
        try:
            with open(tf_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "terraform {" in content:
                    allowed = True
                    break
        except Exception as e:
            log_error(f"Error reading {tf_file}: {e}")
    if not allowed:
        log_error("terraform.py can only be run from a directory containing a .tf file with a terraform {} block.")
        log_info(f"Current directory: {cwd}")
        log_info("Please change to a directory with a valid Terraform configuration.")
        sys.exit(1)
    return cwd.name

def cleanup_existing_files():
    """Clean up any existing temporary files"""
    log_info("Cleaning up existing temporary files...")
    if os.path.exists(CONSOLIDATED_FILE):
        os.remove(CONSOLIDATED_FILE)

def find_terraform_executable():
    """Find terraform executable in PATH, excluding wrapper scripts"""
    # Look for terraform.exe specifically on Windows, terraform on Unix
    if os.name == 'nt':  # Windows
        terraform_bin = shutil.which("terraform.exe")
    else:  # Unix-like systems
        terraform_bin = shutil.which("terraform")
        # Make sure we don't find our own wrapper scripts
        if terraform_bin and (terraform_bin.endswith('/terraform') or terraform_bin.endswith('\\terraform')):
            # Check if this is our wrapper by looking for terraform.py in the same directory
            script_dir = Path(terraform_bin).parent
            if (script_dir / "src" / "terraform.py").exists():
                # This is our wrapper, keep looking
                terraform_bin = None

    if not terraform_bin:
        log_error("terraform executable not found in PATH")
        log_info("Please install Terraform: https://developer.hashicorp.com/terraform/install")
        sys.exit(1)
    return terraform_bin

def consolidate_tf_files():
    """Find all .tf files in subdirectories and consolidate them"""
    log_info(f"Consolidating .tf files from subdirectories into {CONSOLIDATED_FILE}...")
    
    current_dir = Path.cwd()
    file_count = 0
    
    # Find all .tf files recursively
    for tf_file in current_dir.rglob("*.tf"):
        # Skip files in the current directory (only process subdirectories)
        if tf_file.parent == current_dir:
            continue
            
        # Get relative path for logging
        rel_path = tf_file.relative_to(current_dir)
        
        try:
            # Add comment header to identify the source file
            with open(CONSOLIDATED_FILE, "a", encoding="utf-8") as consolidated:
                consolidated.write("\n")
                consolidated.write("# " + "=" * 76 + "\n")
                consolidated.write(f"# Source: {rel_path}\n")
                consolidated.write("# " + "=" * 76 + "\n")
                consolidated.write("\n")
                
                # Append the file content
                with open(tf_file, "r", encoding="utf-8") as source:
                    consolidated.write(source.read())
                    consolidated.write("\n")
            
            file_count += 1
            
        except Exception as e:
            log_error(f"Failed to append file {tf_file}: {e}")
    
    log_info(f"Consolidated {file_count} files into {CONSOLIDATED_FILE}")
    return file_count

def run_terraform(args):
    """Run terraform with the provided arguments"""
    terraform_bin = find_terraform_executable()
    log_info(f"Running terraform with arguments: {' '.join(args)}")
    log_info(f"Using terraform executable: {terraform_bin}")
    
    # Run terraform with all provided arguments
    try:
        result = subprocess.run([terraform_bin] + args, check=False)
        return result.returncode
    except Exception as e:
        log_error(f"Failed to run terraform: {e}")
        return 1

def cleanup_temporary_files():
    """Clean up temporary files"""
    log_info("Cleaning up temporary file...")
    if os.path.exists(CONSOLIDATED_FILE):
        log_info(f"Removing: {CONSOLIDATED_FILE}")
        os.remove(CONSOLIDATED_FILE)

def main():
    """Main function"""
    try:
        # Step 1: Prevent infinite recursion
        check_infinite_recursion()
        
        # Step 2: Validate current directory
        current_dir = validate_current_directory()
        log_info(f"Starting Terraform preprocessing in {current_dir} environment...")
        
        # Step 3: Clean up existing files
        cleanup_existing_files()
        
        # Step 4: Consolidate .tf files
        consolidate_tf_files()
        
        # Step 5: Run terraform
        terraform_args = sys.argv[1:]  # All arguments except script name
        exit_code = run_terraform(terraform_args)
        
    except KeyboardInterrupt:
        log_info("Operation cancelled by user")
        exit_code = 130
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        exit_code = 1
    finally:
        # Always clean up temporary files
        cleanup_temporary_files()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
