from sailpoint.configuration import Configuration
from sailpoint.v2025.api_client import ApiClient
from sailpoint.paginator import Paginator
from sailpoint.v2025.api.entitlements_api import EntitlementsApi

configuration = Configuration()
configuration.experimental = True
configuration.suppress_experimental_warnings = True

with ApiClient(configuration) as api_client:
    # Get all groups from Okta source
    filters = 'source.id eq "" and type eq "group"'

    try:
        results = Paginator.paginate(
            EntitlementsApi(api_client).list_entitlements,
            result_limit=99999,
            filters=filters,
        )

        print("The response of EntitlementsApi->list_entitlements:\n")
        print(len(results))
        # for item in results:
        #     print(item.model_dump_json(by_alias=True, indent=4))

    except Exception as e:
        print("Exception when calling EntitlementsApi: %s\n" % e)
