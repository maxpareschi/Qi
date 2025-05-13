$rootPath = Split-Path -parent $PSScriptRoot;
$env:PYTHONPATH = $rootPath;$env:PYTHONPATH

$rootPath + "\.venv\Scripts\Activate.ps1"

Start-Process "bun" -WorkingDirectory $rootPath -ArgumentList "run", "dev"
Start-Process "python" -WorkingDirectory $rootPath -ArgumentList ".\hub\launcher.py", "--dev"
