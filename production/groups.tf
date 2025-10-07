resource "okta_group" "example" {
  name        = "Example"
  description = "My Example Group"
}

resource "okta_group" "example2" {
  name        = "Example2"
  description = "My Example Group"
}

resource "okta_group" "example3" {
  name        = "Example3"
  description = "My Example Group"
}

resource "okta_group" "example4" {
  name        = "Example4"
  description = "My Example Group"
}

resource "okta_group" "example5" {
  name        = "Example5"
  description = "My Example Group"
}

resource "okta_group" "example6" {
  name        = "Example6"
  description = "My Example Group"
}

import {
  to = okta_group.example6
  id = "00gq7829t9tbGRpf15d7"
}

resource "okta_group" "example7" {
  name        = "Example7"
  description = "My Example Group"
}
