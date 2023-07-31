"""PyInstaller helper module to enable packaging tcl/tk with app bundles."""

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# ----------------------------------------------------------------------------
# Copyright (c) 2005-2023, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License (version 2
# or later) with exception for distributing the bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#
# SPDX-License-Identifier: (GPL-2.0-or-later WITH Bootloader-exception)
# ----------------------------------------------------------------------------

# Some code in this module (where noted) is copied and modified from the
# original version. The original version can be found at
# https://github.com/pyinstaller/pyinstaller.
# See also: https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

import importlib
import os
import shutil
from pathlib import Path

import PyInstaller.log as logging
from PyInstaller.building.datastruct import Tree
from PyInstaller.building.osx import BUNDLE
from PyInstaller.compat import exec_command_all, is_darwin
from PyInstaller.utils.hooks.tcl_tk import (
    _collect_tcl_modules,
    _find_tcl_tk,
    find_tcl_tk_shared_libs,
)

logger = logging.getLogger(__name__)


class BUNDLE_WITH_TK(BUNDLE):
    """A BUNDLE class that incorporates tcl/tk libraries."""

    def __init__(self, *args, **kwargs):
        if not is_darwin:
            # This class can only be used on macOS.
            return
        super().__init__(*args, **kwargs)

    def assemble(self):
        """Run BUNDLE.assemble, and then run post assembly methods."""
        super().assemble()
        self.post_assemble()
        self.resign_binary()

    def post_assemble(self):
        """Collect tcl/tk library/module files and add them to the bundle."""

        # These files will not be needed (originally excluded by PyInstaller).
        EXCLUDES = ["demos", "*.lib", "*Config.sh"]

        # Discover location of tcl/tk dynamic library files (i.e., dylib).
        _tkinter_module = importlib.import_module("_tkinter")
        _tkinter_file = _tkinter_module.__file__
        tcl_lib, tk_lib = find_tcl_tk_shared_libs(_tkinter_file)

        # Determine full path/location of tcl/tk libraries.
        tcl_root, tk_root = _find_tcl_tk(_tkinter_file)

        # Determine original prefixes to put all the library files in.
        tcl_prefix, tk_prefix = Path(tcl_root).parts[-1], Path(tk_root).parts[-1]

        # Create Tree objects with all the files that need to be included in the bundle.
        # Tree objects are a way of creating a table of contents describing everything in
        # the provided root directory.
        tcltree = Tree(tcl_root, prefix=tcl_prefix, excludes=EXCLUDES)
        tktree = Tree(tk_root, prefix=tk_prefix, excludes=EXCLUDES)
        tclmodulestree = _collect_tcl_modules(tcl_root)
        tcl_tk_files = tcltree + tktree + tclmodulestree

        # Use Tree object to list out files that will be copied (adapted from
        # PyInstaller.building.osx).
        links = [(inm, fnm) for inm, fnm, typ in tcl_tk_files]

        # Append dynamic library files.
        links.append((tcl_lib[0], tcl_lib[1]))
        links.append((tk_lib[0], tk_lib[1]))

        # Create "lib" directory in the .app bundle.
        lib_dir = os.path.join(self.name, "Contents", "lib")
        os.makedirs(lib_dir)

        # Iterate over all files and copy them into "lib" directory.
        # The rest of the code in this method is copied and adapted from the
        # PyInstaller.building.osx module.
        for inm, fnm in links:
            tofnm = os.path.join(lib_dir, inm)
            todir = os.path.dirname(tofnm)
            if not os.path.exists(todir):
                os.makedirs(todir)
            if os.path.isdir(fnm):
                shutil.copytree(fnm, tofnm)
            else:
                shutil.copy(fnm, tofnm)

    def resign_binary(self):
        """Force resigning of the .app bundle."""
        # The code in this method is copied and modified from the original code
        # in PyInstaller.utils.osx.sign_binary. It was modified to allow force
        # signing of the bundle, and assumes the ad-hoc identity.
        args = []
        if self.entitlements_file:
            args.append("--entitlements")
            args.append(self.entitlements_file)
        args.append("--deep")
        args.append("--force")
        cmd = [
            "codesign",
            "-s",
            "-",
            "--force",
            "--all-architectures",
            "--timestamp",
            *args,
            self.name,
        ]
        retcode, stdout, stderr = exec_command_all(*cmd)
        if retcode != 0:
            logger.warning(
                "codesign command (%r) failed with error code %d!\n" "stdout: %r\n" "stderr: %r",
                cmd,
                retcode,
                stdout,
                stderr,
            )
            raise SystemError("codesign failure!")
