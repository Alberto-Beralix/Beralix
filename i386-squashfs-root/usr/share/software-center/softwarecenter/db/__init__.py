try:
    from debfile import DebFileApplication
    DebFileApplication # pyflakes
except ImportError:
    class DebFileApplication(): 
        pass
