# Tutorial

The Algobattle tutorial goes over everything needed to understand how the package works and the most common ways to
use it. It's primarily aimed at students participating in a course and course instructor that want to learn how to work
with the package. If you are an instructor that is trying to get an overview over all features Algobattle offers, the
[Instructor Overview](../advanced/instructor.md) is better suited for you.

The tutorial pages build on each other and are best read in sequence. It assumes almost no prerequisite knowledge of
specific topics, but an understanding of basic theoretical computer science ideas like algorithmic problems and of
the Python language will make things a lot easier.


# Student quick start

If all you want is the fastest way to get started writing code and running things, this is for you. Every step here
links to its more detailed explanation in the full tutorial. If you are already familiar with Docker and Python this is
all you need to do:

1. [Install Python](installation.md#installing-python)

2. [Install Docker](installation.md#installing-docker)

3. [Install the Algobattle package](installation.md#installing-algobattle)

4. Download the Problem your course instructors gave you.

5. Put your code into the `generator` and `solver` subfolders of the problem folder. Each folder needs to contain a
    Dockerfile that builds into an image which can be executed to either generate problem instances or solve them. We
    have an example [generator](programs.md#generator) and [solver](programs.md#solver) setup.

