# ueimporter

Script used to import Unreal Engine releases into Game plastic repository.

## Installation

To install a snapshot of `ueimporter` in your users pip registry you do (from repo root):
```
$ pip install --user .
```
This enables you to invoke `ueimporter` from any directory.

Each time you want to upgrade `ueimporter` you simply pull down the latest code
and run the command again.

## Usage

Here's an example that upgrade from `4.27.1` to `4.27.2`.

```
ueimporter^
 --git-repo-root="H:\UnrealEngine"^
 --from-release-tag="4.27.1-release"^
 --to-release-tag="4.27.2-release"^
 --zip-package-root="H:\Vendor\UnrealEngine"^
 --plastic-workspace-root="H:\Goals\Game"
 --plastic
```

The `--pretend` argument makes the script simply log the files it will upgrade,
without actually doing it. Remove this parameter once you feel confident
that it's what you want.

## Development

If you plan do do active development of `ueimporter` it's more convenient to
install in editable/development mode. This way `pip` installs thin
wrappers in it's registry that simply forwards all invocations to the code
in your git repository.

From your git repo root:
```
$ pip install --user -e .
```
