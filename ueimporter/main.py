import argparse
import datetime
import enum
import sys
import time

from pathlib import Path

import ueimporter.git as git
import ueimporter.job
import ueimporter.path_util as path_util
import ueimporter.plastic as plastic
import ueimporter.version as version
from ueimporter import Logger
from ueimporter import LogLevel

SEPARATOR = '-' * 80
BATCH_SIZE = 20
MAX_OPS_PER_JOB = -1


def create_parser():
    parser = argparse.ArgumentParser(
        description='Imports Unreal Engine releases into plastic vendor branches'
    )
    parser.add_argument('--pretend',
                        action='store_true',
                        help="""
                        If set, ueimporter will log what is about to happen
                        without actually doing anything""")
    parser.add_argument('--git-repo-root',
                        required=True,
                        type=lambda p: Path(p).absolute(),
                        help="""
                        Specifies the root of the UE git repo on disc.

                        Create this directory with
                        "$ git clone git@github.com:EpicGames/UnrealEngine.git"
                        """)
    parser.add_argument('--to-release-tag',
                        required=True,
                        help='Git tag of release to upgrade to')
    parser.add_argument('--from-release-tag',
                        help="""
                        Git tag of release currently used.
                        Required whenever a ueimporter.json file does not exist.
                        """)
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
                        Default is current working directory (CWD)
                        """)
    parser.add_argument('--ueimporter-json',
                        type=lambda p: Path(p).absolute(),
                        default=Path('.ueimporter.json'),
                        help="""
                        Name of file where last integrated UE version will be
                        stored.
                        Default is .ueimporter.json
                        """)
    parser.add_argument('--log-file',
                        type=lambda p: Path(p).absolute(),
                        default=Path('.ueimporter/ueimporter.log'),
                        help="""
                        Name of log file where all output is saved.
                        Default is .ueimporter/ueimporter.log
                        """)
    parser.add_argument('--log-level',
                        default=str(LogLevel.NORMAL).lower(),
                        choices=[str(l).lower() for l in list(LogLevel)],
                        help="""
                        Controls the detail level of logs that show up
                        in STDOUT. All levels always ends up in the logfile.
                        Default is normal
                        """)
    parser.add_argument('--skip-invalid-ops',
                        action='store_true',
                        help="""
                        Skip operations that will fail when executed, for
                        instance a modified file that does not exist in
                        the zip package from which it will be copied.
                        Equivalent to answering "skip-all" in the interactive
                        prompt
                        """)
    parser.add_argument('--git-command-cache',
                        type=lambda p: Path(p).absolute(),
                        help="""
                        If set, results of heavy git commands will be stored
                        in this directory
                        """)
    return parser


def read_change_jobs(config, logger):
    try:
        logger.log('Resolving git hashes of release tags')
        logger.indent()
        from_git_hash = config.git_repo.rev_list(
            config.from_release_tag, logger)
        to_git_hash = config.git_repo.rev_list(config.to_release_tag, logger)
        logger.log(f'{config.from_release_tag} <=> {from_git_hash}')
        logger.log(f'{config.to_release_tag} <=> {to_git_hash}')
        logger.deindent()

        logger.log(f'Reading changes between'
                   f' {config.from_release_tag}'
                   f' and {config.to_release_tag} from git')
        changes = git.read_changes(config.git_repo,
                                   from_git_hash,
                                   to_git_hash,
                                   logger)
    except git.ParseError as e:
        logger.log_error(f'Error: {e}')
        sys.exit(1)

    return ueimporter.job.create_jobs(
        changes,
        plastic_repo=config.plastic_repo,
        source_root_path=config.source_root_path,
        pretend=config.pretend,
        logger=logger)


def verify_plastic_repo_state(config, logger):
    if not config.plastic_repo.is_workspace_clean(logger):
        logger.log_error(f'Error: Plastic workspace needs to be clean')
        return False

    from_version = version.from_git_release_tag(
        config.from_release_tag)
    if not from_version:
        logger.log_error(
            f'Error: Failed to parse version from {config.from_release_tag}')
        return False

    build_version_filename = 'Engine/Build/Build.version'
    build_version_file = config.plastic_repo.to_workspace_path(
        build_version_filename)
    if not build_version_file.is_file():
        logger.log_error(f'{build_version_filename} does not exist')
        return False

    checked_out_version = version.from_build_version_json(
        build_version_file.read_text())
    if checked_out_version != from_version:
        logger.log_error(f'Error: Plastic repo has version {checked_out_version}'
                         f' checked out, expected {from_version}')
        return False

    ueimporter_json = version.read_ueimporter_json(
        config.ueimporter_json_filename)
    if ueimporter_json and \
            (ueimporter_json.git_release_tag != config.from_release_tag):
        logger.log_error(f'Error: {config.ueimporter_json} says repo'
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
        logger.log_error(
            f'Error: Failed to find plastic repo at {args.plastic_workspace_root}')
        sys.exit(1)

    git_repo = git.Repo(args.git_repo_root, args.git_command_cache)
    if not git_repo.to_repo_path('.git').is_dir():
        logger.log_error(
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
        logger.log_error(
            f'Error: Please specify a git release tag with either'
            f' a {args.ueimporter_json} file or --from-release-tag')
        sys.exit(1)

    if not args.to_release_tag:
        logger.log_error(
            f'Error: Please specify a git release tag with --to-release-tag')
        sys.exit(1)

    if not git_repo.rev_list(from_release_tag, logger):
        logger.log_error(
            f'Error: Failed to find release tag named {from_release_tag}')
        sys.exit(1)

    if not git_repo.rev_list(args.to_release_tag, logger):
        logger.log_error(
            f'Error: Failed to find release tag named {args.to_release_tag}')
        sys.exit(1)

    if not args.zip_package_root.is_dir():
        logger.log_error(
            f'Error: Failed to find zip package root {args.zip_package_root}')
        sys.exit(1)

    source_release_zip_path = args.zip_package_root.joinpath(
        f'UnrealEngine-{args.to_release_tag }')
    if not source_release_zip_path.is_dir():
        logger.log_error(
            f'Error: Failed to find release zip package'
            f' {source_release_zip_path}')
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


class ContinuePromptResponse(enum.Enum):
    CONTINUE = 1
    CONTINUE_ALWAYS = 2
    ABORT = 3


def prompt_user_continue(logger,
                         question,
                         include_always_option=False):
    while True:
        logger.log('')
        user_input_map = {
            'yes': ContinuePromptResponse.CONTINUE,
            'y': ContinuePromptResponse.CONTINUE,

            'no': ContinuePromptResponse.ABORT,
            'n': ContinuePromptResponse.ABORT,
        }
        legend = '[yes|'
        if include_always_option:
            legend += 'all|'
            user_input_map |= {
                'all': ContinuePromptResponse.CONTINUE_ALWAYS,
                'a': ContinuePromptResponse.CONTINUE_ALWAYS,
            }
        legend += 'no]'

        logger.log(f'{question} {legend}: ', new_line=False)
        user_input = input()
        response = user_input_map.get(user_input.lower())
        if response:
            logger.log_verbose(f'{user_input}')
            return response
        else:
            logger.log_warning(
                f'"{user_input}" is not a valid choice')


def get_elapsed_time(start_timestamp):
    elapsed_time = time.time() - start_timestamp
    return datetime.timedelta(seconds=round(elapsed_time))


class JobTimeEstimate:
    def __init__(self, op_count):
        self._job_op_count = op_count
        self._processed_op_count = 0
        self._batch_size = 0
        self._batch_start_timestamp = 0
        self._job_elapsed_time = 0

    def start_batch(self, batch_size):
        self._batch_size = batch_size
        self._batch_start_timestamp = time.time()

    def end_batch(self):
        self._processed_op_count += self._batch_size
        batch_elapsed_time = time.time() - self._batch_start_timestamp
        self._job_elapsed_time += batch_elapsed_time
        return datetime.timedelta(seconds=round(batch_elapsed_time))

    def estimate_remaining_time(self):
        if self._processed_op_count == 0:
            return datetime.timedelta(seconds=0)

        time_per_op = self._job_elapsed_time / self._processed_op_count
        remaining_ops = self._job_op_count - self._processed_op_count
        remaining_time = round(remaining_ops * time_per_op)
        return datetime.timedelta(seconds=round(remaining_time))


class ProgressListener(ueimporter.job.JobProgressListener):
    def __init__(self, logger, start_timestamp, total_op_count):
        self._start_timestamp = start_timestamp
        self._logger = logger
        self._total_op_count = total_op_count
        self._processed_op_count = 0
        self._time_estimates = {}
        self._active_time_estimate = None

    def register_job(self, job):
        assert job not in self._time_estimates
        op_count = len(job.ops)
        self._time_estimates[job] = JobTimeEstimate(op_count)

    def start_batch(self, job, ops):
        batch_size = len(ops)
        time_estimate = self._time_estimates.get(job)
        assert time_estimate
        time_estimate.start_batch(batch_size)
        self._active_time_estimate = time_estimate
        remaining_time = self.estimate_remaining_time()

        total_elapsed_time = get_elapsed_time(self._start_timestamp)
        batch_start = self._processed_op_count
        batch_end = batch_start + batch_size
        self._processed_op_count += batch_size
        self._logger.log(SEPARATOR)
        self._logger.log(f'Processing '
                         f'[{batch_start},{batch_end})'
                         f' / {self._total_op_count}'
                         f' - Elapsed {total_elapsed_time}'
                         f' - Remaining {remaining_time}')
        self._logger.indent()
        for op in ops:
            op_desc = str(op)
            for line in op_desc.split('\n'):
                self._logger.log(line)
        self._logger.log('')

    def end_batch(self):
        assert self._active_time_estimate
        batch_elapsed_time = self._active_time_estimate.end_batch()
        self._active_time_estimate = None
        self._logger.deindent()
        self._logger.log('')
        self._logger.log(f'Batch time {batch_elapsed_time}')

    def start_step(self, desc):
        self._logger.log(f'* {desc}')
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

    log_level = LogLevel.from_string(args.log_level)
    logger = Logger(args.log_file, log_level)
    config = create_config(args, logger)

    if not config.pretend and not verify_plastic_repo_state(config, logger):
        return 1

    if not path_util.is_directory_on_case_sensitive_filesystem(
            config.plastic_repo.workspace_root):
        logger.log_warning('Warning: Case insensitive filesystem detected.\n'
                           'ueimporter has no way of correctly replicating'
                           ' case changes of files and directories from git.\n'
                           'You are advised to run ueimporter from an OS'
                           ' with a case sensitive file system instead'
                           ', such as Linux.')

        response = prompt_user_continue(
            question='Do you want to continue anyway?',
            logger=logger)
        if response == ContinuePromptResponse.ABORT:
            logger.log("Aborting")
            return 1
        else:
            logger.log('Beware, yonder there be dragons.')

    start_timestamp = time.time()
    jobs = read_change_jobs(config, logger)
    logger.log(f'Processing {len(jobs)} jobs')

    logger.log(f'Validating ops')
    skip_all_invalid_ops = args.skip_invalid_ops
    invalid_ops = []
    invalid_op_count = 0
    for job in jobs:
        ops = job.find_invalid_ops()
        invalid_ops.append((job, ops))
        invalid_op_count += len(ops)

    if invalid_ops:
        logger.indent()
        logger.log(f'Found {invalid_op_count} invalid ops')
        for job, ops in invalid_ops:
            for (op, err) in ops:
                logger.log(SEPARATOR)
                logger.log_error(f'{op}')
                logger.indent()
                logger.log_warning(f'{err}')

                if skip_all_invalid_ops:
                    response = ContinuePromptResponse.CONTINUE_ALWAYS
                else:
                    response = prompt_user_continue(
                        question='Do you want to continue and skip this op?',
                        include_always_option=True,
                        logger=logger)

                if response == ContinuePromptResponse.ABORT:
                    logger.log("Aborting")
                    return 1
                elif response == ContinuePromptResponse.CONTINUE or \
                        response == ContinuePromptResponse.CONTINUE_ALWAYS:
                    job.remove_op(op)
                    logger.log("Skipping operation")
                    skip_all_invalid_ops = \
                        response == ContinuePromptResponse.CONTINUE_ALWAYS
                logger.deindent()

        logger.deindent()

    job_op_counts = {}
    for job in jobs:
        op_count = job_op_counts.get(job.__class__, 0)
        job_op_counts[job.__class__] = op_count + len(job.ops)

    def print_stats():
        logger.indent()
        total_op_count = 0
        max_line_length = 0
        for job_class in ueimporter.job.JOB_CLASSES:
            op_count = job_op_counts.get(job_class, 0)
            total_op_count += op_count
            line = f'{job_class.job_desc}: {op_count} ops'
            max_line_length = max(len(line), max_line_length)
            logger.log(line)
        line = f'(Skip: {invalid_op_count} invalid ops)'
        logger.log(line)
        max_line_length = max(len(line), max_line_length)
        logger.log('=' * max_line_length)
        logger.log(f'{total_op_count} ops in total')
        logger.deindent()

    logger.log(SEPARATOR)
    logger.log('Job summary')
    print_stats()

    if MAX_OPS_PER_JOB >= 0:
        for job in jobs:
            job.trim_trailing_ops(MAX_OPS_PER_JOB)

    total_op_count = sum([len(j.ops) for j in jobs])
    progress_listener = ProgressListener(
        logger, start_timestamp, total_op_count)

    # Register jobs and process one batch each, to seed time estimates with
    # real world measurements
    for job in jobs:
        progress_listener.register_job(job)
        job.process(BATCH_SIZE, BATCH_SIZE, progress_listener)

    # Process the rest of ops for each job in turn
    for job in jobs:
        job.process(BATCH_SIZE, -1, progress_listener)

    logger.log(SEPARATOR)
    logger.log(f'Updating {config.ueimporter_json_filename}'
               f' with release tag {config.to_release_tag}')

    update_ueimporter_json(config, logger)
    logger.log('')

    logger.log(SEPARATOR)
    logger.log('Summary')
    print_stats()
    total_elapsed_time = get_elapsed_time(start_timestamp)
    logger.log(f'Total elapsed time {total_elapsed_time}')

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
