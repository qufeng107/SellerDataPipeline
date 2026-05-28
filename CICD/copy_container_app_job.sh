#!/usr/bin/env bash
set -euo pipefail

# =========================
# 基本配置：每次复制主要改这里
# =========================

RG="rg-amazon-ops"
SRC="sdp-weekly-report-delivery-dev"
DST="sdp-new-job-dev"

# true  = 修改新 Job 的 args
# false = 完全复制源 Job 的 args
OVERRIDE_ARGS="true"

# 只在 OVERRIDE_ARGS="true" 时生效
NEW_ARGS='python scripts/run_automation_stage.py --workflow weekly --phase collect-ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute'


# =========================
# Secret 值：不要提交到 Git
# 可以直接填，也可以先 export 同名变量
# =========================

AMAZON_SP_API_REFRESH_TOKEN=""
AZURE_SQL_USERNAME=""
AMAZON_ADS_CLIENT_ID=""
PASSWORD_REPORT_EMAIL_SMTP=""
USERNAME_REPORT_EMAIL_SMTP=""
AMAZON_LWA_CLIENT_SECRET=""
AZURE_SQL_PASSWORD=""
AMAZON_ADS_CLIENT_SECRET=""
AMAZON_ADS_REFRESH_TOKEN=""
AMAZON_LWA_CLIENT_ID=""


# =========================
# 不需要改下面
# =========================

echo "Source job: $SRC"
echo "Target job: $DST"
echo "Resource group: $RG"
echo

echo "Checking source job..."
az containerapp job show \
  --resource-group "$RG" \
  --name "$SRC" \
  --query "{name:name,state:properties.provisioningState,trigger:properties.configuration.triggerType,image:properties.template.containers[0].image,envCount:length(properties.template.containers[0].env),secretCount:length(properties.configuration.secrets)}" \
  -o yaml

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
  .properties.template.containers[0].env[]
  | select(.secretRef != null)
  | "\(.name) -> \(.secretRef)"
' clone.raw.json

echo
echo "Generating target config..."

if [ "$OVERRIDE_ARGS" = "true" ]; then
  jq --arg dst "$DST" \
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
    del(.identity.principalId, .identity.tenantId)
    | del(
        .properties.provisioningState,
        .properties.eventStreamEndpoint,
        .properties.latestExecutionName,
        .properties.runningStatus,
        .properties.outboundIpAddresses,
        .properties.configuration.identitySettings
      )
    | .properties.template.containers[0].name = $dst
    | .properties.template.containers[0].args = ["-c", $new_args]
    | (.properties.configuration.secrets[] | select(.name == "amazon-sp-api-refresh-token")).value = $amazon_sp_api_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-username")).value = $azure_sql_username
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-id")).value = $amazon_ads_client_id
    | (.properties.configuration.secrets[] | select(.name == "password-report-email-smtp")).value = $password_report_email_smtp
    | (.properties.configuration.secrets[] | select(.name == "username-report-email-smtp")).value = $username_report_email_smtp
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-secret")).value = $amazon_lwa_client_secret
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-password")).value = $azure_sql_password
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-secret")).value = $amazon_ads_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-refresh-token")).value = $amazon_ads_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-id")).value = $amazon_lwa_client_id
  ' clone.raw.json > clone.new.json
else
  jq --arg dst "$DST" \
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
    del(.identity.principalId, .identity.tenantId)
    | del(
        .properties.provisioningState,
        .properties.eventStreamEndpoint,
        .properties.latestExecutionName,
        .properties.runningStatus,
        .properties.outboundIpAddresses,
        .properties.configuration.identitySettings
      )
    | .properties.template.containers[0].name = $dst
    | (.properties.configuration.secrets[] | select(.name == "amazon-sp-api-refresh-token")).value = $amazon_sp_api_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-username")).value = $azure_sql_username
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-id")).value = $amazon_ads_client_id
    | (.properties.configuration.secrets[] | select(.name == "password-report-email-smtp")).value = $password_report_email_smtp
    | (.properties.configuration.secrets[] | select(.name == "username-report-email-smtp")).value = $username_report_email_smtp
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-secret")).value = $amazon_lwa_client_secret
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-password")).value = $azure_sql_password
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-secret")).value = $amazon_ads_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-refresh-token")).value = $amazon_ads_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-id")).value = $amazon_lwa_client_id
  ' clone.raw.json > clone.new.json
fi

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
  --query "{name:name,state:properties.provisioningState,trigger:properties.configuration.triggerType,image:properties.template.containers[0].image,envCount:length(properties.template.containers[0].env),secretCount:length(properties.configuration.secrets),args:properties.template.containers[0].args}" \
  -o yaml

echo
echo "Done. New job created: $DST"
echo "Confirm args before Run now."