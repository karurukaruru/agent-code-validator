$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$videoDir = Join-Path $taskRoot 'dist/live-video'
New-Item -ItemType Directory -Force -Path $videoDir | Out-Null
$scenes = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'live_video_narration.json') -Raw -Encoding utf8 | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice('Microsoft Zira Desktop')
$voice.Rate = 1
try {
    foreach ($scene in $scenes) {
        $voice.SetOutputToWaveFile((Join-Path $videoDir ($scene.scene + '.wav')))
        $voice.Speak($scene.text)
        $voice.SetOutputToNull()
    }
} finally { $voice.Dispose() }
Write-Output 'Local English narration rendered; no external speech API used.'
