# Writing programs

The main activity in the Algobattle lab course is of course writing the actual code to solve problems. This page will
walk you through the entire process of how that is done and explain what you need to know in order to write your own
programs.

## The Docker environment

If you haven't used Docker before, getting your head around what it's doing and what you need to do can be a bit
confusing. Luckily we do not need to understand most of its functionality and the parts that we do need are pretty
straightforward. You can think of Docker as a virtual machine management tool, it lets you create _images_ that are
basically savefiles of an entire computer including the OS and everything else installed on it. We can then run
_containers_ from these images, independent virtual machines that start off from that savefile and then run some
code. So when we want to write a generator we need to create an image that has all our code in it and some
way to run that code. When an image of it is run it then executes that code and generates an instance.

Images are run essentially as virtual machines that are entirely separate from the host machines' OS. This means that
you can't directly interact with the program itself to debug it or look at its output. It also means that you need to
specify everything that you need to be there, most importantly the code that you want to run and the compiler or
interpreter needed for it.

### Dockerfiles

When you tell Docker to create an image using the content in the `/generator` folder, the first thing it does is
look for a file at `/generator/Dockerfile`. It needs to be in a special file format that specifies exactly what the
image should look like. You can think of Docker as creating a new virtual machine with absolutely nothing installed
on it (not even an OS) and then running each command in order. Once everything has been executed it then saves the state
of the file system of this virtual machine. The image then just refers to that save file and each image of it will
be executed in a virtual machine that looks exactly like it.

The full specification of what Dockerfiles can contain is [here](https://docs.docker.com/engine/reference/builder/), but
most of it is not relevant for us. This example contains all commands you will probably need:

```Dockerfile
FROM python

RUN pip install tqdm
COPY main.py /

ENTRYPOINT python main.py
```

/// abstract | Dockerfile summary
If you don't care about the details and just want to write your code, here's the super short summary for you:

- Start your Dockerfile with a `#!Dockerfile FROM` statement that uses the name of language your code is in. For
example, `#!Dockerfile FROM python:3.11` or `#!Dockerfile FROM rust`. This will give you a Linux environment with that
language's compiler/interpreter installed. You can optionally specify a version after a colon.

- If you need access to files, copy them into the image with `#!Dockerfile COPY source/path target/path`.

- You can run shell commands during the build step with `#!Dockerfile RUN some shell command`.

- Specify the shell command that actually executes your code with `#!Dockerfile ENTRYPOINT run my code`.
///

/// tip | Speedup build times
Docker image builds are cached, you can significantly speed up your development process by ordering the commands
correctly. Docker executes each line one by one and only newly executes lines following the first line that depends on
something that has changed. Further, `#!Dockerfile RUN` commands are assumed to be deterministic and only dependent on
the state of the file system immediately before their execution.

In particular this means that you generally want to order `#!Dockerfile RUN` commands as early as possible, and
`#!Dockerfile COPY` the files you change the most last.
///

#### The `#!Dockerfile FROM` statement

The first line of every Dockerfile has to be a `#!Dockerfile FROM` statement, the most basic example is
`#!Dockerfile FROM scratch`. This line tells Docker what to base your image off of, `#!Dockerfile FROM scratch`
means that it starts with a completely empty file system. If we do that we need to first install an operating system,
configure it enough to be usable, and then install whatever we actually want to run. We can make our Dockerfiles much
simpler by using one of the already existing images in the [_Docker Hub_](https://hub.docker.com/)
in our `#!Dockerfile FROM` statement instead. Instead of starting with an empty file system we then start with the file
system of that image.

All major operating systems have images containing a fresh installation of them on the Docker Hub. For example,
[here](https://hub.docker.com/_/alpine) is the official Alpine image, [here](https://hub.docker.com/_/ubuntu) is Ubuntu,
and [here](https://hub.docker.com/_/debian) is Debian. If you want your code to run in a clean environment with nothing
else you can use any of these as your base.

/// warning
In principle Docker can also run Windows OS's inside the containers, but this requires special setup on the host
machine. In particular, every image needs to then be a Windows image, there is no way to control both Linux and Windows
containers at the same time. We recommend course administrators configure Docker to run Linux containers (this is the
default) and inform students that they are required to use Linux in their images.

Talk to your course administrators if you are a student and unsure about what OS to use.
///

Since you want the container to execute some code you will most likely then need to install a compiler or runtime for
whatever language you're using. We can easily skip this intermediary step and instead base our image off of one that
already includes this. Most languages have officially published images that contain some Linux distro and an
installation of everything that compiler/interpreter needs to work. For example, [here](https://hub.docker.com/_/python)
is Python's and [here](https://hub.docker.com/_/rust) Rust's.

Images on the Docker Hub can also be versioned using tags. For example, the official Python image has dozens of slightly
different versions that come with different OS's, Python versions, etc. If you want to use a specific tag you need to
list it in the `#!Dockerfile FROM` statement after a colon. For example, if your code needs Python 3.10 you can write
`#!Dockerfile FROM python:3.10`.

/// tip
Different languages use different schemes for tagging their images. Always check the official page on the
[Docker Hub](https://hub.docker.com/) to make sure you're getting the right version of everything.
///

#### `#!Dockerfile COPY`ing files

Now that we have a container that includes our language's runtime we also need to include our code and all other files
we may need. The `#!Dockerfile COPY` command does exactly this. For it, we just list the path to the file on the host
file system, and the path it should be at in the image. Our example has the generator code in a single file next to the
Dockerfile, so we can place it into the root directory of the image with `#!Dockerfile COPY main.py /`.

///attention
Copying files that are not inside the folder containing the Dockerfile (or a subfolder of it) requires additional steps
and may not work when sharing the code with course instructors. We recommend you place everything you need in that
directory.
///

If you want to split up your code over multiple files or include other files such as configs, you can add any number of
additional `#!Dockerfile COPY` statements. You can use glob patterns to copy multiple files once, for example
`#!Dockerfile COPY . usr/src` will copy the entire directory on the host machine to `usr/src` in the image.

#### `#!Dockerfile RUN`ning commands

You can use `#!Dockerfile RUN some shell command` to execute `#!shell some shell command` in a shell during the image
build step. This command will have access to everything that was copied into the image beforehand and anything that
previously ran commands created. Most often, this is used to install dependencies of your program.

This statement has two forms, the first `#!Dockerfile RUN some shell command`, and the other
`#!Dockerfile RUN ["some", "shell", "command"]`. For our purposes they do largely the same thing, but their differences
are explained [here](https://docs.docker.com/engine/reference/builder/#run)

#### The program `#!Dockerfile ENTRYPOINT`

Lastly, the container that runs from your image needs to know what it should actually do. You can specify this with the
`#!Dockerfile ENTRYPOINT` statement. Its arguments form some shell command that is not executed during the build step,
but when the container starts.

Similar to run this command also has the same two forms, and you can choose whichever you prefer. They are explained
in detail [here](https://docs.docker.com/engine/reference/builder/#entrypoint).

### An example image

The best way to fully understand how all this works is to run a quick example. For this we will be writing a simple
Python program that displays a short progress bar in the command line. It uses the Dockerfile we saw above

```Dockerfile
FROM python

RUN pip install tqdm
COPY main.py /

ENTRYPOINT python main.py
```

And this Python file:

```python title="main.py"
from time import sleep
from tqdm import tqdm

for i in tqdm(range(20)):
    sleep(.1)
```

We see that the [tqdm](https://pypi.org/project/tqdm/) library we use to display a progress bar is installed in the
image and our code is copied over. When the container is run, it will just execute the python script.

To test this setup we first build the image with Docker

<div class="termy">

```console
docker build ./generator/ -t test_image
```

</div>

/// note
the `-t` parameter lets us _tag_ the image that is created to make it easier to use later on. A full specification of
all parameters can be found in the [official docs](https://docs.docker.com/engine/reference/commandline/build/).
///

To then create and run a container from it, we run

<div class="termy">

```console
docker run -it -rm test_image
```

</div>

/// note
The `-ti` parameters let you see the output of the process running inside the container, and `-rm` cleans up the
container after it has finished running. The (rather lengthy and complicated) description of all parameters is again
found in the [official docs](https://docs.docker.com/engine/reference/run/).
///

We recommend running through this example yourself and trying out various changes to the Dockerfile to see how it
affects what happens when you run the container. Don't forget to always build the image again when you change something!

## Interacting with the match

Now that we know how write programs and get them to run, we need to figure out how to make them interact with the
Algobattle matches correctly. The broad overview is that when Algobattle runs a program it creates two folders in its
root directory, `input` and `output`. As the names suggest, the first contains files that are the input of the program
and the second is where Algobattle expects its output to be.

/// danger
The input folder is read-only to prevent programs from mistakenly placing their outputs in the wrong folder. Attempting
to write to it will cause errors.
///

/// danger
All output files must be placed in the `output` directory during container execution. Any files created there during the
image build will be ignored by the match.
///

### Metadata

Both types of programs will find a file `info.json` in the input directory. It contains some basic info about how the
program is run and the resources it has available. In particular, its keys are:

`size`

:   The instance size of this fight. If the program is a generator, its output must be
    smaller than it and if it is a solver the input instance is guaranteed to be smaller than it.

`timeout`

:   The timeout in seconds, or none if there is no timeout. This is the maximum time the program is allowed to run
    before it will be stopped.

`space`

:   The amount of memory space in MB that this program has available, or none if there is no limit. If it attempts to
    use too much memory, the memory is swapped with disk space leading to very big performance decreases.

`cpus`

:   The number of physical cpu cores the program is allowed to use.

/// example | Example (with more human-readable formatting)
```json title="input/info.json"
{
    "size": 17,
    "timeout": 20,
    "space": none,
    "cpus": 2
}
```
///

/// info | Advanced
The input may also contain a file or folder called `battle_data`, this is an advanced feature of some battle types and
explained [here](../advanced/battle#battle-data).
///

### Problem data

What exactly problem data looks like is highly dependent on the problem being used. Many of them use a single json
file, but other file types and even entire folders are possible. Throughout this section, when we talk about an instance
or solution we mean either a file or a folder depending on what particular problem is being used.

Generally, problems that use single files also use file extensions to indicate the correct type of encoding being used.
In this case the names we are using here refer to only the stems of the actual file names found on disk and need to be
suffixed with the correct extension.

For example, when we say that you should expect a problem instance named `instance`, the actual file system of the
container will most likely contain a file called `instance.json`, but it might also be `instance.png` or a folder
`instance/` containing several files.

#### Generators

Generators will also find a file called `size.txt` in their input directory. This simply contains the maximum allowed
size of the instance they are tasked with generating.

/// example
```text title="input/size.txt"
17
```
///

Generators are tasked with creating a problem instance. It needs to be placed in the `output` folder and called
`instance`.

/// example
```json title="output/instance.json"
{!> pairsum_instance.json!}
```
///

Additionally, many problems require the generator to also output a solution. This can be used to ensure that the
instance is actually solvable or to compare the quality of the solver's solution against the best one possible.
If it is needed Algobattle expects it to be called `solution` in the `output` folder.

/// example
```json title="output/solution.json"
{!> pairsum_instance.json!}
```
///

#### Solvers

Solvers will instead find an encoded instance named `instance` in their input. This is the instance that the other team
generated, and the solver is required to solve.

/// example
```json title="input/instance.json"
{!> pairsum_instance.json!}
```
///

Their solution needs to be named `solution` and placed in the `output` directory.

/// example
```json title="output/solution.json"
{!> pairsum_solution2.json!}
```
///

## A complete example

To get more familiar with everything we can now write a simple generator and solver and try it out. We will again be
using the Pairsum problem for this.

### Generator

First, we'll tackle the generator. A simple (and surprisingly effective) way to generate fairly hard instance is to just
generate them randomly:

```python
{!> pairsum_generator/start.py !}
```

1. This opens the input file and parses it into an integer.

2. This generates as many random numbers as are asked for. Note that they are in the range of a (signed) 64 bit int.
    Many problems use numbers in this range to ensure easy cross language compatibility.

3. This writes the generated instance as a correctly formatted json file at the expected location.

Pairsum also requires the generator to output a certificate solution. The big problem with our approach is that we can't
do that very easily, in fact we don't even know if there is a correct solution at all! We can work around this by not
generating the instances completely randomly but instead inserting a known solution into an otherwise random list.

```python title="generator/main.py" hl_lines="9-15 22-25"
{!> pairsum_generator/main.py !}
```

1. This opens the input file and parses it into an integer.

2. This generates as many random numbers as are asked for, minus the four solution numbers we will generate separately.
    Note that they are in the range of a (signed) 64 bit int. Many problems use numbers in this range to ensure easy
    cross language compatibility.

3. This writes the generated instance as a correctly formatted json file at the expected location.

4. Here we now create the known solution. The first three numbers are randomly chosen, and the last is set to ensure a
    valid solution. Then they are inserted into the instance at random positions.

5. Finally, we output the certificate solution.

Now the only thing left is to create a simple Dockerfile for our program.

```Dockerfile title="generator/Dockerfile"
{!> pairsum_generator/Dockerfile !}
```

And to place both of these files into the `generator` directory of the Pairsum problem.

### Solver

Now we need to figure out how to actually solve instances that are presented to us. Since this is much more complicated
than just randomly generating some numbers we'll want to use a more performant language than Python for this. In this
example I will use rust, but you can choose any language you like.

The simplest approach is to just iterate over all possible combinations of four numbers from the list and check which
one is a valid solution.

```rust title="solver/main.rs"
{!> pairsum_solver/main.rs !}
```

1. This tells rust how to destructure the json input.

2. Here we just open the input file and parse it.

3. Now we can iterate over all combinations of four numbers from the instance list.

4. If the pairs of it sum to the same number we output them as a valid solution.

/// question | Not familiar with Rust?
If you're not familiar with Rust this program probably looks pretty intimidating. You don't need to understand how
exactly this code works, the important bit just is that it iterates over all possible solutions until it finds a correct
one.
///

Since Rust is a compiled language the setup needed to run it is a bit more involved than with Python. First, we need a
`Cargo.toml` file that specifies what our project looks like. The easiest way to do that is running

```console
cargo init
```
and adding the dependencies we used with

```console
cargo add serde serde_json -F serde/derive itertools
```

This results in a file like this:

```toml title="solver/Cargo.toml"
{!> pairsum_solver/Cargo.toml !}
```

Finally, the source code needs to be compiled during the build step so that the container can easily run it during
container execution without losing any additional time.

```Dockerfile title="solver/Dockerfile"
{!> pairsum_solver/Dockerfile !}
```

We put these three files (`main.rs`, `Cargo.toml`, and `Dockerfile`) into the `solver` subdirectory of the Pairsum
problem folder.

### Trying it all out

Now we can finally try out our code in a match! With the program files placed at the right locations Algobattle will
find them automatically, all we need to do is point it to the folder containing the Pairsum problem.

<div class="termy">

```console
algobattle algobattle-problems/pairsum
```

</div>

///note
This should now run without error and display the match screen while doing so. Running the whole match may take a while,
if you don't want to wait you can cancel the execution with `CTRL+C`.
///
