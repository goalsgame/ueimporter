# ueimporter

`ueimporter` is a command line tool that imports
[Unreal Engine](https://www.unrealengine.com) source code releases
into a [plastic scm](https://www.plasticscm.com) repo,
by replicating changes from the official
[UnrealEngine git repo](https://github.com/EpicGames/UnrealEngine).

## Table of Contents
1. [Overview](#overview)

2. [Prequestives](#prequestives)

3. [Installation](#install)
    1. [Uninstall](#install-uninstall)
    2. [Development mode](#install-dev-mode)

4. [Usage](#usage)
    1. [Required Arguments](#usage-args-required)
    1. [Optional Arguments](#usage-args-optional)

5. [Development](#dev)
    1. [Debugging](#dev-debug)
    2. [Testing](#dev-test)


## Overview

`ueimporter` is useful for plastic version control users, that wants to
build a game using Unreal Engine, and plan to make changes to the engine code
itself, while also upgrading engine releases as they are released by Epic.

The idea is to see Unreal Engine as a third party vendor lib (albeit a really
big library). An established strategy for vendor libs is to keep a clean and
unmodified copy of the lib in a separate branch, that you merge into the
branch where you do your active development.
`ueimporter` helps create such a vendor branch, and keep it updated with
the vanilla engine for new releases.

A naive strategy would be to delete all files on the vendor branch simply
copy all files from the new release, and let plastic detect which files have
been added, removed, modified or moved.

It sounds like it should work, but the move detection in plastic seem to miss
most moves, at least when there are as many files involved as there are in an
unreal engine upgrade (4.27.2 -> 5.0.0-early-access-1 modifies over 50k files).
For a moved file you will end up with a delete followed by an add. If you have
made changes to the file in the old location on your main-branch you will miss
these when you merge down the new UE release from the vendor branch.
If plastic would know that a file was in fact moved it would be able to merge
your changes into the new location.

This move file problem is the main reason `ueimporter` exist, and to solve it
it uses information from the git repo that knows how and where a file was moved.
It simply asks git `git diff --name-status <from-release-tag> <to-release-tag>`
and we get a list of exactly which files was added, removed, modified or moved.
Once it knows it's just a question of replicating these exact changes
in plastic.

`ueimporter` is meant to be platform independent and could be used on
Windows, macOs or Linux. These platforms disagree on how line endings is encoded
in text files. The tool avoids the problem completely by not copying files
directly from the git repo, rather it expects you to download the zip files
that Epic publish for each engine release, and copies files from there.
Release zips use LF line endings.

TODO: Show a suggested branch layout from Branch Exporer

## Prequestives <a name="prequestives" />
* Python 3.10+
* Git
* [Plastic scm](https://www.plasticscm.com)
Plastics CLI tool `cm` needs to be present in `PATH`
* A cloned of the [UnrealEngine git repo](https://github.com/EpicGames/UnrealEngine)
Your github user will need to be a registered unreal developer to get access.
* A release zip for the UE release you want to import.
As listed here [UnrealEngine/releases](https://github.com/EpicGames/UnrealEngine/releases)

## Installation <a name="install" />

Install a snapshot of `ueimporter` using `pip`, from the git repo root
```
$ pip install --user .
```
This enables you to invoke `ueimporter` from any directory (such as the target
plastic repo root)

Each time you want to upgrade `ueimporter` you simply pull down the latest code
and run the command again.

### Uninstall <a name="install-uninstall" />
To uninstall you simply call pip, can be invoked from anywhere:
```
$ pip uninstall ueimporter
```

### Development mode <a name="install-dev-mode" />

If you plan do do active development of `ueimporter` it's more convenient to
install in editable/development mode. This way `pip` installs thin
wrappers in it's registry that simply forwards all invocations to the code
in your git repository.

Again, from your git repo root
```
$ pip install --user -e .
```

## Usage <a name="usage" />

TODO:
* Desc how to sync UE github repo
* Desc branch setup in plastic

Step by step guide:
1. Checkout the vendor branch
2. Make sure the workspace is completely clean (no private/ignored files)
3. Download release zip
4. Run script with --pretend

Here's an example that upgrade a UE vendor branch to `4.27.2`.
```
ueimporter
 --git-repo-root="H:\UnrealEngine"
 --to-release-tag="4.27.2-release"
 --zip-package-root="H:\Vendor\UnrealEngine"
 --plastic-workspace-root="H:\Goals\Game"
 --pretend
```
The `--pretend` argument makes the script simply log the files it will upgrade,
without actually doing it. Remove this parameter once you feel confident
that 'ueimporter' will do what you expect.

5. Run script for real

6. Verify that directory structure is identical to the release zip
7. Check in all changes into plastic
8. Rejoice


### Required Arguments <a name="usage-args-required" />

#### --git-repo-root
Specifies the root of the UE git repo on disc. Create this directory with
```
$ git clone git@github.com:EpicGames/UnrealEngine.git
```

#### --to-release-tag
Git tag of release to upgrade to.
Tags is listed here [EpicGames/UnrealEngine/tags](https://github.com/EpicGames/UnrealEngine/tags)

#### --zip-package-root
Specifies where release zip files have been extracted.
Zip files can be downloaded from [EpicGames/UnrealEngine/releases](https://github.com/EpicGames/UnrealEngine/releases)

### Optional Arguments <a name="usage-args-optional" />

#### --pretend
Set to print what is about to happen without doing anything.

#### --plastic-workspace-root
Specifies the root of the UE plastic workspace on disc.
Default is current working directory (CWD).

#### --from-release-tag
Git tag of release currently used.
Required whenever a `ueimporter.json` file does not exist.

#### --ueimporter-json
Name of file where last integrated UE version will be stored.
Default is `.ueimporter.json`.

#### --log-file
Name of log file where all output is saved.
Default is `.ueimporter/ueimporter.log`.

#### --log-level
Controls the detail level of logs that show up in `STDOUT`.
All levels always ends up in the logfile.

Available log levels
* error
* warning
* normal (default)
* verbose
* debug

#### --skip-invalid-ops
Skip operations that will fail when executed. Equivalent to choosing `skip-all` in the interactive prompt.

#### --git-command-cache
If set, results of heavy git commands will be stored in this directory.

## Development <a name="dev" />

Make sure to install `ueimporter` in dev mode, as described [above](#install-dev-mode).

### Debugging <a name="dev-debug" />
To debug you can use pythons build in `pdb` module

```
$ cd ueimporter
$ python -m pdb ueimporter\main.py $(YOUR_OPTIONS)
```

Describing how to use `pdb` is out of scope, for starters try the `help` command.
For more info see the module documentation: [pdb — The Python Debugger](https://docs.python.org/3/library/pdb.html)

### Testing <a name="dev-test" />

`ueimporter` use [pytest](https://docs.pytest.org) to run unit tests, it's
automatically installed when you install `ueimporter` with `pip`.

It's simple to use, again from the repo root:
```
# Run all tests
$ pytest

# Run a specific test-file (tests/test_path_util.py)
$ pytest -q test_path_util.py

```

Note that test coverage is not that high at the time of writing.
