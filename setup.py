#!/usr/bin/env python
from setuplib import setup

setup(
    name = 'inotifyx',
    version = '0.2.3',
    description = 'Simple Linux inotify bindings',
    author = 'Forest Bond',
    author_email = 'forest@forestbond.com',
    url = 'https://launchpad.net/inotifyx/',
    license='MIT',
    packages = ['inotifyx'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
)
