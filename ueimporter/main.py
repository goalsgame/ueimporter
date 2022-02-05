import argparse
import datetime
import enum
import sys
import time

from pathlib import Path

import ueimporter.git as git
import ueimporter.job
import ueimporter.plastic as plastic
import ueimporter.version as version
from ueimporter import Logger
from ueimporter import LogLevel

SEPARATOR = '-' * 80
BATCH_SIZE = 20
MAX_CHANGES_PER_JOB = -1


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
                        default=Path('.ueimporter/ueimporter.log'),
                        help="""
                        Name of log file where all output is saved.
                        Default is .ueimporter.log.
                        """)
    parser.add_argument('--log-level',
                        type=LogLevel,
                        default=LogLevel.NORMAL,
                        help="""
                        Controls the detail level of logs that show up
                        in STDOUT. All levels always ends up in the logfile.
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
    parser.add_argument('--git-command-cache',
                        type=lambda p: Path(p).absolute(),
                        help="""
                        If set, results of heavy git commands will be stored
                        in this directory.
                        """)
    return parser


def read_change_jobs(config, logger):
    try:
        changes = git.read_changes(config.git_repo,
                                   config.from_release_tag,
                                   config.to_release_tag,
                                   logger)
    except git.ParseError as e:
        logger.eprint(f'Error: {e}')
        sys.exit(1)

    return ueimporter.job.create_jobs(
        changes,
        plastic_repo=config.plastic_repo,
        source_root_path=config.source_root_path,
        pretend=config.pretend,
        logger=logger)


def verify_plastic_repo_state(config, logger):
    if not config.plastic_repo.is_workspace_clean(logger):
        logger.eprint(f'Error: Plastic workspace needs to be clean')
        return False

    from_version = version.from_git_release_tag(
        config.from_release_tag)
    if not from_version:
        logger.eprint(
            f'Error: Failed to parse version from {config.from_release_tag}')
        return False

    build_version_filename = 'Engine/Build/Build.version'
    build_version_file = config.plastic_repo.to_workspace_path(
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
                 git_repo,
                 plastic_repo,
                 from_release_tag,
                 to_release_tag,
                 source_root_path,
                 ueimporter_json_filename,
                 pretend):
        self.git_repo = git_repo
        self.plastic_repo = plastic_repo
        self.from_release_tag = from_release_tag
        self.to_release_tag = to_release_tag
        self.source_root_path = source_root_path
        self.ueimporter_json_filename = ueimporter_json_filename
        self.pretend = pretend


def create_config(args, logger):
    plastic_repo = plastic.Repo(args.plastic_workspace_root, args.pretend)
    if not plastic_repo.to_workspace_path('.plastic').is_dir():
        logger.eprint(
            f'Error: Failed to find plastic repo at {args.plastic_workspace_root}')
        sys.exit(1)

    git_repo = git.Repo(args.git_repo_root, args.git_command_cache)
    if not git_repo.to_repo_path('.git').is_dir():
        logger.eprint(
            f'Error: Failed to find git repo at {args.git_repo_root}')
        sys.exit(1)

    ueimporter_json_filename = args.ueimporter_json \
        if args.ueimporter_json.is_absolute() \
        else plastic_repo.to_workspace_path(args.ueimporter_json)

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

    if not git_repo.rev_parse(from_release_tag, logger):
        logger.eprint(
            f'Error: Failed to find release tag named {from_release_tag}')
        sys.exit(1)

    if not git_repo.rev_parse(args.to_release_tag, logger):
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

    return Config(git_repo,
                  plastic_repo,
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
        config.plastic_repo.add(config.ueimporter_json_filename, logger)
    else:
        config.plastic_repo.checkout(config.ueimporter_json_filename, logger)


class Continue(enum.Enum):
    UNKNOWN = 0
    NO = 1
    YES = 2
    ALWAYS = 3


def prompt_user_wants_to_continue(logger):
    while True:
        logger.print(LogLevel.NORMAL, '')
        logger.print(LogLevel.NORMAL, SEPARATOR)
        user_input = input(
            'Do you want to continue? [yes|always|no]: ').lower()
        if user_input in ['yes', 'y']:
            return Continue.YES
        elif user_input in ['always', 'a']:
            return Continue.ALWAYS
        elif user_input in ['no', 'n']:
            return Continue.NO
        else:
            logger.print(LogLevel.NORMAL,
                         f'"{user_input}" is not a valid choice')


def get_elapsed_time(start_timestamp):
    elapsed_time = time.time() - start_timestamp
    return datetime.timedelta(seconds=round(elapsed_time))


class JobTimeEstimate:
    def __init__(self, change_count):
        self._job_change_count = change_count
        self._processed_change_count = 0
        self._batch_size = 0
        self._batch_start_timestamp = 0
        self._job_elapsed_time = 0

    def start_batch(self, batch_size):
        self._batch_size = batch_size
        self._batch_start_timestamp = time.time()

    def end_batch(self):
        self._processed_change_count += self._batch_size
        batch_elapsed_time = time.time() - self._batch_start_timestamp
        self._job_elapsed_time += batch_elapsed_time
        return datetime.timedelta(seconds=round(batch_elapsed_time))

    def estimate_remaining_time(self):
        if self._processed_change_count == 0:
            return datetime.timedelta(seconds=0)

        time_per_change = self._job_elapsed_time / self._processed_change_count
        remaining_changes = self._job_change_count - self._processed_change_count
        remaining_time = round(remaining_changes * time_per_change)
        return datetime.timedelta(seconds=round(remaining_time))


class ProgressListener(ueimporter.job.JobProgressListener):
    def __init__(self, logger, start_timestamp, total_change_count):
        self._start_timestamp = start_timestamp
        self._logger = logger
        self._total_change_count = total_change_count
        self._processed_change_count = 0
        self._time_estimates = {}
        self._active_time_estimate = None

    def register_job(self, job):
        assert job.desc not in self._time_estimates
        change_count = len(job.changes)
        self._time_estimates[job.desc] = JobTimeEstimate(change_count)

    def start_batch(self, job_desc, changes):
        batch_size = len(changes)
        time_estimate = self._time_estimates.get(job_desc)
        assert time_estimate
        time_estimate.start_batch(batch_size)
        self._active_time_estimate = time_estimate
        remaining_time = self.estimate_remaining_time()

        total_elapsed_time = get_elapsed_time(self._start_timestamp)
        batch_start = self._processed_change_count
        batch_end = batch_start + batch_size
        self._processed_change_count += batch_size
        self._logger.print(LogLevel.NORMAL, SEPARATOR)
        self._logger.print(LogLevel.NORMAL,
                           f'Processing '
                           f'[{batch_start},{batch_end})'
                           f' / {self._total_change_count}'
                           f' - Elapsed {total_elapsed_time}'
                           f' - Remaining {remaining_time}')
        self._logger.indent()
        for change in changes:
            change_desc = str(change)
            for line in change_desc.split('\n'):
                self._logger.print(LogLevel.NORMAL, line)
            self._logger.print(LogLevel.NORMAL, str(change))
        self._logger.print(LogLevel.NORMAL, '')

    def end_batch(self):
        assert self._active_time_estimate
        batch_elapsed_time = self._active_time_estimate.end_batch()
        self._active_time_estimate = None
        self._logger.deindent()
        self._logger.print(LogLevel.NORMAL, '')
        self._logger.print(LogLevel.NORMAL, f'Batch time {batch_elapsed_time}')

    def start_step(self, desc):
        self._logger.print(LogLevel.NORMAL, f'* {desc}')
        self._logger.indent()

    def end_step(self):
        self._logger.deindent()

    def estimate_remaining_time(self):
        remaining_time = datetime.timedelta(seconds=0)
        for time_estimate in self._time_estimates.values():
            remaining_time += time_estimate.estimate_remaining_time()
        return remaining_time


def main():
    parser = create_parser()
    args = parser.parse_args()

    logger = Logger(args.log_file, args.log_level)
    config = create_config(args, logger)

    if not config.pretend and not verify_plastic_repo_state(config, logger):
        return 1

    start_timestamp = time.time()
    jobs = read_change_jobs(config, logger)
    logger.print(LogLevel.NORMAL, f'Processing {len(jobs)} jobs')

    logger.print(LogLevel.NORMAL,
                 f'Validating source files in {config.source_root_path}')
    continue_on_error = Continue.ALWAYS if args.continue_on_error \
        else Continue.UNKNOWN
    for job in jobs:
        changes_with_missing = job.prune_changes_with_missing_source_files()
        if not changes_with_missing:
            continue
        logger.print(LogLevel.NORMAL,
                     f'Found {len(changes_with_missing)} with missing files')
        logger.indent()
        for change in changes_with_missing:
            logger.print(LogLevel.NORMAL, f'{change}')
        logger.deindent()

        if continue_on_error == Continue.ALWAYS:
            continue

        continue_on_error = prompt_user_wants_to_continue(logger)
        if continue_on_error == Continue.NO:
            return 1

    if MAX_CHANGES_PER_JOB >= 0:
        for job in jobs:
            job.trim_trailing_changes(MAX_CHANGES_PER_JOB)

    total_change_count = sum([len(j.changes) for j in jobs])
    progress_listener = ProgressListener(
        logger, start_timestamp, total_change_count)

    # Register jobs and process one batch each, to seed time estimates with
    # real world measurements
    for job in jobs:
        progress_listener.register_job(job)
        job.process(BATCH_SIZE, BATCH_SIZE, progress_listener)

    # Process the rest of changes for each job in turn
    for job in jobs:
        job.process(BATCH_SIZE, -1, progress_listener)

    logger.print(LogLevel.NORMAL, SEPARATOR)
    logger.print(LogLevel.NORMAL, f'Updating {config.ueimporter_json_filename}'
                 f' with release tag {config.to_release_tag}')

    update_ueimporter_json(config, logger)
    logger.print(LogLevel.NORMAL, '')

    logger.print(LogLevel.NORMAL, SEPARATOR)
    total_elapsed_time = get_elapsed_time(start_timestamp)
    logger.print(LogLevel.NORMAL, f'Total elapsed time {total_elapsed_time}')

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
