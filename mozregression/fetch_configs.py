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
    Define the nightly-related required configuration.
    """
    nightly_base_repo_name = "firefox"

    def nightly_inbound_branch(self, date):
        raise NotImplementedError

class FireFoxNightlyConfigMixin(NightlyConfigMixin):
    def nightly_inbound_branch(self, date):
        if date < datetime.date(2008, 6, 17):
            return "trunk"
        else:
            return "mozilla-central"

class ThunderbirdNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = 'thunderbird'

    def nightly_inbound_branch(self, date):
        # sneaking this in here
        if self.os == "win" and date < datetime.date(2010, 03, 18):
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

    def nightly_inbound_branch(self, date):
        return "mozilla-central"

class FennecNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = "mobile"

    def nightly_inbound_branch(self, date):
        return "mozilla-central-android"

class InboundConfigMixin(object):
    """
    Define the inbound-related required configuration.
    """
    inbound_branch = 'mozilla-inbound'
    def set_inbound_branch(self, inbound_branch):
        if inbound_branch:
            self.inbound_branch = inbound_branch

    def inbound_base_url(self):
        raise NotImplementedError

class FirefoxInboundConfigMixin(InboundConfigMixin):
    build_base_os_part = {
        'linux': {32: 'linux', 64: 'linux64'},
        'win': {32: 'win32', 64: 'win64'},
        'mac': {64: 'macosx64'}
    }
    root_build_base_url = ('http://inbound-archive.pub.build.mozilla.org/pub'
                           '/mozilla.org/firefox/tinderbox-builds/%s-%s/')

    def inbound_base_url(self):
        return (self.root_build_base_url
                % (self.inbound_branch,
                   self.build_base_os_part[self.os][self.bits]))

class B2GInboundConfigMixin(FirefoxInboundConfigMixin):
    inbound_branch = 'b2g-inbound'
    build_base_os_part = copy.deepcopy(FirefoxInboundConfigMixin.build_base_os_part)
    build_base_os_part['linux'][32] = 'linux32'

    root_build_base_url = ('http://ftp.mozilla.org/pub/mozilla.org/b2g'
                           '/tinderbox-builds/%s-%s_gecko/')

class FennecInboundConfigMixin(InboundConfigMixin):
    def inbound_base_url(self):
        return ("http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org"
                "/mobile/tinderbox-builds/%s-android/") % self.inbound_branch

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
class BGConfig(CommonConfig,
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
