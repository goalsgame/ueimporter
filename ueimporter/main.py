import argparse
import datetime
import enum
import os
import re
import shutil
import sys
import time

from pathlib import Path

import ueimporter.version as version
from ueimporter import Logger
from ueimporter import run

OP_SEPARATOR = '-' * 80


def create_parser():
    parser = argparse.ArgumentParser(
        description='Imports Unreal Engine releases into plastic vendor branches'
    )
    parser.add_argument('--git-repo-root',
                        required=True,
                        type=lambda p: Path(p).absolute(),
                        help="""
                        Specifies the root of the UE git repo on disc.

                        Create this directory with
                        "$ git clone git@github.com:EpicGames/UnrealEngine.git"
                        """)
    parser.add_argument('--from-release-tag',
                        help="""
                        Git tag of release currently used.
                        Required whenever a ueimporter.json file does not exist.
                        """)
    parser.add_argument('--to-release-tag',
                        required=True,
                        help='Git tag of release to upgrade to')
    parser.add_argument('--zip-package-root',
                        required=True,
                        type=lambda p: Path(p).absolute(),
                        help="""
                        Specifies where release zip files have been extracted.
                        See https://github.com/EpicGames/UnrealEngine/releases
                        """)
    parser.add_argument('--plastic-workspace-root',
                        type=lambda p: Path(p).absolute(),
                        default=Path.cwd(),
                        help="""
                        Specifies the root of the UE plastic workspace on disc.
                        Default is CWD.
                        """)
    parser.add_argument('--ueimporter-json',
                        type=lambda p: Path(p).absolute(),
                        default=Path('.ueimporter.json'),
                        help="""
                        Name of file where last integrated UE version will be
                        stored.
                        Default is ueimporter.json.
                        """)
    parser.add_argument('--log-file',
                        type=lambda p: Path(p).absolute(),
                        default=Path('.ueimporter.log'),
                        help="""
                        Name of log file where all output is saved.
                        Default is .ueimporter.log.
                        """)
    parser.add_argument('--pretend',
                        action='store_true',
                        help="""
                        Set to print what is about to happen without
                        doing anything""")
    parser.add_argument('--continue-on-error',
                        action='store_true',
                        help="""
                        Continue on non-fatal errors while executing operations.
                        Equivalent to answering "always" in the interactive
                        prompt.
                        All errors will be listed at the end, even when this
                        option is set.
                        """)
    return parser


class Git:
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
        return run(command, logger, cwd=self.repo_root)


class Plastic:
    def __init__(self, workspace_root, pretend):
        self.workspace_root = workspace_root
        self.pretend = pretend

    def to_workspace_path(self, path):
        return self.workspace_root.joinpath(path)

    def is_workspace_clean(self, logger):
        arguments = ['status',
                     '--machinereadable']
        stdout = self.run_cmd(arguments, logger)
        lines = stdout.split('\n')
        if len(lines) == 1:
            return True
        elif len(lines) == 2:
            return len(lines[1]) == 0
        else:
            return False

    def add(self, path, logger):
        return self.run_cmd(['add', path], logger)

    def remove(self, path, logger):
        return self.run_cmd(['remove', path], logger)

    def checkout(self, path, logger):
        self.run_cmd(['checkout', path], logger)

    def move(self, from_path, to_path, logger):
        self.run_cmd(['move', from_path, to_path], logger)

    def run_cmd(self, arguments, logger):
        command = ['cm'] + arguments
        logger.print(' '.join([str(s) for s in command]))
        if self.pretend:
            return ''

        stdout = run(command, logger, cwd=self.workspace_root)

        logger.indent()
        for line in stdout.split('\n'):
            if len(line) > 0:
                logger.print(line)
        logger.deindent()

        return stdout


def is_empty_dir(directory):
    for _ in directory.iterdir():
        return False
    return True


class OpException(Exception):
    def __init__(self, message):
        self.message = message


class Operation:
    def __init__(self, desc, plastic, source_root_path, pretend, logger):
        self.desc = desc
        self.plastic = plastic
        self.source_root_path = source_root_path
        self.pretend = pretend
        self.logger = logger

    def __str__(self):
        return self.desc

    def do(self):
        pass

    def ensure_directory_exists(self, directory):
        directory = self.plastic.workspace_root.joinpath(directory)
        if directory.is_dir():
            return

        self.logger.print(f'Creating {directory}')
        if not self.pretend:
            os.makedirs(directory)
        self.plastic.add(directory, self.logger)

    def copy(self, filename):
        source_filename = self.source_root_path.joinpath(
            filename)
        target_filename = self.plastic.to_workspace_path(filename)

        if not source_filename.is_file():
            raise OpException(f'Failed to find {source_filename}')

        self.ensure_directory_exists(filename.parent)

        self.logger.print(f'Copy from {source_filename}')
        if not self.pretend:
            # Copy file including file permissions and create/modify timstamps
            shutil.copy2(source_filename, target_filename)

    def remove_empty_directories(self, directory):
        directory = self.plastic.to_workspace_path(directory)
        while directory != self.plastic.workspace_root and is_empty_dir(directory):
            self.plastic.remove(directory, self.logger)
            directory = directory.parent


class AddOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Add {filename}', **kwargs)
        self.filename = Path(filename)

    def do(self):
        self.copy(self.filename)
        self.plastic.add(self.filename, self.logger)


class ModifyOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Modify {filename}', **kwargs)
        self.filename = Path(filename)

    def do(self):
        self.plastic.checkout(self.filename, self.logger)
        self.copy(self.filename)


class DeleteOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Delete {filename}', **kwargs)
        self.filename = Path(filename)

    def do(self):
        self.plastic.remove(self.filename, self.logger)
        self.remove_empty_directories(self.filename.parent)


class MoveOp(Operation):
    def __init__(self, source_filename, target_filename, **kwargs):
        Operation.__init__(
            self, f'Move {source_filename} to {target_filename}', **kwargs)
        self.source_filename = Path(source_filename)
        self.target_filename = Path(target_filename)

    def do(self):
        self.ensure_directory_exists(self.target_filename.parent)
        self.plastic.move(self.source_filename,
                          self.target_filename,
                          self.logger)
        self.copy(self.target_filename)
        self.remove_empty_directories(self.source_filename.parent)


def read_change_ops(config, logger):
    stdout = config.git.diff(config.from_release_tag,
                             config.to_release_tag, logger)
    move_regex = re.compile('^r[0-9]*$')
    mods = []
    adds = []
    dels = []
    moves = []
    for line in stdout.split('\n'):
        parts = line.split('\t')
        mode = parts[0].lower()
        if mode == 'm':
            mods.append(ModifyOp(parts[1],
                                 logger=logger,
                                 plastic=config.plastic,
                                 source_root_path=config.source_root_path,
                                 pretend=config.pretend))
        elif mode == 'a':
            adds.append(AddOp(parts[1],
                              logger=logger,
                              plastic=config.plastic,
                              source_root_path=config.source_root_path,
                              pretend=config.pretend))
        elif mode == 'd':
            dels.append(DeleteOp(parts[1],
                                 logger=logger,
                                 plastic=config.plastic,
                                 source_root_path=config.source_root_path,
                                 pretend=config.pretend))
        elif move_regex.match(mode):
            moves.append(MoveOp(parts[1], parts[2],
                                logger=logger,
                                plastic=config.plastic,
                                source_root_path=config.source_root_path,
                                pretend=config.pretend))
        elif line:
            logger.eprint('Error: Unrecognized mode', parts)
            sys.exit(1)

    return mods + adds + dels + moves


def verify_plastic_repo_state(config, logger):
    if not config.plastic.is_workspace_clean(logger):
        logger.eprint(f'Error: Plastic workspace needs to be clean')
        return False

    from_version = version.from_git_release_tag(
        config.from_release_tag)
    if not from_version:
        logger.eprint(
            f'Error: Failed to parse version from {config.from_release_tag}')
        return False

    build_version_filename = 'Engine/Build/Build.version'
    build_version_file = config.plastic.to_workspace_path(
        build_version_filename)
    if not build_version_file.is_file():
        logger.eprint(f'{build_version_filename} does not exist')
        return False

    checked_out_version = version.from_build_version_json(
        build_version_file.read_text())
    if checked_out_version != from_version:
        logger.eprint(f'Error: Plastic repo has version {checked_out_version}'
                      f' checked out, expected {from_version}')
        return False

    ueimporter_json = version.read_ueimporter_json(
        config.ueimporter_json_filename)
    if ueimporter_json and \
            (ueimporter_json.git_release_tag != config.from_release_tag):
        logger.eprint(f'Error: {config.ueimporter_json} says repo'
                      f' has UE version {checked_out_version}'
                      f' checked out, expected {from_version}')
        return False

    return True


class Config:
    def __init__(self,
                 git,
                 plastic,
                 from_release_tag,
                 to_release_tag,
                 source_root_path,
                 ueimporter_json_filename,
                 pretend):
        self.git = git
        self.plastic = plastic
        self.from_release_tag = from_release_tag
        self.to_release_tag = to_release_tag
        self.source_root_path = source_root_path
        self.ueimporter_json_filename = ueimporter_json_filename
        self.pretend = pretend


def create_config(args, logger):
    plastic = Plastic(args.plastic_workspace_root, args.pretend)
    if not plastic.to_workspace_path('.plastic').is_dir():
        logger.eprint(
            f'Error: Failed to find plastic repo at {args.plastic_workspace_root}')
        sys.exit(1)

    git = Git(args.git_repo_root)
    if not git.to_repo_path('.git').is_dir():
        logger.eprint(
            f'Error: Failed to find git repo at {args.git_repo_root}')
        sys.exit(1)

    ueimporter_json_filename = args.ueimporter_json \
        if args.ueimporter_json.is_absolute() \
        else plastic.to_workspace_path(args.ueimporter_json)

    ueimporter_json = version.read_ueimporter_json(ueimporter_json_filename)
    from_release_tag = ueimporter_json.git_release_tag \
        if ueimporter_json \
        else args.from_release_tag
    if not from_release_tag:
        logger.eprint(
            f'Error: Please specify a git release tag with either'
            f'a {args.ueimporter_json} file or --from-release-tag')
        sys.exit(1)

    if not args.to_release_tag:
        logger.eprint(
            f'Error: Please specify a git release tag with --to-release-tag')
        sys.exit(1)

    if not git.rev_parse(from_release_tag, logger):
        logger.eprint(
            f'Error: Failed to find release tag named {from_release_tag}')
        sys.exit(1)

    if not git.rev_parse(args.to_release_tag, logger):
        logger.eprint(
            f'Error: Failed to find release tag named {args.to_release_tag}')
        sys.exit(1)

    if not args.zip_package_root.is_dir():
        logger.eprint(
            f'Error: Failed to find zip package root {args.zip_package_root}')
        sys.exit(1)

    source_release_zip_path = args.zip_package_root.joinpath(
        f'UnrealEngine-{args.to_release_tag }')
    if not source_release_zip_path.is_dir():
        logger.eprint(
            f'Error: Failed to find release zip package'
            ' {source_release_zip_path}')
        sys.exit(1)

    return Config(git,
                  plastic,
                  from_release_tag,
                  args.to_release_tag,
                  source_release_zip_path,
                  ueimporter_json_filename,
                  args.pretend)


def update_ueimporter_json(config, logger):
    ueimporter_json = version.read_ueimporter_json(
        config.ueimporter_json_filename)
    ueimporter_created = False
    if not ueimporter_json:
        ueimporter_json = version.create_ueimporter_json()
        ueimporter_created = True

    ueimporter_json.git_release_tag = config.to_release_tag
    if not config.pretend:
        version.write_ueimporter_json(
            config.ueimporter_json_filename, ueimporter_json,
            force_overwrite=True)

    if ueimporter_created:
        config.plastic.add(config.ueimporter_json_filename, logger)
    else:
        config.plastic.checkout(config.ueimporter_json_filename, logger)


class Continue(enum.Enum):
    UNKNOWN = 0
    NO = 1
    YES = 1
    ALWAYS = 2


def prompt_user_wants_to_continue(logger):
    while True:
        logger.print('')
        logger.print(OP_SEPARATOR)
        user_input = input(
            'Do you want to continue? [yes|always|no]: ').lower()
        if user_input in ['yes', 'y']:
            return Continue.YES
        elif user_input in ['always', 'a']:
            return Continue.ALWAYS
        elif user_input in ['no', 'n']:
            return Continue.NO
        else:
            logger.print(f'"{user_input}" is not a valid choice')


def main():
    parser = create_parser()
    args = parser.parse_args()

    logger = Logger(args.log_file)
    config = create_config(args, logger)

    if not config.pretend and not verify_plastic_repo_state(config, logger):
        return 1

    ops = read_change_ops(config, logger)
    op_count = len(ops)
    if op_count == 0:
        logger.print('Nothing to import, exiting')
        return 0

    logger.print(f'Processing {op_count} operations')
    failed_ops = []
    continue_choice = Continue.ALWAYS if args.continue_on_error \
        else Continue.UNKNOWN
    start_timestamp = time.time()
    for i, op in enumerate(ops):
        logger.print('')
        logger.print(OP_SEPARATOR)
        elapsed_time = time.time() - start_timestamp
        remaining_time = ((elapsed_time / i) * (op_count - i)) if i else -1.0
        elapsed_time_delta = datetime.timedelta(seconds=round(elapsed_time))
        remaining_time_delta = datetime.timedelta(
            seconds=round(remaining_time))
        logger.print(f'{i + 1}/{op_count} ({i * 100 / op_count:3.1f}%)'
                     f' - Elapsed {elapsed_time_delta}'
                     f' - Remaining {remaining_time_delta}')
        logger.print(op)
        try:
            op.do()
        except OpException as e:
            logger.eprint(f'Error: {e.message}')
            if continue_choice != Continue.ALWAYS:
                continue_choice = prompt_user_wants_to_continue(logger)
                if continue_choice == Continue.NO:
                    return 1

            failed_ops.append((op, e))
        except BaseException as e:
            raise e

    if len(failed_ops) > 0:
        logger.print('')
        logger.print(OP_SEPARATOR)
        logger.print(f'Failed to process {len(failed_ops)} operations')
        for (failed_op, exception) in failed_ops:
            logger.print('')
            logger.print(OP_SEPARATOR)
            logger.print(f'{failed_op}')
            logger.indent()
            logger.print(f'{exception}')
            logger.deindent()

    logger.print('')
    logger.print(OP_SEPARATOR)
    logger.print(f'Updating {config.ueimporter_json_filename}'
                 f' with release tag {config.to_release_tag}')

    update_ueimporter_json(config, logger)

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
