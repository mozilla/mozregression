import pytest

from argparse import ArgumentParser, Namespace

from mozregression import __version__
from mozregression.mach_interface import new_release_on_pypi, parser, run


@pytest.mark.parametrize('pypi_version, result', [
    (lambda: 'latest', 'latest'),
    (lambda: __version__, None),  # same version, None is returned
    (lambda: None, None),
    (Exception, None),  # on exception, None is returned
])
def test_new_release_on_pypi(mocker, pypi_version, result):
    pypi_latest_version = mocker.patch(
        'mozregression.mach_interface.pypi_latest_version'
    )
    pypi_latest_version.side_effect = pypi_version
    assert new_release_on_pypi() == result


def test_parser(mocker):
    get_defaults = mocker.patch('mozregression.mach_interface.get_defaults')
    get_defaults.return_value = {'profile-persistence': 'clone',
                                 'app': 'firefox',
                                 'persist-size-limit': 0,
                                 'http-timeout': 30.0,
                                 'no-background-dl': '',
                                 'background-dl-policy': 'cancel',
                                 'persist': 'stuff'}
    p = parser()
    assert isinstance(p, ArgumentParser)
    options = p.parse_args(['--persist-size-limit=1'])

    assert options.persist == 'stuff'
    assert options.persist_size_limit == 1.0


def test_run(mocker):
    main = mocker.patch('mozregression.mach_interface.main')
    run({'persist': 'foo', 'bits': 64})
    main.assert_called_once_with(check_new_version=False,
                                 namespace=Namespace(bits=64, persist='foo'))
