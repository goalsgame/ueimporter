import os
import os.path
import re
import ueimporter
import unicodedata

from pathlib import Path
from ueimporter import LogLevel


class ParseError(Exception):
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return self._message


class Change:
    def __init__(self, filename):
        self._filename = Path(filename)

    @property
    def filename(self):
        return self._filename


class Add(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)

    def __str__(self):
        return f'Add {self.filename}'


class Modify(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)

    def __str__(self):
        return f'Modify {self.filename}'


class Delete(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)

    def __str__(self):
        return f'Delete {self.filename}'


class Move(Change):
    def __init__(self, source_filename, target_filename):
        Change.__init__(self, source_filename)
        self._target_filename = Path(target_filename)

    @property
    def target_filename(self):
        return self._target_filename

    def __str__(self):
        common = Path(os.path.commonpath([self.filename, self.target_filename]))
        if common:
            from_relative = self.filename.relative_to(common)
            to_relative = self.target_filename.relative_to(common)
            return f'Move {from_relative}\n' \
                   f'  to {to_relative}\n' \
                   f'  in {common}'
        else:
            return f'Move {self.filename}\n' \
                   f'  to {self.target_filename}\n' \



def to_valid_filename(value):
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode(
        'ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


class CommandCache:
    def __init__(self, command_cache_dir):
        self._command_cache_dir = command_cache_dir
        if not command_cache_dir.is_dir():
            os.makedirs(command_cache_dir)

    def has_entry(self, command):
        filename = self.get_entry_filename(command)
        return filename.is_file()

    def read_entry(self, command):
        filename = self.get_entry_filename(command)
        if filename.is_file():
            return filename.read_text(encoding='utf-8')
        return None

    def write_entry(self, command, stdout):
        filename = self.get_entry_filename(command)
        filename.write_text(stdout, encoding='utf-8')
        pass

    def get_entry_filename(self, command):
        entry_name = to_valid_filename("_".join(command))
        return self._command_cache_dir.joinpath(f'{entry_name}.stdout')


class Repo:
    def __init__(self, repo_root, command_cache):
        self.repo_root = repo_root
        self.command_cache = CommandCache(
            command_cache) if command_cache else None

    def to_repo_path(self, path):
        return self.repo_root.joinpath(path)

    def rev_parse(self, ref, logger):
        return self.run_cmd(['rev-parse', ref], logger)

    def diff(self, from_ref, to_ref, logger):
        arguments = [
            'diff',
            '--name-status',
            from_ref,
            to_ref]
        return self.run_cmd_cached(arguments, logger)

    def run_cmd_cached(self, arguments, logger):
        cache_command = ['git'] + arguments
        if self.command_cache and self.command_cache.has_entry(cache_command):
            logger.print(LogLevel.VERBOSE, ' '.join([str(s) for s in cache_command]))
            logger.print(LogLevel.VERBOSE, 'Reading stdout from command cache')
            return self.command_cache.read_entry(cache_command)

        stdout = self.run_cmd(arguments, logger)

        if self.command_cache:
            logger.print(LogLevel.VERBOSE, 'Writing stdout to command cache')
            self.command_cache.write_entry(cache_command, stdout)

        return stdout

    def run_cmd(self, arguments, logger):
        command = ['git'] + arguments
        logger.print(LogLevel.VERBOSE, ' '.join([str(s) for s in command]))
        return ueimporter.run(command, logger, cwd=self.repo_root)


def read_changes(git_repo, from_release_tag, to_release_tag, logger):
    stdout = git_repo.diff(from_release_tag,
                           to_release_tag, logger)
    move_regex = re.compile('^r[0-9]*$')
    mods = []
    adds = []
    dels = []
    moves = []
    for line in stdout.split('\n'):
        parts = line.split('\t')
        mode = parts[0].lower()
        if mode == 'm':
            mods.append(Modify(parts[1]))
        elif mode == 'a':
            adds.append(Add(parts[1]))
        elif mode == 'd':
            dels.append(Delete(parts[1]))
        elif move_regex.match(mode):
            moves.append(Move(parts[1], parts[2]))
        elif line:
            raise ParseError(
                f'Unrecognized git diff change mode "{mode}" in "{line}"')

    mods = sorted(mods, key=lambda m: m.filename)
    adds = sorted(adds, key=lambda m: m.filename)
    dels = sorted(dels, key=lambda m: m.filename)
    moves = sorted(moves, key=lambda m: m.filename)

    return mods + adds + dels + moves
