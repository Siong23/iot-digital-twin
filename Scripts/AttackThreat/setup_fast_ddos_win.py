#!/usr/bin/env python3
"""
Setup script for Windows-compatible fast DDoS attack C extension
"""

from setuptools import setup, Extension
import sys
import os

# Define the extension module
ext_module = Extension(
    'fast_ddos_attack',
    sources=['fast_ddos_attack_win.c'],
    libraries=['ws2_32'] if sys.platform == 'win32' else [],
    define_macros=[('_WIN32_WINNT', '0x0601')] if sys.platform == 'win32' else []
)

if __name__ == '__main__':
    setup(
        name='fast_ddos_attack',
        version='1.0',
        description='Fast DDoS attack C extension for Windows',
        ext_modules=[ext_module],
        zip_safe=False,
    )
