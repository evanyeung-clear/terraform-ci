import asyncio
from OktaTFImport import OktaTFImport

async def main():
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

    okta = OktaTFImport(
        directory="../preview",
        config=config,
        state_file="../preview/terraform.tfstate"
    )

    await okta.process_users()
    await okta.close()

asyncio.run(main())
