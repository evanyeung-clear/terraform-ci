terraform {
  required_providers {
    okta = {
      source  = "okta/okta"
      version = "~> 4.19.0"
    }
  }
}

# ClearXXX
resource "okta_group" "airport" {
  name = "Clear${var.airport_code}"
}

resource "okta_group_rule" "airport" {
  name = "Distro - Clear${var.airport_code}"
  group_assignments = [
    okta_group.airport.id
  ]
  expression_type  = "urn:okta:expression:1.0"
  expression_value = "user.locationcode=='${var.airport_code}'"
}

# XXXAssistantManagers
resource "okta_group" "asst_managers" {
  name = "${var.airport_code}AssistantManagers"
}

resource "okta_group_rule" "asst_managers" {
  name = "Distro - ${var.airport_code}AssistantManagers"
  group_assignments = [
    okta_group.asst_managers.id
  ]
  expression_type  = "urn:okta:expression:1.0"
  expression_value = "user.locationcode=='${var.airport_code}' AND user.title=='Assistant Manager, Airport Operations'"
}

# XXXManagers
resource "okta_group" "managers" {
  name = "${var.airport_code}Managers"
}

resource "okta_group_rule" "managers" {
  name = "Distro - ${var.airport_code}Managers"
  group_assignments = [
    okta_group.managers.id
  ]
  expression_type  = "urn:okta:expression:1.0"
  expression_value = "user.locationcode=='${var.airport_code}' AND user.SubDepartment=='Airport Ops Field'"
}
