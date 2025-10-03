"""User retrieval and processing functions."""

from typing import List
from ._utils import sanitize_resource_name

async def _get_all_users(client) -> List:
    print("Fetching all users from Okta...")
    users = []
    try:
        user_list, resp, err = await client.list_users()
        if err:
            raise Exception(f"Error fetching users: {err}")
        users.extend(user_list)
        while resp.has_next():
            user_list, err = await resp.next()
            if err:
                print(f"Warning: Error fetching additional users: {err}")
                break
            users.extend(user_list)
        print(f"Successfully retrieved {len(users)} users")

        ids = list(map(lambda user: {
                    "type": "okta_user",
                    "id": user.id,
                    "name": sanitize_resource_name(user.profile.login)
                }, users))
        
        return ids
    except Exception as e:
        raise Exception(f"Failed to retrieve users: {str(e)}") from e
    
def _existing_users(resource) -> bool:
    if resource.get('type') == 'okta_user':
        return True

    return False
