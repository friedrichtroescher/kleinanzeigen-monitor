variable "prometheus_datasource_uid" {
  description = "UID of the existing Prometheus data source receiving the monitor's OTLP metrics."
  type        = string
  default     = "grafanacloud-prom"
}

variable "loki_datasource_uid" {
  description = "UID of the existing Loki data source receiving the monitor's OTLP logs."
  type        = string
  default     = "grafanacloud-logs"
}

variable "contact_point_name" {
  description = "Name of an existing Grafana contact point for heartbeat notifications."
  type        = string
}
