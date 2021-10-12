# The Runtime Delay Test
There is a certain I/O delay when starting and stopping `docker` containers
depending on the machine that the `battle` is executed on. This problem is used
to calculate this overhead for starting and stopping docker containers that do
nothing but return a little bit of text. The measured maximal overhead is then
added to the basic runtimes given in the config file used in the run.

This problem is not meant to be run on its own. It is automatically invoked by
the `battle` at the start of running any problem file as long as the option
`--no-overhead-calculation` is not set.