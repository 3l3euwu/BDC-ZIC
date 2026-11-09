# Build a ready-to-copy mod folder using Zig (https://ziglang.org/download/).
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$package = Join-Path $root 'dev-build/BDC_ZIC'
New-Item -ItemType Directory -Force $package | Out-Null
New-Item -ItemType Directory -Force (Join-Path $package 'Scripts'), (Join-Path $package 'panel') | Out-Null
Copy-Item -Force (Join-Path $root 'mod/BDC_ZIC/Scripts/main.lua') (Join-Path $package 'Scripts')
Copy-Item -Force (Join-Path $root 'mod/BDC_ZIC/panel/panel.py') (Join-Path $package 'panel')
Copy-Item -Force (Join-Path $root 'mod/BDC_ZIC/Open-Panel.cmd') $package
Copy-Item -Force (Join-Path $root 'mod/BDC_ZIC/Open-Panel.vbs') $package
$native = Join-Path $package 'native'
New-Item -ItemType Directory -Force $native | Out-Null
$out = Join-Path $native 'capture.exe'
& zig c++ -target x86_64-windows-gnu -O2 -s -municode (Join-Path $root 'native/capture.cpp') -o $out -lole32 -lmmdevapi -luuid
if ($LASTEXITCODE -ne 0) { throw "Compilation failed ($LASTEXITCODE)" }
Write-Host "Built $package"
