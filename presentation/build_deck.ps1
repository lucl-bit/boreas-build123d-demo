# Baut die Praesentation aus deck_content.json auf der Boreas-Vorlage (PowerPoint per COM, Layouts der Vorlage).
#   powershell -ExecutionPolicy Bypass -File presentation\build_deck.ps1 [-Template <pptx>] [-Out <pptx>] [-Png <dir>]
param(
    [string]$Template = "$env:USERPROFILE\Downloads\Sprint_0_Review_Final.pptx",
    [string]$Content = "$PSScriptRoot\deck_content.json",
    [string]$Out = "$PSScriptRoot\Boreas_CAD_Benchmark_BRep_vs_Voxel.pptx",
    [string]$Png = ""
)
$ErrorActionPreference = "Stop"
trap { if ($pres) { $pres.Close() }; if ($app) { $app.Quit() }; throw $_ }
$data = Get-Content $Content -Raw -Encoding UTF8 | ConvertFrom-Json

function RGB([string]$hex) { $h = $hex.TrimStart('#'); return [int]("0x" + $h.Substring(0, 2)) + 256 * [int]("0x" + $h.Substring(2, 2)) + 65536 * [int]("0x" + $h.Substring(4, 2)) }
$NAVY = RGB "0D192F"; $CREAM = RGB "F2EDE3"; $MUTED = RGB "565E6D"; $LIGHT = RGB "E8E2D6"; $WHITE = RGB "FFFFFF"
$BREP = RGB "1F5FA8"; $VOX = RGB "D9731A"; $OKC = RGB "2E7D4F"; $PARTC = RGB "B7791F"; $NOC = RGB "A33A3A"

function Set-Paragraphs($shape, $items, [double]$size = 0) {
    # items: Strings oder Objekte {t, lvl, b}; eine Zeile je Absatz
    $tr = $shape.TextFrame.TextRange
    $lines = @(); foreach ($it in $items) { if ($it -is [string]) { $lines += $it } else { $lines += [string]$it.t } }
    $tr.Text = ($lines -join "`r")
    $tr.ParagraphFormat.Alignment = 1
    try { $shape.TextFrame2.TextRange.Font.Spacing = 0 } catch { }
    for ($i = 0; $i -lt $items.Count; $i++) {
        $it = $items[$i]; $p = $tr.Paragraphs($i + 1)
        $isHead = ($it -isnot [string]) -and $it.b
        if ($it -isnot [string] -and $it.lvl) { $p.IndentLevel = [int]$it.lvl + 1 }
        if ($isHead) { $p.Font.Bold = -1; $p.ParagraphFormat.Bullet.Visible = 0; $p.ParagraphFormat.SpaceBefore = $(if ($i -gt 0) { 8 } else { 0 }) }
        else { $p.ParagraphFormat.Bullet.Visible = -1; $p.ParagraphFormat.Bullet.Character = 8226 }
        $p.ParagraphFormat.SpaceAfter = 4
        if ($size -gt 0) { $p.Font.Size = [single]$size }
    }
}

function Add-Box($slide, $b) {
    $s = $slide.Shapes.AddTextbox(1, [single]$b.x, [single]$b.y, [single]$b.w, [single]$b.h)
    $s.TextFrame.WordWrap = -1; $s.TextFrame.AutoSize = 0
    $s.TextFrame.MarginLeft = 0; $s.TextFrame.MarginRight = 0; $s.TextFrame.MarginTop = 0; $s.TextFrame.MarginBottom = 0
    $tr = $s.TextFrame.TextRange
    $lines = @(); foreach ($it in $b.lines) { if ($it -is [string]) { $lines += $it } else { $lines += [string]$it.t } }
    $tr.Text = ($lines -join "`r")
    $tr.Font.Name = "Outfit"; $tr.Font.Size = [single]$(if ($b.size) { $b.size } else { 14 })
    $tr.Font.Color.RGB = $(if ($b.color) { RGB $b.color } else { $NAVY })
    if ($b.bold) { $tr.Font.Bold = -1 }
    if ($b.align -eq "center") { $tr.ParagraphFormat.Alignment = 2 }
    for ($i = 0; $i -lt $b.lines.Count; $i++) {
        $it = $b.lines[$i]
        if ($it -isnot [string]) {
            $p = $tr.Paragraphs($i + 1)
            if ($it.b) { $p.Font.Bold = -1 }
            if ($it.c) { $p.Font.Color.RGB = RGB $it.c }
            if ($it.s) { $p.Font.Size = [single]$it.s }
            if ($it.bullet) { $p.ParagraphFormat.Bullet.Visible = -1; $p.ParagraphFormat.Bullet.Character = 8226; $p.IndentLevel = 1 }
        }
        $tr.Paragraphs($i + 1).ParagraphFormat.SpaceAfter = [single]$(if ($b.gap) { $b.gap } else { 4 })
    }
    if ($b.fill) {
        $s.Fill.Visible = -1; $s.Fill.ForeColor.RGB = RGB $b.fill
        $s.TextFrame.MarginLeft = 10; $s.TextFrame.MarginRight = 10; $s.TextFrame.MarginTop = 8; $s.TextFrame.MarginBottom = 8
    }
    return $s
}

function Add-Table($slide, $t) {
    $rows = $t.rows.Count; $cols = $t.rows[0].Count
    $sh = $slide.Shapes.AddTable($rows, $cols, [single]$t.x, [single]$t.y, [single]$t.w, [single]$t.h)
    $tb = $sh.Table
    for ($c = 1; $c -le $cols; $c++) { if ($t.colw) { $tb.Columns($c).Width = [single]$t.colw[$c - 1] } }
    for ($r = 1; $r -le $rows; $r++) {
        for ($c = 1; $c -le $cols; $c++) {
            $cell = $tb.Cell($r, $c); $v = $t.rows[$r - 1][$c - 1]
            $txt = if ($v -is [string]) { $v } else { [string]$v.t }
            $cell.Shape.TextFrame.TextRange.Text = $txt
            $f = $cell.Shape.TextFrame.TextRange.Font; $f.Name = "Outfit"; $f.Size = [single]$(if ($t.size) { $t.size } else { 11 })
            $cell.Shape.TextFrame.MarginTop = 2; $cell.Shape.TextFrame.MarginBottom = 2; $cell.Shape.TextFrame.MarginLeft = 5; $cell.Shape.TextFrame.MarginRight = 5
            if ($r -eq 1) { $cell.Shape.Fill.ForeColor.RGB = $NAVY; $f.Color.RGB = $CREAM; $f.Bold = -1 }
            else { $cell.Shape.Fill.ForeColor.RGB = $(if ($r % 2 -eq 0) { $WHITE } else { $LIGHT }); $f.Color.RGB = $NAVY }
            if ($v -isnot [string]) {
                if ($v.c) { $f.Color.RGB = RGB $v.c }
                if ($v.b) { $f.Bold = -1 }
                if ($v.bg) { $cell.Shape.Fill.ForeColor.RGB = RGB $v.bg }
            }
            if ($c -gt 1 -and $t.center) { $cell.Shape.TextFrame.TextRange.ParagraphFormat.Alignment = 2 }
        }
        if ($t.rowh) { $tb.Rows($r).Height = [single]$t.rowh }
    }
    return $sh
}

$app = New-Object -ComObject PowerPoint.Application
$tmp = Join-Path $env:TEMP ("boreas_tpl_" + [guid]::NewGuid().ToString() + ".pptx")
Copy-Item $Template $tmp
$pres = $app.Presentations.Open($tmp, $false, $false, $false)
$orig = $pres.Slides.Count
$layouts = @{}; $k = 0; foreach ($cl in $pres.SlideMaster.CustomLayouts) { $k++; $layouts[$cl.Name] = $k }

foreach ($sd in $data.slides) {
    $lay = $pres.SlideMaster.CustomLayouts.Item($layouts[$sd.layout])
    $slide = $pres.Slides.AddSlide($pres.Slides.Count + 1, $lay)
    $ph = @(); foreach ($s in $slide.Shapes) { if ($s.Type -eq 14 -and $s.PlaceholderFormat.Type -ne 13) { $ph += $s } }
    switch ($sd.layout) {
        "Boreas Titel" { $ph[0].TextFrame.TextRange.Text = $sd.title; $ph[1].TextFrame.TextRange.Text = $sd.subtitle }
        "Boreas Kapitel" { $ph[0].TextFrame.TextRange.Text = $sd.title }
        "Boreas Abschluss" { $ph[0].TextFrame.TextRange.Text = $sd.title }
        "Boreas Drei Kacheln" {
            $ph[0].TextFrame.TextRange.Text = $sd.title
            for ($i = 0; $i -lt 3; $i++) { $ph[1 + 2 * $i].TextFrame.TextRange.Text = $sd.tiles[$i].v; $ph[2 + 2 * $i].TextFrame.TextRange.Text = $sd.tiles[$i].l }
            $ph[7].TextFrame.TextRange.Text = $(if ($sd.footnote) { $sd.footnote } else { " " })
        }
        default {
            $ph[0].TextFrame.TextRange.Text = $sd.title
            if ($sd.layout -eq "Boreas Inhalt") { if ($sd.body) { Set-Paragraphs $ph[1] $sd.body ([double]$sd.bodysize) } else { $ph[1].Delete() } }
            if ($sd.layout -eq "Boreas Zwei Spalten") {
                if ($sd.left) { Set-Paragraphs $ph[1] $sd.left ([double]$sd.bodysize) } else { $ph[1].Delete() }
                if ($sd.right) { Set-Paragraphs $ph[2] $sd.right ([double]$sd.bodysize) } else { $ph[2].Delete() }
            }
        }
    }
    if ($sd.titlesize) { $ph[0].TextFrame.TextRange.Font.Size = [single]$sd.titlesize }
    foreach ($img in $sd.images) {
        $p = (Resolve-Path (Join-Path $PSScriptRoot $img.path)).Path
        $pic = $slide.Shapes.AddPicture($p, 0, -1, [single]$img.x, [single]$img.y)
        $pic.LockAspectRatio = -1
        if ($img.w) { $pic.Width = [single]$img.w }
        if ($img.h -and ($pic.Height -gt $img.h)) { $pic.Height = [single]$img.h }
        if ($img.center) { $pic.Left = [single]($img.x + ($img.w - $pic.Width) / 2) }
    }
    foreach ($b in $sd.boxes) { [void](Add-Box $slide $b) }
    foreach ($t in $sd.tables) { [void](Add-Table $slide $t) }
    if ($sd.notes) { $slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = $sd.notes }
}
for ($i = $orig; $i -ge 1; $i--) { $pres.Slides.Item($i).Delete() }
if (Test-Path $Out) { Remove-Item $Out -Force }
$pres.SaveAs($Out)
if ($Png) { New-Item -ItemType Directory -Force $Png | Out-Null; Get-ChildItem $Png -Filter *.PNG | Remove-Item; $pres.Export($Png, "PNG", 1280, 720) }
"Folien: " + $pres.Slides.Count + " -> " + $Out
$pres.Close(); $app.Quit(); Remove-Item $tmp -Force
