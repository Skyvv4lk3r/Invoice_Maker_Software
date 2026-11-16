"""An allowlisted authorization decorator, not a service locator.

Each returned capability exposes only the methods explicitly selected in bootstrap.
The original services remain private to the composition root.
"""


class AuthorizedCapability:
    def __init__(self, service, authentication, methods):
        self.__service = service
        self.__authentication = authentication
        self.__methods = frozenset(methods)

    def __getattr__(self, name):
        if name not in self.__methods:
            raise AttributeError(name)
        method = getattr(self.__service, name)
        return lambda *args, **kwargs: self.__authentication.protect(
            lambda: method(*args, **kwargs)
        )
