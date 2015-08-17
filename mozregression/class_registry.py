# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


class ClassRegistry(object):
    """
    A registry to store classes identified by a unique name.

    :param attr_name: On each registered class, the unique name will be saved
                      under this class attribute name.
    """
    def __init__(self, attr_name='name'):
        self._classes = {}
        self.attr_name = attr_name

    def register(self, name, attr_value=None):
        """
        Register a class with a given name.

        :param name: name to identify the class
        :param attr_value: If given, it will be used to define the value of
                           the class attribute. If not given, *name* is used.
        """
        assert name not in self._classes

        def wrapper(klass):
            self._classes[name] = klass
            setattr(klass, self.attr_name, attr_value or name)
            return klass
        return wrapper

    def get(self, name):
        """
        Returns a registered class.
        """
        return self._classes[name]

    def names(self):
        """
        Returns a list of registered class names.
        """
        return sorted(self._classes)
