"""
This module defines the configuration needed for nightly and inbound
fetching for each application.
"""
import datetime
import copy

from mozregression.utils import get_build_regex, ClassRegistry
from mozregression import errors


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
        return ("http://ftp.mozilla.org/pub/mozilla.org/%s/nightly/%04d/%02d/"
                % (self.nightly_base_repo_name, date.year, date.month))

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

    def inbound_base_urls(self):
        raise NotImplementedError


class FirefoxInboundConfigMixin(InboundConfigMixin):
    build_base_os_part = {
        'linux': {32: 'linux', 64: 'linux64'},
        'win': {32: 'win32', 64: 'win64'},
        'mac': {64: 'macosx64'}
    }
    root_build_base_url = ('http://inbound-archive.pub.build.mozilla.org/pub'
                           '/mozilla.org/firefox/tinderbox-builds/%s-%s/')

    def inbound_base_urls(self):
        return [self.root_build_base_url
                % (self.inbound_branch,
                   self.build_base_os_part[self.os][self.bits])]


class B2GInboundConfigMixin(FirefoxInboundConfigMixin):
    inbound_branch = 'b2g-inbound'
    build_base_os_part = copy.deepcopy(
        FirefoxInboundConfigMixin.build_base_os_part
        )
    build_base_os_part['linux'][32] = 'linux32'

    root_build_base_url = ('http://ftp.mozilla.org/pub/mozilla.org/b2g'
                           '/tinderbox-builds/%s-%s_gecko/')


class FennecInboundConfigMixin(InboundConfigMixin):
    inbound_branchs = ['mozilla-inbound-android']

    def inbound_base_urls(self):
        return ["http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org"
                "/mobile/tinderbox-builds/%s/" % inbound_branch
                for inbound_branch in self.inbound_branchs]

    def set_inbound_branch(self, inbound_branch):
        if inbound_branch:
            self.inbound_branchs = [inbound_branch]

# ------------ full config implementations ------------

REGISTRY = ClassRegistry('app_name')


def create_config(name, os, bits):
    """
    Create and returns a configuration for the given name.
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
    inbound_branchs = (FennecInboundConfigMixin.inbound_branchs
                       + ['mozilla-inbound-android-api-10',
                          'mozilla-inbound-android-api-11'])

    def build_regex(self):
        return r'fennec-.*\.apk'

    def build_info_regex(self):
        return r'fennec-.*\.txt'


@REGISTRY.register('fennec-2.3', attr_value='fennec')
class Fennec23Config(FennecConfig):
    inbound_branchs = (FennecInboundConfigMixin.inbound_branchs
                       + ['mozilla-inbound-android-api-9'])

    def _get_nightly_repo(self, date):
        if date < datetime.date(2014, 12, 6):
            return "mozilla-central-android"
        return "mozilla-central-android-api-9"
