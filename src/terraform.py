#!/usr/bin/env -S uv run --script
"""
terraform.py - Cross-platform Python script for Terraform with preprocessing

Usage: uv run terraform.py [terraform_arguments...]

This script performs the following preprocessing before running terraform:
1. Validates current directory has a Terraform {} block in it
2. Consolidates all .tf files from subdirectories into a single temporary file
3. Passes all arguments to terraform command

Examples:
  cd preview
  uv run ../src/terraform.py --help
  uv run ../src/terraform.py version
  uv run ../src/terraform.py init
  uv run ../src/terraform.py plan -var-file=terraform.tfvars.json
  uv run ../src/terraform.py apply -var-file=terraform.tfvars.json
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Global constants
CONSOLIDATED_FILE = "_consolidated.tf"
SOURCE_MAP_FILE = "_consolidated_source_map.json"

def log_info(message):
    """Print an info message"""
    print(f"[INFO] {message}", file=sys.stderr)

def log_error(message):
    """Print an error message"""
    print(f"[ERROR] {message}", file=sys.stderr)

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
    for f in [CONSOLIDATED_FILE, SOURCE_MAP_FILE]:
        if os.path.exists(f):
            os.remove(f)

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
    """Find all .tf files in subdirectories, consolidate them, and write a source map.

    The source map (SOURCE_MAP_FILE) records which line ranges in the consolidated
    file correspond to which original source files so that CI can map formatting
    errors back to the correct file and line number.
    """
    log_info(f"Consolidating .tf files from subdirectories into {CONSOLIDATED_FILE}...")

    current_dir = Path.cwd()
    file_count = 0
    source_map = []   # list of {consolidated_start, source_file, line_count}
    all_lines = []    # 0-indexed; joined with \n when writing

    for tf_file in sorted(current_dir.rglob("*.tf")):
        # Skip files in the current directory (only process subdirectories)
        if tf_file.parent == current_dir:
            continue
        # Skip .terraform/ (downloaded providers/modules from terraform init)
        if ".terraform" in tf_file.parts:
            continue

        rel_path = tf_file.relative_to(current_dir)

        try:
            with open(tf_file, "r", encoding="utf-8") as source:
                source_content = source.read()

            source_lines = source_content.splitlines()

            # 5-line header block
            all_lines.append("")
            all_lines.append("# " + "=" * 76)
            all_lines.append(f"# Source: {rel_path}")
            all_lines.append("# " + "=" * 76)
            all_lines.append("")

            # consolidated_start is 1-indexed line number where source content begins
            content_start = len(all_lines) + 1

            all_lines.extend(source_lines)
            all_lines.append("")  # blank line after each file

            source_map.append({
                "consolidated_start": content_start,
                "source_file": str(rel_path).replace("\\", "/"),
                "line_count": len(source_lines),
            })

            file_count += 1

        except Exception as e:
            log_error(f"Failed to append file {tf_file}: {e}")

    # Write consolidated file
    with open(CONSOLIDATED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines) + "\n")

    # Write source map — intentionally kept after terraform runs so CI can read it
    with open(SOURCE_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(source_map, f, indent=2)

    log_info(f"Consolidated {file_count} files into {CONSOLIDATED_FILE}")
    log_info(f"Source map written to {SOURCE_MAP_FILE}")
    return file_count

def is_allowed_terraform_cmd(cmd):
    """List of allowed terraform commands"""
    return cmd in ["init", "fmt", "validate", "plan", "apply", "show", "plan-light"]

def discover_changed_targets(terraform_bin):
    """Run a JSON-mode plan and return the list of changed resource addresses.

    Mirrors the CI pipeline:
        terraform plan -refresh=false -json | jq '.change.resource.addr'
    Returns a deduped list preserving discovery order.
    """
    cmd = [terraform_bin, "plan", "-refresh=false", "-input=false", "-json"]
    log_info(f"Discovering changed resources: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as e:
        log_error(f"Failed to run discovery plan: {e}")
        return None

    if result.returncode != 0:
        log_error(f"Discovery plan failed (exit {result.returncode})")
        if result.stderr:
            sys.stderr.write(result.stderr)
        return None

    targets = []
    seen = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        addr = obj.get("change", {}).get("resource", {}).get("addr")
        if addr and addr not in seen:
            seen.add(addr)
            targets.append(addr)
    return targets

def run_plan_light(args, terraform_bin):
    """plan-light: discover changed resources, then run plan with -target=... for each.

    args: arguments after 'plan-light' (forwarded to the final plan call).
    """
    targets = discover_changed_targets(terraform_bin)
    if targets is None:
        return 1
    if not targets:
        log_info("No changes detected; skipping plan.")
        return 0

    log_info(f"Found {len(targets)} target(s): {', '.join(targets)}")
    target_args = [f"-target={a}" for a in targets]
    final_cmd = [terraform_bin, "plan"] + args + target_args
    log_info(f"Running: {' '.join(final_cmd)}")
    try:
        result = subprocess.run(final_cmd, check=False)
        return result.returncode
    except Exception as e:
        log_error(f"Failed to run terraform: {e}")
        return 1

def run_terraform(args):
    """Run terraform with the provided arguments"""
    if not is_allowed_terraform_cmd(args[0]):
        log_error(f"Command {args[0]} is not allowed")
        return 1

    terraform_bin = find_terraform_executable()
    log_info(f"Using terraform executable: {terraform_bin}")

    if args[0] == "plan-light":
        return run_plan_light(args[1:], terraform_bin)

    log_info(f"Running terraform with arguments: {' '.join(args)}")

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
