import pytest
import os
import mozfile
import tempfile

from mozregression.config import write_conf, get_defaults


@pytest.yield_fixture
def tmp():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    mozfile.remove(temp_dir)


@pytest.mark.parametrize('os_,bits,inputs,conf_dir_exists,results', [
    ('mac', 64, ['', ''], False,
     {'persist': None, 'persist-size-limit': '20.0'}),
    ('linux', 32, ['NONE', 'NONE'], True,
     {'persist': '', 'persist-size-limit': '0.0'}),
    ('win', 32, ['', '10'], True,
     {'persist': None, 'persist-size-limit': '10.0'}),
    # on 64 bit (except for mac), bits option is asked
    ('linu', 64, ['NONE', 'NONE', ''], True,
     {'persist': '', 'persist-size-limit': '0.0', 'bits': '64'}),
    ('win', 64, ['NONE', 'NONE', '32'], True,
     {'persist': '', 'persist-size-limit': '0.0', 'bits': '32'}),
])
def test_write_conf(tmp, mocker, os_, bits, inputs, conf_dir_exists, results):
    mozinfo = mocker.patch('mozregression.config.mozinfo')
    mozinfo.os = os_
    mozinfo.bits = bits
    mocked_input = mocker.patch('__builtin__.raw_input')
    mocked_input.side_effect = inputs
    conf_path = os.path.join(tmp, 'conf.cfg')
    if not conf_dir_exists:
        mozfile.remove(conf_path)
    write_conf(conf_path)
    if 'persist' in results and results['persist'] is None:
        # default persist is base on the directory of the conf file
        results['persist'] = os.path.join(tmp, 'persist')
    conf = get_defaults(conf_path)
    for key in results:
        assert conf[key] == results[key]
    with open(conf_path) as f:
        # ensure we have comments
        assert "# ------ mozregression configuration file ------" in f.read()


def test_write_existing_conf(tmp, mocker):
    mocked_input = mocker.patch('__builtin__.raw_input')
    mocked_input.return_value = ""
    conf_path = os.path.join(tmp, 'conf.cfg')
    write_conf(conf_path)
    results = get_defaults(conf_path)
    assert results
    # write conf again
    write_conf(conf_path)
    # nothing changed
    assert results == get_defaults(conf_path)
    with open(conf_path) as f:
        # ensure we have comments
        assert "# ------ mozregression configuration file ------" in f.read()
