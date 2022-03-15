from setuptools import setup
from pathlib import Path

# Stolen from microsofts recommenders repository:
here = Path(__file__).absolute().parent
version_data = {}
with open(here.joinpath("algobattle", "__init__.py"), "r") as f:
    exec(f.read(), version_data)
version = version_data.get("__version__", "0.0")

setup(
    name='algobattle',
    version=version,
    packages=['algobattle'],
    scripts=['scripts/battle'],
    python_requires='>=3.9',
    include_package_data=True
)
