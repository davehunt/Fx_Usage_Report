#!/usr/bin/env python
from setuptools import setup, find_packages

test_deps = [
    'coverage',
    'pytest',
    'pytest-cov',
    'pytest-timeout',
    'moto',
    'mock',
]

extras = {
    'testing': test_deps,
}

setup(
    name='fx_usage_report',
    version='0.1',
    description='Python ETL job for the Firefox Usage Report',
    author='Firefox Public Data Platform',
    author_email='fx-public-data@mozilla.com',
    url='https://github.com/mozilla/Fx_Usage_Report.git',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=[
        'arrow',
        'click',
        'click_datetime',
        'numpy',
        'pyspark',
        'python_moztelemetry',
        'scipy',
    ],
    tests_require=test_deps,
    extras_require=extras,
)
