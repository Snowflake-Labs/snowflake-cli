# Copyright (c) 2024 Snowflake Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import stat
from pathlib import Path

from snowflake.connector.compat import IS_WINDOWS


def _get_windows_whitelisted_users():
    # whitelisted users list obtained in consultation with prodsec: CASEC-9627
    import os

    return ["SYSTEM", "Administrators", os.getlogin()]


def _run_icacls(file_path: Path) -> str:
    import subprocess

    return subprocess.check_output(["icacls", str(file_path)], text=True)


def _windows_permissions_are_denied(permission_codes: str) -> bool:
    # according to https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls
    return "(DENY)" in permission_codes or "(N)" in permission_codes


def _windows_file_permissions_are_strict(file_path: Path) -> bool:
    import re

    # according to https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls
    icacls_output_regex = r".*\\(?P<user>.*):(?P<permissions>[(A-Z),]+)"
    whitelisted_users = _get_windows_whitelisted_users()

    for permission in re.finditer(icacls_output_regex, _run_icacls(file_path)):
        if (permission.group("user") not in whitelisted_users) and (
            not _windows_permissions_are_denied(permission.group("permissions"))
        ):
            return False

    return True


def _unix_file_permissions_are_strict(file_path: Path) -> bool:
    accessible_by_others = (
        # https://docs.python.org/3/library/stat.html
        stat.S_IRGRP  # readable by group
        | stat.S_IROTH  # readable by others
        | stat.S_IWGRP  # writeable by group
        | stat.S_IWOTH  # writeable by others
        | stat.S_IXGRP  # executable by group
        | stat.S_IXOTH  # executable by others
    )
    return (file_path.stat().st_mode & accessible_by_others) == 0


def file_permissions_are_strict(file_path: Path) -> bool:
    if IS_WINDOWS:
        return True
    return _unix_file_permissions_are_strict(file_path)
