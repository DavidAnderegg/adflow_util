from setuptools import setup
import re

__version__ = re.findall(
    r"""__version__ = ["']+([0-9\.]*)["']+""",
    open('adflow_util/__init__.py').read(),
)[0]

setup(name='adflow',
      version=__version__,


      description="ADflow util...",
      long_description="""ADflow util...
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
    #   install_requires=[
    #         'numpy>=1.16.4',
    #         'baseclasses>=1.2.0',
    #         'mpi4py>=3.0.2',
    #         'petsc4py>=3.11.0',

    #   ],
    #   classifiers=[
    #     "Operating System :: Linux",
    #     "Programming Language :: Python, Fortran"]
    #   )