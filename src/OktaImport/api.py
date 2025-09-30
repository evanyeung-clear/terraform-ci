"""Okta API manager abstraction.

Provides initialization of the Okta Python SDK client using credentials
decrypted from terraform.plan.enc.tfvars.json located in a target environment
directory (e.g. preview/, production/). Keeping this in its own module makes
the top-level import script thinner and allows future reuse (e.g. tests or
other tooling) without copying logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import subprocess
from okta.client import Client as OktaClient


class OktaImportManager:
    """Manages Okta API operations using the Okta Python SDK."""

    def __init__(self, directory: str):
        self.client = None
        self.directory = directory
        self.base_dir = Path(__file__).parent.parent  # repo root
        self.output_dir = self.base_dir / self.directory
        self._setup_client()

    def _setup_client(self):
        config_data = self._load_terraform_config()
        if not config_data:
            raise ValueError("Configuration data is None or empty")
        try:
            org_name = config_data.get("okta_org_name")
            base_url = config_data.get("okta_base_url", "okta.com")
            client_id = config_data.get("okta_api_client_id")
            private_key_id = config_data.get("okta_api_private_key_id")
            private_key = config_data.get("okta_api_private_key")
            scopes = config_data.get(
                "okta_api_scopes", ["okta.groups.read", "okta.users.read"]
            )
            if not all([org_name, client_id, private_key_id, private_key]):
                missing = []
                if not org_name:
                    missing.append("okta_org_name")
                if not client_id:
                    missing.append("okta_api_client_id")
                if not private_key_id:
                    missing.append("okta_api_private_key_id")
                if not private_key:
                    missing.append("okta_api_private_key")
                raise ValueError(
                    "Missing required Okta configuration in terraform file: "
                    + ", ".join(missing)
                )
            config = {
                "orgUrl": f"https://{org_name}.{base_url}",
                "authorizationMode": "PrivateKey",
                "clientId": client_id,
                "privateKey": private_key,
                "kid": private_key_id,
                "scopes": scopes,
                "logging": {"enabled": True},
            }
            self.client = OktaClient(config)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Error configuring Okta client: {e}")

    # ---------------- Public API -----------------
    async def close(self):
        if self.client and hasattr(self.client, "close"):
            await self.client.close()
        elif self.client and hasattr(self.client, "_http_client"):
            if hasattr(self.client._http_client, "close"):
                await self.client._http_client.close()
        self.client = None


__all__ = ["OktaAPIManager"]
