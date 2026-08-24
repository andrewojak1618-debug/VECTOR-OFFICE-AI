"""Hält die feste Windows-OneCore-Skriptvorlage ohne Laufzeitlogik."""


ONECORE_TTS_SCRIPT = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]

$text = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__TEXT__')
)
$voiceName = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__VOICE__')
)
$outputPath = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__OUTPUT__')
)
$isSsml = '__IS_SSML__' -eq 'true'

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object DisplayName -eq $voiceName |
    Where-Object Language -eq 'de-DE' |
    Select-Object -First 1

if ($null -eq $voice) {
    throw "German TTS voice not found: $voiceName"
}

$synth.Voice = $voice
if ($isSsml) {
    $operation = $synth.SynthesizeSsmlToStreamAsync($text)
} else {
    $operation = $synth.SynthesizeTextToStreamAsync($text)
}
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1
    } |
    Select-Object -First 1
$task = $asTask.MakeGenericMethod(
    [Windows.Media.SpeechSynthesis.SpeechSynthesisStream]
).Invoke($null, @($operation))
$task.Wait()

$speechStream = $task.Result
$inputStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead(
    $speechStream
)
$fileStream = [System.IO.File]::Create($outputPath)

try {
    $inputStream.CopyTo($fileStream)
} finally {
    $fileStream.Dispose()
    $inputStream.Dispose()
    $speechStream.Dispose()
    $synth.Dispose()
}
"""
