param(
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$VoiceName = 'Microsoft Zira Desktop',
    [ValidateRange(-2,5)][int]$Rate = 1
)
$ErrorActionPreference = 'Stop'
$videoOutput = [System.IO.Path]::GetFullPath($Output)
$narrationPath = Join-Path $videoOutput 'narration.json'
if (-not (Test-Path -LiteralPath $narrationPath)) { throw 'Run prepare_submission_video.py first.' }
$scenes = Get-Content -LiteralPath $narrationPath -Raw -Encoding utf8 | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice($VoiceName)
$voice.Rate = $Rate
try {
    foreach ($scene in $scenes) {
        if ($scene.scene -notmatch '^[a-z][a-z0-9_-]*$') { throw 'Unsafe narration scene name.' }
        $wavePath = Join-Path $videoOutput ($scene.scene + '.wav')
        if (Test-Path -LiteralPath $wavePath) { throw 'Narration already exists; preserve it or use a fresh output.' }
        $voice.SetOutputToWaveFile($wavePath)
        $voice.Speak($scene.text)
        $voice.SetOutputToNull()
    }
} finally { $voice.Dispose() }
@{status='LOCAL_SPEECH_RENDERED'; voice=$VoiceName; rate=$Rate; provider_calls=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $videoOutput 'voice.json') -Encoding utf8
Write-Output 'Local English narration rendered. No external speech service was called.'
