terraform {
  required_version = ">= 1.5"
  required_providers {
    grafana = {
      source  = "grafana/grafana"
      version = "~> 3.25"
    }
  }
}

# Credentials come from GRAFANA_URL and GRAFANA_AUTH.
provider "grafana" {}

resource "grafana_folder" "kleinanzeigen_monitor" {
  title = "Kleinanzeigen Monitor"
}

resource "grafana_dashboard" "kleinanzeigen_monitor" {
  folder    = grafana_folder.kleinanzeigen_monitor.id
  overwrite = true
  config_json = replace(replace(
    file("${path.module}/dashboards/kleinanzeigen-monitor.json"),
    "grafanacloud-prom", var.prometheus_datasource_uid),
    "grafanacloud-logs", var.loki_datasource_uid
  )
}
