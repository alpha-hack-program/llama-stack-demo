#!/usr/bin/env bash
# Applies general (cluster-wide) monitoring resources so they exist outside any
# Helm release. The Helm chart then only deploys particular (app-specific)
# resources (Grafana dashboards, datasources, service monitors, DSCI patch).
#
# General resources (this script):
#   - namespace redhat-ods-monitoring
#   - TempoMonolithic (data-science-tempomonolithic)
#   - OpenTelemetryCollector (data-science-collector)
#   - Instrumentation (data-science-instrumentation) for inject-python annotation targets
#   - DSCInitialization monitoring spec (merge patch) so the operator creates Prometheus
#     (data-science-monitoringstack-prometheus)
#
# Particular resources (Helm chart, with monitoring.deployTempo/deployCollector false):
#   - Grafana, GrafanaFolder, GrafanaDatasource, GrafanaDashboard
#   - ServiceMonitors
#
# Usage: ./scripts/setup-monitoring.sh [--dry-run]
# Env:   MANIFESTS_DIR  Directory with general manifests (default: scripts/resources)
#        DSCI_NAME      DSCInitialization name to patch (default: default-dsci)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFESTS_DIR="${MANIFESTS_DIR:-$SCRIPT_DIR/resources}"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

run() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

if [[ ! -d "$MANIFESTS_DIR" ]]; then
  echo "Error: manifests directory not found: $MANIFESTS_DIR" >&2
  exit 1
fi

echo "Applying general monitoring manifests from: $MANIFESTS_DIR"
echo ""

# True if the cluster serves the given API group (operator installed). Targeted
# discovery call — reliable even when an unrelated aggregated APIService flakes.
api_group_available() { oc get --raw "/apis/$1" >/dev/null 2>&1; }

# Apply only full resource manifests (namespace, Tempo, OTel collector, Instrumentation). Do not apply
# dsci-monitoring-patch.yaml here — it is a merge patch (no apiVersion/kind), used below with oc patch.
# Skip a manifest when its operator/CRD is absent so the apply does not hard-fail.
for f in namespace.yaml tempo-monolithic.yaml otel-collector.yaml data-science-instrumentation.yaml; do
  [[ -f "$MANIFESTS_DIR/$f" ]] || continue
  if [[ "$DRY_RUN" == false ]]; then
    case "$f" in
      tempo-monolithic.yaml)
        if ! api_group_available tempo.grafana.com; then
          echo "Tempo operator not installed (tempo.grafana.com); skipping $f."
          continue
        fi ;;
      otel-collector.yaml|data-science-instrumentation.yaml)
        if ! api_group_available opentelemetry.io; then
          echo "OpenTelemetry operator not installed (opentelemetry.io); skipping $f."
          continue
        fi ;;
    esac
  fi
  run oc apply -f "$MANIFESTS_DIR/$f"
done

# 4. Patch DSCInitialization so the OpenShift AI operator deploys the monitoring stack
#    (Prometheus service data-science-monitoringstack-prometheus).
#    Required for Grafana datasources; Instrumentation is applied above for OTel injection in workloads.
#    Safe to run multiple times or after a manual patch: merge patch is idempotent.
DSCI_PATCH="$MANIFESTS_DIR/dsci-monitoring-patch.yaml"
DSCI_NAME="${DSCI_NAME:-default-dsci}"
if [[ -f "$DSCI_PATCH" ]]; then
  if oc get dscinitialization "$DSCI_NAME" &>/dev/null; then
    echo "Patching DSCInitialization/$DSCI_NAME with monitoring spec (enables Prometheus and instrumentation)..."
    run oc patch dscinitialization "$DSCI_NAME" --type=merge --patch-file "$DSCI_PATCH"
  else
    echo "DSCInitialization/$DSCI_NAME not found; skipping DSCI monitoring patch (cluster may not have OpenShift AI)."
  fi
fi

echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "Dry-run finished. Run without --dry-run to apply."
else
  echo "Done. General monitoring resources are in place. Deploy the Helm chart with monitoring.deployTempo and monitoring.deployCollector set to false so it only manages particular (app-specific) resources."
fi
