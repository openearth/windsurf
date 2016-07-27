from setuptools import setup, find_packages

setup(
    name='windsurf',
    version='0.0',
    author='Bas Hoonhout',
    author_email='b.m.hoonhout@tudelft.nl',
    packages=find_packages(),
    description='A composite model for simulating integrated nearshore and aeolian sediment transport',
    long_description=open('README.txt').read(),
    install_requires=[
        'numpy',
        'docopt',
    ],
    #setup_requires=[
    #    'sphinx',
    #    'sphinx_rtd_theme'
    #],
    tests_require=[
        'nose'
    ],
    test_suite='nose.collector',
    entry_points={'console_scripts': [
        'windsurf = windsurf.console:windsurf',
        'windsurf-setup = windsurf.console:windsurf_setup'
    ]},
)
