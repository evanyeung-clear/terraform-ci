"""Application retrieval and processing functions."""

from typing import List
from ._utils import sanitize_resource_name


skip_builtin_apps = [
    "okta_enduser", # Okta Dashboard
    "okta_browser_plugin",
    "saasure" # Okta Admin Console
]

def _map_app_type(sign_on_mode: str):
    """Map Okta application sign-on mode to Terraform resource type."""

    match sign_on_mode:
        case 'AUTO_LOGIN':
            return 'auto_login'
        case 'BASIC_AUTH':
            return 'basic_auth'
        case 'BOOKMARK':
            return 'bookmark'
        case 'BROWSER_PLUGIN':
            return 'swa'
        case 'OPENID_CONNECT':
            return 'oauth'
        case 'SAML_1_1' | 'SAML_2_0':
            return 'saml'
        case 'SECURE_PASSWORD_STORE':
            return 'secure_password_store'
        case 'WS_FEDERATION':
            return 'ws_federation'
        case _:
            return 'unknown'

async def _get_all_apps(client) -> List:
    print("Fetching all applications from Okta...")
    apps = []
    try:
        app_list, resp, err = await client.list_applications()
        if err:
            raise Exception(f"Error fetching applications: {err}")
        apps.extend(app_list)
        while resp.has_next():
            app_list, err = await resp.next()
            if err:
                print(f"Warning: Error fetching additional applications: {err}")
                break
            apps.extend(app_list)
        print(f"Successfully retrieved {len(apps)} applications")

        # Build list of app IDs, filtering out unknown types
        ids = []
        for app in apps:
            app_type = _map_app_type(app.sign_on_mode)
            if app_type == 'unknown':
                print(f"Warning: Skipping application '{app.label}' with unknown sign-on mode: {app.sign_on_mode}")
                continue

            if app.name in skip_builtin_apps:
                continue

            ids.append({
                "type": f"okta_app_{app_type}",
                "id": app.id,
                "name": sanitize_resource_name(app.label)
            })

            ids.append({
                "type": "okta_app_group_assignments",
                "id": app.id,
                "name": sanitize_resource_name(app.label)
            })

        return ids
    except Exception as e:  # noqa: BLE001
        raise Exception(f"Failed to retrieve applications: {str(e)}") from e

def _existing_apps(resource) -> bool:
    if resource.get('type').startswith('okta_app_'):
        return True

    return False
