"""
This module defines the configuration needed for nightly and inbound
fetching for each application. This configuration is a base block
for everything done in mozregression since it holds information
about how to get information about builds for a given application.

The public entry point in there is :func:`create_config`, which
creates an returns a fetch configuration. the configuration will
be an instance of :class:`CommonConfig`, possibly using the mixins
:class:`NightlyConfigMixin` and/or :class:`InboundConfigMixin`.
<
Example to create a configuration for firefox on linux 64: ::

  fetch_config = create_config('firefox', 'linux', 64)

You can also use the variable *REGISTRY* defined in this module to get a
list of application names that can be used to build a configuration. This is
an instance of :class:`ClassRegistry`. Example: ::

  print REGISTRY.names()
"""
import re
import datetime

from mozregression.class_registry import ClassRegistry
from mozregression import errors, branches
from mozregression.dates import to_utc_timestamp
from mozregression.config import ARCHIVE_BASE_URL
from abc import ABCMeta, abstractmethod


# switch from fennec api-11 to api-15 on taskcluster
# appeared on this date for m-c.
TIMESTAMP_FENNEC_API_15 = to_utc_timestamp(
    datetime.datetime(2016, 1, 29, 0, 30, 13)
)

# switch from fennec api-15 to api-16 on taskcluster
# appeared on this date for m-c.
TIMESTAMP_FENNEC_API_16 = to_utc_timestamp(
    datetime.datetime(2017, 8, 29, 18, 28, 36)
)


def get_build_regex(name, os, bits, processor, psuffix='', with_ext=True):
    """
    Returns a string regexp that can match a build filename.

    :param name: must be the beginning of the filename to match
    :param os: the os, as returned by mozinfo.os
    :param bits: the bits information of the build. Either 32 or 64.
    :param processor: the architecture of the build. Only one that alters
                      results is aarch64.
    :param psuffix: optional suffix before the extension
    :param with_ext: if True, the build extension will be appended (either
                     .zip, .tar.bz2 or .dmg depending on the os).
    """
    if os == "win":
        if bits == 64:
            if processor == "aarch64":
                suffix = r".*win64-aarch64"
            else:
                suffix = r".*win64(-x86_64)?"
            ext = r"\.zip"
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

    # New taskcluster builds now just name the binary archive 'target', so
    # that is added as one possibility in the regex.
    regex = '(target|%s%s%s)' % (name, suffix, psuffix)
    if with_ext:
        return '%s%s' % (regex, ext)
    else:
        return regex


class CommonConfig(object):
    """
    Define the configuration for both nightly and inbound fetching.
    """
    BUILD_TYPES = ('opt',)  # only opt allowed by default
    BUILD_TYPE_FALLBACKS = {}
    app_name = None

    def __init__(self, os, bits, processor):
        self.os = os
        self.bits = bits
        self.processor = processor
        self.repo = None
        self.set_build_type('opt')
        self._used_build_index = 0

    @property
    def build_type(self):
        """
        Returns the currently selected build type, which can change if there
        are fallbacks specified.
        """
        return self.build_types[self._used_build_index]

    def _inc_used_build(self):
        """
        Increments the index into the build_types indicating the currently
        selected build type.
        """
        self._used_build_index = (
            # Need to be careful not to overflow the list
            (self._used_build_index + 1) % len(self.build_types)
        )

    def build_regex(self):
        """
        Returns a string regex that can match a build file on the servers.
        """
        return get_build_regex(self.app_name, self.os, self.bits,
                               self.processor) + '$'

    def build_info_regex(self):
        """
        Returns a string regex that can match a build info file (txt)
        on the servers.
        """
        return get_build_regex(self.app_name, self.os, self.bits,
                               self.processor, with_ext=False) + r'\.txt$'

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

    def available_build_types(self):
        res = []
        for available in self.BUILD_TYPES:
            match = re.match("(.+)\[(.+)\]", available)
            if match:
                suffix = ('-aarch64' if self.processor == 'aarch64' and
                          self.bits == 64 else '')
                available = match.group(1)
                platforms = match.group(2)
                if '{}{}{}'.format(
                    self.os, self.bits, suffix
                ) not in platforms.split(','):
                    available = None
            if available:
                res.append(available)
        return res

    def set_build_type(self, build_type):
        """
        Define the build type (opt, debug, asan...).

        :raises: MozRegressionError on error.
        """
        if build_type in self.available_build_types():
            fallbacks = self.BUILD_TYPE_FALLBACKS.get(build_type)
            self.build_types = (
                (build_type,) + fallbacks if fallbacks else (build_type,)
            )
            return
        raise errors.MozRegressionError(
            "Unable to find a suitable build type %r." % str(build_type)
        )

    def set_repo(self, repo):
        """
        Allow to define the repo name.

        If not set or set to None, default repos would be used (see
        :meth:`get_nightly_repo` and :attr:`inbound_branch`)
        """
        self.repo = branches.get_name(repo) if repo else None

    def should_use_taskcluster(self):
        """
        Returns True if taskcluster should be used as the bisection method.

        Note that this method relies on the repo and build type defined.
        """
        return (branches.get_category(self.repo) in
                ('integration', 'try', 'releases') or
                # we can find the asan builds (firefox and jsshell) in
                # archives.m.o
                self.build_type not in ('opt', 'asan', 'shippable'))


class NightlyConfigMixin:
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
    archive_base_url = ARCHIVE_BASE_URL
    __metaclass__ = ABCMeta
    nightly_base_repo_name = "firefox"
    nightly_repo = None

    def set_base_url(self, url):
        self.archive_base_url = url.rstrip('/')

    def get_nighly_base_url(self, date):
        """
        Returns the base part of the nightly build url for a given date.
        """
        return "%s/%s/nightly/%04d/%02d/" % (self.archive_base_url,
                                             self.nightly_base_repo_name,
                                             date.year,
                                             date.month)

    def get_nightly_repo(self, date):
        """
        Returns the repo name for a given date.
        """
        if isinstance(date, datetime.datetime):
            date = date.date()
        return self.repo or self._get_nightly_repo(date)

    @abstractmethod
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
        return self._get_nightly_repo_regex(date, self.get_nightly_repo(date))

    def _get_nightly_repo_regex(self, date, repo):
        if isinstance(date, datetime.datetime):
            return (r'^%04d-%02d-%02d-%02d-%02d-%02d-%s/$'
                    % (date.year, date.month, date.day, date.hour,
                       date.minute, date.second, repo))
        return (r'^%04d-%02d-%02d-[\d-]+%s/$'
                % (date.year, date.month, date.day, repo))

    def can_go_inbound(self):
        """
        Indicate if we can bisect inbound from this nightly config.
        """
        return self.is_inbound()


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


class FennecNightlyConfigMixin(NightlyConfigMixin):
    nightly_base_repo_name = "mobile"

    def _get_nightly_repo(self, date):
        return 'mozilla-central'

    def get_nightly_repo_regex(self, date):
        repo = self.get_nightly_repo(date)
        if repo in ('mozilla-central',):
            if date < datetime.date(2014, 12, 6):
                repo += "-android"
            elif date < datetime.date(2014, 12, 13):
                repo += "-android-api-10"
            elif date < datetime.date(2016, 1, 29):
                repo += "-android-api-11"
            elif date < datetime.date(2017, 8, 30):
                repo += "-android-api-15"
            else:
                repo += "-android-api-16"
        return self._get_nightly_repo_regex(date, repo)


class InboundConfigMixin:
    """
    Define the inbound-related required configuration.
    """
    __metaclass__ = ABCMeta
    default_inbound_branch = 'mozilla-inbound'
    _tk_credentials = None

    @property
    def inbound_branch(self):
        return self.repo or self.default_inbound_branch

    def tk_inbound_route(self, push):
        """
        Returns the first taskcluster route for a specific changeset
        """
        return next(self.tk_inbound_routes(push))

    @abstractmethod
    def tk_inbound_routes(self, push):
        """
        Returns a generator of taskcluster routes for a specific changeset.
        """
        raise NotImplementedError

    def inbound_persist_part(self):
        """
        Allow to add a part in the generated persist file name to distinguish
        builds. Returns an empty string by default, or 'debug' if build type
        is debug.
        """
        return self.build_type if self.build_type != 'opt' else ''

    def tk_needs_auth(self):
        """
        Returns True if we need taskcluster credentials
        """
        return False

    def set_tk_credentials(self, creds):
        """
        Define the credentials required to download private builds on
        TaskCluster.
        """
        self._tk_credentials = creds

    def tk_options(self):
        """
        Returns the takcluster options, including the credentials required to
        download private artifacts.
        """
        tk_options = {'rootUrl': 'https://taskcluster.net'}
        if self.tk_needs_auth():
            tk_options.update({'credentials': self._tk_credentials})
        return tk_options


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
        if inbound_conf.processor == 'aarch64' and inbound_conf.bits == 64:
            part += '-aarch64'
    return part


class FirefoxInboundConfigMixin(InboundConfigMixin):
    def tk_inbound_routes(self, push):
        for build_type in self.build_types:
            yield 'gecko.v2.{}{}.revision.{}.firefox.{}-{}'.format(
                self.inbound_branch,
                '.shippable' if build_type == 'shippable' else '',
                push.changeset,
                _common_tk_part(self),
                'opt' if build_type == 'shippable' else build_type
            )
            self._inc_used_build()
        return


class FennecInboundConfigMixin(InboundConfigMixin):
    tk_name = 'android-api-11'

    def tk_inbound_routes(self, push):
        tk_name = self.tk_name
        if tk_name == 'android-api-11':
            if push.timestamp >= TIMESTAMP_FENNEC_API_16:
                tk_name = 'android-api-16'
            elif push.timestamp >= TIMESTAMP_FENNEC_API_15:
                tk_name = 'android-api-15'
        for build_type in self.build_types:
            yield 'gecko.v2.{}.revision.{}.mobile.{}-{}'.format(
                self.inbound_branch, push.changeset, tk_name,
                build_type
            )
            self._inc_used_build()
            return


class ThunderbirdInboundConfigMixin(InboundConfigMixin):
    default_inbound_branch = 'comm-central'

    def tk_inbound_routes(self, push):
        for build_type in self.build_types:
            yield 'comm.v2.{}.revision.{}.thunderbird.{}-{}'.format(
                self.inbound_branch, push.changeset, _common_tk_part(self),
                build_type
            )
            self._inc_used_build()
        return

# ------------ full config implementations ------------


REGISTRY = ClassRegistry('app_name')


def create_config(name, os, bits, processor):
    """
    Create and returns a configuration for the given name.

    :param name: application name, such as 'firefox'
    :param os: os name, e.g 'linux', 'win' or 'mac'
    :param bits: the bit of the os as an int, e.g 32 or 64. Can be None
                 if the bits do not make sense (e.g. fennec)
    :param processor: processor family, e.g 'x86', 'x86_86', 'ppc', 'ppc64' or
                      'aarch64'
    """
    return REGISTRY.get(name)(os, bits, processor)


@REGISTRY.register('firefox')
class FirefoxConfig(CommonConfig,
                    FireFoxNightlyConfigMixin,
                    FirefoxInboundConfigMixin):
    BUILD_TYPES = ('shippable', 'opt', 'pgo[linux32,linux64,win32,win64]',
                   'debug', 'asan[linux64]', 'asan-debug[linux64]')
    BUILD_TYPE_FALLBACKS = {
        'shippable': ('opt', 'pgo'),
        'opt': ('shippable', 'pgo'),
    }

    def __init__(self, os, bits, processor):
        super(FirefoxConfig, self).__init__(os, bits, processor)
        self.set_build_type('shippable')

    def build_regex(self):
        return get_build_regex(
            self.app_name, self.os, self.bits, self.processor,
            psuffix='-asan' if 'asan' in self.build_type else ''
        ) + '$'


@REGISTRY.register('thunderbird')
class ThunderbirdConfig(CommonConfig,
                        ThunderbirdNightlyConfigMixin,
                        ThunderbirdInboundConfigMixin):
    pass


@REGISTRY.register('fennec')
class FennecConfig(CommonConfig,
                   FennecNightlyConfigMixin,
                   FennecInboundConfigMixin):
    BUILD_TYPES = ('opt', 'debug')

    def build_regex(self):
        return r'(target|fennec-.*)\.apk'

    def build_info_regex(self):
        return r'(target|fennec-.*)\.txt'

    def available_bits(self):
        return ()


@REGISTRY.register('gve')
class GeckoViewExampleConfig(CommonConfig,
                             FennecNightlyConfigMixin,
                             FennecInboundConfigMixin):
    BUILD_TYPES = ('opt', 'debug')

    def build_regex(self):
        return r'geckoview_example\.apk'

    def build_info_regex(self):
        return r'(target|fennec-.*)\.txt'

    def available_bits(self):
        return ()

    def should_use_taskcluster(self):
        # GVE is not on archive.mozilla.org, only on taskcluster
        return True


@REGISTRY.register('fennec-2.3', attr_value='fennec')
class Fennec23Config(FennecConfig):
    tk_name = 'android-api-9'

    def get_nightly_repo_regex(self, date):
        repo = self.get_nightly_repo(date)
        if repo == 'mozilla-central':
            if date < datetime.date(2014, 12, 6):
                repo = "mozilla-central-android"
            else:
                repo = "mozilla-central-android-api-9"
        return self._get_nightly_repo_regex(date, repo)


@REGISTRY.register('jsshell', disable_in_gui=True)
class JsShellConfig(FirefoxConfig):
    def build_info_regex(self):
        # the info file is the one for firefox
        return get_build_regex('firefox', self.os, self.bits, self.processor,
                               with_ext=False) + r'\.txt$'

    def build_regex(self):
        if self.os == 'linux':
            if self.bits == 64:
                part = 'linux-x86_64'
            else:
                part = 'linux-i686'
        elif self.os == 'win':
            if self.bits == 64:
                if self.processor == "aarch64":
                    part = 'win64-aarch64'
                else:
                    part = 'win64(-x86_64)?'
            else:
                part = 'win32'
        else:
            part = 'mac'
        psuffix = '-asan' if 'asan' in self.build_type else ''
        return r'jsshell-%s%s\.zip$' % (part, psuffix)
