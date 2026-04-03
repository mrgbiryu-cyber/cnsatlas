param(
  [Parameter(Mandatory = $true)][string]$InputPptx,
  [Parameter(Mandatory = $true)][string]$OutputDir,
  [Parameter(Mandatory = $true)][string]$Slides,
  [int]$Width = 0,
  [int]$Height = 0
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $InputPptx)) {
  throw "Input PPTX not found: $InputPptx"
}

if (!(Test-Path -LiteralPath $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$slideNos = @()
foreach ($token in ($Slides -split ",")) {
  $trimmed = $token.Trim()
  if ($trimmed -eq "") { continue }
  $slideNos += [int]$trimmed
}
if ($slideNos.Count -eq 0) {
  throw "No slide numbers provided."
}

$ppApp = $null
$presentation = $null
try {
  $ppApp = New-Object -ComObject PowerPoint.Application
  $presentation = $ppApp.Presentations.Open($InputPptx, $false, $true, $false)

  foreach ($slideNo in $slideNos) {
    if ($slideNo -lt 1 -or $slideNo -gt $presentation.Slides.Count) {
      continue
    }
    $slide = $presentation.Slides.Item($slideNo)
    $outputPath = Join-Path $OutputDir ("slide-" + $slideNo + ".png")
    if ($Width -gt 0 -and $Height -gt 0) {
      $slide.Export($outputPath, "PNG", $Width, $Height)
    } else {
      $slide.Export($outputPath, "PNG")
    }
    Write-Output $outputPath
  }
}
finally {
  if ($presentation -ne $null) {
    $presentation.Close()
  }
  if ($ppApp -ne $null) {
    $ppApp.Quit()
  }
}
