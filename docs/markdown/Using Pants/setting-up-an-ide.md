---
title: "Setting up an IDE"
slug: "setting-up-an-ide"
hidden: false
createdAt: "2021-05-02T06:21:57.663Z"
updatedAt: "2022-03-14T22:23:16.110Z"
---
If you use a code-aware editor or IDE, such as PyCharm or VSCode, you may want to set it up to understand your code layout and dependencies. This will allow it to perform code navigation, auto-completion and other features that rely on code comprehension.

First-party sources
-------------------

To get your editor to understand the repo's first-party sources, you will probably need to tell it about the repo's [source roots](doc:source-roots). You can list those with:

```shell
$ ./pants roots
```

and then apply the corresponding IDE concept. 

For example, in PyCharm you would mark each source root as a "Sources" folder. See [Configuring Project Structure](https://www.jetbrains.com/help/pycharm/configuring-project-structure.html) to learn more.

In VSCode, the Python extension will look for a file named `.env` in the current workspace folder. If the file is found, then it will be loaded and evaluated. For Python, this file can be used to set the `PYTHONPATH` variable. Having this file makes it possible to jump to definitions in the source code across multiple projects. It also makes cross-project refactoring possible.

For Python, to generate the `.env` file containing all the source roots, you can use something like this:

```shell
$ ROOTS=$(./pants roots --roots-sep=' ')
$ python3 -c "print('PYTHONPATH=\"./' + ':./'.join(\"${ROOTS}\".split()) + ':\$PYTHONPATH\"')" > .env
```

See [Use of the PYTHONPATH variable](https://code.visualstudio.com/docs/python/environments#_use-of-the-pythonpath-variable) to learn more about using the `PYTHONPATH` variable in VSCode.

Python third-party dependencies and tools
-----------------------------------------

To get your editor to understand the repo's third-party Python dependencies, you will probably want to point it at a virtualenv containing those dependencies.

Assuming you are using the ["resolves" feature for Python lockfiles](doc:python-third-party-dependencies)—which we strongly recommend—Pants can export a virtualenv for each of your resolves. You can then point your IDE to whichever resolve you want to load at the time.

To use the `export` goal to create a virtualenv:

```
❯ ./pants export --symlink-python-virtualenv --resolve=python-default
Wrote symlink to immutable virtualenv for python-default (using Python 3.9.13) to dist/export/python/virtualenvs/python-default
```

You can specify the `--resolve` flag [multiple times](doc:options#list-values) to export multiple virtualenvs at once.

The `--symlink-python-virtualenv` option symlinks to an immutable, internal virtualenv that does not have `pip` installed in it. This method is faster, but you must be careful not to attempt to modify the virtualenv. If you omit this flag, Pants will create a standalone, mutable virtualenv that includes `pip`, and that you can modify, but this method is slower.

### Tool virtualenvs

`./pants export` can also create a virtualenv for each of the Python tools you use via Pants, such as `black`, `isort`, `pytest`, `mypy`, `flake8` and so on (you can run `/pants help tools` to get a list of the tools Pants uses). Use the tool name as the resolve name argument to the `--resolve` flag. This allows you to configure your editor to use the same version of the tool as Pants does for workflows like formatting on save.


Generated code
--------------

If you're using [Protobuf and gRPC](doc:protobuf), you may want your editor to be able to index and navigate the generated source code. 

Normally Pants treats generated code as an internal byproduct, and doesn't expose it. But you can run the `export-codegen` goal to generate code to a well-known output location for consumption:

```shell
$ ./pants export-codegen ::
```

The generated code will be written to `dist/codegen`, and you can now add them as sources in the IDE. For example, in PyCharm you would mark `dist/codegen` as a "Sources" folder. 

Warning: you will have to manually rerun this goal when changes are made.

Remote debugging
----------------

You can use PyCharm to debug code running under Pants. 

See the following links for instructions on how to do so under the [test goal](doc:python-test-goal) and under the [run goal](doc:python-run-goal).

IDE integrations
----------------

We have not yet developed tight IDE integrations, such as a PyCharm plugin or a VSCode extension, that would allow the IDE to run Pants on your behalf. If you're interested in developing this functionality for your favorite IDE, [let us know](doc:the-pants-community)!
