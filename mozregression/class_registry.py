class ClassRegistry(object):
    """
    A registry to store classes identified by a unique name.

    :param attr_name: On each registered class, the unique name will be saved
                      under this class attribute name.
    """

    def __init__(self, attr_name="name"):
        self._classes = {}
        self.attr_name = attr_name

    def register(self, name, attr_value=None, **kwargs):
        """
        Register a class with a given name.

        :param name: name to identify the class
        :param attr_value: If given, it will be used to define the value of
                           the class attribute. If not given, *name* is used.
        :param kwargs: key and values to add to the class object
        """
        assert name not in self._classes

        def wrapper(klass):
            self._classes[name] = klass
            setattr(klass, self.attr_name, attr_value or name)
            for key, value in kwargs.items():
                setattr(klass, key, value)
            return klass

        return wrapper

    def get(self, name):
        """
        Returns a registered class.
        """
        return self._classes[name]

    def names(self, predicate=None):
        """
        Returns a list of registered class names.

        :param predicate: if provided, should be a function to filter
                          classes. Only the names of the classes where
                          predicate returns True will be included.
        """
        names = sorted(self._classes)
        if predicate:
            for name, klass in self._classes.items():
                if not predicate(klass):
                    names.remove(name)
        return names
