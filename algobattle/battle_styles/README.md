# Battle Styles
There is more than one possible type of algorithmic battle, which is realized
through different types of battle styles. A battle style receives a matchup of
teams involved in a battle, determines what fights will be fought and then exectues
them with the provided fight object.

The original style, which is used by default, is the *iterated* one.
This style executes battles on instances of increasing size, until either
the iteration cap is reached or one of the teams fails on some instance size.

If you want to add your own style, simply include it in this directory and have it
subclass from `BattleStyle`, it will be automatically integrated into the command line
interface and match scripts. Any additional arguments in its `__init__` will be
command line and config file parameters, their help messages taken from the docstring.