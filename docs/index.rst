##########
Algobattle
##########

.. toctree::
   :hidden:

   guide
   api

Algobattle is a framework that lets you run tournaments where teams compete to solve algorithmic problems.
It is being developed by the `Computer Science Theory group of RWTH Aachen University <https://tcs.rwth-aachen.de/>`_,
which also offers a lab course based on it since 2019. This repository contains the code that instructors and students
need to run the tournament itself. In addition to that, we also develop `Algobattle Web`, a web server providing an easy
to use interface to manage the overall structure of such a course.

The idea of the lab is to pose several, usually NP-complete problems over the course of the semester. Teams of students
then write code that generates hard-to-solve instances for these problems and solvers that solve these problems quickly.
The teams then battle against each other, generating instances for other teams, and solving instances that were
generated for them. Each team then is evaluated on its performance and is awarded points.


User guide
==========
If you are a student participating in an Algobattle course you can find the information most relevant to you in our
:ref:`student-guide`.

If you are an instructor looking to run a course, the :ref:`instructor-guide` is best suited for you.


Requirements
============
This project is being developed and tested on both Windows and Linux, MacOS support is being worked on but still is
tentative.

Algobattle requires python version ``3.11`` or higher and docker.


Usage
=====
You can install the algobattle package with any standard python package manager. For example:

.. code-block:: console

   pip install . --user

You can then run matches using the command line interface. Run

.. code-block:: console

   algobattle --help

to see all options, or read the :ref:`cli-guide` tutorial.
