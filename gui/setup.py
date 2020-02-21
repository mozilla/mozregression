import sys
from setuptools import setup
from mozregui import __version__


if sys.version_info < (3, 5):
    sys.exit("mozregression-gui requires python >= 3.5")

# we pin these dependencies in the requirements files -- all of these
# should be python 3 compatible
DEPENDENCIES = [
    'mozregression>=3.0.0',

]

desc = """Graphical regression range finder for Mozilla nightly builds"""
long_desc = """Graphical regression range finder for Mozilla nightly builds.
For more information see the mozregression website:
http://mozilla.github.io/mozregression/"""

setup(name="mozregui",
      version=__version__,
      description=desc,
      long_description=long_desc,
      author='Mozilla Automation and Tools Team',
      author_email='tools@lists.mozilla.org',
      url='http://github.com/mozilla/mozregression',
      license='MPL 1.1/GPL 2.0/LGPL 2.1',
      packages=['mozregui'],
      entry_points="""
          [console_scripts]
          mozregui = mozregui.main:main
        """,
      platforms=['Any'],
      install_requires=DEPENDENCIES,
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Operating System :: OS Independent'
      ])
