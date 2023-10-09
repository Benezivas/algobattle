
# Installing Algobattle

The first thing we'll need to do is install the Algobattle framework. There's several ways to do this, which one you
choose is entirely up to you and won't change the way things behaves. For each step we've outlined what we think is the
easiest option and also outlined some alternatives.


## Setting up your environment

### Installing Python

Algobattle is a python package, so the first step is to make sure we have Python version 3.11 or higher available to us
in an environment that you can install the Algobattle package and some dependencies into. If you already have that
setup or know how to do it, feel free to skip to [the next section](#installing-docker).

/// question | Not sure if you've already got python 3.11?
You can check if you've already installed Python and what version it is by running `python --version`.
///

/// abstract | Our recommendation
There's a few different ways to install and use Python. If you don't care too much about the specifics, we recommend
using Conda since it can do everything in one tool. There's several other programs that do similar jobs, and they all
will have the same result. If you're already using one of them, feel free to just stick to using that one.
///

#### With Conda

Conda is very easy to use and manages python versions, virtual environments, and packages for you. You can get an
installer for your operating system from the [official Conda website](https://anaconda.org/anaconda/conda). Once you've
got it running you don't need to do anything else for this step since it will install python for you when we make a
virtual environment.

#### Manually

You can also install Python manually from [the Python website](https://wiki.python.org/moin/BeginnersGuide/Download),
or use another package manager.

### Virtual environments
Python doesn't do a great job of managing package dependencies, which can cause issues if Algobattle needs a version
of a library (or of Python itself) that some other program you use is incompatible with. To prevent this issue we use
_virtual environments_, which basically behave as though they are separate installations of Python that do not affect
each other. This means we can just make a fresh environment with Python 3.11 and install Algobattle there and never
have to worry about anything breaking.

First we create a virtual environment like this

```console
conda create -n algobattle python=3.11
```

This process may take a second if it needs to download and install python. Once it's done we can now _activate_ the
environment

```console
conda  activate algobattle
```

What this does, is make your current shell session use the Python installation from that environment. So if you now run
`python --version` you should see 3.11, not whatever your global installation is (if you even have one). The environment
will stay active until you close the shell or run `conda deactivate`. For everything other than Python commands your
console will keep behaving just like it normally would.

/// tip
Always remember to activate this environment when you want to use Algobattle. You won't need to do it every time
you run a command, but once when you start a new terminal. If you're using an IDE like VSCode you can also configure
it to automatically activate the environment whenever you open a console in a specific project.
///

/// warning | Using the global Python
If you have a global Python installation that is 3.11 or higher you can also skip making a virtual environment. This
generally is not a great idea, but if you really want to you can do it. In that case we recommend installing Algobattle
into user space as explained in the last step.
///

### Installing Docker

We use Docker to easily manage and run the code students write, so you'll need to grab a fresh installation of it too.
You can get the latest version from the official site [here](https://www.docker.com/).

/// tip
If you're using Linux you have the choice between Docker desktop and the Linux Docker Engine. If you're unsure what to
get, we recommend Docker desktop as it provides a nicer user experience.
///


### Installing Algobattle

Installing Algobattle itself is the easiest part of everything since it's available in the
[Python Package Index](https://pypi.org/project/algobattle-base/). All we need to do is make sure the correct
environment is active and run this

```console
pip install algobattle-base
```

/// warning | Using the global Python
If you really want to install Algobattle into the global environment we recommend running
`pip install --user algobattle-base` instead.
///
