import os
import sys
import subprocess


class Logger:
    INDENTATION = ' ' * 2

    def __init__(self, log_filename):
        self.indentation = ''
        self._logfile = open(log_filename, 'w') if log_filename else None

    def print(self, line):
        log_line = f'{self.indentation}{line}'
        print(log_line)
        if self._logfile:
            self._logfile.write(log_line + os.linesep)

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)
        if self._logfile:
            print(*args, file=self._logfile, **kwargs)

    def indent(self):
        self.indentation += Logger.INDENTATION

    def deindent(self):
        if len(self.indentation) >= len(Logger.INDENTATION):
            self.indentation = self.indentation[:-len(Logger.INDENTATION)]


def run(command, logger, cwd=None):
    res = subprocess.run(command, capture_output=True,
                         encoding='utf-8', cwd=cwd)

    if res.returncode != 0 or res.stderr:
        logger.eprint(f'Error: returncode {res.returncode}')
        logger.eprint(res.stderr)
        sys.exit(res.returncode)

    return res.stdout
