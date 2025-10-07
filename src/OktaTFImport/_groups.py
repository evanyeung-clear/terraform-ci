"""Group retrieval and processing functions."""

from typing import List
from ._utils import sanitize_resource_name


async def _get_all_groups(client) -> List:
    print("Fetching all groups from Okta...")
    groups = []
    try:
        group_list, resp, err = await client.list_groups(query_params={"search": "type eq \"OKTA_GROUP\""})
        if err:
            raise Exception(f"Error fetching groups: {err}")
        groups.extend(group_list)
        while resp.has_next():
            group_list, err = await resp.next()
            if err:
                print(f"Warning: Error fetching additional groups: {err}")
                break
            groups.extend(group_list)
        print(f"Successfully retrieved {len(groups)} groups")

        ids = list(map(lambda group: {
                    "type": "okta_group",
                    "id": group.id,
                    "name": sanitize_resource_name(group.profile.name)
                }, groups))
        
        return ids
    except Exception as e:  # noqa: BLE001
        raise Exception(f"Failed to retrieve groups: {str(e)}") from e


def _existing_groups(resource) -> bool:
    if resource.get('type') == 'okta_group':
        return True

    return False
