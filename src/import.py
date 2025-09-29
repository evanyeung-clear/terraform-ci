#!/usr/bin/env python3
"""
Okta Terraform Import Script

This script uses the Okta Python SDK to generate Terraform import blocks for Okta resources.
It reads OAuth2 credentials from a terraform.plan.enc.tfvars.json file in a specified directory.

Usage:
    python import.py <directory_name> [--type=<types>]

    Where <directory_name> is the directory containing terraform.plan.enc.tfvars.json
    (e.g., 'preview' or 'production')

    And <types> is a comma-separated list of Okta resource types to process:
    - groups: Okta groups
    - users: Okta users
    - apps: Okta applications

    If no --type is specified, all resource types will be processed.

Examples:
    python import.py preview
    python import.py production --type=groups
    python import.py preview --type=groups,users

The script will look for terraform.plan.enc.tfvars.json in the specified directory and use
SOPS to decrypt the Okta OAuth2 credentials.
"""

import sys
import json
import asyncio
import subprocess
import importlib
from pathlib import Path
from typing import List, Dict, Any
from okta.client import Client as OktaClient
from import_okta import groups, users, applications

class OktaAPIManager:
    """Manages Okta API operations using the Okta Python SDK."""

    def __init__(self, directory: str):
        """Initialize the Okta client with OAuth2 authentication from terraform config."""
        self.client = None
        self.directory = directory
        self.base_dir = Path(__file__).parent.parent
        self.output_dir = self.base_dir / self.directory
        self._setup_client()

    def _load_terraform_config(self) -> Dict[str, Any]:
        terraform_file = self.base_dir / self.directory / "terraform.plan.enc.tfvars.json"

        if not terraform_file.exists():
            raise FileNotFoundError(f"terraform.plan.enc.tfvars.json not found in directory: {self.directory}")
        print(f"Loading configuration from: {terraform_file}")

        try:
            # Use SOPS to decrypt the file
            print("Running SOPS to decrypt terraform configuration...")
            result = subprocess.run(
                ["sops", "--decrypt", str(terraform_file)],
                capture_output=True,
                text=True,
                check=True
            )

            print("SOPS decryption successful, parsing JSON...")
            if not result.stdout.strip():
                raise ValueError("SOPS returned empty output")

            config_data = json.loads(result.stdout)
            print("Successfully decrypted and parsed terraform configuration")

            # Debug: Show the structure without sensitive data
            if isinstance(config_data, dict):
                print(f"Configuration contains {len(config_data)} keys")
            else:
                print(f"Warning: Configuration is not a dictionary, it's a {type(config_data)}")

            return config_data
        except Exception as e:
            print(f"Failed to load terraform config: {e}")
            raise

    def _setup_client(self):
        """Set up the Okta client with OAuth2 authentication."""
        config_data = self._load_terraform_config()

        if not config_data:
            raise ValueError("Configuration data is None or empty")
        
        # Extract Okta configuration from terraform variables
        try:
            org_name = config_data.get('okta_org_name')
            base_url = config_data.get('okta_base_url', 'okta.com')
            client_id = config_data.get('okta_api_client_id')
            private_key_id = config_data.get('okta_api_private_key_id')
            private_key = config_data.get('okta_api_private_key')
            scopes = config_data.get('okta_api_scopes', ['okta.groups.read', 'okta.users.read'])

            if not all([org_name, client_id, private_key_id, private_key]):
                missing = []
                if not org_name: missing.append('okta_org_name')
                if not client_id: missing.append('okta_api_client_id')
                if not private_key_id: missing.append('okta_api_private_key_id')
                if not private_key: missing.append('okta_api_private_key')

                raise ValueError(
                    f"Missing required Okta configuration in terraform file: {', '.join(missing)}"
                )

            config = {
                'orgUrl': f"https://{org_name}.{base_url}",
                'authorizationMode': 'PrivateKey',
                'clientId': client_id,
                'privateKey': private_key,
                'kid': private_key_id,
                'scopes': scopes,
                'logging': {
                    'enabled': True
                }
            }

            self.client = OktaClient(config)

        except Exception as e:
            raise ValueError(f"Error configuring Okta client: {e}")

    # Retrieval and processing functions moved to package modules under src/import
    # (groups.py, users.py, applications.py). This class now focuses solely on
    # client setup/teardown and exposing directory metadata.

    async def close(self):
        """Close the Okta client connection."""
        if self.client and hasattr(self.client, 'close'):
            await self.client.close()
        elif self.client and hasattr(self.client, '_http_client'):
            # Try to close the underlying HTTP client if it exists
            if hasattr(self.client._http_client, 'close'):
                await self.client._http_client.close()
        # If no close method exists, just set to None
        self.client = None


def parse_arguments() -> tuple[str, list[str]]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python import.py <directory_name> [--type=<types>]")
        print("\nWhere <directory_name> is the directory containing terraform.plan.enc.tfvars.json")
        print("(relative to the base project directory, e.g., 'preview' or 'production')")
        print("and <types> is a comma-separated list of Okta resources to read")
        print("\nSupported types:")
        print("  groups    - Okta groups")
        print("  users     - Okta users")
        print("  apps      - Okta applications")
        print("\nExamples:")
        print("  python import.py preview")
        print("  python import.py production --type=groups")
        print("  python import.py preview --type=groups,users")

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

        # Initialize the Okta API manager with the specified directory
        okta = OktaAPIManager(directory)

        # Process each resource type
        for resource_type in resource_types:
            print(f"\n{'='*60}")
            print(f"Processing {resource_type.upper()}")
            print(f"{'='*60}")

            if resource_type == 'groups':
                await groups.process_groups(okta)
            elif resource_type == 'users':
                await users.process_users(okta)
            elif resource_type == 'apps':
                await applications.process_applications(okta)

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