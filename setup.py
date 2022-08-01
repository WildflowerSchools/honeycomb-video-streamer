import json
import os
from setuptools import setup, find_packages


BASEDIR = os.path.dirname(os.path.abspath(__file__))
VERSION = os.environ.get("VERSION")

print(VERSION)

BASE_DEPENDENCIES = [
    'click>=8.0',
    'python-dotenv>=0.19.0',
    'wildflower-honeycomb-sdk>=0.7.3',
    'boto3>=1.18.0',
    'ffmpeg-python==0.2.0',
    'numpy>=1.21',
    'pandas>=1.3.0',
    'wf-video-io>=3.0.3'
]

DEVELOPMENT_DEPENDENCIES = [
    'autopep8>=1.5',
    'pylint>=2.10.2',
]

# allow setup.py to be run from any path
os.chdir(os.path.normpath(BASEDIR))

setup(
    name='honeycomb-video-streamer',
    packages=find_packages(),
    setup_requires=['numpy'],
    version=VERSION,
    include_package_data=True,
    description='Python tools to prepare videos for streaming from honeycomb',
    long_description='',
    url='https://github.com/WildflowerSchools/honeycomb-video-streamer',
    author='Paul DeCoursey',
    author_email='paul.decoursey@wildflowerschools.org',
    install_requires=BASE_DEPENDENCIES,
    extras_require={
        'development': DEVELOPMENT_DEPENDENCIES
    },
    keywords=['video'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
    ]
)
