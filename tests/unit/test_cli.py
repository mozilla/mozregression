#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import tempfile
import os

from mozregression import cli


class TestMainCli(unittest.TestCase):

    def test_get_erronous_cfg_defaults(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('aaaaaaaaaaa [Defaults]\n')

        with self.assertRaises(SystemExit):
            cli.get_defaults(filepath)

    def test_get_defaults(self):
        valid_values = {'http-timeout': '10.2',
                        'persist': '/home/foo/.mozregression',
                        'bits': '64'}

        handle, filepath = tempfile.mkstemp()
        conf_default = cli.DEFAULT_CONF_FNAME

        self.addCleanup(os.unlink, filepath)
        self.addCleanup(setattr, cli, "DEFAULT_CONF_FNAME", conf_default)

        cli.DEFAULT_CONF_FNAME = filepath

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('[Defaults]\n')
            for key, value in valid_values.iteritems():
                conf_file.write("%s=%s\n" % (key, value))

        options = cli.parse_args(['--bits=32'])

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.persist, '/home/foo/.mozregression')
        self.assertEqual(options.bits, '32')

if __name__ == '__main__':
    unittest.main()
