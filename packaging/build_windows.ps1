$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $Root "build\windows"
$Icon = Join-Path $PSScriptRoot "moss.ico"

python -m pip install --disable-pip-version-check pyinstaller pillow

@'
from pathlib import Path
from PIL import Image, ImageDraw

out = Path("packaging/moss.ico")
image = Image.new("RGBA", (256, 256), "#121916")
draw = ImageDraw.Draw(image)
green, gold, blue = "#71D6A2", "#F2C14E", "#8BD9F7"
draw.line([(55, 190), (55, 75), (128, 153), (201, 75), (201, 190)], fill=green, width=26, joint="curve")
draw.line([(128, 153), (128, 50)], fill=gold, width=18)
draw.ellipse((39, 174, 71, 206), fill=blue)
draw.ellipse((112, 34, 144, 66), fill=gold)
draw.ellipse((185, 174, 217, 206), fill=green)
image.save(out, sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
'@ | python -

Remove-Item $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue

python -m PyInstaller --noconfirm --clean --onedir --console `
  --name moss --icon $Icon `
  --paths (Join-Path $Root "src") `
  --add-data "$Root\examples;examples" `
  --distpath $BuildRoot `
  --workpath (Join-Path $Root "build\pyinstaller-cli") `
  --specpath (Join-Path $Root "build") `
  (Join-Path $PSScriptRoot "moss_cli.py")

python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "Moss Studio" --icon $Icon `
  --paths (Join-Path $Root "src") `
  --add-data "$Root\examples;examples" `
  --collect-data mosslang `
  --distpath (Join-Path $Root "build\studio") `
  --workpath (Join-Path $Root "build\pyinstaller-studio") `
  --specpath (Join-Path $Root "build") `
  (Join-Path $PSScriptRoot "moss_studio.py")

$StudioRoot = Join-Path $Root "build\studio\Moss Studio"
Copy-Item (Join-Path $StudioRoot "Moss Studio.exe") (Join-Path $BuildRoot "moss\Moss Studio.exe")
Copy-Item (Join-Path $StudioRoot "_internal\*") (Join-Path $BuildRoot "moss\_internal") -Recurse -Force

$IsccCommand = Get-Command iscc -ErrorAction SilentlyContinue
$Iscc = if ($IsccCommand) { $IsccCommand.Source } else { $null }
if (-not $Iscc) {
  $Candidate = "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
  if (Test-Path $Candidate) { $Iscc = $Candidate }
}
if (-not $Iscc) { throw "Inno Setup compiler was not found." }

& $Iscc (Join-Path $PSScriptRoot "moss.iss")
