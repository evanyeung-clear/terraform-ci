# METADATA
# title: Okta group naming standard
# description: Ensure group names meet standards {app-name}_{role-name}
# scope: package
# schemas:
#   - input: schema["terraform-raw"]
# custom:
#   id: OKTA_GROUP_NAME_STANDARD
#   severity: HIGH
#   recommended_actions: No spaces and only one underscore
#   input:
#     selector:
#       - type: terraform-raw

package okta.group_name_standard

import rego.v1

resource_types_to_check := {"okta_group"}

resources_to_check := {block |
	some module in input.modules
	some block in module.blocks
	block.kind == "resource"
	block.type in resource_types_to_check
}

deny contains res if {
	some block in resources_to_check
    
	name := block.attributes.name.value
	not regex.match(`^[^ _]+_[^ _]+$`, name)

	res := result.new(
		sprintf("Group name does not meet standards: %v", [name]),
		block,
	)
}
