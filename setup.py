from setuptools import setup
import re

__version__ = re.findall(
    r"""__version__ = ["']+([0-9\.]*)["']+""",
    open('adflow_util/__init__.py').read(),
)[0]

setup(name='adflow_util',
    version=__version__,


    description="ADflow utility",
    long_description="""This utility allows the 
    """,
    long_description_content_type="text/markdown",
    keywords='',
    author='',
    author_email='',
    url='https://github.com/DavidAnderegg/adflow_util',
    license='',
    packages=[
        'adflow_util',
    ],
      install_requires=[
            'baseclasses>=1.2.0',
            'adflow>=2.2.0',
            'numpy>=1.18.5',
            'tabulate>=0.8.7'
      ],

    #   ],
    #   classifiers=[
    #     "Operating System :: Linux",
    #     "Programming Language :: Python, Fortran"]
    
    entry_points = {
    'console_scripts': ['adflow_plot=adflow_util:adflow_plot'],
    }
    )