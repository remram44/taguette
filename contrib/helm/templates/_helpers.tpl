{{/*
Expand the name of the chart.
*/}}
{{- define "taguette.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "taguette.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "taguette.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "taguette.labels" -}}
helm.sh/chart: {{ include "taguette.chart" . }}
{{ include "taguette.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "taguette.selectorLabels" -}}
app.kubernetes.io/name: {{ include "taguette.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
The name of the postgres service
*/}}
{{- define "taguette.postgresServiceName" -}}
{{- if .Values.postgres.enabled -}}
{{- include "postgres.fullname" .Subcharts.postgres -}}
{{- if .Values.postgres.serviceName -}}
{{- fail "postgres.serviceName is set but postgres subchart is enabled" -}}
{{- end -}}
{{- else -}}
{{- if empty .Values.postgres.serviceName -}}
{{- fail "postgres.serviceName is not set and postgres subchart is disabled" -}}
{{- end -}}
{{- .Values.postgres.serviceName -}}
{{- end -}}
{{- end -}}

{{/*
The name of the postgres secret
*/}}
{{- define "taguette.postgresSecretName" -}}
{{- $postgresSecretName := get (.Values.postgres.secret | default dict) "name" -}}
{{- if not (empty $postgresSecretName) -}}
  {{- $postgresSecretName -}}
{{- else -}}
  {{- if .Values.postgres.enabled -}}
    {{- include "postgres.fullname" .Subcharts.postgres -}}
  {{- else -}}
    {{- include "taguette.fullname" . -}}-postgres
  {{- end -}}
{{- end -}}
{{- end -}}
