param(
    [string]$SourceDir = "$env:USERPROFILE\Downloads",
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"
$destination = Join-Path $ProjectDir "assets\images_hq"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$hashes = [ordered]@{
    "Start.png" = "13f19117e3d0a1ac179537df26df013c26f763e242f69d34257ad7d255f4e26e"
    "campaign.png" = "e80340b3dab1b0daeedb5a1bbb539dc13dc5dbba386da5ba8fbf1fe4b305e20e"
    "character.png" = "833fa68a7f1792cf0d43c2252e1386eb450ce6079fb1018135064211cb20ebda"
    "quest.png" = "a29acc2325d136754a85014d753fdbadf6b07d6a47cffdeb1c9ccfb9d5b2e334"
    "npc.png" = "a59cd6bcbecdd36c4ce5080d3598bcb66502991b366bc73ea858cf19d6b11588"
    "encounter_friendly.png" = "25b13007e2ca6c871a3387cdcf855a43d5a15b3c3c8c7a0d8e6bf3ded1a28797"
    "encounter_neutral.png" = "2158ad6414f98fb4ceb798c7502e2fe59f35faa748aa27d41a2670e0ed5823f8"
    "encounter_hostile.png" = "d3028077e5ee0caab056f498ff678ec53ce7ecc1c56c20075c0f41285d2ab186"
    "combat.png" = "db076110dadc2d2f3679864fc3ebed66bd5b35786fc40cfb2b2435d1a5ae11e6"
    "attack.png" = "db076110dadc2d2f3679864fc3ebed66bd5b35786fc40cfb2b2435d1a5ae11e6"
    "spell.png" = "814bae913579c04a04ca922ca1dc2c2adfeee03551588c375eb16175927031e6"
    "rest.png" = "144525293d6a1fe6168597628de37e2ffeda4a4e21904999149918bbf7d07f98"
    "levelup.png" = "f9385bb0a701d68ee7036cb3e755801f8d80979db92a366a2b61ca6eaaea496d"
    "loot_common.png" = "87e51ceb0d57ac24cfea3caf8b1e701eb5bce52f8e0cc2438ffbd96f29263de5"
    "loot_rare.png" = "23367b7cda80feb9db6e4cbdea8d4de7d499dc05417f4a880e4632e529ffcc81"
    "journal.png" = "ae570f95123386aa0cb3801021a7bc441f952e0b28a652f99e1362328896a7d0"
}

$missing = @()
foreach ($entry in $hashes.GetEnumerator()) {
    $source = Join-Path $SourceDir $entry.Key
    if (-not (Test-Path $source)) {
        $missing += $entry.Key
        continue
    }
    $actual = (Get-FileHash -Path $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value) {
        throw "Файл $($entry.Key) не совпадает с исходным PNG. SHA256: $actual"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $destination $entry.Key) -Force
    Write-Host "OK  $($entry.Key)"
}

if ($missing.Count -gt 0) {
    throw "Не найдены файлы в $SourceDir`: $($missing -join ', ')"
}

Write-Host "Все исходные PNG установлены без перекодирования: $destination"
