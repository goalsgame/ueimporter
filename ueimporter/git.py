import ueimporter
import re

from pathlib import Path


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
        return f'Move {self.filename} to {self.target_filename}'


class Repo:
    def __init__(self, repo_root):
        self.repo_root = repo_root

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
        return self.run_cmd(arguments, logger)

    def run_cmd(self, arguments, logger):
        command = ['git'] + arguments
        logger.print(' '.join([str(s) for s in command]))
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
