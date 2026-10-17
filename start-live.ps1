param(
    [ValidateSet('gemini', 'adk')]
    [string]$Provider = 'gemini',
    [switch]$Evaluate,
    [ValidateSet('onboarding', 'purchasing', 'facilities', 'training')]
    [string]$Case = 'purchasing',
    [switch]$AllCases,
    [switch]$BothProviders,
    [switch]$Plan,
    [ValidateRange(1, 2147483647)]
    [int]$RequestsPerMinute = 5,
    [string]$Model = '',
    [string]$PythonPath = "$PSScriptRoot\.venv-live\Scripts\python.exe"
)

$ErrorActionPreference = 'Stop'
if (($Plan -or $AllCases -or $BothProviders) -and -not $Evaluate) {
    throw '-Plan, -AllCases and -BothProviders require -Evaluate.'
}
if ($AllCases -and $PSBoundParameters.ContainsKey('Case')) {
    throw 'Choose either -Case or -AllCases, not both.'
}
if (-not (Test-Path $PythonPath)) {
    throw 'Create .venv-live with 64-bit Python 3.11+ and install backend\requirements-dev.txt first.'
}
$PythonPath = (Resolve-Path $PythonPath).Path
$originalKey = $env:GEMINI_API_KEY
$originalProvider = $env:KATALYST_AI_PROVIDER
$originalStore = $env:KATALYST_STORE
$originalVertex = $env:GOOGLE_GENAI_USE_VERTEXAI
$originalModel = $env:KATALYST_GEMINI_MODEL
$originalAuth = $env:KATALYST_AUTH_MODE
$location = Get-Location
try {
    Set-Location $PSScriptRoot
    Write-Host 'Use an eligible free-tier model/project. This launcher cannot verify your billing tier or guarantee zero cost.'
    Write-Host 'Use synthetic data only: free-tier content may be used to improve Google products.'
    if (-not $Plan -and -not $env:GEMINI_API_KEY -and -not $env:GOOGLE_API_KEY) {
        $secureKey = Read-Host 'Gemini Developer API key (used only in this process)' -AsSecureString
        $env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
        Remove-Variable secureKey
    }
    if (-not $Plan -and -not $env:GEMINI_API_KEY -and -not $env:GOOGLE_API_KEY) {
        throw 'An API key is required; demo mode will not be substituted.'
    }
    $env:KATALYST_AI_PROVIDER = $Provider
    $env:KATALYST_STORE = 'sqlite'
    $env:KATALYST_AUTH_MODE = 'demo'
    Write-Host 'Local demo identity only. Firebase login is configured separately; do not expose this server publicly.'
    $env:GOOGLE_GENAI_USE_VERTEXAI = 'false'
    if ($Model) {
        $env:KATALYST_GEMINI_MODEL = $Model
    }
    if ($Evaluate) {
        $output = Join-Path $PSScriptRoot ("data\live-evaluation\" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        $evaluationProvider = $Provider
        if ($BothProviders) { $evaluationProvider = 'both' }
        $evaluationArgs = @('backend\evaluate_live.py', '--provider', $evaluationProvider,
                            '--output', $output, '--requests-per-minute', $RequestsPerMinute)
        if ($AllCases) { $evaluationArgs += '--all-cases' }
        else { $evaluationArgs += @('--case', $Case) }
        if ($Model) { $evaluationArgs += @('--model', $Model) }
        if ($Plan) { $evaluationArgs += '--plan' }
        & $PythonPath @evaluationArgs
    } else {
        Set-Location backend
        Write-Host "Configured provider: $Provider. Open http://127.0.0.1:8000; model access is verified on generation."
        & $PythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Live run failed with exit code $LASTEXITCODE; inspect the console and evaluation report."
    }
} finally {
    $env:GEMINI_API_KEY = $originalKey
    $env:KATALYST_AI_PROVIDER = $originalProvider
    $env:KATALYST_STORE = $originalStore
    $env:GOOGLE_GENAI_USE_VERTEXAI = $originalVertex
    $env:KATALYST_GEMINI_MODEL = $originalModel
    $env:KATALYST_AUTH_MODE = $originalAuth
    Set-Location $location
}
