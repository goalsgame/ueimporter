import os
import sys
import subprocess
import enum


class OrderedEnum(enum.Enum):
    def __ge__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value >= rhs.value
        return NotImplemented

    def __gt__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value > rhs.value
        return NotImplemented

    def __le__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value <= rhs.value
        return NotImplemented

    def __lt__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value < rhs.value
        return NotImplemented

    def __eq__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value == rhs.value
        return NotImplemented

    def __ne__(self, rhs):
        if self.__class__ is rhs.__class__:
            return self.value != rhs.value
        return NotImplemented


class LogLevel(OrderedEnum):
    NORMAL = 0
    VERBOSE = 1
    DEBUG = 2


class Logger:
    INDENTATION = ' ' * 2

    def __init__(self, log_filename, log_level):
        self.indentation = ''
        if log_filename and not log_filename.parent.is_dir():
            os.makedirs(log_filename.parent)
        self._logfile = open(log_filename, 'w') if log_filename else None
        self._log_level = log_level

    def print(self, log_level, line):
        log_line = f'{self.indentation}{line}'
        if log_level <= self._log_level:
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


def run(command, logger, input_lines=None, cwd=None):
    input = ('\n'.join(input_lines) + '\n') if input_lines else None
    res = subprocess.run(command,
                         capture_output=True,
                         input=input,
                         encoding='utf-8', cwd=cwd)

    if res.returncode != 0 or res.stderr:
        logger.eprint(f'Error: returncode {res.returncode}')
        logger.eprint(res.stderr)
        sys.exit(res.returncode)

    return res.stdout
