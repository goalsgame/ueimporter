# UEIMPORTER

UEIMPORTER is a command line tool that imports
[Unreal Engine](https://www.unrealengine.com) source code releases
into a [Plastic scm](https://www.plasticscm.com) repo,
by replicating changes from the official
[UnrealEngine GitHub repo](https://github.com/EpicGames/UnrealEngine).

## Table of Contents
1. [Overview](#overview)

1. [Suggested branch layout](#branch-layout)

1. [Prequestives](#prequestives)

1. [Installation](#install)
    1. [Uninstall](#install-uninstall)
    1. [Development mode](#install-dev-mode)

1. [Usage](#usage)
    1. [Step by step guide](#usage-guide)
    1. [Arguments](#usage-args)

1. [Development](#dev)
    1. [Debugging](#dev-debug)
    1. [Testing](#dev-test)

1. [Contributions](#contributions)

1. [License](#licence)

## Overview

UEIMPORTER is useful for Plastic version control users, that wants to
build a game using Unreal Engine, and plan to make changes to the engine code
itself, while also upgrading engine releases as they are released by Epic.

The idea is to see Unreal Engine as a third party vendor lib (albeit a really
big library). An established strategy for vendor libs is to keep a clean and
unmodified copy of the lib in a separate branch, that you merge into the
branch where you do your active development.
UEIMPORTER helps create such a vendor branch, and keep it updated with
the vanilla engine for new releases.

A naive strategy would be to delete all files on the vendor branch simply
copy all files from the new release, and let Plastic detect which files have
been added, removed, modified or moved.

It sounds like it should work, but the move detection in Plastic seem to miss
most moves, at least when there are as many files involved as there are in an
Unreal Engine upgrade (`4.27.2` -> `5.0.0-early-access-1` modifies over 50k files).
For a moved file you will instead end up with a delete followed by an add.
If you have made changes to the file in the old location on your main-branch,
Plastic will not help you merge these changes into the file in its new location.
Instead, it will ask you how to resolve your changes to the old, deleted file.
Forcing you to manually copy your changes into the new location.
If Plastic would know that a file was in fact moved it would be able to merge
your changes into the new location.

This move file problem is the main reason UEIMPORTER exist, and to solve it
it uses information from the Git repo that knows how and where a file was moved.
It simply asks Git `git diff --name-status <from-release-tag> <to-release-tag>`
and we get a list of exactly which files was added, removed, modified or moved.
Once it knows it's just a question of replicating these exact changes
in Plastic.

UEIMPORTER is meant to be platform independent and could be used on
Windows, macOs or Linux. These platforms disagree on how line endings are encoded
in text files. The tool avoids the problem completely by not copying files
directly from the checked out Git repo, rather it expects you to download the zip files
that Epic publish for each engine release, and copies files from there.
Release zips seem to consistently use `LF` line endings.

If you ever use macOs or Linux to develop your game, we also need to take file permissions
into account. There are many shell scripts in Unreal Engine, these needs to be checked
into Plastic with the `+x` flag set, or else non-windows users will have to manually
`chmod +x` the script files before they can be used.
This means that UEIMPORTER **needs to be executed on Linux or macOs** so that
Plastic has a chance to read file permission flags from the file system when files
are checked in.

# Suggested branch layout <a name="branch-layout" />

![Branch Layout](/images/ueimporter-branch-layout-4.27.0-4.27.2.png)

Here we see a suggested branch layout. The game itself is developed on `main`
, on `vendor-unreal-engine` we keep unmodified Unreal Engine releases and finally
there is a couple of task branches called `upgrade-ue-4.27.1` and `upgrade-ue-4.27.2`
used as a staging area for updating `main` with corresponding engine releases.

In this example, the first changesets on `main` contains change unrelated to Unreal Engine,
the same goes for the second changeset, after which there is not a single file from the
engine present.

From the very first changeset (where no engine files exist) we create the `vendor-unreal-engine` branch,
and the first changeset to it is a simple copy paste of the all files found in
[4.27.0-release.tar.gz](https://github.com/EpicGames/UnrealEngine/releases/tag/4.27.0-release).
Make sure to add and check in files on either macOs or Linux or else file permission flags
(`+x`) will not be recorded in Plastic.

Next step is to add this to `main`, let's use a task branch called `add-ue-4.27.0`.
Before we merge the result back we remove the `Samples` and `Templates` directories from the
root, we do not need them on `main`, this is labeled as `local UE change #1`.

On main we do another local change to the engines source code, labeled as `local UE change #2`.
There might be other changesets here, for example adding your main game module.

When we are ready to upgrade to `4.27.1` we switch back to `vendor-unreal-engine`, download
[4.27.1-release.tar.gz](https://github.com/EpicGames/UnrealEngine/releases/tag/4.27.1-release),
clone/fetch the main [UnrealEngine GitHub repo](https://github.com/EpicGames/UnrealEngine) and use
UEIMPORTER to replicate all changes to your Plastic workspace. Review the result
in Plastics UI and check in the result. See [Usage](#usage) for a more detailed description.

Now, we create a branch called `upgrade-ue-4.27.1`, and we merge with the `4.27.1` release
we just imported. Solving any conflicts that local change `#1` or `#2` might have caused.
When we test out our game we notice that we need to do local change `#3` to make it work.

The result is merged back to `main` and we can continue developing our game.
Once again, we can make changes to engine code, such as local change `#4`

Whenever it's time to upgrade we rince and repeat the same process;
First we import changes using UEIMPORTER, then merge with main on a task branch
before we publish it to `main`.


## Prequestives <a name="prequestives" />

#### * Python 3.10+

You also need `pip`, which comes included in most Python distributions these days. See [pips documentation](https://pip.pypa.io/en/stable/installation/) for more info.

#### * Git
UEIMPORTER needs to be executed from an environment where `git` is present in `PATH`.

#### * Plastic CLI
[Plastics ](https://www.plasticscm.com) CLI tool `cm` also needs to be present in `PATH`.

#### * Clone of the [UnrealEngine GitHub repo](https://github.com/EpicGames/UnrealEngine)
Your github user will need to be a registered Unreal Developer to get access.
See [How do I access Unreal Engine 4 C++ source code via GitHub?](https://www.unrealengine.com/en-US/ue4-on-github)

#### * Release zip for the UE release you want to import.
You can find zips/tarballs for all UE releases under [UnrealEngine/releases](https://github.com/EpicGames/UnrealEngine/releases)

## Installation <a name="install" />

Install a snapshot of UEIMPORTER using `pip`, from the Git repo root
```sh
$ pip install --user .
```
This enables you to invoke `ueimporter` from any directory (such as the target
Plastic repo root)

Each time you want to upgrade UEIMPORTER you simply pull down the latest code
and run the command again.

### Uninstall <a name="install-uninstall" />
To uninstall you simply call pip, can be invoked from anywhere:
```sh
$ pip uninstall ueimporter
```

### Development mode <a name="install-dev-mode" />

If you plan do do active development of UEIMPORTER it's more convenient to
install in editable/development mode. This way `pip` installs thin
wrappers in its registry that simply forwards all invocations to the code
in your Git repository.

Again, from your Git repo root
```sh
$ pip install --user -e .
```

## Usage <a name="usage" />

### Step by step guide <a name="usage-guide" />

#### 1. Switch to the lastest changeset on Plastics vendor branch

#### 2. Fetch latest from Epics main Git repo

For this example we assume that you have previously cloned [UnrealEngine](https://github.com/EpicGames/UnrealEngine) into
`~/github.com/UnrealEngine`
```sh
$ cd ~/github.com/UnrealEngine
$ git fetch
```

#### 3. Make sure the workspace is completely clean

There can be no private/ignored files present in the directory tree, they might interfere
with the upgrade process.

#### 4. Download & extract release zip/tarball

From [UnrealEngine/releases](https://github.com/EpicGames/UnrealEngine/releases)
In this example we unpack all releases in a directory called `~/vendor/UnrealEngine`,
it is assumed to hold a subdirectory for each release named exactly like the Git release tag.

#### 5. Run script with --pretend

Here's an example that upgrade a UE vendor branch to `4.27.2`.
```sh
$ ueimporter
  --git-repo-root="~/github.com/UnrealEngine"
  --zip-package-root="~/vendor/UnrealEngine"
  --plastic-workspace-root="~/wkspaces/YourGame"
  --to-release-tag="4.27.2-release"
  --pretend
```
The `--pretend` argument makes the script simply log the files it will upgrade,
without actually doing it. Remove this parameter once you feel confident
that UEIMPORTER will do what you expect.

#### 6. Stop pretending, and run UEIMPORTER for real
```sh
$ ueimporter
  --git-repo-root="~/github.com/UnrealEngine"
  --zip-package-root="~/vendor/UnrealEngine"
  --plastic-workspace-root="~/wkspaces/YourGame"
  --to-release-tag="4.27.2-release"
```

This might take a while, hours even on a fast machine. The slow part is communicating with
Plastics CLI tool `cm` to add/delete/check out or move files and directories.
For me it took over 7 hours to import the 100k changes that differentiates `5.0.0-preview-1` from `5.0.0-early-access-2`.

#### 7. Verify that directory structure is identical to the release zip
To make sure that UEIMPORTER has not missed anything it can be a good idea to
compare the Plastic workspace directory is now identical to the release zip
file.

There are several tools for this.

On Linux and Mac you can use the stock `diff` command line utility.

```sh
$ diff -qr ~/wkspaces/YourGame ~/vendor/UnrealEngine/UnrealEngine-4.27.2-release
```

On Windows there is no shortage of options. [WinMerge](https://winmerge.org/) is one free alternative and
another great one that you have to pay for is [Beyond Compare](https://www.scootersoftware.com).

#### 8. Check in all changes into Plastic
There is no need to compile and test anything. Remember that the vendor branch simply contains
unmodified versions of UnrealEngine, if the files and folders are identical that's good enough.
Any building and testing happens later, when you merge the new release with your `main` branch.

#### 9. Rejoice
Now you have a smoking fresh engine release. Next step is to merge it into your development branch (`main`). That
is out of scope for this guide.

### Arguments <a name="usage-args" />

#### Required arguments <a name="usage-args-required" />

##### --git-repo-root
Specifies the root of the UE Git repo on disc. Create this directory with
```sh
$ git clone git@github.com:EpicGames/UnrealEngine.git
```

##### --zip-package-root
Specifies where release zip files have been extracted.
Zip files can be downloaded from [EpicGames/UnrealEngine/releases](https://github.com/EpicGames/UnrealEngine/releases)

##### --to-release-tag
Git tag of release to upgrade to.
Tags is listed here [EpicGames/UnrealEngine/tags](https://github.com/EpicGames/UnrealEngine/tags)

#### Optional arguments <a name="usage-args-optional" />

##### --pretend
Set to print what is about to happen without doing anything.

##### --plastic-workspace-root
Specifies the root of the UE Plastic workspace on disc.
Default is current working directory (CWD).

##### --ueimporter-json
Name of file where last integrated UE version will be stored.
Unless specified path is absolute it will be interpreted as relative to the plastic workspace root.
Default is `.ueimporter.json`.

##### --from-release-tag
Git tag of release currently used.
Required whenever a `ueimporter.json` file does not exist.

##### --log-file
Name of log file where all output is saved.
Default is `.ueimporter/ueimporter.log`.

##### --log-level
Controls the detail level of logs that show up in `STDOUT`.
All levels always ends up in the logfile.

Available log levels
* error
* warning
* normal (default)
* verbose
* debug

##### --skip-invalid-ops
Skip operations that will fail when executed. Equivalent to choosing `skip-all` in the interactive prompt.

##### --git-command-cache
If set, results of heavy Git commands will be stored in this directory.

## Development <a name="dev" />

Make sure to install UEIMPORTER in dev mode, as described [above](#install-dev-mode).

### Debugging <a name="dev-debug" />
To debug you can use pythons built in `pdb` module

```sh
$ python -m pdb ueimporter/main.py $(YOUR_OPTIONS)
```

Describing how to use `pdb` is out of scope, for starters try the `help` command.
For more info see the module documentation: [pdb — The Python Debugger](https://docs.python.org/3/library/pdb.html)

### Testing <a name="dev-test" />

UEIMPORTER use [pytest](https://docs.pytest.org) to run unit tests, it's
automatically installed when you install it with `pip`.

It's simple to use, again from the repo root:
```sh
# Run all tests
$ pytest

# Run a specific test-file (tests/test_path_util.py)
$ pytest -q test_path_util.py
```

Note that test coverage is not that high at the time of writing.

## Contributions <a name="contributions" />
We welcome contributions to this project. Just fork the repo, make your changes
and submit a pull request and we'll get back to you. For more detailed instructions
head on over to GitHubs [Fork a repo](https://docs.github.com/en/get-started/quickstart/fork-a-repo])
docs.

## License <a name="licence" />
The ueimporter project is dual-licensed.

* [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
* [MIT license](https://opensource.org/licenses/MIT).

As a user/licensee you choose which license to adhere to.

### Contribution
Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall
be dual licensed as above, without any additional terms or conditions.
