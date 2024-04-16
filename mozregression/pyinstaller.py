"""PyInstaller helper module to enable packaging tcl/tk with app bundles."""

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import _tkinter
import shutil
import subprocess
from pathlib import Path

import PyInstaller.log as logging
from PyInstaller.building.datastruct import Tree
from PyInstaller.building.osx import BUNDLE
from PyInstaller.compat import is_darwin
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
        excluded_files = ["demos", "*.lib", "*Config.sh"]

        # Discover location of tcl/tk dynamic library files (i.e., dylib).
        _tkinter_file = _tkinter.__file__
        tcl_lib, tk_lib = find_tcl_tk_shared_libs(_tkinter_file)

        # Determine full path/location of tcl/tk libraries.
        tcl_root, tk_root = _find_tcl_tk(_tkinter_file)

        # Determine original prefixes to put all the library files in.
        tcl_prefix, tk_prefix = Path(tcl_root).name, Path(tk_root).name

        # Create Tree objects with all the files that need to be included in the bundle.
        # Tree objects are a way of creating a table of contents describing everything in
        # the provided root directory.
        tcltree = Tree(tcl_root, prefix=tcl_prefix, excludes=excluded_files)
        tktree = Tree(tk_root, prefix=tk_prefix, excludes=excluded_files)
        tclmodulestree = _collect_tcl_modules(tcl_root)
        tcl_tk_files = tcltree + tktree + tclmodulestree

        # Use Tree object to list out files that will be copied (adapted from
        # PyInstaller.building.osx).
        files = [(dest, source) for dest, source, _type in tcl_tk_files]

        # Append dynamic library files.
        files.append((tcl_lib[0], tcl_lib[1]))
        files.append((tk_lib[0], tk_lib[1]))

        # Create "lib" directory in the .app bundle.
        lib_dir = Path(self.name) / "Contents" / "lib"
        lib_dir.mkdir()

        # Iterate over all files and copy them into "lib" directory.
        for dest, source in files:
            dest_full_path = lib_dir / dest
            dest_full_path.parent.mkdir(parents=True, exist_ok=True)
            if dest_full_path.is_dir():
                shutil.copytree(source, dest_full_path)
            else:
                shutil.copy(source, dest_full_path)

    def resign_binary(self):
        """Force resigning of the .app bundle."""
        command = [
            "codesign",
            "-s",
            "-",
            "--force",
            "--all-architectures",
            "--timestamp",
            "--deep",
            "--force",
        ]
        if self.entitlements_file:
            command.append("--entitlements")
            command.append(self.entitlements_file)

        command.append(self.name)
        subprocess.check_output(command)
