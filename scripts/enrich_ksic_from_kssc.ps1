$ErrorActionPreference = "Stop"

$detailUrl = "https://kssc.mods.go.kr:8443/ksscNew_web/kssc/common/ClassificationContentMainTreeListView.do"
$jsonPath = "ksic_index_full.json"

if (-not (Test-Path $jsonPath)) {
  throw "Missing file: $jsonPath"
}

$data = Get-Content -Raw -Encoding UTF8 $jsonPath | ConvertFrom-Json
$items = @($data.items)

$hdrDesc = "$([char]0xC124)$([char]0xBA85)"      # 설명
$hdrIndex = "$([char]0xC0C9)$([char]0xC778)$([char]0xC5B4)"  # 색인어
$markInc = "$([char]0xD3EC)$([char]0xD568)"      # 포함
$markExc = "$([char]0xC81C)$([char]0xC678)"      # 제외
$markExm = "$([char]0xC608)$([char]0xC2DC)"      # 예시

function Normalize-List([object[]]$arr, [int]$max = 10) {
  $seen = @{}
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($x in $arr) {
    $v = [System.Net.WebUtility]::HtmlDecode([string]$x)
    $v = ($v -replace '\s+', ' ').Trim()
    $v = $v -replace '^[\s\-\*]+', ''
    if (-not $v) { continue }
    if (-not $seen.ContainsKey($v)) {
      $seen[$v] = $true
      $out.Add($v)
      if ($out.Count -ge $max) { break }
    }
  }
  return @($out)
}

function Extract-CellByHeader([string]$html, [string]$headerText) {
  $pat = "(?is)<th[^>]*>\s*$([regex]::Escape($headerText))\s*</th>\s*<td[^>]*>(.*?)</td>"
  $m = [regex]::Match($html, $pat)
  if (-not $m.Success) { return "" }
  $x = $m.Groups[1].Value
  $x = [regex]::Replace($x, '(?is)<!--.*?-->', '')
  $x = [regex]::Replace($x, '(?i)<br\s*/?>', "`n")
  $x = [regex]::Replace($x, '<[^>]+>', ' ')
  $x = [System.Net.WebUtility]::HtmlDecode($x)
  return $x
}

function Parse-Detail([string]$html) {
  $desc = Extract-CellByHeader $html $hdrDesc
  $idx = Extract-CellByHeader $html $hdrIndex

  $notes = New-Object System.Collections.Generic.List[string]
  $includes = New-Object System.Collections.Generic.List[string]
  $excludes = New-Object System.Collections.Generic.List[string]
  $examples = New-Object System.Collections.Generic.List[string]

  if ($desc) {
    $section = "notes"
    $lines = $desc -split "`n"
    foreach ($line in $lines) {
      $v = ($line -replace '\s+', ' ').Trim()
      if (-not $v) { continue }
      if ($v -eq $markInc) { $section = "inc"; continue }
      if ($v -eq $markExc) { $section = "exc"; continue }
      if ($v -eq $markExm) { $section = "exm"; continue }
      switch ($section) {
        "notes" { $notes.Add($v) }
        "inc" { $includes.Add($v) }
        "exc" { $excludes.Add($v) }
        "exm" { $examples.Add($v) }
      }
    }
  }

  if ($idx) {
    $tokens = $idx -split '[,;]'
    foreach ($t in $tokens) {
      $v = ($t -replace '\s+', ' ').Trim()
      if ($v) { $includes.Add($v) }
    }
  }

  return [PSCustomObject]@{
    notes = Normalize-List @($notes) 8
    include_notes = Normalize-List @($includes) 12
    exclude_notes = Normalize-List @($excludes) 10
    example_notes = Normalize-List @($examples) 10
  }
}

$updated = 0
$failed = 0
$total = $items.Count

for ($i = 0; $i -lt $total; $i++) {
  $item = $items[$i]
  $code = [string]$item.code
  if ($code -match '^[A-U]$') { continue }

  $body = "strCategoryNameCode=001" + "&" +
          "strCategoryCode=$code" + "&" +
          "strCategoryDegree=11" + "&" +
          "pageIndex=1" + "&" +
          "categoryMenu=007"

  try {
    $resp = Invoke-WebRequest -Uri $detailUrl -Method Post -Body $body -ContentType "application/x-www-form-urlencoded" -UseBasicParsing -TimeoutSec 30
    $parsed = Parse-Detail ([string]$resp.Content)

    if ($parsed.notes.Count -gt 0) { $item.notes = @($parsed.notes) }
    if ($parsed.include_notes.Count -gt 0) { $item.include_notes = @($parsed.include_notes) }
    if ($parsed.exclude_notes.Count -gt 0) { $item.exclude_notes = @($parsed.exclude_notes) }
    if ($parsed.example_notes.Count -gt 0) { $item.example_notes = @($parsed.example_notes) }
    $updated += 1
  } catch {
    $failed += 1
  }

  if ((($i + 1) % 100) -eq 0) {
    Write-Output "progress: $($i + 1)/$total updated=$updated failed=$failed"
  }
  Start-Sleep -Milliseconds 20
}

$data.source = $detailUrl
$data.generated_at = (Get-Date).ToString("s")
$data.notes_strategy = "kssc detail view enrichment"
$data.item_count = $items.Count
$data.items = $items

$data | ConvertTo-Json -Depth 8 | Set-Content -Path $jsonPath -Encoding UTF8
Write-Output "done: updated=$updated failed=$failed total=$total"
