class ArgumentsError(Exception):
    pass


class GenericPluginError(Exception):
    pass


class IncompatibleQueryError(Exception):
    """
    Raised by Providers if cant generate an URI for a query
    """
    pass


class QueryConversionError(Exception):
    pass
