#trivy:ignore:OKTA_GROUP_NAME_STANDARD
resource "okta_group" "example" {
  name        = "Example"
  description = "My Example Group"
}

#trivy:ignore:OKTA_GROUP_NAME_STANDARD
resource "okta_group" "example2" {
  name        = "Example2"
  description = "My Example Group"
}

#trivy:ignore:OKTA_GROUP_NAME_STANDARD
resource "okta_group" "example3" {
  name        = "Example3"
  description = "My Example Group"
}

#trivy:ignore:OKTA_GROUP_NAME_STANDARD
resource "okta_group" "example4" {
  name        = "Example4"
  description = "My Example Group"
}

#trivy:ignore:OKTA_GROUP_NAME_STANDARD
resource "okta_group" "example5" {
  name        = "Example5"
  description = "My Example Group"
}

resource "okta_group" "example6" {
  name        = "Example6"
  description = "My Example Group"
}

resource "okta_group" "example7" {
  name = "example_admin"
}

resource "okta_group" "example8" {
  name = "example_user"
}
