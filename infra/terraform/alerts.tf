# Google Cloud Monitoring Alert Policies
# These alerts trigger the Self-Healing Agent via webhook

# ─── Alert: High Error Rate ───────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "[GitGuardian] High Error Rate - task-manager"
  combiner     = "OR"
  
  conditions {
    display_name = "Error rate > 5% for 5 minutes"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"task-manager\" AND metric.type = \"run.googleapis.com/request_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_FRACTION_TRUE"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.webhook.name]
  
  alert_strategy {
    auto_close = "1800s"
  }
}

# ─── Alert: Service Latency ───────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "[GitGuardian] High Latency - task-manager"
  combiner     = "OR"
  
  conditions {
    display_name = "p99 latency > 2000ms"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"task-manager\" AND metric.type = \"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.webhook.name]
}

# ─── Webhook Notification Channel ────────────────────────────────────────────
resource "google_monitoring_notification_channel" "webhook" {
  display_name = "GitGuardian Self-Healing Webhook"
  type         = "webhook_tokenauth"
  
  labels = {
    url = "${google_cloud_run_v2_service.webhook_receiver.uri}/webhook/cloud-monitoring"
  }

  sensitive_labels {
    auth_token = var.gitlab_token
  }
}
