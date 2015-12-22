# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from taskcluster import utils as tc_utils

from mozregression.config import (get_defaults, DEFAULT_CONF_FNAME,
                                  TC_CREDENTIALS_FNAME)


def tc_authenticate(logger):
    """
    Returns valid credentials for use with Taskcluster private builds.
    """
    # first, try to load credentials from mozregression config file
    defaults = get_defaults(DEFAULT_CONF_FNAME)
    client_id = defaults.get('taskcluster-clientid')
    access_token = defaults.get('taskcluster-accesstoken')
    if client_id and access_token:
        return dict(clientId=client_id, accessToken=access_token)

    try:
        # else, try to load a valid certificate locally
        with open(TC_CREDENTIALS_FNAME) as f:
            creds = json.load(f)
        if not tc_utils.isExpired(creds['certificate']):
            return creds
    except Exception:
        pass

    # here we need to ask for a certificate, this require web browser
    # authentication
    logger.info(
        "Authentication required from taskcluster. We are going to ask for a"
        " certificate.\nNote that if you have long term access you can instead"
        " set your taskcluster-clientid and taskcluster-accesstoken in the"
        " configuration file (%s)." % DEFAULT_CONF_FNAME
    )
    creds = tc_utils.authenticate("mozregression private build access")

    # save the credentials and the certificate for later use
    with open(TC_CREDENTIALS_FNAME, 'w') as f:
        json.dump(creds, f)
    return creds
