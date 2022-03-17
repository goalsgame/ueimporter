# Working with Unreal Engine source releases in Plastic SCM

This guide is for [Plastic SCM](https://www.plasticscm.com) users, that want to
build a game using [Unreal Engine](https://www.unrealengine.com)
, and plan to compile and make changes to the engine code itself, while also
upgrading engine releases as they are released by Epic.

Incidentally this is exactly what we at Goals wanted, and something I set out
to solve earlier this year.

## Building blocks

Full engine source code is served via
[Unreal Engine own GitHub repository](https://github.com/EpicGames/UnrealEngine),
to which you get access by registering your GitHub user with Epic.
See [How do I access Unreal Engine 4 C++ source code via GitHub?](https://www.unrealengine.com/en-US/ue4-on-github)

Each official engine release is labeled with a Git tag, for example
[4.27.2-release](https://github.com/EpicGames/UnrealEngine/releases/tag/4.27.2-release)
or
[5.0.0-preview-2](https://github.com/EpicGames/UnrealEngine/releases/tag/5.0.0-preview-2).
Here you also find a downloadable tarball or zip for the release.

Then we have a Plastic repository, where we want to develop our game.

## The idea

The main idea is to see Unreal Engine as a third party vendor library
(albeit a really big one). One strategy for vendor libs is to keep a clean and
unmodified copy of it in a separate branch, that is then merged into your
development branch.
This idea isn't new, it's basically exactly what Karl Fogel describe in
[Tracking Third-Party Sources (Vendor Branches)](https://durak.org/sean/pubs/software/cvsbook/Tracking-Third_002dParty-Sources-_0028Vendor-Branches_0029.html)
, a section of his 20+ years old book titled *Open Source Development With CVS*.

Sounds simple enough, but how do we apply it to Plastic and Unreal Engine?

## Branch layout and upgrade flow

Lets start with deciding a branch layout. The game itself is developed on `main`
, we keep unmodified Unreal Engine releases in `vendor-unreal-engine` that is
**merged** down to main for each release.

Let's take this example, where we set up an empty repo with `4.27.0` that we
upgrade to `4.27.1` and finally `4.27.2`.

![Branch Layout](/images/unreal-engine-in-plastic-branch-layout.png)

This image contains a thousand words, spelled out it becomes:
1. Start with an empty Plastic repo
1. Add `4.27.0` to `vendor-unreal-engine`
1. Make a small tweak to the engine itself.
1. Merge it all down into `main`
1. Add your games main module
1. Upgrade `vendor-unreal-engine` with release `4.27.1`
1. Merge the new release with `main`, and apply fixes to make
   your game module compile and work again.
1. Merge the new engine into `main`
1. Make local modification to the engine itself
1. Upgrade `vendor-unreal-engine` with release `4.27.2`
1. Merge it with `main`, and apply even more fixes
   to your game so that it still works.
1. Publish the new release to `main`
1. And contiue making local changes to the engine

## Importing Unreal Engine releases

So, how do you import or upgrade the engine source code into our `vendor-unreal-engine`?

### Import by delete and re-adding all files

One crude strategy is to delete all files on the vendor branch and simply
copy all files from the new release, and then let Plastic detect which files have
been added, removed, modified or moved.

This should work well. Alas, plastics move detection seem to miss
most moves, maybe there are too many files involved in engine upgrades for it
to be practically possible? It would be understandable, upgrading
`4.27.2` to `5.0.0-early-access-1` modifies over 50k files.

One downside is that moved files will be imported as a delete followed by an add.
If you have made changes to the file in the old location on your `main`-branch
, Plastic will not help you merge these changes into the file in it's new location.
Instead, it will ask you how to resolve your changes to the old deleted file, forcing
you to manually copy your changes into the new location.

Depending on how widespread your changes to the engine code are, this strategy
might be good enough, for us at Goals it was not.

### Import by replicating changes from Git

Luckily, we can do better. Full revision history is available in the main
Git repo, it knows which files has been modified, added or removed, and most
importantly it also knows which files have been renamed or moved.

The command we use is `git diff --name-status`, here's the output of
the diff between `4.27.1` and `4.27.2`. Note that this is just an excerpt,
the real diff contains roughly 460 changes.

```sh
$ git diff –-name-status 4.27.1-release 4.27.2-release
M     Engine/Build/Build.version
A     Engine/Extras/ThirdPartyNotUE/libimobiledevice/src/libimobiledevice-vs/usbmuxd/.gitattributes
A     Engine/Extras/ThirdPartyNotUE/libimobiledevice/src/libimobiledevice-vs/usbmuxd/.gitignore
R100  Engine/Source/Runtime/Core/Public/HAL/PlatformFilemanager.h Engine/Source/Runtime/Core/Public/HAL/PlatformFileManager.h
D     Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SPIRVContext.cpp
A     Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SpirvContext.cpp
R087  Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SPIRVEmitter.cpp Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SpirvEmitter.cpp
R095  Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SPIRVEmitter.h Engine/Source/ThirdParty/ShaderConductor/ShaderConductor/External/DirectXShaderCompiler/tools/clang/lib/SPIRV/SpirvEmitter.h
```

The leading column means:
* `M` - File was modified in place
* `A` - File was added
* `D` - File was deleted
* `R*` - File was renamed or moved.
  The number is a percentage of how certain Git is that the file was in fact moved, and not a delete followed
  by an add.
  There is some grey area when it comes to moves in Git, sometimes a file is moved, but then modified
  to fit in its new location. For example, a moved `C++` file may need to have include paths
  tweaked to compile. Git uses some fuzzy heuristict to discern moves from adds+deletes, I don't know the details,
  but most of the time it seems make good guesses. When it fails it isn't such a big deal;
  the file in the old location was deleted, and the content of the new location will be correct.

Now, it's just a matter of replicating these changes in `vendor-unreal-engine`.

Modified files is simple, just check out in Plastic and copy the file from the
new release.

Adding files is almost as easy, just copy their content. But, if the target
folder does not exist in Plastic we need to first create and add it before
we copy the file.

For deletes, the opposite of adds, we start by deleting the file itself.
If the folder in which it existed became empty we need to remove the folder,
we also need to delete any now empty parent directories.

For moves we start by creating and adding target directories to before we
tell Plastic to move the file. Finally, we copy the contents of the file
from the new release.

This process is very scriptable, and I wrote a commandline tool (in python)
that takes care of it all. We at Goals hope to be able to open source this soon.

## Ignoring the elephant in the room

If you have ever tried to store Unreal Engine source inside Plastic, you may have
noticed a rather big elephant that I so far avoided; Plastics ignore
file, and it's incompatibility with Gits equivalent.

As you may know, Unreal Engines GitHub repo comes with a rather complex `.gitignore` file. Whenever you build
or work with the engine various intermediate and temporary files is scattered all over your workspace,
not to mention the thousands of files that is downloaded when you run `Setup.bat`.
These files should not be committed into Git, and likewise we do not want them checked into Plastic.

It is not possible to directly translate Gits `.gitignore` file into Plastics `ignore.conf`,
the two systems have rather different rules deciding in what order ignore patterns are applied.

### Ignoring in Git

On one hand, we have Git, where each line specifies a file or directory pattern, any subsequent matching
line will override preceding matches. A simple philosophy that is relatively easy to understand.

If we compress Unreals `.gitignore` into a nutshell, it can be described like this:
1. Start by ignoring **all** files
1. Adds exceptions to **not ignore** certain extensions,
   For instance `*.h` and `*.cpp`.
1. Add exceptions to those exceptions to ignore temporary build folders completely.
   For example `Engine/Intermediate/`, or else the `*.h` and `*.cpp` files that
   `UnrealHeaderTool` generates during the build process would be tracked.

On and on the list goes, with more detailed exceptions and ignore patterns.
There are close to 160 rules listed in the ignore file for the `5.0.0-preview-2` release.

### Plastic ignorance is not a bliss

Then we have Plastic, it prioritize patterns based on which type of pattern it is,
rather than in what order they occur in its `ignore.conf`. Two patterns of the same type
are applied in the order they appear in the file. Exception patterns take presendence over
ignore patterns.

So what pattern types are we talking about? Quoting the
[Pattern evaluation hierarchy](https://www.plasticscm.com/book/#_pattern_files)
section of the `Version Control, DevOps and Agile Development with Plastic SCM` book.
>> Plastic SCM will try to match the path of an item using the patterns in the file in a predefined way.
>> This means that some pattern formats take precedence over others rather than processing the patterns
>> in the order they appear in the file.
>>
>> 1. Absolute path rules that match exactly
>> 2. Catch-all rules
>> 3. Name rules applied to the current item
>> 4. Absolute path rules applied to the item directory structure
>> 5. Name rules applied to the item directory structure
>> 6. Extension rules
>> 7. Wildcard and Regular expression rules

There are more devils in the details, but that's the gist of it.

Unreals `.gitignore` use most of these ignore types, but of course relies on the order to accomplish desired ignore
behaviour. Just copy pasting this to Plastic does not work, because it wreaks havoc to this order.

### An acceptable workaround

We at Goals have wrestled quite a bit with this, trying to come up with equivalent ignore behaviour in Plastic.
But so far we haven't nailed it, but have at least arrived at a workaround.
We simply ignore the entire `/Engine`-folder, that gets rid of most of the intermediate and temporary
files that is explicitly ignored in `.gitignore`.
The main drawback with this is that we have to manually remember to add files to Plastic,
if we were to add anything to `Engine`, or else it will not show up as a pending change.
We can edit files that are already checked into Plastic just fine, it will be detected as changed.

### Ignore files and our vendor branch

Thankfully, the ignore file is irrelevant on our `vendor-unreal-engine` branch,
here we always want Plastic to detect all files, so that we can check them in
and later have them merged into `main`.
You should never build or do anything to pollute your workspace when you are on this branch,
and make sure to clear out any private files before you start importing a new engine release.

## Parting words

With this setup you have the power to change the engine at will, and still stay up to date with new releases,
how you wield this power is up to you.

Consider that any merge conflicts you get with new engine releases, after making local changes, will need to be resolved.
This is a manual process that is hard to automate. In the past, when working in another big game engine, I have seen
many, many, **many** dev-months been sunk into resolving merge conflicts and follow up issues, due to local modifications
when the engine was upgraded.

If you can, keep your engine changes small and isolated, and tag changed lines with begin/end comments. If
a change can be done in your game module or a plugin that is the prefered way.

Another good example is that you can cherry-pick fixes from Epics mainline and push directly into your own `main`.
Later, when the fix gets included in an official release your divergence should just resolve itself in the upgrade
process.

Take care, stay safe and happy game making.
