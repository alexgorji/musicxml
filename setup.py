import setuptools
from pathlib import Path

long_description = (Path(__file__).parent / "README.rst").read_text()
setuptools.setup(
    name="musicxml",
    version="1.2",
    author="Alex Gorji",
    author_email="aligorji@hotmail.com",
    description="generating musicxml",
    url="https://github.com/alexgorji/musicxml.git",
    packages=setuptools.find_packages(),
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    long_description=long_description,
    long_description_content_type='text/markdown',
    include_package_data=True
)
