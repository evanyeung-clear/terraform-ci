variable "airport_code" {
  type        = string
  description = "The three letter IATA desgination for the airport"

  validation {
    condition     = var.airport_code == upper(var.airport_code)
    error_message = "airport_code must be all uppercase (e.g. \"JFK\", not \"jfk\")."
  }

  validation {
    condition     = !can(regex("\\s", var.airport_code))
    error_message = "airport_code must not contain spaces."
  }
}
