import json
import os
from setuptools import setup, find_packages


BASEDIR = os.path.dirname(os.path.abspath(__file__))
VERSION = json.load(open(os.path.join(BASEDIR, 'package.json'))).get("version")

BASE_DEPENDENCIES = [
    'click>=7.0',
    'python-dotenv>=0.10.3',
    'wildflower-honeycomb-sdk>=0.7.3',
    'boto3>=1.10.0',
    'ffmpeg-python==0.1.17',
    'numpy>=1.19.5',
    'pandas>=1.2.0'
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
    long_description=open('honeycomb_tools/README.md').read(),
    url='https://github.com/WildflowerSchools/honeycomb-video-streamer',
    author='Paul DeCoursey',
    author_email='paul.decoursey@wildflowerschools.org',
    install_requires=BASE_DEPENDENCIES,
    keywords=['video'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
    ]
)
