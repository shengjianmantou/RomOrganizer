"""
Native OS directory selection dialog service.
Runs platform-specific native folder pickers (macOS AppleScript, Windows PowerShell, Linux zenity/tkinter).
"""
from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import Optional

log = logging.getLogger(__name__)


def _pick_directory_sync(prompt: str = "Select Directory") -> Optional[str]:
    system = platform.system()

    # 1. macOS (AppleScript)
    if system == "Darwin":
        # Escape quotes in prompt
        escaped_prompt = prompt.replace('"', '\\"')
        apple_script = (
            f'try\n'
            f'  set chosenFolder to choose folder with prompt "{escaped_prompt}"\n'
            f'  return POSIX path of chosenFolder\n'
            f'on error number -128\n'
            f'  return ""\n'
            f'end try'
        )
        try:
            res = subprocess.run(
                ["osascript", "-e", apple_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = res.stdout.strip()
            return out if out else None
        except Exception as e:
            log.warning(f"macOS osascript dialog failed: {e}")

    # 2. Windows (PowerShell FolderBrowserDialog)
    elif system == "Windows":
        ps_cmd = (
            '[System.Reflection.Assembly]::LoadWithPartialName("System.windows.forms") | Out-Null; '
            '$f = New-Object System.Windows.Forms.FolderBrowserDialog; '
            f'$f.Description = "{prompt}"; '
            '$f.ShowNewFolderButton = $true; '
            'if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }'
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = res.stdout.strip()
            return out if out else None
        except Exception as e:
            log.warning(f"Windows PowerShell dialog failed: {e}")

    # 3. Linux (zenity, kdialog, or tkinter)
    elif system == "Linux":
        # Try zenity
        try:
            res = subprocess.run(
                ["zenity", "--file-selection", "--directory", f"--title={prompt}"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except FileNotFoundError:
            pass

        # Try kdialog
        try:
            res = subprocess.run(
                ["kdialog", "--getexistingdirectory", "--title", prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except FileNotFoundError:
            pass

    # 4. Universal Fallback: Tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=prompt)
        root.destroy()
        return selected if selected else None
    except Exception as e:
        log.debug(f"Tkinter directory dialog fallback failed: {e}")

    return None


async def pick_directory(prompt: str = "Select Directory") -> Optional[str]:
    """Asynchronously trigger the native folder chooser dialog."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _pick_directory_sync, prompt)
