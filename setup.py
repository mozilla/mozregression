import os
import sys
from contextlib import suppress
from pathlib import Path

from setuptools import Command, setup
from setuptools.command.build import build

from gui.build import main


class CustomCommand(Command):
    def initialize_options(self) -> None:
        self.saved_argv = sys.argv
        self.saved_pwd = os.path.dirname(os.path.realpath(__file__))

    def finalize_options(self) -> None:
        os.chdir(self.saved_pwd)
        sys.argv = self.saved_argv

    def run(self) -> None:
        sys.argv = ['gui/build.py', 'rcc']
        print("gui build starting")
        main()
        print("gui build done")

class CustomBuild(build):
    sub_commands = [('build_custom', None)] + build.sub_commands

setup(cmdclass={'build': CustomBuild, 'build_custom': CustomCommand})
