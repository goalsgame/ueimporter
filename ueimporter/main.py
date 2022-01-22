import argparse
import json
import subprocess
import sys
import re

from pathlib import Path


OP_SEPARATOR = '-' * 80
INDENTATION = ' ' * 2


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
                        $ git clone git@github.com:EpicGames/UnrealEngine.git
                        """)
    parser.add_argument('--from-release-tag',
                        required=True,
                        help='Git tag of release currently used')
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
    parser.add_argument('--pretend',
                        action='store_true',
                        help="""
                        Set to print what is about to happen without
                        doing anything""")
    return parser


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class Logger:
    def __init__(self):
        self.indentation = ''

    def print(self, line):
        print(f'{self.indentation}{line}')

    def indent(self):
        self.indentation += INDENTATION

    def deindent(self):
        if len(self.indentation) >= len(INDENTATION):
            self.indentation = self.indentation[:-len(INDENTATION)]


def run(command, cwd=None):
    res = subprocess.run(command, capture_output=True,
                         encoding='utf-8', cwd=cwd)

    if res.returncode != 0 or res.stderr:
        eprint(res.stderr)
        sys.exit(res.returncode)

    return res.stdout


class Git:
    def __init__(self, repo_root):
        self.repo_root = repo_root

    def to_repo_path(self, path):
        return self.repo_root.joinpath(path)

    def rev_parse(self, ref):
        return self.run_cmd(['rev-parse', ref])

    def diff(self, from_ref, to_ref):
        arguments = [
            'diff',
            '--name-status',
            from_ref,
            to_ref]
        return self.run_cmd(arguments)

    def run_cmd(self, arguments):
        return run(['git'] + arguments, cwd=self.repo_root)


class Plastic:
    def __init__(self, workspace_root):
        self.workspace_root = workspace_root

    def to_workspace_path(self, path):
        return self.workspace_root.joinpath(path)

    def is_workspace_clean(self):
        arguments = ['status',
                     '--machinereadable']
        stdout = self.run_cmd(arguments)
        lines = stdout.split('\n')
        if len(lines) == 1:
            return True
        elif len(lines) == 2:
            return len(lines[1]) == 0
        else:
            return False

    def run_cmd(self, arguments):
        command = ['cm'] + arguments
        print(' '.join([str(s) for s in command]))

        return run(command, cwd=self.workspace_root)


class Operation:
    def __init__(self, desc, logger):
        self.desc = desc
        self.logger = logger

    def __str__(self):
        return self.desc

    def do(self):
        pass


class AddOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Add {filename}', kwargs)
        self.filename = Path(filename)

    def do(self):
        pass


class ModifyOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Modify {filename}', kwargs)
        self.filename = Path(filename)

    def do(self):
        pass


class DeleteOp(Operation):
    def __init__(self, filename, **kwargs):
        Operation.__init__(self, f'Delete {filename}', kwargs)
        self.filename = Path(filename)

    def do(self):
        pass


class MoveOp(Operation):
    def __init__(self, source_filename, target_filename, **kwargs):
        Operation.__init__(
            self, f'Move {source_filename} to {target_filename}', kwargs)
        self.source_filename = Path(source_filename)
        self.target_filename = Path(target_filename)

    def do(self):
        pass


def read_change_ops(config, logger):
    stdout = config.git.diff(config.from_release_tag, config.to_release_tag)
    move_regex = re.compile('^r[0-9]*$')
    mods = []
    adds = []
    dels = []
    moves = []
    for line in stdout.split('\n'):
        parts = line.split('\t')
        mode = parts[0].lower()
        if mode == 'm':
            mods.append(ModifyOp(parts[1], logger=logger))
        elif mode == 'a':
            adds.append(AddOp(parts[1], logger=logger))
        elif mode == 'd':
            dels.append(DeleteOp(parts[1], logger=logger))
        elif move_regex.match(mode):
            moves.append(MoveOp(parts[1], parts[2], logger=logger))
        elif line:
            eprint('Error: Unrecognized mode', parts)
            sys.exit(1)

    return mods + adds + dels + moves


def read_unreal_engine_version(filename):
    try:
        with open(filename) as build_version_file:
            build_version_dict = json.load(build_version_file)

            keys = ['MajorVersion', 'MinorVersion', 'PatchVersion']
            for key in keys:
                if not key in build_version_dict:
                    eprint(
                        f'Error: Failed to find "{key}" in {filename}')
                    sys.exit(1)
            return '.'.join([str(build_version_dict.get(key)) for key in keys])
    except Exception as e:
        eprint(f'Failed to open {filename}, {e}')
        sys.exit(1)


def release_tag_to_unreal_engine_version(release_tag):
    match = re.match('^([0-9]*).([0-9]*).([0-9]*)-.*', release_tag)
    if match:
        return '.'.join([match.group(i) for i in range(1, 4)])
    else:
        eprint(f'Error: Failed to parse version from {release_tag}')
        sys.exit(1)


def verify_plastic_repo_state(config):
    if not config.plastic.is_workspace_clean():
        eprint(
            f'Error: Plastic workspace needs to be clean')
        return False

    from_version = release_tag_to_unreal_engine_version(
        config.from_release_tag)
    build_version_filename = config.plastic.to_workspace_path(
        'Engine/Build/Build.version')
    checked_out_version = read_unreal_engine_version(build_version_filename)
    if checked_out_version != from_version:
        eprint(f'Error: Plastic repo has version {checked_out_version}'
               f' checked out, expected {from_version}')
        return False

    return True


class Config:
    def __init__(self,
                 git,
                 plastic,
                 from_release_tag,
                 to_release_tag,
                 source_release_zip_path,
                 pretend):
        self.git = git
        self.plastic = plastic
        self.from_release_tag = from_release_tag
        self.to_release_tag = to_release_tag
        self.source_release_zip_path = source_release_zip_path
        self.pretend = pretend


def create_config(args):
    git = Git(args.git_repo_root)
    if not git.to_repo_path('.git').is_dir():
        eprint(
            f'Error: Failed to find git repo at {args.git_repo_root}')
        sys.exit(1)

    if not git.rev_parse(args.from_release_tag):
        eprint(
            f'Error: Failed to find release tag named {args.from_release_tag}')
        sys.exit(1)

    if not git.rev_parse(args.to_release_tag):
        eprint(
            f'Error: Failed to find release tag named {args.from_release_tag}')
        sys.exit(1)

    plastic = Plastic(args.plastic_workspace_root)
    if not plastic.to_workspace_path('.plastic').is_dir():
        eprint(
            f'Error: Failed to find plastic repo at {args.plastic_workspace_root}')
        sys.exit(1)

    if not args.zip_package_root.is_dir():
        eprint(
            f'Error: Failed to find zip package root {args.zip_package_root}')
        sys.exit(1)

    source_release_zip_path = args.zip_package_root.joinpath(
        f'UnrealEngine-{args.to_release_tag }')
    if not source_release_zip_path.is_dir():
        eprint(
            f'Error: Failed to find release zip package'
            ' {source_release_zip_path}')
        sys.exit(1)

    return Config(git,
                  plastic,
                  args.from_release_tag,
                  args.to_release_tag,
                  source_release_zip_path,
                  args.pretend)


def main():
    parser = create_parser()
    args = parser.parse_args()
    config = create_config(args)

    if not config.pretend and not verify_plastic_repo_state(config):
        return 1

    logger = Logger()
    ops = read_change_ops(config, logger)
    op_count = len(ops)
    if op_count == 0:
        logger.print('Nothing to import, exiting')
        return 0

    logger.print('Processing {op_count} operations')
    for i, op in enumerate(ops):
        logger.print('')
        logger.print(OP_SEPARATOR)
        logger.print(f'{i + 1}/{op_count}: {op}')
        op.do()
    return 0
