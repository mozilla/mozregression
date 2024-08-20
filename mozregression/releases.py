from __future__ import absolute_import

import re
from datetime import date

from mozregression.errors import UnavailableRelease
from mozregression.network import retry_get


def releases():
    """
    Provide the list of releases with their associated dates.

    The date is a string formated as "yyyy-mm-dd", and the release an integer.
    """
    # The dates comes from from https://wiki.mozilla.org/RapidRelease/Calendar,
    # using the ones in the "beta" column (formerly "aurora"). This is because
    # the merge date for beta corresponds to the last nightly for that
    # release. See bug 996812.
    releases = {
        5: "2011-04-12",
        6: "2011-05-24",
        7: "2011-07-05",
        8: "2011-08-16",
        9: "2011-09-27",
        10: "2011-11-08",
        11: "2011-12-20",
        12: "2012-01-31",
        13: "2012-03-13",
        14: "2012-04-24",
        15: "2012-06-05",
        16: "2012-07-16",
        17: "2012-08-27",
        18: "2012-10-08",
        19: "2012-11-19",
        20: "2013-01-07",
        21: "2013-02-19",
        22: "2013-04-01",
        23: "2013-05-13",
        24: "2013-06-24",
        25: "2013-08-05",
        26: "2013-09-16",
        27: "2013-10-28",
        28: "2013-12-09",
        29: "2014-02-03",
        30: "2014-03-17",
        31: "2014-04-28",
        32: "2014-06-09",
        33: "2014-07-21",
        34: "2014-09-02",
        35: "2014-10-13",
        36: "2014-11-28",
        37: "2015-01-12",
        38: "2015-02-23",
        39: "2015-03-30",
        40: "2015-05-11",
        41: "2015-06-29",
        42: "2015-08-10",
        43: "2015-09-21",
        44: "2015-10-29",
        45: "2015-12-14",
        46: "2016-01-25",
        47: "2016-03-07",
        48: "2016-04-25",
        49: "2016-06-06",
        50: "2016-08-01",
        51: "2016-09-19",
        52: "2016-11-14",
        53: "2017-01-23",
        54: "2017-03-06",
        55: "2017-06-12",
        56: "2017-08-02",
    }

    def filter_tags(tag_node):
        match = re.match(r"^FIREFOX_NIGHTLY_(\d+)_END$", tag_node["tag"])
        return int(match.group(1)) > 56 if match else False

    def map_tags(tag_node):
        release = {}
        merge_date = date.fromtimestamp(tag_node["date"][0] + tag_node["date"][1])
        ver_match = re.search(r"_(\d+)_", tag_node["tag"])
        release[int(ver_match.group(1))] = merge_date.isoformat()
        return release

    tags_url = "https://hg.mozilla.org/mozilla-central/json-tags"
    response = retry_get(tags_url)

    if response.status_code == 200:
        fetched_releases = list(map(map_tags, list(filter(filter_tags, response.json()["tags"]))))

        for release in fetched_releases:
            releases.update(release)

    return releases


def date_of_release(release):
    """
    Provide the date of a release.
    """
    try:
        return releases()[int(release)]
    except (KeyError, ValueError):
        raise UnavailableRelease(release)


def tag_of_release(release):
    """
    Provide the mercurial tag of a release, suitable for use in place of a hash
    """
    if re.match(r"^\d+$", release):
        release += ".0"
    if re.match(r"^\d+\.\d(\.\d)?$", release):
        return "FIREFOX_%s_RELEASE" % release.replace(".", "_")
    else:
        raise UnavailableRelease(release)


def tag_of_beta(release):
    """
    Provide the mercurial tag of a beta release, suitable for use in place of a
    hash
    """
    if re.match(r"^\d+\.0b\d+$", release):
        return "FIREFOX_%s_RELEASE" % release.replace(".", "_")
    elif re.match(r"^\d+(\.0)?$", release):
        return "FIREFOX_RELEASE_%s_BASE" % release.replace(".0", "")
    else:
        raise UnavailableRelease(release)


def tag_of_esr(release):
    """
    Provide the mercurial tag of an ESR release, suitable for use in place of a hash
    """
    release = release.replace("esr", "")
    if re.match(r"^\d+$", release):
        release += ".0"
    else:
        minorVersion = re.match(r"^\d+\.(\d+)$", release)
        if minorVersion and not minorVersion.group(1) == "0":
            release += ".0"
    release += "esr"
    if re.match(r"^\d+\.\d+(\.\d)?esr$", release):
        return "FIREFOX_%s_RELEASE" % release.replace(".", "_")
    else:
        raise UnavailableRelease(release)


def formatted_valid_release_dates():
    """
    Returns a formatted string (ready to be printed) representing
    the valid release dates.
    """
    message = "Valid releases: \n"
    for key, value in releases().items():
        message += "% 3s: %s\n" % (key, value)

    return message
