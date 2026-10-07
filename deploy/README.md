# Kubernetes and GitOps deployment

These templates are adapted from the monitor's deployment in the private
`troescher-gitops` repository. They include only monitor resources, with a generic
search and no credentials, personal location, or notification recipient.

## Prerequisites

- An existing Kubernetes cluster and `kubectl` access.
- A `local-path` storage class, as provided by a typical k3s installation, or a
  replacement in `kubernetes/pvc.yaml`.
- ARM64 worker nodes: the repository's existing GitHub Actions workflow publishes
  `ghcr.io/friedrichtroescher/kleinanzeigen-monitor:latest` for `linux/arm64` only.
  For AMD64, build a matching image or extend the workflow's platform list.
- Argo CD installed in namespace `argocd` for the GitOps option.
- Optional: Grafana with existing Prometheus and Loki data sources, an OTLP/HTTP
  ingestion endpoint, and Terraform 1.5 or newer.

Cluster provisioning, Argo CD installation and Grafana account setup belong to
your infrastructure and are not included here.

## Configure and deploy

Run commands from the repository root.

1. Edit `kubernetes/configmap.yaml` to set your model, searches and evaluation
   criteria. The TOML uses `common_prompt` and `addition_prompt`, as in
   `config.toml.example`. Kubernetes scheduling comes from `cronjob.yaml`
   (`*/15 * * * *`), independently of the local `[schedule]` configuration.
2. Adjust the storage class and image if needed. When using a fork, also update
   `argocd/application.yaml` with your repository URL and revision. Argo CD must
   have read access to that repository. The image must be public, or you must
   configure an image pull secret on the pod.
3. Create the namespace and the credentials before starting the CronJob:

   ```bash
   kubectl apply -f deploy/kubernetes/namespace.yaml
   cp deploy/secret.yaml.example deploy/secret.yaml
   # Fill in deploy/secret.yaml locally; it is gitignored.
   kubectl apply -f deploy/secret.yaml
   ```

   For telemetry, uncomment and fill in the two OTEL entries. For Grafana Cloud,
   the Basic authorization value contains the base64 encoding of your instance
   ID and access token; `%20` represents the space after `Basic`. Secrets are
   managed separately from the Argo CD application. If you want secrets in Git,
   integrate your own encrypted secrets workflow.

4. Commit your customized manifests to the repository Argo CD will track, then
   register the application:

   ```bash
   kubectl apply -f deploy/argocd/application.yaml
   ```

   Argo CD reconciles `deploy/kubernetes` with automatic pruning and self-healing.
   The application manifest lives outside that directory so the application does
   not manage itself. For deployment without Argo CD, use:

   ```bash
   kubectl apply -k deploy/kubernetes
   ```

The container loads `/config/config.toml` from the ConfigMap and stores
`seen.json` on the PVC at `/data/seen.json`. Keep the PVC to retain deduplication
across runs. Deleting the PVC, namespace or an Argo CD application with cascading
deletion can remove this state. `concurrencyPolicy: Forbid` prevents overlapping
scheduled jobs; it does not prevent manually created jobs from overlapping.

The default uses `latest` with `imagePullPolicy: Always`, so each new run pulls
the current image. To pin a release, change the image to an immutable tag or
digest and commit the manifest change.

## Inspect and trigger runs

```bash
kubectl kustomize deploy/kubernetes  # Render manifests without applying them
kubectl get cronjobs,jobs,pods,pvc -n kleinanzeigen-monitor
./scripts/run-monitor.sh
```

Only trigger a manual run when no other monitor job is running. To avoid a
scheduled run starting during the manual job, temporarily suspend the CronJob
in the tracked manifest and let Argo CD sync it first, then restore it afterwards.
Concurrent runs share `seen.json` and can cause duplicate notifications or lost
state updates. The helper streams logs and returns a nonzero exit status if the
Job does not complete successfully within its wait timeout. Manual jobs remain
available for inspection and can be deleted after use.

## Optional Grafana dashboard and heartbeat alert

`grafana/` is a standalone Terraform configuration. It creates a monitor folder,
the dashboard exported from the private deployment, and a heartbeat rule. It uses
an existing contact point and does not change the account's notification policy.

```bash
export GRAFANA_URL='https://your-stack.grafana.net'
read -r -s -p 'Grafana service account token: ' GRAFANA_AUTH; echo
export GRAFANA_AUTH
export TF_VAR_contact_point_name='your-existing-contact-point'
# Override these if your data sources use different UIDs:
export TF_VAR_prometheus_datasource_uid='grafanacloud-prom'
export TF_VAR_loki_datasource_uid='grafanacloud-logs'
terraform -chdir=deploy/grafana init
terraform -chdir=deploy/grafana plan -out=monitor.tfplan
terraform -chdir=deploy/grafana apply monitor.tfplan
```

The token prompt above uses Bash syntax; run it in Bash or set `GRAFANA_AUTH`
through your preferred secret manager. Give the token permissions to manage
folders, dashboards and alert rules. Terraform state, plans and variable files
are gitignored but may contain sensitive information; keep them securely. If
these resources already exist in your Terraform infrastructure, continue using
that state or import them rather than managing them from two states.

The rule checks `monitor_run_last_success_time_seconds` for jobs matching
`.*/kleinanzeigen-monitor`, so heartbeats from other monitors do not mask a
failure. It uses a 20-minute lookback and a 960-second (16-minute) threshold,
matching the 15-minute CronJob interval. Missing data produces Grafana's `NoData`
state. Adjust the threshold and lookback when changing the schedule or allowing
longer runs.

OTLP ingestion must map the service to that Prometheus `job` label and expose
Loki's `service_name` and `detected_level` labels, as in the original deployment.
Adapt queries if your collector uses different labels or metric names. The
dashboard includes SQL expressions for price quantiles and was exported with
Grafana schema version 42; use a Grafana version with that feature enabled or
adapt those panels. Data source UIDs, including Explore links, are replaced by
the Terraform variables. Dashboard changes are managed by Terraform, so commit
edits to the JSON to preserve them across applies.
