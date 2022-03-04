from importlib import import_module
from pathlib import Path

for path in Path(__file__).resolve().parent.iterdir():
    if not path.name[:2] == ("__") and path.name[-3:] == ".py":
        import_module(f".{path.name[:-3]}", "algobattle.battle_wrappers")