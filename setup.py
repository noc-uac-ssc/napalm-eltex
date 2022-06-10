"""setup.py file."""

from setuptools import setup, find_packages



__author__ = 'Lagovskiy Sergey <slagovskiy@gmail.com>'



# with open("requirements.txt", "r") as fs:

#     reqs = [r for r in fs.read().splitlines() if (len(r) > 0 and not r.startswith("#"))]



with open("README.md", "r") as fs:

    long_description = fs.read()



setup(

    name="napalm-eltex",

    version="0.1.1",

    packages=find_packages(exclude=("test*",)),

    author="UAC-SSC",

    author_email="noc@uac-ssc.ru",

    description="NAPALM driver for Eltex switches",

    license="NIT License",

    long_description=long_description,

    long_description_content_type="text/markdown",

    classifiers=[

        "Topic :: Utilities",

        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",

        "Programming Language :: Python :: 3",

        "Programming Language :: Python :: 3.6",

        "Programming Language :: Python :: 3.7",

        "Programming Language :: Python :: 3.8",

        "Programming Language :: Python :: 3.9",

        "Programming Language :: Python :: 3.10",

        'Operating System :: OS Independent',

    ],

    url="https://github.com/noc-uac-ssc/napalm-eltex",

    project_urls={
        "Bug Tracker": "https://github.com/noc-uac-ssc/napalm-eltex/issues",
    },
    include_package_data=True,

    install_requires=[
        'napalm>=3.3',
        'pandas>=1.3'
    ]
)

