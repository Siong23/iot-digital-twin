#!/usr/bin/env python3
"""
Setup script for Windows-compatible fast telnet bruteforce C extension
"""

from setuptools import setup, Extension
import sys
import os

# Define the extension module
ext_module = Extension(
    'fast_telnet_bruteforce',
    sources=['fast_telnet_bruteforce_win.c'],
    libraries=['ws2_32'] if sys.platform == 'win32' else [],
    define_macros=[('_WIN32_WINNT', '0x0601')] if sys.platform == 'win32' else []
)

if __name__ == '__main__':
    setup(
        name='fast_telnet_bruteforce',
        version='1.0',
        description='Fast telnet brute force C extension for Windows',
        ext_modules=[ext_module],
        zip_safe=False,
    )
