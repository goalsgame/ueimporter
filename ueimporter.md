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

Each official engine release is labeled with a git tag, for example
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
1. Start with an empty plastic repo
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

### Import by delete and readding all files

One crude strategy is to delete all files on the vendor branch and simply
copy all files from the new release, and then let plastic detect which files have
been added, removed, modified or moved.

This should work well. Alas, plastics move detection seem to miss
most moves, maybe there are too many files involved in engine upgrades for it
to be practically possible? It would be understandable, upgrading
`4.27.2` to `5.0.0-early-access-1` modifies over 50k files.

One downside is that moved files will be imported as a delete followed by an add.
If you have made changes to the file in the old location on your `main`-branch
, plastic will not help you merge these changes into the file in it's new location.
Plastic will ask you how to resolve your changes to the old file, and you will have
to manually copy it into the new location.

Depending on how widespread your changes to the engine code is this strategy
might be good enough, for us at Goals it was not.

### Import by replicating changes from git

Luckily, we can do better. Full revision history is available in the main
git repo, it knows which files has been modified, added or removed, and most
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
  The number is a percentage of how certain gitis that the file was in fact moved, and not a delete followed
  by an add.
  There is some grey area in moves when it comes to git, sometimes a file is moved, but then modified
  to fit in its new location. For example, a moved `C++` file may need to have paths to includes
  tweaked to compile. Git uses some fuzzy heuristict to discern moves from adds+deletes, I don't know the details,
  but most of the time it seems to be correct. I've only came across one case where it guess was plain wrong.

Now it's just a matter of replicating these changes in `vendor-unreal-engine`.

Modified files is simple, just check out in plastic and copy the file from the
new release.

Adding files is almost as easy, just copy their content. But, if the target
folder does not exist in plastic we need to first create and add it before
we copy the file.

For deletes, the opposite of adds, we start by deleting the file itself.
If the folder in which it existed became empty we need to remove the folder,
we also need to delete any now empty parent directories.

For moves we start by creating and adding target directories to before we
tell plastic to move the file. Finally, we copy the contents of the file
from the new release.

This problem is very scriptable, and I wrote a commandline python tool
that takes care of it all. We at Goals hope to be able to open source this soon.
