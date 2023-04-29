
# Installing Algobattle

The first thing we'll need to do is install the Algobattle package. There's several different ways to do this.
Which one you choose is entirely up to you and won't change the way the package behaves. For each step we've outlined
what we think is the easiest option and also outlined some alternatives.


## Setting up your environment

### Installing Python

Algobattle is a python package, so the first step is to make sure we have a recent python version available to us.
In particular, we need Python 3.11 or higher. If you already have that installed you can skip to the
[next section](#installing-docker).

/// question | Not sure if you've already got python 3.11?
You can check if you've already installed Python and what version it is by running `python --version`.
///

/// abstract | Our recommendation
There's a few different ways to install and use Python. If you don't care too much about the specifics, we recommend
using Conda as described [below](#inside-a-virtual-environment).
///

#### Inside a virtual environment
Python doesn't do a great job of managing package dependencies, so people have developed tools to help us with that.
They let you create _virtual environments_ and easily install specific Python versions, packages, and their
dependencies in them. This means you need to install the environment manager first, but will save you some hassle in
the long run.

We recommend using [Conda](https://anaconda.org/anaconda/conda). You can install it on all major operating systems and
it will take care of most things for you. On Linux, you can also use [pyenv](https://github.com/pyenv/pyenv). It's a
bit smaller but also requires a bit more care taken manually.

Once you've installed either one you can just create a new environment and have it install python 3.11 for you:

/// tab | conda
```console
$ conda create -n algobattle python=3.11
```
///

/// tab | pyenv
```console
$ pyenv virtualenv 3.11 algobattle
```
///

Just remember to always activate the environment before trying to install or run Algobattle:

/// tab | conda
```console
$ conda  activate algobattle
```
///

/// tab | pyenv
```console
$ pyenv activate algobattle
```
///

You won't need to rerun this command before every time you use Algobattle, only once per shell session.

#### Globally

If you don't want to deal with yet another program you can also just install python globally on your computer.
[The official python wiki](https://wiki.python.org/moin/BeginnersGuide/Download) has donwload links and instructions
specific to your operating system.

### Installing Docker

We use Docker to easily manage and run the code students write, so you'll need to grab a fresh install of it too.
You can get the latest version from the offical site [here](https://www.docker.com/).

/// tip
If you're using Linux you have the choice between Docker desktop and the Linux Docker Engine. If you're unsure what to
get, we recommend Docker desktop as it provides a nicer user experience.
///


### Installing Algobattle

Now we're finally ready to install Algobattle itself. Head over to
[our GitHub repository](https://github.com/Benezivas/algobattle) and download the code. Then you can use pip to install
it.

```console
$ pip install .
```

