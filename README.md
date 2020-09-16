# adflow_util

This package provides some convenience functions for [ADflow](https://github.com/mdolab/adflow). It allows to:

1. Easily calculate a Polar sweep with ADflow.
2. Plot realtime ADflow state variables in the terminal.


# Usage
## ADFLOW_UTIL
The following script sweeps through a list of Angle of Attacks (the full example can be found at *example/polar_sweep.py*).

``` python
from adflow_util import ADFLOW_UTIL

name = 'test'

aeroOptions = {
    'alpha': [1, 2, 3, 4],
    'reynolds': 3e6,
    # ...
    'evalFuncs': ['cl','cd', 'cmz']
}

solverOptions = {
    # Common Parameters
    'gridFile': 'n0012.cgns',
    'outputDirectory':'output',

    # Physics Parameters
    'equationType':'RANS',
    # ...
    'L2Convergence':1e-12,
}

au = ADFLOW_UTIL(aeroOptions, solverOptions, name)
au.run()
```
The dict **aeroOptions** holds all the variables that normally **baseclasses.AeroProblem** would. If one variable is a list, this is considered the sweep variable. All variables except **coefPol, cosCoefFourier, sinCoefFourier, momentAxis, solverOptions, evalFuncs** can be sweeped. 

This script will generate a file called *test.out* with this content:
```
# ...
 RESULTS 
  alpha          cd          cl         cmz    totalRes    iterTot
-------  ----------  ----------  ----------  ----------  ---------
      1  0.01011288  0.11602992  0.00066774  0.00085824        633
      2  0.01024706  0.23189008  0.00131727  0.00088097        557
      3  0.01047568  0.34740544  0.00193006  0.00084232        564
      4  0.01080607  0.46238766  0.00248672  0.00089012        541
```



It is also possible to have multiple sweep variables. But all must be the same length. There will be no cross calculation. It was choosen this way to allow for maximal control. 


## adflow_plot
If this package was installed using pip the command **adflow_plot** should be available in your terminal. To use it, simply type **adflow_plot -i yourADflowScript.py**. As this utility reads the stdout stream, it should work with all scripts as long as the ADflow option **printIterations** is **True**. 

If you want to parallelize your ADflow calculation, simply add **-np number_of_cores** oder **-H list_of_nodes**. As a default **mpirun** is used to start mpi. If you have a different installation of mpi, you can change it with **-mpi some_different_mpi_command**. Type **adflow_plot -h** to get a list of all available start options. 


The output looks something like this:

![adflow_plot_output](adflow_plot.PNG)
At the top, a few raw lines from ADflow are shown. In the middle is the ASCII plot and at the bottom is a command line to change some behaviour. Type **h** or **help** to get a list of all commands. type **h a_command** oder **help a_command** to get additional information about this specific command.



# Instalation
simply clone this repo with
```
git clone https://github.com/DavidAnderegg/adflow_util.git
```
move into its directory
```
cd adflow_util
```
and pip-install it
```
pip install .
```