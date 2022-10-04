# Battle wrappers
There is more than one possible type of algorithmic battle, which is realized
through different types of battle wrappers.

The original wrapper, which is used by default, is the *iterated* one.
This wrapper executes battles on instances of increasing size, until either
the iteration cap is reached or one of the teams fails on some instance size.

If you want to add your own wrapper, include it in this directory. You can then
use it by providing the name of the module to the
`BattleWrapper.initialize` method or by simply using the modules name for
the `--battle_type` option of the `battle` script (you may have to add its name
to the *choices* list of this option).

If you want a battle wrapper to use additional options, you can add a section in
the config file given to initialize `match_data` to provide them to the
`__init__()` method of your wrapper. Make sure that the name of the section
and of your module name match.
