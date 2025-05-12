$rootPath = Split-Path -parent $PSScriptRoot;
$env:QI_DEV = "1"
$env:PYTHONPATH = $rootPath;$env:PYTHONPATH

$rootPath + "\.venv\Scripts\Activate.ps1"
uv sync

Start-Process "bun" -WorkingDirectory $rootPath -ArgumentList "run", "dev"
Start-Process "python" -WorkingDirectory $rootPath -ArgumentList ".\hub\qi_launcher.py", "--dev"
