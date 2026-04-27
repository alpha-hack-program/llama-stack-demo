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
Optional HTTP(S) proxy env for Helm hook Jobs. Include only .Values http_proxy, https_proxy, and/or no_proxy
when set (e.g. | nindent 8 after a container env: key).
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
{{- with .Values.no_proxy }}
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