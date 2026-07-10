param(
    [string]$HostName = '192.168.1.142',
    [int]$Port = 22,
    [string]$User = 'minecraft',
    [string]$SshPassword = $env:AI_MODER_SSH_PASSWORD,
    [string]$RootPassword = $env:AI_MODER_ROOT_PASSWORD,
    [string]$Archive = (Join-Path $env:TEMP 'ai-moder-release.tar.gz'),
    [string]$RemoteArchive = '/tmp/ai-moder-release.tar.gz',
    [string]$RemoteDeployScript = '/tmp/ai_moder_deploy.sh',
    [string]$RemoteEnvFile = '/tmp/ai-moder.env',
    [string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) '.env'),
    [string]$Services = 'ai-moder.service'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SshPassword)) {
    throw 'SshPassword is required. Pass -SshPassword or set AI_MODER_SSH_PASSWORD.'
}

if ([string]::IsNullOrWhiteSpace($RootPassword)) {
    throw 'RootPassword is required. Pass -RootPassword or set AI_MODER_ROOT_PASSWORD.'
}

$deployScript = Join-Path $PSScriptRoot 'ai_moder_deploy.sh'
if (-not (Test-Path -LiteralPath $deployScript)) {
    throw "Deploy script was not found: $deployScript"
}

& (Join-Path $PSScriptRoot 'build_ai_moder_release.ps1') -Archive $Archive

pscp.exe -batch -P $Port -pw $SshPassword $Archive "${User}@${HostName}:$RemoteArchive"
pscp.exe -batch -P $Port -pw $SshPassword $deployScript "${User}@${HostName}:$RemoteDeployScript"
if (-not (Test-Path -LiteralPath $EnvFile)) { throw "Local .env was not found: $EnvFile" }
pscp.exe -batch -P $Port -pw $SshPassword $EnvFile "${User}@${HostName}:$RemoteEnvFile"

$remoteCommand = "chmod +x $RemoteDeployScript; printf '%s\n' '$RootPassword' | su root -c 'SERVICES=""$Services"" ARCHIVE=$RemoteArchive ENV_FILE=$RemoteEnvFile APP_DIR=/opt/ai-moder $RemoteDeployScript'"
plink.exe -batch -ssh "${User}@${HostName}" -P $Port -pw $SshPassword $remoteCommand

$statusCommand = "systemctl is-active $Services"
plink.exe -batch -ssh "${User}@${HostName}" -P $Port -pw $SshPassword $statusCommand
