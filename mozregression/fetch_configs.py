"""
This module defines the configuration needed for nightly and inbound
fetching for each application. This configuration is a base block
for everything done in mozregression since it holds information
about how to get information about builds for a given application.

The public entry point in there is :func:`create_config`, which
creates an returns a fetch configuration. the configuration will
be an instance of :class:`CommonConfig`, possibly using the mixins
:class:`NightlyConfigMixin` and/or :class:`InboundConfigMixin`.

Example to create a configuration for firefox on linux 64: ::

  fetch_config = create_config('firefox', 'linux', 64)

You can also use the variable *REGISTRY* defined in this module to get a
list of application names that can be used to build a configuration. This is
an instance of :class:`ClassRegistry`. Example: ::

  print REGISTRY.names()
"""
import datetime

from mozregression.class_registry import ClassRegistry
from mozregression import errors


def get_build_regex(name, os, bits, with_ext=True):
    """
    Returns a string regexp that can match a build filename.

    :param name: must be the beginning of the filename to match
    :param os: the os, as returned by mozinfo.os
    :param bits: the bits information of the build. Either 32 or 64.
    :param with_ext: if True, the build extension will be appended (either
                     .zip, .tar.bz2 or .dmg depending on the os).
    """
    if os == "win":
        if bits == 64:
            suffix, ext = r".*win64(-x86_64)?", r"\.zip"
        else:
            suffix, ext = r".*win32", r"\.zip"
    elif os == "linux":
        if bits == 64:
            suffix, ext = r".*linux-x86_64", r"\.tar.bz2"
        else:
            suffix, ext = r".*linux-i686", r"\.tar.bz2"
    elif os == "mac":
        suffix, ext = r".*mac.*", r"\.dmg"
    else:
        raise errors.MozRegressionError(
            "mozregression supports linux, mac and windows but your"
            " os is reported as '%s'." % os
        )

    regex = '%s%s' % (name, suffix)
    if with_ext:
        return '%s%s' % (regex, ext)
    else:
        return regex


class CommonConfig(object):
    """
    Define the configuration for both nightly and inbound fetching.

    :attr name: the name of the application
    """

    app_name = None

    def __init__(self, os, bits):
        self.os = os
        self.bits = bits

    def build_regex(self):
        """
        Returns a string regex that can match a build file on the servers.
        """
        return get_build_regex(self.app_name, self.os, self.bits) + '$'

    def build_info_regex(self):
        """
        Returns a string regex that can match a build info file (txt)
        on the servers.
        """
        return get_build_regex(self.app_name, self.os, self.bits,
                               with_ext=False) + r'\.txt$'

    def is_nightly(self):
        """
        Returns True if the configuration can be used for nightly fetching.
        """
        return isinstance(self, NightlyConfigMixin)

    def is_inbound(self):
        """
        Returns True if the configuration can be used for inbound fetching.
        """
        return isinstance(self, InboundConfigMixin)

    def available_bits(self):
        """
        Returns the no. of bits of the OS for which the application should
        run.
        """
        return (32, 64)


class NightlyConfigMixin(object):
    """
    Define the nightly-related required configuration to find nightly builds.

    A nightly build url is divided in 2 parts here:

    1. the base part as returned by :meth:`get_nighly_base_url`
    2. the final part, which can be found using :meth:`get_nighly_repo_regex`

    The final part contains a repo name, which is returned by
    :meth:`get_nightly_repo`.

    Note that subclasses must implement :meth:`_get_nightly_repo` to
    provide a default value.
    """
    nightly_base_repo_name = "firefox"
    nightly_repo = None

    def get_nighly_base_url(self, date):
        """
        Returns the base part of the nightly build url for a given date.
        """
        return (
            "https://archive.mozilla.org/pub/mozilla.org/%s/nightly/%04d/%02d/"
            % (self.nightly_base_repo_name, date.year, date.month)
        )

    def set_nightly_repo(self, repo):
        """
        Allow to define the repo name.

        If None, :meth:`_get_nightly_repo` will be called to return a value
        when :meth:`get_nightly_repo` is called.
        """
        self.nightly_repo = repo

    def get_nightly_repo(self, date):
        """
        Returns the repo name for a given date.
        """
        return self.nightly_repo or self._get_nightly_repo(date)

    def _get_nightly_repo(self, date):
        """
        Returns a default repo name for a given date.
        """
        raise NotImplementedError

    def get_nightly_repo_regex(self, date):
        """
        Returns a string regex that can match the last folder name for a given
        date.
        """
        repo = self.get_nightly_repo(date)
        return (r'^%04d-%02d-%02d-[\d-]+%s/$'
                % (date.year, date.month, date.day, repo))

    def can_go_inbound(self):
        """
        Indicate if we can bissect inbound from this nightly config.
        """
        # we can go on inbound if no nightly repo has been specified.
        return self.is_inbound() and not self.nightly_repo


class FireFoxNightlyConfigMixin(NightlyConfigMixin):
    def _get_nightly_repo(self, date):
        if date < datetime.date(2008, 6, 17):
            return "trunk"
        else:
            return "mozilla-central"


class ThunderbirdNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = 'thunderbird'

    def _get_nightly_repo(self, date):
        # sneaking this in here
        if self.os == "win" and date < datetime.date(2010, 3, 18):
            # no .zip package for Windows, can't use the installer
            raise errors.WinTooOldBuildError()

        if date < datetime.date(2008, 7, 26):
            return "trunk"
        elif date < datetime.date(2009, 1, 9):
            return "comm-central"
        elif date < datetime.date(2010, 8, 21):
            return "comm-central-trunk"
        else:
            return "comm-central"


class B2GNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = 'b2g'

    def _get_nightly_repo(self, date):
        return "mozilla-central"


class FennecNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = "mobile"

    def _get_nightly_repo(self, date):
        if date < datetime.date(2014, 12, 6):
            return "mozilla-central-android"
        if date < datetime.date(2014, 12, 13):
            return "mozilla-central-android-api-10"
        return "mozilla-central-android-api-11"


class InboundConfigMixin(object):
    """
    Define the inbound-related required configuration.
    """
    inbound_branch = 'mozilla-inbound'

    def set_inbound_branch(self, inbound_branch):
        if inbound_branch:
            self.inbound_branch = inbound_branch

    def tk_inbound_route(self, changeset):
        """
        Returns a taskcluster route for a specific changeset.
        """
        raise NotImplementedError


def _common_tk_part(inbound_conf):
    # private method to avoid copy/paste for building taskcluster route part.
    if inbound_conf.os == 'linux':
        part = 'linux'
        if inbound_conf.bits == 64:
            part += str(inbound_conf.bits)
    elif inbound_conf.os == 'mac':
        part = 'macosx64'
    else:
        # windows
        part = '{}{}'.format(inbound_conf.os, inbound_conf.bits)
    return part


class FirefoxInboundConfigMixin(InboundConfigMixin):
    def tk_inbound_route(self, changeset):
        return 'buildbot.revisions.{}.{}.{}'.format(
            changeset, self.inbound_branch, _common_tk_part(self)
        )


class B2GInboundConfigMixin(InboundConfigMixin):
    inbound_branch = 'b2g-inbound'

    def tk_inbound_route(self, changeset):
        if self.os != 'linux':
            # this is quite strange, but sometimes we have to limit the
            # changeset size, and sometimes not. see
            # https://bugzilla.mozilla.org/show_bug.cgi?id=1159700#c13
            changeset = changeset[:12]
        return 'buildbot.revisions.{}.{}.{}'.format(
            changeset, self.inbound_branch, _common_tk_part(self) + '_gecko'
        )


class FennecInboundConfigMixin(InboundConfigMixin):
    tk_name = 'android-api-11'

    def tk_inbound_route(self, changeset):
        return 'buildbot.revisions.{}.{}.{}'.format(
            changeset, self.inbound_branch, self.tk_name
        )

# ------------ full config implementations ------------

REGISTRY = ClassRegistry('app_name')


def create_config(name, os, bits):
    """
    Create and returns a configuration for the given name.

    :param name: application name, such as 'firefox'
    :param os: os name, e.g 'linux', 'win' or 'mac'
    :param bits: the bit of the os as an int, e.g 32 or 64. Can be None
                 if the bits do not make sense (e.g. fennec)
    """
    return REGISTRY.get(name)(os, bits)


@REGISTRY.register('firefox')
class FirefoxConfig(CommonConfig,
                    FireFoxNightlyConfigMixin,
                    FirefoxInboundConfigMixin):
    pass


@REGISTRY.register('thunderbird')
class ThunderbirdConfig(CommonConfig,
                        ThunderbirdNightlyConfigMixin):
    pass


@REGISTRY.register('b2g')
class B2GConfig(CommonConfig,
                B2GNightlyConfigMixin,
                B2GInboundConfigMixin):
    pass


@REGISTRY.register('fennec')
class FennecConfig(CommonConfig,
                   FennecNightlyConfigMixin,
                   FennecInboundConfigMixin):

    def build_regex(self):
        return r'fennec-.*\.apk'

    def build_info_regex(self):
        return r'fennec-.*\.txt'

    def available_bits(self):
        return ()


@REGISTRY.register('fennec-2.3', attr_value='fennec')
class Fennec23Config(FennecConfig):
    tk_name = 'android-api-9'

    def _get_nightly_repo(self, date):
        if date < datetime.date(2014, 12, 6):
            return "mozilla-central-android"
        return "mozilla-central-android-api-9"
