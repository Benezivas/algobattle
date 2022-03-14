# Battle Styles
There is more than one possible type of algorithmic battle, which is realized
through different types of battle styles. A battle style receives a
match object and executes the fights in some predefined way.

The original style, which is used by default, is the *iterated* one.
This style executes battles on instances of increasing size, until either
the iteration cap is reached or one of the teams fails on some instance size.

If you want to add your own style, include it in this directory. You can
then import it in the `match.py` and edit the `match.run` method to recognize
your style.