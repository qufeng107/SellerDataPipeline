#!/usr/bin/env bash
set -euo pipefail

# =========================
# 需要你修改的配置
# =========================

RG="rg-amazon-ops"

# 源 Job
SRC="sdp-weekly-submit-dev"

# 新 Job
DST="sdp-weekly-collect-ingest-dev"

# 是否覆盖新 Job 的运行参数
# true = 创建后把 args 改成 NEW_ARGS
# false = 完全复制源 Job 的 args
OVERRIDE_ARGS="true"

# 新 Job 的 args，只在 OVERRIDE_ARGS="true" 时生效
# 注意这里目前是 weekly collect-ingest 示例
NEW_ARGS='python scripts/run_automation_stage.py --workflow weekly --phase collect-ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute'

# =========================
# Secret 值：只在 Cloud Shell 里临时填写，不要提交到 Git
# =========================

AMAZON_LWA_CLIENT_SECRET='这里填 amazon-lwa-client-secret'
AMAZON_SP_API_REFRESH_TOKEN='这里填 amazon-sp-api-refresh-token'
AZURE_SQL_PASSWORD='这里填 azure-sql-password'
AZURE_SQL_USERNAME='这里填 azure-sql-username'
AMAZON_ADS_CLIENT_ID='这里填 amazon-ads-client-id'
AMAZON_ADS_CLIENT_SECRET='这里填 amazon-ads-client-secret'
AMAZON_ADS_REFRESH_TOKEN='这里填 amazon-ads-refresh-token'
AMAZON_LWA_CLIENT_ID='这里填 amazon-lwa-client-id'


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
  --query "{name:name, triggerType:properties.configuration.triggerType, image:properties.template.containers[0].image, envCount:length(properties.template.containers[0].env), secretCount:length(properties.configuration.secrets)}" \
  -o yaml

echo
echo "Exporting source job..."
az containerapp job show \
  --resource-group "$RG" \
  --name "$SRC" \
  --query "{location:location,tags:tags,identity:identity,properties:properties}" \
  -o json > clone.raw.json

echo "Generating new job config..."

if [ "$OVERRIDE_ARGS" = "true" ]; then
  jq --arg dst "$DST" \
    --arg new_args "$NEW_ARGS" \
    --arg amazon_lwa_client_secret "$AMAZON_LWA_CLIENT_SECRET" \
    --arg amazon_sp_api_refresh_token "$AMAZON_SP_API_REFRESH_TOKEN" \
    --arg azure_sql_password "$AZURE_SQL_PASSWORD" \
    --arg azure_sql_username "$AZURE_SQL_USERNAME" \
    --arg amazon_ads_client_id "$AMAZON_ADS_CLIENT_ID" \
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
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-secret")).value = $amazon_lwa_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-sp-api-refresh-token")).value = $amazon_sp_api_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-password")).value = $azure_sql_password
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-username")).value = $azure_sql_username
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-id")).value = $amazon_ads_client_id
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-secret")).value = $amazon_ads_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-refresh-token")).value = $amazon_ads_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-id")).value = $amazon_lwa_client_id
  ' clone.raw.json > clone.new.json
else
  jq --arg dst "$DST" \
    --arg amazon_lwa_client_secret "$AMAZON_LWA_CLIENT_SECRET" \
    --arg amazon_sp_api_refresh_token "$AMAZON_SP_API_REFRESH_TOKEN" \
    --arg azure_sql_password "$AZURE_SQL_PASSWORD" \
    --arg azure_sql_username "$AZURE_SQL_USERNAME" \
    --arg amazon_ads_client_id "$AMAZON_ADS_CLIENT_ID" \
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
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-secret")).value = $amazon_lwa_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-sp-api-refresh-token")).value = $amazon_sp_api_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-password")).value = $azure_sql_password
    | (.properties.configuration.secrets[] | select(.name == "azure-sql-username")).value = $azure_sql_username
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-id")).value = $amazon_ads_client_id
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-client-secret")).value = $amazon_ads_client_secret
    | (.properties.configuration.secrets[] | select(.name == "amazon-ads-refresh-token")).value = $amazon_ads_refresh_token
    | (.properties.configuration.secrets[] | select(.name == "amazon-lwa-client-id")).value = $amazon_lwa_client_id
  ' clone.raw.json > clone.new.json
fi

echo "Creating target job..."
SUB=$(az account show --query id -o tsv)

az rest \
  --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.App/jobs/$DST?api-version=2024-03-01" \
  --body @clone.new.json > clone.result.json

echo
echo "Created job summary:"
az containerapp job show \
  --resource-group "$RG" \
  --name "$DST" \
  --query "{name:name, triggerType:properties.configuration.triggerType, image:properties.template.containers[0].image, envCount:length(properties.template.containers[0].env), secretCount:length(properties.configuration.secrets), args:properties.template.containers[0].args}" \
  -o yaml

echo
echo "Done. New job created: $DST"
echo "Do NOT run it until you confirm args are correct."