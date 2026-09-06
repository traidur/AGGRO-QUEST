# Launches the PnP tool (Vite) and both web sim servers (Flask) as tabs in one
# Windows Terminal window. Reuses the most recently used wt window if one is
# already open (-w 0), otherwise opens a new one.
#
# Usage: right-click > Run with PowerShell, or from a terminal: .\launch-tools.ps1

$root = $PSScriptRoot
$pnpDir = Join-Path $root "pnp-tool"
$simDir = Join-Path $root "sim"

$wtArgs = @(
    "-w", "0",
    "new-tab", "--title", "PnP Tool", "-d", $pnpDir, "powershell", "-NoExit", "-Command", "npm run dev",
    ";",
    "new-tab", "--title", "Web Sim (solo)", "-d", $simDir, "powershell", "-NoExit", "-Command", "python playtest_web.py",
    ";",
    "new-tab", "--title", "Web Sim (board)", "-d", $simDir, "powershell", "-NoExit", "-Command", "python playtest_board_web.py"
)

& wt @wtArgs
