import re

def verify_proxy(proxy_type, proxy):
    """
    This verifies a proxy string. It works by whitelisting
    certain charackters: 0-9a-zA-Z:/?=-;~+
    """
    # protocol://host:port/stuff
    verify_str = "%s://[a-zA-Z0-9.-]+:[0-9]+/*$" % proxy_type

    if not re.match(verify_str, proxy):
            return False
    return True

def verify_no_proxy(proxy):
    """
    This verifies a proxy string. It works by whitelisting
    certain charackters: 0-9a-zA-Z:/?=-;~+
    """
    # protocol://host:port/stuff
    verify_str = "[a-zA-Z0-9.-:,]+" 

    if not re.match(verify_str, proxy):
            return False
    return True

