terraform {
  required_providers {
    okta = {
      source  = "okta/okta"
      version = "~> 4.19.0"
    }
  }
}

# Airport
resource "okta_group" "airport" {
  name = var.airport_code
}

resource "okta_group_rule" "airport" {
  name = "Group - ${var.airport_code}"
  group_assignments = [
    okta_group.airport.id
  ]
  expression_type  = "urn:okta:expression:1.0"
  expression_value = "user.department=='${var.airport_code}'"
}
