# ==============================================================================
# Build and Deployment Script for Visual Paradigm MCP Plugin
# ==============================================================================
param(
    [string]$VpDir = "C:\Program Files\Visual Paradigm 18.1",
    [switch]$Deploy = $true
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SrcDir = Join-Path $ScriptDir "src"
$BinDir = Join-Path $ScriptDir "bin"
$LibDir = Join-Path $ScriptDir "lib"
$DistDir = Join-Path $ScriptDir "dist"
$PluginId = "com.mcp.visualparadigm"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Building MCP Visual Paradigm Plugin..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Locate openapi.jar
$OpenApiJar = Join-Path $VpDir "lib\openapi.jar"
if (-not (Test-Path $OpenApiJar)) {
    $OpenApiJar = Join-Path $VpDir "bundled\openapi.jar"
}
if (-not (Test-Path $OpenApiJar)) {
    throw "Cannot find openapi.jar at $OpenApiJar. Please verify Visual Paradigm directory."
}
Write-Host "[1/5] Using Visual Paradigm OpenAPI: $OpenApiJar" -ForegroundColor Green

# 2. Locate javac and jar
$JavacCandidates = @(
    "C:\Program Files (x86)\Android\openjdk\jdk-17.0.14\bin\javac.exe",
    (Join-Path $VpDir "jre\bin\javac.exe"),
    "javac.exe"
)
$Javac = $null
foreach ($cand in $JavacCandidates) {
    if (Test-Path $cand) {
        $Javac = $cand
        break
    }
}
if (-not $Javac) {
    $found = Get-Command javac -ErrorAction SilentlyContinue
    if ($found) { $Javac = $found.Source }
}
if (-not $Javac) {
    throw "javac compiler not found. Please install a JDK."
}
Write-Host "[2/5] Using Java Compiler: $Javac" -ForegroundColor Green

# 3. Clean and prepare output directories
if (Test-Path $BinDir) { Remove-Item -Path $BinDir -Recurse -Force }
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
New-Item -ItemType Directory -Path $LibDir -Force | Out-Null
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

# 4. Compile Java sources
$JavaFiles = Get-ChildItem -Path $SrcDir -Filter "*.java" -Recurse | ForEach-Object { $_.FullName }
Write-Host "[3/5] Compiling $($JavaFiles.Count) Java sources (Target Java 11)..." -ForegroundColor Green

& $Javac --release 11 -cp "$OpenApiJar" -d "$BinDir" $JavaFiles
if ($LASTEXITCODE -ne 0) {
    throw "Java compilation failed with exit code $LASTEXITCODE"
}

# 5. Package JAR
$JarPath = Join-Path $LibDir "mcp-plugin.jar"
if (Test-Path $JarPath) { Remove-Item $JarPath -Force }

# Locate jar.exe
$JarExe = $Javac.Replace("javac.exe", "jar.exe")
if (Test-Path $JarExe) {
    Push-Location $BinDir
    try {
        & $JarExe -cf "$JarPath" .
    } finally {
        Pop-Location
    }
} else {
    # Fallback to .NET Zip compression renamed to .jar
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($BinDir, $JarPath)
}
Write-Host "[4/5] Created JAR: $JarPath ($([math]::Round((Get-Item $JarPath).Length / 1KB, 1)) KB)" -ForegroundColor Green

# 6. Deploy to Visual Paradigm User Plugins Directory
if ($Deploy) {
    $UserPluginsDir = Join-Path $env:APPDATA "VisualParadigm\plugins"
    $TargetPluginDir = Join-Path $UserPluginsDir $PluginId
    $TargetLibDir = Join-Path $TargetPluginDir "lib"

    New-Item -ItemType Directory -Path $TargetLibDir -Force | Out-Null
    Copy-Item -Path (Join-Path $ScriptDir "plugin.xml") -Destination (Join-Path $TargetPluginDir "plugin.xml") -Force
    Copy-Item -Path $JarPath -Destination (Join-Path $TargetLibDir "mcp-plugin.jar") -Force

    $IconsDir = Join-Path $ScriptDir "icons"
    if (Test-Path $IconsDir) {
        $TargetIconsDir = Join-Path $TargetPluginDir "icons"
        New-Item -ItemType Directory -Path $TargetIconsDir -Force | Out-Null
        Copy-Item -Path "$IconsDir\*" -Destination $TargetIconsDir -Force
    }

    Write-Host "[5/5] Deployed plugin to: $TargetPluginDir" -ForegroundColor Green

    # Also build standalone ZIP for manual distribution
    $ZipPath = Join-Path $DistDir "mcp-visualparadigm-plugin.zip"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    
    $StagingDir = Join-Path $DistDir "staging\$PluginId"
    New-Item -ItemType Directory -Path "$StagingDir\lib" -Force | Out-Null
    Copy-Item -Path (Join-Path $ScriptDir "plugin.xml") -Destination "$StagingDir\plugin.xml" -Force
    Copy-Item -Path $JarPath -Destination "$StagingDir\lib\mcp-plugin.jar" -Force
    if (Test-Path $IconsDir) {
        $StagingIconsDir = Join-Path $StagingDir "icons"
        New-Item -ItemType Directory -Path $StagingIconsDir -Force | Out-Null
        Copy-Item -Path "$IconsDir\*" -Destination $StagingIconsDir -Force
    }
    
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $DistDir "staging"), $ZipPath)
    Remove-Item (Join-Path $DistDir "staging") -Recurse -Force
    
    Write-Host "Created distribution package: $ZipPath" -ForegroundColor Cyan
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "BUILD AND DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "To activate: Start or restart Visual Paradigm 18.1." -ForegroundColor Yellow
Write-Host "Live Sync HTTP server will listen on: http://127.0.0.1:19842" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green
