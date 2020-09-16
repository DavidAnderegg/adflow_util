from adflow_util import ADFLOW_UTIL

name = 'n0012_sweep'

aeroOptions = {
    'alpha': [1, 2, 3, 4],
    'reynolds': 3e6,
    'mach': 0.15,
    'T': 288,
    
    'reynoldsLength': 1.0,
    'xRef': 0.25,
    'areaRef': 1.0,
    'chordRef': 1.0,
    'evalFuncs': ['cl','cd', 'cmz']
}

solverOptions = {
    # Common Parameters
    'gridFile': 'n0012.cgns',
    'outputDirectory':'output',

    # Physics Parameters
    'equationType':'RANS',

    # RK
    'smoother':'runge kutta',
    'rkreset':True,
    'nrkreset':20,
    'CFL':0.8,
    'MGCycle':'sg',
        
    # ANK
    'useanksolver' : True,
    
    # NK
    'useNKSolver':False,
    'nkswitchtol':1e-9,
    
    # General
    'monitorvariables':['resrho', 'resturb', 'cl','cd'],
    'printIterations': True,
    'writeSurfaceSolution': True,
    'writeVolumeSolution': True,
    'outputsurfacefamily': 'wall',
    'surfacevariables': ['cp','vx', 'vy','vz', 'mach'],
    'volumevariables': ['resrho'],
    'nCycles':10000,
    'L2Convergence':1e-9,
}

au = ADFLOW_UTIL(aeroOptions, solverOptions, name)
au.run()