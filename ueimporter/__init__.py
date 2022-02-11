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
    ERROR = -2
    WARNING = -1
    NORMAL = 0
    VERBOSE = 1
    DEBUG = 2

    def __str__(self):
        return self.name

    @classmethod
    def from_string(cls, s):
        try:
            return cls[s]
        except KeyError:
            raise ValueError()


class Logger:
    INDENTATION = ' ' * 2

    def __init__(self, log_filename, log_level):
        self.indentation = ''
        if log_filename and not log_filename.parent.is_dir():
            os.makedirs(log_filename.parent)
        self._logfile = open(log_filename, 'w') if log_filename else None
        self._log_level = log_level

    def log(self, line):
        self.print(LogLevel.NORMAL, line)

    def log_verbose(self, line):
        self.print(LogLevel.VERBOSE, line)

    def log_debug(self, line):
        self.print(LogLevel.DEBUG, line)

    def log_warning(self, line):
        self.print(LogLevel.WARNING, line)

    def log_error(self, line):
        self.print(LogLevel.ERROR, line)

    def indent(self):
        self.indentation += Logger.INDENTATION

    def deindent(self):
        if len(self.indentation) >= len(Logger.INDENTATION):
            self.indentation = self.indentation[:-len(Logger.INDENTATION)]

    def print(self, log_level, line):
        indentation = self.indentation if log_level > LogLevel.ERROR else ''
        log_line = f'{indentation}{line}'
        if log_level <= self._log_level:
            stream = sys.stderr if log_level == LogLevel.ERROR else sys.stdout
            print(log_line, file=stream)
        if self._logfile:
            self._logfile.write(log_line + os.linesep)


def run(command, logger, input_lines=None, cwd=None):
    input = ('\n'.join(input_lines) + '\n') if input_lines else None
    res = subprocess.run(command,
                         capture_output=True,
                         input=input,
                         encoding='utf-8', cwd=cwd)

    if res.returncode != 0 or res.stderr:
        logger.log_error(f'Error: returncode {res.returncode}')
        logger.log_error(res.stderr)
        sys.exit(res.returncode)

    return res.stdout
