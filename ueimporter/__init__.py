import sys


class Logger:
    INDENTATION = ' ' * 2

    def __init__(self):
        self.indentation = ''

    def print(self, line):
        print(f'{self.indentation}{line}')

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def indent(self):
        self.indentation += Logger.INDENTATION

    def deindent(self):
        if len(self.indentation) >= len(Logger.INDENTATION):
            self.indentation = self.indentation[:-len(Logger.INDENTATION)]
