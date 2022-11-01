import os
import re
import ueimporter
import unicodedata

from pathlib import PurePosixPath

import ueimporter.path_util as path_util


class ParseError(Exception):
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return self._message


class Change:
    def __init__(self, filename):
        self._filename = PurePosixPath(filename)

    @property
    def filename(self):
        return self._filename

    def __str__(self):
        return f'{self.__class__.__name__} {self.filename}'


class Add(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)


class Modify(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)


class Delete(Change):
    def __init__(self, filename):
        Change.__init__(self, filename)


class Move(Change):
    def __init__(self, source_filename, target_filename):
        Change.__init__(self, source_filename)
        self._target_filename = PurePosixPath(target_filename)

    @property
    def target_filename(self):
        return self._target_filename

    def __str__(self):
        common = path_util.commonpath(self.filename, self.target_filename)
        if common:
            from_relative = self.filename.relative_to(common)
            to_relative = self.target_filename.relative_to(common)
            return \
                f'Move {from_relative}\n' \
                f'  to {to_relative}\n' \
                f'  in {common}'
        else:
            return \
                f'Move {self.filename}\n' \
                f'  to {self.target_filename}'


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

    def rev_list(self, ref, logger):
        return self.run_cmd(['rev-list', '-n', '1', ref], logger).rstrip('\r\n')

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
            logger.log_verbose(' '.join(
                [str(s) for s in cache_command]))
            logger.log_verbose('Reading stdout from command cache')
            return self.command_cache.read_entry(cache_command)

        stdout = self.run_cmd(arguments, logger)

        if self.command_cache:
            logger.log_verbose('Writing stdout to command cache')
            self.command_cache.write_entry(cache_command, stdout)

        return stdout

    def run_cmd(self, arguments, logger):
        command = ['git'] + arguments
        logger.log_verbose(' '.join([str(s) for s in command]))
        return ueimporter.run(command, logger, cwd=self.repo_root)


MOVE_REGEX = re.compile('^r[0-9]*$')


def parse_change_line(line_number, line):
    parts = line.split('\t')
    mode = parts[0].lower()
    if mode == 'm':
        return Modify(parts[1])
    elif mode == 'a':
        return Add(parts[1])
    elif mode == 'd':
        return Delete(parts[1])
    elif MOVE_REGEX.match(mode):
        return Move(parts[1], parts[2])

    raise ParseError(
        f'Unrecognized git diff change mode on line {line_number}:'
        f' "{line}"')


class Changes:
    def __init__(self, per_file_changes, modifications, adds, deletes, moves):
        self.per_file_changes = per_file_changes
        self.modifications = modifications
        self.adds = adds
        self.deletes = deletes
        self.moves = moves


def read_changes(git_repo, from_release_tag, to_release_tag, logger):
    stdout = git_repo.diff(from_release_tag,
                           to_release_tag, logger)

    filename_to_changes = {}
    for line_it, line in enumerate(stdout.split('\n')):
        if not line:
            continue

        change = parse_change_line(line_it + 1, line)
        lower_filename = str(change.filename).lower()
        if lower_filename in filename_to_changes:
            filename_to_changes[lower_filename].append(change)
        else:
            filename_to_changes[lower_filename] = [change]

    changes_per_type = {
        Modify: [],
        Add: [],
        Delete: [],
        Move: []
    }
    per_file_changes = {}
    for lower_filename, changes in filename_to_changes.items():
        if len(changes) == 1:
            change = changes[0]
            changes_per_type[type(change)].append(change)
        else:
            per_file_changes[lower_filename] = changes

    mods = sorted(changes_per_type[Modify], key=lambda m: m.filename)
    adds = sorted(changes_per_type[Add], key=lambda m: m.filename)
    dels = sorted(changes_per_type[Delete], key=lambda m: m.filename)
    moves = sorted(changes_per_type[Move], key=lambda m: m.filename)

    return Changes(per_file_changes, mods, adds, dels, moves)
