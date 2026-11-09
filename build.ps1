# Build with Zig (https://ziglang.org/download/) or a Windows C++ toolchain.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'mod/BDC_ZIC/native/capture.exe'
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
& zig c++ -target x86_64-windows-gnu -O2 -municode (Join-Path $root 'native/capture.cpp') -o $out -lole32 -lmmdevapi -luuid
if ($LASTEXITCODE -ne 0) { throw "Compilation failed ($LASTEXITCODE)" }
Write-Host "Built $out"
