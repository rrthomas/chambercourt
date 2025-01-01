"""
Detect the user's preferred language for messages.

Uses the standard library's `locale` module, except on macOS and Windows,
where custom code is used.
"""

import locale
import logging
import subprocess
import sys
from typing import Optional


_logger = logging.getLogger(__name__)


def language_code() -> Optional[str]:
    """
    Returns the user's environment language as a language code string.
    (examples: 'en_GB', 'en_US', 'pt_PT', 'pt_BR', etc.)
    """

    if sys.platform == "darwin":
        lang_code = _lang_code_mac()
    elif sys.platform == "win32":
        lang_code, _encoding = locale.getlocale()
    else:
        lang_code, _encoding = locale.getlocale(locale.LC_MESSAGES)

    return lang_code


def _lang_code_mac() -> Optional[str]:
    """
    Returns the user's language preference as defined in the Language & Region
    preference pane in macOS's System Preferences.
    
    Uses the shell command `defaults read -g AppleLocale` that prints out a
    language code to standard output. Assumptions about the command:
    - It exists and is in the shell's PATH.
    - It accepts those arguments.
    - It returns a usable language code.
    
    Reference documentation:
    - The man page for the `defaults` command on macOS.
    - The macOS underlying API:
      https://developer.apple.com/documentation/foundation/nsuserdefaults.
    """

    lang_detect_command = "defaults read -g AppleLocale"

    status, output = subprocess.getstatusoutput(lang_detect_command)
    if status == 0:  # Command was successful.
        lang_code = output
    else:
        _logger.warning("Language detection command failed: %r", output)
        lang_code = None

    return lang_code
