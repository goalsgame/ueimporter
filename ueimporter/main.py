import argparse
import subprocess
import sys
import re

from pathlib import Path


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
    return parser


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


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


def list_modifications(config):
    stdout = config.git.diff(config.from_release_tag, config.to_release_tag)
    move_regex = re.compile('^r[0-9]*$')
    for line in stdout.split('\n'):
        parts = line.split('\t')
        mode = parts[0].lower()
        if mode == 'a':
            print('Added', parts[1])
        elif mode == 'm':
            print('Modified', parts[1])
        elif mode == 'd':
            print('Deleted', parts[1])
        elif move_regex.match(mode):
            print('Renamed', parts[1], 'to', parts[1])
        elif line:
            eprint('Error: Unrecognized mode', parts)
            return 1

    return 0


def verify_plastic_repo_state(config):
    if not config.plastic.is_workspace_clean():
        eprint(
            f'Error: Plastic workspace needs to be clean')
        return False

    return True


class Config:
    def __init__(self,
                 git,
                 plastic,
                 from_release_tag,
                 to_release_tag,
                 source_release_zip_path):
        self.git = git
        self.plastic = plastic
        self.from_release_tag = from_release_tag
        self.to_release_tag = to_release_tag
        self.source_release_zip_path = source_release_zip_path


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
                  source_release_zip_path)


def main():
    parser = create_parser()
    args = parser.parse_args()
    config = create_config(args)

    if not verify_plastic_repo_state(config):
        return 1

    return list_modifications(config)
