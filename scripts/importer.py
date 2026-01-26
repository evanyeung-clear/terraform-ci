#!/usr/bin/env python3
"""
Okta Terraform Import Script

This script uses the Okta Python SDK to generate Terraform import blocks for Okta resources.
It reads OAuth2 credentials from a terraform.tfvars.json file in the current working directory.

Usage:
    uv run okta-import [--type=<types>]

    Where <types> is a comma-separated list of Okta resource types to process:
    - groups: Okta groups
    - users: Okta users
    - apps: Okta applications

    If no --type is specified, all resource types will be processed.

Examples:
    cd preview && uv run okta-import
    cd production && uv run okta-import --type=groups
    cd preview && uv run okta-import --type=groups,users

The script will look for terraform.tfvars.json in the current working directory.
"""

import sys
import json
import asyncio
import subprocess
from pathlib import Path
from .OktaTFImport import OktaTFImport

def parse_arguments() -> tuple[str, list[str]]:
    """Parse command line arguments."""
    # Use current working directory
    directory = str(Path.cwd())

    # Parse type argument
    resource_types = []
    for arg in sys.argv[1:]:
        if arg.startswith('--type='):
            types_str = arg.split('=', 1)[1]
            resource_types = [t.strip().lower() for t in types_str.split(',')]
            break
        elif arg in ['--help', '-h']:
            print("Usage: uv run okta-import [--type=<types>]")
            print("\nWhere <types> is a comma-separated list of Okta resources to read")
            print("\nSupported types:")
            print("  groups    - Okta groups")
            print("  users     - Okta users")
            print("  apps      - Okta applications")
            print("\nExamples:")
            print("  cd preview && uv run okta-import")
            print("  cd production && uv run okta-import --type=groups")
            print("  cd preview && uv run okta-import --type=groups,users")
            sys.exit(0)

    # If no types specified, default to all supported types
    if not resource_types:
        resource_types = ['groups', 'users', 'apps']

    # Validate resource types
    supported_types = {'groups', 'users', 'apps'}
    invalid_types = set(resource_types) - supported_types
    if invalid_types:
        print(f"Error: Unsupported resource types: {', '.join(invalid_types)}")
        print(f"Supported types: {', '.join(supported_types)}")
        sys.exit(1)

    return directory, resource_types

def read_terraform_config(directory: str) -> dict:
    """Read the terraform plan configuration from the specified directory."""
    try:
        config_file = Path(directory) / "terraform.tfvars.json"
        with open(config_file, 'r') as f:
            print(f"Reading config from {config_file}")
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: terraform.tfvars.json not found in {directory}")
        sys.exit(1)

def export_terraform_state(directory: str) -> str | None:
    """Export current terraform state to JSON."""
    try:
        result = subprocess.run(
            ["docker", "compose", "run", "--rm", "terraform", "show", "--json"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )

        output_file = Path(directory) / "terraform.tfstate"
        with open(output_file, 'w') as f:
            f.write(result.stdout)
            print(f"Terraform state exported to {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error exporting terraform state: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing terraform state JSON: {str(e)}", file=sys.stderr)
        return None
    
def generate_terraform_config(directory: str) -> None:
    """Generate terraform config from import blocks."""
    try:
        generated_file = "generated.tf"
        subprocess.run(
            ["docker", "compose", "run", "--rm", "terraform", "plan", f"-generate-config-out={generated_file}"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False
        )
    except subprocess.CalledProcessError as e:
        print(f"Error generating terraform config: {e.stderr}", file=sys.stderr)

async def main():
    """Main function to run the Okta terraform import tool."""
    print("Okta Terraform Import Tool")
    print("=" * 40)

    try:
        # Parse command line arguments
        directory, resource_types = parse_arguments()

        print(f"Processing resource types: {', '.join(resource_types)}")
        print(f"Output directory: {directory}")
        print()

        # Read Okta credentials from terraform.tfvars.json
        tfvars = read_terraform_config(directory)
        org_name = tfvars['okta_org_name']
        base_url = tfvars['okta_base_url']
        client_id = tfvars['okta_api_client_id']
        private_key_id = tfvars['okta_api_private_key_id']
        private_key = tfvars['okta_api_private_key']
        scopes = tfvars['okta_api_scopes']

        config = {
            "orgUrl": f"https://{org_name}.{base_url}",
            "authorizationMode": "PrivateKey",
            "clientId": client_id,
            "privateKey": private_key,
            "kid": private_key_id,
            "scopes": scopes,
            "logging": {"enabled": False},
        }
        
        # Export current terraform state to JSON
        state_file = export_terraform_state(directory)

        # Initialize the OktaTFImport for the directory
        okta = OktaTFImport(
            directory=directory,
            config=config,
            state_file=state_file
        )

        # Process each resource type (skipping ones already in state)
        for resource_type in resource_types:
            print(f"\n{'='*60}")
            print(f"Processing {resource_type.upper()}")
            print(f"{'='*60}")

            if resource_type == 'groups':
                await okta.process_groups()
            elif resource_type == 'users':
                await okta.process_users()
            elif resource_type == 'apps':
                await okta.process_apps()

        print(f"\n{'='*60}")
        print("PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Terraform import files have been written to the '{directory}' directory.")
        print("You can now run 'terraform plan -generate-config-out' to see what resources will be imported.")

        # Close the client
        await okta.close()

        # Generate terraform config
        generate_terraform_config(directory)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cli_entry():
    """Entry point for uv tool / pip install."""
    asyncio.run(main())


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
