"""
Various linux-specific tools
"""

import os
import sys


def check_unprivileged_userns(logger):
    """
    Some distribution started to block unprivileged user namespaces via
    AppArmor.  This might result in crashes on older builds, and in degraded
    sandbox behavior.  It is fixed with an AppArmor profile that allows the
    syscall to proceed, but this is path dependant on the binary we download
    and needs to be installed at a system level, so we can only advise people
    of the situation.

    The following sys entry should be enough to verify whether it is blocked or
    not, but the Ubuntu security team recommend cross-checking with actual
    syscall.  This code is a simplification of how Firerox does it, cf
    https://searchfox.org/mozilla-central/rev/23efe2c8c5b3a3182d449211ff9036fb34fe0219/security/sandbox/linux/SandboxInfo.cpp#114-175
    and has been the most reliable way so far (shell with unshare would not
    reproduce EPERM like we want).

    Return False if there is no problem or True if the user needs to fix their
    setup.
    """

    apparmor_file = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
    if not os.path.isfile(apparmor_file):
        return False

    with open(apparmor_file, "r") as f:
        if f.read().strip() != "1":
            return False

    import ctypes
    import errno
    import platform
    import signal

    # Values are from
    # https://github.com/hrw/syscalls-table/tree/163e238e4d7761fcf6ac500aad92d53ac88d663a/system_calls/tables
    # imported from linux kernel headers
    SYS_clone = {
        "i386": 120,
        "x32": 1073741880,
        "x86_64": 56,
        "arm": 120,
        "armv7l": 120,
        "arm64": 220,
        "aarch64": 220,
        "aarch64_be": 220,
        "armv8b": 220,
        "armv8l": 220,
    }.get(platform.machine())
    if not SYS_clone:
        logger.warning(
            "Unprivileged user namespaces might be disabled, but unsupported platform? {}".format(
                platform.machine()
            )
        )
        return False

    libc = ctypes.CDLL(None, use_errno=True)

    logger.warning(
        "Unprivileged user namespaces might be disabled. Checking clone() + unshare() syscalls ..."
    )

    try:
        # Introduced in 3.12 which is the version of Ubuntu 24.04
        clone_newuser = os.CLONE_NEWUSER
        clone_newpid = os.CLONE_NEWPID
    except AttributeError:
        # From
        # https://github.com/torvalds/linux/blob/5bbd9b249880dba032bffa002dd9cd12cd5af09c/include/uapi/linux/sched.h#L31-L32
        # Last change 12 years ago, so it should be a stable fallback
        clone_newuser = 0x10000000
        clone_newpid = 0x20000000

    pid = libc.syscall(SYS_clone, signal.SIGCHLD.value | clone_newuser, None, None, None, None)

    if pid == 0:
        # Child side ...
        rv = libc.unshare(clone_newpid)
        _errno = ctypes.get_errno()
        if rv < 0:
            sys.exit(_errno)
        sys.exit(0)
    else:
        (pid, statuscode) = os.waitpid(pid, 0)
        exitcode = os.waitstatus_to_exitcode(statuscode)

        if exitcode == 0:
            return False

        if exitcode == errno.EPERM:
            logger.warning(
                "Unprivileged user namespaces is disabled. This is likely because AppArmor policy "
                "change. Please refer to {} to learn how to setup AppArmor so that mozregression "
                "works correctly. Missing AppArmor profile can lead to crashes or to incorrectly "
                "sandboxed processes.".format(
                    "https://mozilla.github.io/mozregression/documentation/usage.html#unprivileged-user-namespaces"  # noqa: E501
                )
            )
            logger.warning(
                "If you already applied the suggested fix, then this warning can be ignored. "
                "It can also be silenced by the --dont-check-userns flag."
                "Another side effect is that browser's tab may crash because "
                "they incorrectly test for the feature. If your regression "
                "window covers that, you may want to set MOZ_ASSUME_USER_NS=0 "
                "environmnent variable before launching mozregression."
            )
            return True

        logger.warning(
            "Unexpected exit code {} while performing user namespace "
            "checks. You might want to file a bug.".format(exitcode)
        )

    return False
