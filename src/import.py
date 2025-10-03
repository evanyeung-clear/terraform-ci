#!/usr/bin/env python3
"""
Okta Terraform Import Script

This script uses the Okta Python SDK to generate Terraform import blocks for Okta resources.
It reads OAuth2 credentials from a terraform.plan.enc.tfvars.json file in a specified directory.

Usage:
    import.py <directory_name> [--type=<types>]

    Where <directory_name> is the directory containing terraform.plan.enc.tfvars.json
    (e.g., 'preview' or 'production')

    And <types> is a comma-separated list of Okta resource types to process:
    - groups: Okta groups
    - users: Okta users
    - apps: Okta applications

    If no --type is specified, all resource types will be processed.

Examples:
    import.py preview
    import.py production --type=groups
    import.py preview --type=groups,users

The script will look for terraform.plan.enc.tfvars.json in the specified directory and use
SOPS to decrypt the Okta OAuth2 credentials.
"""

import sys
import json
import asyncio
import subprocess
from pathlib import Path
from OktaTFImport import OktaTFImport

def parse_arguments() -> tuple[str, list[str]]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: import.py <directory_name> [--type=<types>]")
        print("\nWhere <directory_name> is the directory containing terraform.plan.enc.tfvars.json")
        print("(relative to the base project directory, e.g., 'preview' or 'production')")
        print("and <types> is a comma-separated list of Okta resources to read")
        print("\nSupported types:")
        print("  groups    - Okta groups")
        print("  users     - Okta users")
        print("  apps      - Okta applications")
        print("\nExamples:")
        print("  import.py preview")
        print("  import.py production --type=groups")
        print("  import.py preview --type=groups,users")

        # Show available directories
        try:
            script_dir = Path(__file__).parent  # src directory
            base_dir = script_dir.parent  # base directory
            available_dirs = []
            for dir_path in base_dir.iterdir():
                if dir_path.is_dir() and (dir_path / "terraform.plan.enc.tfvars.json").exists():
                    available_dirs.append(dir_path.name)

            if available_dirs:
                print(f"\nAvailable directories: {', '.join(available_dirs)}")
        except Exception:
            pass  # Don't fail if we can't list directories

        sys.exit(1)

    directory = sys.argv[1]

    # Parse type argument
    resource_types = []
    for arg in sys.argv[2:]:
        if arg.startswith('--type='):
            types_str = arg.split('=', 1)[1]
            resource_types = [t.strip().lower() for t in types_str.split(',')]
            break

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

def export_terraform_state(directory: str) -> str | None:
    """Export current terraform state to JSON."""
    try:
        result = subprocess.run(
            ["docker", "compose", "run", "terraform", "show", "--json"],
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

        # Export current terraform state to JSON
        state_file = export_terraform_state(directory)

        org_name = ""
        base_url = ""
        client_id = ""
        private_key_id = ""
        private_key = ""
        scopes = ["okta.groups.read", "okta.users.read"]

        config = {
            "orgUrl": f"https://{org_name}.{base_url}",
            "authorizationMode": "PrivateKey",
            "clientId": client_id,
            "privateKey": private_key,
            "kid": private_key_id,
            "scopes": scopes,
            "logging": {"enabled": True},
        }

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

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
