{{/*
Sanitize name for environment variable usage
*/}}
{{- define "rag-lsd.envVarName" -}}
{{- . | replace " " "_" | replace "-" "_" | replace "." "_" | replace "/" "_" | replace ":" "_" | upper -}}
{{- end -}}

{{/*
Expose .Values.assigned for use in templates. Wrapped in "value" key for fromYaml.
*/}}
{{- define "assigned" -}}
{{- dict "value" (.Values.assigned | default "") | toYaml -}}
{{- end -}}

{{/*
Combine localModels and remoteModels into a single list.
This allows localModels to be in values.yaml (git) and remoteModels in values-secrets.yaml (not in git).
Wrapped in "items" key because fromYaml doesn't handle root-level lists.
*/}}
{{- define "allModels" -}}
{{- $local := .Values.localModels | default list -}}
{{- $remote := .Values.remoteModels | default list -}}
{{- dict "items" (concat $local $remote) | toYaml -}}
{{- end -}}

{{/*
True when this model entry owns a KServe InferenceService (and optional OCI connection Secret).

Excludes: .url (off-cluster / explicit endpoint), inline::sentence-transformers, and .forcedName
(*-remote-style rows that reuse another predictor — no duplicate IS or modelcar URI secret).
*/}}
{{- define "rag-lsd.modelUsesKserve" -}}
{{- $m := . -}}
{{- if and (not $m.url) (not $m.forcedName) (ne (default "" $m.providerType) "inline::sentence-transformers") (or $m.image $m.connection) -}}true{{- end -}}
{{- end -}}

{{/*
In-cluster OpenAI-compatible /v1 base URL for the KServe predictor <base>-predictor in the release
namespace. Pass (dict "root" $ "model" <model>) from a range over allModels.

The host base is coalesce(forcedName, name). Use forcedName for a *-remote-style entry so it points at
the sibling predictor; for the entry that creates the IS, usually omit forcedName, or set url.
*/}}
{{- define "rag-lsd.inClusterPredictorV1URL" -}}
{{- $r := index . "root" -}}
{{- $m := index . "model" -}}
{{- $base := coalesce $m.forcedName $m.name -}}
http://{{ $base }}-predictor.{{ $r.Release.Namespace }}.svc.{{ $r.Values.clusterDomain | default "cluster.local" }}:8080/v1
{{- end -}}

{{/*
In-cluster MCP endpoint URI for a server entry in .Values.mcpServers.
Pass (dict "root" $ "server" <mcpServer>) from ranges over mcpServers.
*/}}
{{- define "rag-lsd.inClusterMcpURI" -}}
{{- $r := index . "root" -}}
{{- $s := index . "server" -}}
{{- $protocol := $s.protocol | default "http" -}}
{{- $uri := $s.uri | default "" -}}
{{ $protocol }}://{{ $s.host }}.{{ $r.Release.Namespace }}.svc.{{ $r.Values.clusterDomain | default "cluster.local" }}:{{ $s.port }}{{ $uri }}
{{- end -}}

{{/*
Expand the name of the chart.
*/}}
{{- define "rag-lsd.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rag-lsd.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Effective NO_PROXY / no_proxy: .Values.no_proxy plus in-cluster service hostnames when a proxy is in use.

Short names like "milvus-service" do not match "no_proxy" patterns such as .cluster.local or .svc, so
gRPC (e.g. pymilvus) would otherwise try the HTTP proxy and fail. When http(s)_proxy is set, we append
.postgres.host (when .Values.postgres) and .milvus.host (when .milvus.enableRemote).
*/}}
{{- define "rag-lsd.mergedNoProxy" -}}
{{- $m := .Values.no_proxy | default "" -}}
{{- if or .Values.http_proxy .Values.https_proxy -}}
{{- if .Values.postgres -}}
  {{- $ph := .Values.postgres.host | default "pg-lsd-service" -}}
  {{- if $m -}}
    {{- $m = printf "%s,%s" $m $ph -}}
  {{- else -}}
    {{- $m = $ph -}}
  {{- end -}}
{{- end -}}
{{- if and .Values.milvus .Values.milvus.enableRemote -}}
  {{- $mh := .Values.milvus.host | default "milvus-service" -}}
  {{- if $m -}}
    {{- $m = printf "%s,%s" $m $mh -}}
  {{- else -}}
    {{- $m = $mh -}}
  {{- end -}}
{{- end -}}
{{- end -}}
{{- $m -}}
{{- end -}}

{{/*
Optional HTTP(S) proxy env from .Values http_proxy, https_proxy, and/or no_proxy when set.
NO_PROXY uses rag-lsd.mergedNoProxy (see above). Used for hook Jobs, LSD (lsd.yaml), and models.yaml;
pipe through | nindent 8 under container env:.
*/}}
{{- define "rag-lsd.hookProxyEnv" -}}
{{- with .Values.http_proxy }}
- name: HTTP_PROXY
  value: {{ . | quote }}
- name: http_proxy
  value: {{ . | quote }}
{{- end }}
{{- with .Values.https_proxy }}
- name: HTTPS_PROXY
  value: {{ . | quote }}
- name: https_proxy
  value: {{ . | quote }}
{{- end }}
{{- $n := include "rag-lsd.mergedNoProxy" . | trim -}}
{{- with $n }}
- name: NO_PROXY
  value: {{ . | quote }}
- name: no_proxy
  value: {{ . | quote }}
{{- end }}
{{- end -}}

{{/*
Optional pip / PyPI settings for jobs and KFP step pods (same as rag-pipeline-config when set).
*/}}
{{- define "rag-lsd.hookPipEgressEnv" -}}
{{- with .Values.pip_index_url }}
- name: PIP_INDEX_URL
  value: {{ . | quote }}
{{- end }}
{{- with .Values.pip_extra_index_url }}
- name: PIP_EXTRA_INDEX_URL
  value: {{ . | quote }}
{{- end }}
{{- with .Values.pip_trusted_host }}
- name: PIP_TRUSTED_HOST
  value: {{ . | quote }}
{{- end }}
{{- end -}}

{{/*
Proxy + pip env for hook Jobs and for compile-time pipeline upload (so ConfigMap keys match use_config_map_as_env).
*/}}
{{- define "rag-lsd.hookEgressEnv" -}}
{{- include "rag-lsd.hookProxyEnv" . -}}
{{- include "rag-lsd.hookPipEgressEnv" . -}}
{{- end -}}