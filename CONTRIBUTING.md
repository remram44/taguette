# Contents
* [Notes](#notes)
* [Contributing](#contributing)
* [Resolving Merge Conflicts](#resolving-merge-conflicts)
* [Best Practices for Contributing](#best-practices-for-contributing)
* [Attribution](#attribution)

# Notes

Any contributions received are assumed to be covered by the [BSD 3-Clause license](https://gitlab.com/remram44/taguette/blob/master/LICENSE.txt). We might ask you to sign a Contributor License Agreement before accepting a large contribution. To learn more about Taguette, see the [Taguette Website](https://www.taguette.org/) and the [README](https://gitlab.com/remram44/taguette/blob/master/README.md) in this repository. You can find an introduction to the codebase in [ARCHITECTURE.md](https://gitlab.com/remram44/taguette/blob/master/ARCHITECTURE.md).

# Contributing

Please follow the [Contributor Covenant](CODE_OF_CONDUCT.md) in all your interactions with the project. If you would like to contribute to this project by modifying/adding to the code, please read the [Best Practices for Contributing](#best-practices-for-contributing) below and feel free to use [GitLab's Web IDE](https://docs.gitlab.com/ee/user/project/web_ide/) for small changes (e.g. fixing a typo on the website) or for contributions to the code base the following workflow:

1. Fork the project.
2. Clone your fork to your computer.
    * From the command line: `git clone https://gitlab.com/<USERNAME>/taguette.git`
3. Change into your new project folder.
    * From the command line: `cd taguette`
4. [optional]  Add the upstream repository to your list of remotes.
    * From the command line: `git remote add upstream https://gitlab.com/remram44/taguette.git`
5. Create a branch for your new feature.
    * From the command line: `git checkout -b my-feature-branch-name`
6. Make your changes.
    * Avoid making changes to more files than necessary for your feature (i.e. refrain from combining your "real" merge request with incidental bug fixes). This will simplify the merging process and make your changes clearer.
7. Commit your changes. From the command line:
    * `git add <FILE-NAMES>`
    * `git commit -m "A descriptive commit message"`
8. While you were working some other changes might have gone in and break your stuff or vice versa. This can be a *merge conflict* but also conflicting behavior or code. Before you test, merge with master.
    * `git fetch upstream`
    * `git merge upstream/master`
9. Test. Run the program and do something related to your feature/fix.
10. Push the branch, uploading it to GitLab.
    * `git push origin my-feature-branch-name`
11. Make a "merge request" from your branch here on GitLab.

# Resolving Merge Conflicts

Depending on the order that merge requests get processed, your MR may result in a conflict and become un-mergeable.  To correct this, do the following from the command line:

Switch to your branch: `git checkout my-feature-branch-name`
Pull in the latest upstream changes: `git pull upstream master`
Find out what files have a conflict: `git status`

Edit the conflicting file(s) and look for a block that looks like this:
```
<<<<<<< HEAD
my awesome change
=======
some other person's less awesome change
>>>>>>> some-branch
```

Replace all five (or more) lines with the correct version (yours, theirs, or
a combination of the two).  ONLY the correct content should remain (none of
that `<<<<< HEAD` stuff.)

Then re-commit and re-push the file.

```
git add the-changed-file.cs
git commit -m "Resolved conflict between this and MR #123"
git push origin my-feature-branch-name
```

The merge request should automatically update to reflect your changes.

## Best Practices for Contributing

* Before you start coding, open an issue so that the community can discuss your change to ensure it is in line with the goals of the project and not being worked on by someone else. This allows for discussion and fine-tuning of your feature and results in a more succinct and focused addition.
    * If you are fixing a small glitch or bug, you may make a MR without opening an issue.
    * If you are adding a large feature, create an issue so that we may give you feedback and agree on what makes the most sense for the project before making your change and submitting a MR (this will make sure you don't have to do major changes down the line).

* Merge requests are eventually merged into the codebase. Please ensure they are:
    * Well tested by the author. It is the author's job to ensure their code works as expected.
    * Free of unnecessary log calls. Logging is important for debugging, but when a MR is made, log calls should only be present when there is an actual error or to record some important piece of information or progress.

* If your code is untested, log-heavy, or incomplete, prefix your MR with "[WIP]", so others know it is still being tested and shouldn't be considered for merging yet. This way we can still give you feedback or help finalize the feature even if it's not ready for prime time.

That's it! Following these guidelines will ensure that your additions are approved quickly and integrated into the project. Thanks for your contribution!

## Running tests

This projects includes automated tests. Should you send us your changes in the form of a merge request on GitLab, the tests will be run automatically by GitLab CI to check that your version still works. You can also run the tests locally in a terminal:

```
python tests.py
```

Some tests control a web browser. You will need to install Chrome/Chromium or Firefox and get the corresponding webdriver ([geckodriver](https://github.com/mozilla/geckodriver) for Firefox and [chromedriver](https://chromedriver.chromium.org/downloads) for Chrome/Chromium). You can then enable those tests by running:

```
TAGUETTE_TEST_WEBDRIVER=firefox python tests.py
# or
TAGUETTE_TEST_WEBDRIVER=chromium python tests.py
```

## Debugging Taguette with PyCharm

1. Install the poetry plugin for pycharm: https://plugins.jetbrains.com/plugin/14307-poetry
2. In PyCharm's menu: Run/Edit Configurations
3. Add a new configuration by clicking the top-left plus icon or by pressing alt+insert on your keyboard.
4. Select `Python` in the pop-up list (other options that show are `Shell Script`, `Python tests`, etc.)
5. In _Module Name_ type `taguette.main`
6. In _Environment_, _Python interpreter_, choose "Poetry (taguette)"

You can now just click on _Run/Debug_ (if you only have one run configuration) or click on _Run/Debug..._ and choose _taguette.main_ to start the debugging.

# Attribution

This CONTRIBUTING.md was adapted from [ProjectPorcupine](https://github.com/TeamPorcupine/ProjectPorcupine)'s [CONTRIBUTING.md](https://github.com/TeamPorcupine/ProjectPorcupine/blob/master/CONTRIBUTING.md)

# Contact info

You are welcome to chat with us in our [Element room](https://app.element.io/#/room/#taguette:matrix.org) or contact the maintainers directly at [hi@taguette.org](mailto:hi@taguette.org).
