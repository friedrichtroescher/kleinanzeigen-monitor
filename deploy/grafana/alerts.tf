resource "grafana_rule_group" "kleinanzeigen_monitor" {
  name             = "kleinanzeigen-monitor-evaluation-group"
  folder_uid       = grafana_folder.kleinanzeigen_monitor.uid
  interval_seconds = 60

  rule {
    name      = "kleinanzeigen-monitor-heartbeat-check"
    condition = "C"
    for       = "0s"

    no_data_state  = "NoData"
    exec_err_state = "Error"

    annotations = {
      summary = "Kleinanzeigen Monitor: No successful run in the last 16 minutes."
    }

    notification_settings {
      contact_point = var.contact_point_name
    }

    data {
      ref_id = "A"

      relative_time_range {
        from = 3600
        to   = 0
      }

      datasource_uid = var.prometheus_datasource_uid

      model = jsonencode({
        editorMode    = "code"
        expr          = "time() - last_over_time(monitor_run_last_success_time_seconds{job=~\".*/kleinanzeigen-monitor\"}[20m])"
        instant       = true
        intervalMs    = 1000
        legendFormat  = "__auto"
        maxDataPoints = 43200
        range         = false
        refId         = "A"
      })
    }

    data {
      ref_id = "C"

      relative_time_range {
        from = 0
        to   = 0
      }

      datasource_uid = "__expr__"

      model = jsonencode({
        conditions = [
          {
            evaluator = {
              params = [960]
              type   = "gt"
            }
            operator = {
              type = "and"
            }
            query = {
              params = ["C"]
            }
            reducer = {
              params = []
              type   = "last"
            }
            type = "query"
          }
        ]
        datasource = {
          type = "__expr__"
          uid  = "__expr__"
        }
        expression    = "A"
        intervalMs    = 1000
        maxDataPoints = 43200
        refId         = "C"
        type          = "threshold"
      })
    }
  }
}
