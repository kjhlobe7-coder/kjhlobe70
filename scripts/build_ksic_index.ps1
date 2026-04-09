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

$dict = @{}
foreach ($r in $rows) { $dict[$r.code] = $r.name }

$items = $dict.GetEnumerator() |
  Sort-Object Name |
  ForEach-Object { [PSCustomObject]@{ code = $_.Name; name = $_.Value } }

$out = [PSCustomObject]@{
  source = $sourceUrl
  generated_at = (Get-Date).ToString("s")
  item_count = $items.Count
  items = $items
}

$out | ConvertTo-Json -Depth 5 | Set-Content $outputPath -Encoding UTF8

Write-Output "Generated: $outputPath (items=$($items.Count))"

Remove-Item $tmpZip -Force
Remove-Item $tmpDir -Recurse -Force
