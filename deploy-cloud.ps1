param(
    [string]$ProjectId = 'katalyst-b780e',
    [string]$Region = 'asia-south1',
    [string]$Service = 'katalyst-mvp'
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw 'Install Google Cloud CLI and sign in before deploying.'
}

$required = @(
    'KATALYST_FIREBASE_WEB_API_KEY',
    'KATALYST_FIREBASE_AUTH_DOMAIN',
    'KATALYST_FIREBASE_WEB_APP_ID',
    'KATALYST_JIRA_SITE',
    'KATALYST_JIRA_PROJECT_KEY',
    'KATALYST_JIRA_EMAIL',
    'KATALYST_JIRA_ISSUE_TYPE_ID',
    'KATALYST_JIRA_ALLOWED_UIDS',
    'KATALYST_SMTP_HOST',
    'KATALYST_SMTP_PORT',
    'KATALYST_SMTP_SECURITY',
    'KATALYST_SMTP_USER',
    'KATALYST_SMTP_FROM',
    'KATALYST_EMAIL_ALLOWED_UIDS'
)
$settings = @{
    KATALYST_AUTH_MODE = 'firebase'
    KATALYST_STORE = 'firestore'
    KATALYST_AI_PROVIDER = 'gemini'
    KATALYST_GEMINI_MODEL = 'gemini-3.1-flash-lite'
    GOOGLE_CLOUD_PROJECT = $ProjectId
    GOOGLE_CLOUD_LOCATION = $Region
    GOOGLE_GENAI_USE_VERTEXAI = 'false'
}
$missing = @()
foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $missing += $name
    } else {
        $settings[$name] = $value
    }
}
if ($missing.Count -gt 0) {
    throw ('Run in your configured backend terminal. Missing settings: ' + ($missing -join ', '))
}
foreach ($name in @('KATALYST_FIRESTORE_COLLECTION', 'KATALYST_UPLOAD_BUCKET', 'KATALYST_LIVE_ENABLED', 'KATALYST_LIVE_MODEL', 'KATALYST_LIVE_ALLOWED_UIDS')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $settings[$name] = $value
    }
}

$billing = & gcloud billing projects describe $ProjectId --format='value(billingEnabled)' --quiet
if ($LASTEXITCODE -ne 0 -or "$billing".Trim() -ne 'True') {
    throw 'The target project must have active billing.'
}
$bindings = @()
foreach ($pair in @(
    @('GOOGLE_API_KEY', 'katalyst-gemini-api-key'),
    @('KATALYST_JIRA_API_TOKEN', 'katalyst-jira-api-token'),
    @('KATALYST_SMTP_PASSWORD', 'katalyst-smtp-password')
)) {
    $version = & gcloud secrets versions list $pair[1] "--project=$ProjectId" --filter='state=ENABLED' --sort-by='~createTime' --limit=1 --format='value(name)' --quiet
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace("$version")) {
        throw ('No enabled version for secret: ' + $pair[1])
    }
    $versionId = ("$version".Trim() -split '/')[-1]
    $bindings += ($pair[0] + '=' + $pair[1] + ':' + $versionId)
}

Write-Host 'Deploying a public HTTPS endpoint with Firebase-protected project APIs.'
Write-Host 'Billing can apply. Minimum instances: 0; maximum instances: 1.'
Write-Host 'Per-user AI rate limits are not implemented. Share with a small trusted evaluator group.'
$configPath = Join-Path ([IO.Path]::GetTempPath()) ('katalyst-deploy-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    $json = ConvertTo-Json -InputObject $settings
    [IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    $arguments = @(
        'run', 'deploy', $Service,
        "--project=$ProjectId", "--region=$Region",
        "--source=$PSScriptRoot",
        "--service-account=katalyst-runtime@$ProjectId.iam.gserviceaccount.com",
        "--env-vars-file=$configPath",
        ('--set-secrets=' + ($bindings -join ',')),
        '--allow-unauthenticated',
        '--ingress=all',
        '--min=0', '--max=1',
        '--cpu=1', '--memory=1Gi', '--concurrency=4',
        '--timeout=300', '--cpu-throttling', '--quiet'
    )
    & gcloud @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Cloud Run deployment failed. Review the error above; do not paste secrets into chat.'
    }
    $url = & gcloud run services describe $Service "--project=$ProjectId" "--region=$Region" --format='value(status.url)' --quiet
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace("$url")) {
        throw 'Could not retrieve the deployed service URL.'
    }
    $health = Invoke-RestMethod -Uri ("$url".Trim() + '/api/health')
    if ($health.status -ne 'ok') {
        throw 'The deployed health check did not report ok.'
    }
    Write-Host ('Deployed and responding: ' + "$url".Trim())
    Write-Host 'Next: add this hostname to Firebase Authentication > Settings > Authorized domains.'
    Write-Host 'Then verify sign-in, storage, AI generation, downloads, Jira and email on this URL.'
} finally {
    if (Test-Path -LiteralPath $configPath) {
        Remove-Item -LiteralPath $configPath
    }
}
