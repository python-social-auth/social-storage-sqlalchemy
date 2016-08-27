# -*- coding: utf-8 -*-
"""Setup file for easy installation"""
from os.path import join, dirname
from setuptools import setup


def long_description():
    return open(join(dirname(__file__), 'README.rst')).read()

def load_requirements():
    return open(join(dirname(__file__), 'requirements.txt')).readlines()

setup(
    name='python-social-auth-app-flask',
    version='0.0.1',
    author='Matias Aguirre',
    author_email='matiasaguirre@gmail.com',
    description='Python social authentication made simple.',
    license='BSD',
    keywords='flask, social auth',
    url='https://github.com/python-social-auth/social-app-flask',
    packages=['social_flask'],
    long_description=long_description(),
    install_requires=load_requirements(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Internet',
        'License :: OSI Approved :: BSD License',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3'
    ],
    zip_safe=False
)
