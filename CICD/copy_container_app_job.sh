#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Azure Container Apps Job clone helper
# - Clone an existing job config
# - Optionally override args/image
# - Choose Manual or Schedule BEFORE PUT creation
# - Re-inject secret values from shell env vars
#
# Do NOT commit this file after filling secrets.
# ============================================================

# =========================
# 每次复制主要改这里
# =========================

RG="rg-amazon-ops"

# 建议一一对应复制：
#   sdp-weekly-submit-dev          -> sdp-weekly-submit
#   sdp-weekly-collect-ingest-dev  -> sdp-weekly-collect-ingest
#   sdp-weekly-report-delivery-dev -> sdp-weekly-report-delivery
SRC="sdp-monthly-report-delivery-dev"
DST="sdp-monthly-report-delivery"

# 正式周报建议用 main；留空则沿用源 job image。
TARGET_IMAGE="ghcr.io/qufeng107/seller-data-pipeline:main"
TARGET_IMAGE_TAG="${TARGET_IMAGE##*:}"

# Manual 或 Schedule。注意：用 PUT 创建时直接创建成对应类型。
TARGET_TRIGGER_TYPE="Schedule"

# 只在 TARGET_TRIGGER_TYPE="Schedule" 时生效。Azure cron 使用 UTC。
# weekly submit:          0 6 * * 1
# weekly collect_ingest:  0 9 * * 1
# weekly report_delivery: 0 10 * * 1
CRON_EXPRESSION="0 6 6 * *"

# true  = 修改新 Job 的 args
# false = 完全复制源 Job 的 args
OVERRIDE_ARGS="true"

# 只在 OVERRIDE_ARGS="true" 时生效。
# 注意 collect phase 是 collect_ingest，不是 collect-ingest。
NEW_ARGS='python scripts/run_automation_stage.py --workflow monthly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --send-email --email-to feng@cuidena.cn'

# 如果目标 job 已存在，默认停止，避免误覆盖。
# 真要覆盖时改成 true。
ALLOW_OVERWRITE="false"

# true = 源 job 里出现的已知 secret，必须在 shell env 中有值；否则退出。
# 正式创建建议保持 true。
REQUIRE_SECRET_VALUES="true"


# =========================
# Secret 值：不要提交到 Git
# =========================

# export AMAZON_LWA_CLIENT_SECRET=''
# export AMAZON_SP_API_REFRESH_TOKEN=''
# export AZURE_SQL_PASSWORD=''
# export AZURE_SQL_USERNAME=''
# export AMAZON_ADS_CLIENT_ID=''
# export AMAZON_ADS_CLIENT_SECRET=''
# export AMAZON_ADS_REFRESH_TOKEN=''
# export AMAZON_LWA_CLIENT_ID=''
# export PASSWORD_REPORT_EMAIL_SMTP=''
# export USERNAME_REPORT_EMAIL_SMTP=''


AMAZON_SP_API_REFRESH_TOKEN="${AMAZON_SP_API_REFRESH_TOKEN:-}"
AZURE_SQL_USERNAME="${AZURE_SQL_USERNAME:-}"
AMAZON_ADS_CLIENT_ID="${AMAZON_ADS_CLIENT_ID:-}"
PASSWORD_REPORT_EMAIL_SMTP="${PASSWORD_REPORT_EMAIL_SMTP:-}"
USERNAME_REPORT_EMAIL_SMTP="${USERNAME_REPORT_EMAIL_SMTP:-}"
AMAZON_LWA_CLIENT_SECRET="${AMAZON_LWA_CLIENT_SECRET:-}"
AZURE_SQL_PASSWORD="${AZURE_SQL_PASSWORD:-}"
AMAZON_ADS_CLIENT_SECRET="${AMAZON_ADS_CLIENT_SECRET:-}"
AMAZON_ADS_REFRESH_TOKEN="${AMAZON_ADS_REFRESH_TOKEN:-}"
AMAZON_LWA_CLIENT_ID="${AMAZON_LWA_CLIENT_ID:-}"


# =========================
# 不需要改下面
# =========================

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 1
  }
}

secret_env_name_for() {
  case "$1" in
    amazon-sp-api-refresh-token) echo "AMAZON_SP_API_REFRESH_TOKEN" ;;
    azure-sql-username) echo "AZURE_SQL_USERNAME" ;;
    amazon-ads-client-id) echo "AMAZON_ADS_CLIENT_ID" ;;
    password-report-email-smtp) echo "PASSWORD_REPORT_EMAIL_SMTP" ;;
    username-report-email-smtp) echo "USERNAME_REPORT_EMAIL_SMTP" ;;
    amazon-lwa-client-secret) echo "AMAZON_LWA_CLIENT_SECRET" ;;
    azure-sql-password) echo "AZURE_SQL_PASSWORD" ;;
    amazon-ads-client-secret) echo "AMAZON_ADS_CLIENT_SECRET" ;;
    amazon-ads-refresh-token) echo "AMAZON_ADS_REFRESH_TOKEN" ;;
    amazon-lwa-client-id) echo "AMAZON_LWA_CLIENT_ID" ;;
    *) echo "" ;;
  esac
}

require_cmd az
require_cmd jq

case "$TARGET_TRIGGER_TYPE" in
  Manual|Schedule) ;;
  *)
    echo "ERROR: TARGET_TRIGGER_TYPE must be Manual or Schedule, got: $TARGET_TRIGGER_TYPE" >&2
    exit 1
    ;;
esac

if [ "$TARGET_TRIGGER_TYPE" = "Schedule" ] && [ -z "$CRON_EXPRESSION" ]; then
  echo "ERROR: CRON_EXPRESSION is required when TARGET_TRIGGER_TYPE=Schedule" >&2
  exit 1
fi

if [ "$OVERRIDE_ARGS" != "true" ] && [ "$OVERRIDE_ARGS" != "false" ]; then
  echo "ERROR: OVERRIDE_ARGS must be true or false, got: $OVERRIDE_ARGS" >&2
  exit 1
fi

if [ "$ALLOW_OVERWRITE" != "true" ] && [ "$ALLOW_OVERWRITE" != "false" ]; then
  echo "ERROR: ALLOW_OVERWRITE must be true or false, got: $ALLOW_OVERWRITE" >&2
  exit 1
fi

echo "Source job: $SRC"
echo "Target job: $DST"
echo "Resource group: $RG"
echo "Target trigger: $TARGET_TRIGGER_TYPE"
if [ "$TARGET_TRIGGER_TYPE" = "Schedule" ]; then
  echo "Cron expression (UTC): $CRON_EXPRESSION"
fi
if [ -n "$TARGET_IMAGE" ]; then
  echo "Target image: $TARGET_IMAGE"
else
  echo "Target image: copy source image"
fi
echo

echo "Checking source job..."
az containerapp job show \
  --resource-group "$RG" \
  --name "$SRC" \
  --query "{name:name,state:properties.provisioningState,trigger:properties.configuration.triggerType,image:properties.template.containers[0].image,envCount:length(properties.template.containers[0].env),secretCount:length(properties.configuration.secrets)}" \
  -o yaml

echo
if az containerapp job show --resource-group "$RG" --name "$DST" >/dev/null 2>&1; then
  if [ "$ALLOW_OVERWRITE" != "true" ]; then
    echo "ERROR: target job already exists: $DST" >&2
    echo "Set ALLOW_OVERWRITE=true only if you intentionally want to overwrite it." >&2
    exit 1
  fi
  echo "WARNING: target job already exists and ALLOW_OVERWRITE=true; PUT will overwrite: $DST"
fi

echo
echo "Exporting source job..."
az containerapp job show \
  --resource-group "$RG" \
  --name "$SRC" \
  --query "{location:location,tags:tags,identity:identity,properties:properties}" \
  -o json > clone.raw.json

echo
echo "Source command / args:"
jq -r '
  .properties.template.containers[0]
  | "command: " + (.command | tostring) + "\nargs: " + (.args | tostring)
' clone.raw.json

echo
echo "Source secret refs:"
jq -r '
  .properties.template.containers[0].env[]?
  | select(.secretRef != null)
  | "\(.name) -> \(.secretRef)"
' clone.raw.json

echo
echo "Checking secret values supplied in shell env..."
missing_secret=0
unknown_secret=0
while IFS= read -r secret_name; do
  [ -z "$secret_name" ] && continue
  env_name="$(secret_env_name_for "$secret_name")"
  if [ -z "$env_name" ]; then
    echo "ERROR: no env-var mapping for source secret: $secret_name" >&2
    echo "Add it in secret_env_name_for() and jq secret assignment block." >&2
    unknown_secret=1
    continue
  fi

  env_value="${!env_name:-}"
  if [ -z "$env_value" ]; then
    echo "MISSING: $secret_name <- \\$$env_name" >&2
    missing_secret=1
  else
    echo "OK: $secret_name <- \\$$env_name"
  fi
done < <(jq -r '.properties.configuration.secrets[]?.name' clone.raw.json)

if [ "$unknown_secret" -ne 0 ]; then
  exit 1
fi

if [ "$REQUIRE_SECRET_VALUES" = "true" ] && [ "$missing_secret" -ne 0 ]; then
  echo >&2
  echo "ERROR: one or more required secret values are missing." >&2
  echo "Export them before running this script, or set REQUIRE_SECRET_VALUES=false only for inspection." >&2
  exit 1
fi

echo
echo "Generating target config..."

jq \
  --arg dst "$DST" \
  --arg rg "$RG" \
  --arg target_image "$TARGET_IMAGE" \
  --arg target_image_tag "$TARGET_IMAGE_TAG" \
  --arg target_trigger_type "$TARGET_TRIGGER_TYPE" \
  --arg cron_expression "$CRON_EXPRESSION" \
  --arg override_args "$OVERRIDE_ARGS" \
  --arg new_args "$NEW_ARGS" \
  --arg amazon_sp_api_refresh_token "$AMAZON_SP_API_REFRESH_TOKEN" \
  --arg azure_sql_username "$AZURE_SQL_USERNAME" \
  --arg amazon_ads_client_id "$AMAZON_ADS_CLIENT_ID" \
  --arg password_report_email_smtp "$PASSWORD_REPORT_EMAIL_SMTP" \
  --arg username_report_email_smtp "$USERNAME_REPORT_EMAIL_SMTP" \
  --arg amazon_lwa_client_secret "$AMAZON_LWA_CLIENT_SECRET" \
  --arg azure_sql_password "$AZURE_SQL_PASSWORD" \
  --arg amazon_ads_client_secret "$AMAZON_ADS_CLIENT_SECRET" \
  --arg amazon_ads_refresh_token "$AMAZON_ADS_REFRESH_TOKEN" \
  --arg amazon_lwa_client_id "$AMAZON_LWA_CLIENT_ID" '
  def set_secret($name; $value):
    (.properties.configuration.secrets[]? | select(.name == $name)).value = $value;

  def upsert_env($name; $value):
    if $value == "" then .
    else
      .properties.template.containers[0].env = (
        ((.properties.template.containers[0].env // []) | map(select(.name != $name)))
        + [{name: $name, value: $value}]
      )
    end;

  del(.identity.principalId, .identity.tenantId)
  | del(
      .properties.provisioningState,
      .properties.eventStreamEndpoint,
      .properties.latestExecutionName,
      .properties.runningStatus,
      .properties.outboundIpAddresses,
      .properties.configuration.identitySettings
    )

  # Azure show/export may include read-only or Portal-only fields that PUT does not accept.
  | (.properties.template.containers[]? |= del(.imageType))
  | (.properties.template.initContainers[]? |= del(.imageType))

  # Target container identity.
  | .properties.template.containers[0].name = $dst

  # Optional image override.
  | if $target_image != "" then
      .properties.template.containers[0].image = $target_image
    else . end

  # Optional args override. Force the known-good /bin/sh -c pattern.
  | if $override_args == "true" then
      .properties.template.containers[0].command = ["/bin/sh"]
      | .properties.template.containers[0].args = ["-c", $new_args]
    else . end

  # Create as Manual or Schedule directly during PUT.
  | if $target_trigger_type == "Schedule" then
      .properties.configuration.triggerType = "Schedule"
      | .properties.configuration.scheduleTriggerConfig = {
          cronExpression: $cron_expression,
          parallelism: (.properties.configuration.manualTriggerConfig.parallelism // .properties.configuration.scheduleTriggerConfig.parallelism // 1),
          replicaCompletionCount: (.properties.configuration.manualTriggerConfig.replicaCompletionCount // .properties.configuration.scheduleTriggerConfig.replicaCompletionCount // 1)
        }
      | del(.properties.configuration.manualTriggerConfig, .properties.configuration.eventTriggerConfig)
    else
      .properties.configuration.triggerType = "Manual"
      | .properties.configuration.manualTriggerConfig = {
          parallelism: (.properties.configuration.manualTriggerConfig.parallelism // .properties.configuration.scheduleTriggerConfig.parallelism // 1),
          replicaCompletionCount: (.properties.configuration.manualTriggerConfig.replicaCompletionCount // .properties.configuration.scheduleTriggerConfig.replicaCompletionCount // 1)
        }
      | del(.properties.configuration.scheduleTriggerConfig, .properties.configuration.eventTriggerConfig)
    end

  # Add non-secret audit metadata so pipeline_job_run can identify the Azure job/config.
  | upsert_env("SDP_AZURE_RESOURCE_GROUP"; $rg)
  | upsert_env("SDP_AZURE_JOB_NAME"; $dst)
  | upsert_env("SDP_CONFIGURED_TRIGGER_TYPE"; $target_trigger_type)
  | upsert_env("SDP_CONTAINER_IMAGE"; $target_image)
  | upsert_env("SDP_IMAGE_TAG"; $target_image_tag)

  # Re-inject known secret values. Azure cannot reliably export secret values from the source job.
  | set_secret("amazon-sp-api-refresh-token"; $amazon_sp_api_refresh_token)
  | set_secret("azure-sql-username"; $azure_sql_username)
  | set_secret("amazon-ads-client-id"; $amazon_ads_client_id)
  | set_secret("password-report-email-smtp"; $password_report_email_smtp)
  | set_secret("username-report-email-smtp"; $username_report_email_smtp)
  | set_secret("amazon-lwa-client-secret"; $amazon_lwa_client_secret)
  | set_secret("azure-sql-password"; $azure_sql_password)
  | set_secret("amazon-ads-client-secret"; $amazon_ads_client_secret)
  | set_secret("amazon-ads-refresh-token"; $amazon_ads_refresh_token)
  | set_secret("amazon-lwa-client-id"; $amazon_lwa_client_id)
' clone.raw.json > clone.new.json

echo
echo "Planned target summary from clone.new.json:"
jq -r '
  {
    triggerType: .properties.configuration.triggerType,
    cron: .properties.configuration.scheduleTriggerConfig.cronExpression,
    image: .properties.template.containers[0].image,
    command: .properties.template.containers[0].command,
    args: .properties.template.containers[0].args,
    envCount: (.properties.template.containers[0].env | length),
    secretCount: (.properties.configuration.secrets | length)
  }
' clone.new.json

echo
echo "Creating target job..."
SUB="$(az account show --query id -o tsv)"

az rest \
  --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.App/jobs/$DST?api-version=2024-03-01" \
  --body @clone.new.json > clone.result.json

echo
echo "Created job summary:"
az containerapp job show \
  --resource-group "$RG" \
  --name "$DST" \
  --query "{name:name,state:properties.provisioningState,trigger:properties.configuration.triggerType,cron:properties.configuration.scheduleTriggerConfig.cronExpression,image:properties.template.containers[0].image,envCount:length(properties.template.containers[0].env),secretCount:length(properties.configuration.secrets),args:properties.template.containers[0].args}" \
  -o yaml

echo
echo "Done. New job created: $DST"
echo "Confirm trigger/image/args before waiting for the scheduled run."
