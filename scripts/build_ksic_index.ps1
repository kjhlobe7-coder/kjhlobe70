$ErrorActionPreference = "Stop"

$sourceUrl = "https://sri.kostat.go.kr/boardDownload.es?bid=107&list_no=428660&seq=5"
$tmpZip = "tmp_ksic11.bin"
$tmpDir = "tmp_ksic11"
$sectionPath = Join-Path $tmpDir "Contents/section1.xml"
$outputPath = "ksic_index_full.json"

if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }

Invoke-WebRequest -Uri $sourceUrl -OutFile $tmpZip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory($tmpZip, $tmpDir)

$raw = Get-Content $sectionPath -Raw -Encoding UTF8
$trs = [regex]::Matches($raw, '<hp:tr>(.*?)</hp:tr>', [Text.RegularExpressions.RegexOptions]::Singleline)

$rows = @()
$lastName = ""
foreach ($tr in $trs) {
  $tcs = [regex]::Matches($tr.Groups[1].Value, '<hp:tc\b.*?>(.*?)</hp:tc>', [Text.RegularExpressions.RegexOptions]::Singleline)
  if ($tcs.Count -lt 2) { continue }

  $code = (([regex]::Matches($tcs[0].Groups[1].Value, '<hp:t>(.*?)</hp:t>', [Text.RegularExpressions.RegexOptions]::Singleline) | ForEach-Object { $_.Groups[1].Value }) -join "") -replace '\s+', ''
  $code = $code.Trim()
  if ($code -notmatch '^(?:[A-U]|\d{2,5})$') { continue }

  $name = (([regex]::Matches($tcs[1].Groups[1].Value, '<hp:t>(.*?)</hp:t>', [Text.RegularExpressions.RegexOptions]::Singleline) | ForEach-Object { $_.Groups[1].Value }) -join " ") -replace '\s+', ' '
  $name = $name.Trim()
  if ($name.Length -gt 0) { $lastName = $name } else { $name = $lastName }
  if ($name.Length -eq 0) { continue }

  $rows += [PSCustomObject]@{ code = $code; name = $name }
}

$map = @{}
foreach ($r in $rows) {
  if (-not $map.ContainsKey($r.code)) {
    $map[$r.code] = [ordered]@{
      code = $r.code
      name = $r.name
      notes = New-Object System.Collections.Generic.List[string]
      include_notes = New-Object System.Collections.Generic.List[string]
      exclude_notes = New-Object System.Collections.Generic.List[string]
      example_notes = New-Object System.Collections.Generic.List[string]
    }
  } else {
    $map[$r.code].name = $r.name
  }
}

$allText = [regex]::Matches($raw, '<hp:t>(.*?)</hp:t>', [Text.RegularExpressions.RegexOptions]::Singleline) | ForEach-Object { $_.Groups[1].Value }
$currentCode = ""
$ignore = @(
  "Numerical List of Titles",
  "KOREAN STANDARD INDUSTRIAL CLASSIFICATION",
  "KSIC-11",
  "KSIC-10",
  "Agriculture",
  "Manufacturing",
  "Services"
)

foreach ($t in $allText) {
  $v = ($t -replace '\s+', ' ').Trim()
  if ($v.Length -eq 0) { continue }

  if ($v -match '^(?:[A-U]|\d{2,5})$') {
    if ($map.ContainsKey($v)) { $currentCode = $v }
    continue
  }
  if (-not $currentCode) { continue }

  if ($ignore | Where-Object { $v -like "*$_*" }) { continue }
  if ($v.Length -lt 4) { continue }
  if ($v -match '^[A-Za-z0-9 .,:;()/-]+$') { continue }

  if ($map[$currentCode].notes.Count -lt 25) {
    $map[$currentCode].notes.Add($v)
  }
  if ($v -match '\uD3EC\uD568') { $map[$currentCode].include_notes.Add($v) } # 포함
  if ($v -match '\uC81C\uC678') { $map[$currentCode].exclude_notes.Add($v) } # 제외
  if ($v -match '\uC608\uC2DC|\uC608:') { $map[$currentCode].example_notes.Add($v) } # 예시/예:
}

function Unique-Trimmed([System.Collections.Generic.List[string]]$list, [int]$max = 12) {
  $seen = @{}
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($x in $list) {
    $k = ($x -replace '\s+', ' ').Trim()
    if ($k.Length -eq 0) { continue }
    if (-not $seen.ContainsKey($k)) {
      $seen[$k] = $true
      $out.Add($k)
      if ($out.Count -ge $max) { break }
    }
  }
  return @($out)
}

$items = $map.GetEnumerator() |
  Sort-Object Name |
  ForEach-Object {
    $obj = $_.Value
    $n = Unique-Trimmed $obj.notes 12
    $inc = Unique-Trimmed $obj.include_notes 8
    $exc = Unique-Trimmed $obj.exclude_notes 8
    $exm = Unique-Trimmed $obj.example_notes 8
    [PSCustomObject]@{
      code = $obj.code
      name = $obj.name
      notes = @($n)
      include_notes = @($inc)
      exclude_notes = @($exc)
      example_notes = @($exm)
    }
  }

$out = [PSCustomObject]@{
  source = $sourceUrl
  generated_at = (Get-Date).ToString("s")
  item_count = $items.Count
  notes_strategy = "section1 code-context extraction"
  items = $items
}

$out | ConvertTo-Json -Depth 7 | Set-Content $outputPath -Encoding UTF8

Write-Output "Generated: $outputPath (items=$($items.Count))"

Remove-Item $tmpZip -Force
Remove-Item $tmpDir -Recurse -Force
