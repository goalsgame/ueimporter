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


class Config:
    def __init__(self, git, from_release_tag, to_release_tag):
        self.git = git
        self.from_release_tag = from_release_tag
        self.to_release_tag = to_release_tag


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

    return Config(git, args.from_release_tag, args.to_release_tag)


def main():
    parser = create_parser()
    args = parser.parse_args()
    config = create_config(args)

    return list_modifications(config)
