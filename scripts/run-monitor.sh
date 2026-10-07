#!/usr/bin/env bash
# Trigger a manual run of the deployed CronJob and stream its logs.
set -euo pipefail

NAMESPACE="${NAMESPACE:-kleinanzeigen-monitor}"
CRONJOB="${CRONJOB:-kleinanzeigen-monitor}"
JOB_NAME="${CRONJOB}-manual-$(date +%Y%m%d-%H%M%S)"

echo "Creating manual job '$JOB_NAME' from CronJob '$CRONJOB'..."
kubectl create job "$JOB_NAME" --from="cronjob/$CRONJOB" -n "$NAMESPACE"

echo "Waiting for pod to be created..."
POD=""
for ((attempt = 0; attempt < 60; attempt++)); do
  POD=$(kubectl get pods -n "$NAMESPACE" -l "job-name=$JOB_NAME" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) || POD=""
  if [[ -n "$POD" ]]; then
    break
  fi
  sleep 1
done
if [[ -z "$POD" ]]; then
  echo "No pod created for '$JOB_NAME' within 60 seconds." >&2
  exit 1
fi

# A short-lived pod may already have finished before it becomes Ready.
kubectl wait --for=condition=Ready "pod/$POD" -n "$NAMESPACE" --timeout=120s || true
kubectl logs -f "$POD" -n "$NAMESPACE"

# Check the Job as well: the pod may have failed or been retried.
kubectl wait --for=condition=Complete "job/$JOB_NAME" -n "$NAMESPACE" --timeout=120s
echo "Job '$JOB_NAME' completed successfully."
