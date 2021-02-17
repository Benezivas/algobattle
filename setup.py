from setuptools import setup
from glob import glob

setup(
    name='algobattle',
    version='0.1.0',
    packages=['algobattle'],
    scripts=['scripts/algobattle'],
    python_requires='>=3.9',
    include_package_data=True
)