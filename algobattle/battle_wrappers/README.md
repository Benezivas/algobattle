# Battle wrappers
There is more than one possible type of algorithmic battle, which is realized
through different types of battle wrappers. A battle wrapper receives a
match object and executes the fights in some predefined way.

The original wrapper, which is used by default, is the *iterated* one.
This wrapper executes battles on instances of increasing size, until either
the iteration cap is reached or one of the teams fails on some instance size.

If you want to add your own wrapper, include it in this directory. You can
then import it in the `match.py` and edit the `match.run` method to recognize
your wrapper.