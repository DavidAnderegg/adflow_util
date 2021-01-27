from adflow_util import ADFLOW_UTIL


options = {
    'name': 'n0012_sweep',
    'resetAP': True,
}

aeroOptions = {
    'alpha': [1, 2, 3, 4],
    'reynolds': 3e6,
    'mach': 0.15,
    'T': 288,
    
    'reynoldsLength': 1.0,
    'xRef': 0.25,
    'areaRef': 1.0,
    'chordRef': 1.0,
    'evalFuncs': ['cl','cd', 'cmz'],
}

solverOptions = {
    # Common Parameters
    'gridFile': 'n0012.cgns',
    'outputDirectory':'output',

    # Physics Parameters
    'equationType':'RANS',

    # RK
    'smoother':'Runge-Kutta',
    'rkreset':True,
    'nrkreset':20,
    'CFL':0.8,
    'MGCycle':'sg',
    'nsubiterturb': 5, 
        
    # ANK
    'useanksolver': True,
    'anklinresmax': 0.1,
    'anksecondordswitchtol': 1e-3,
    'ankasmoverlap': 4,
    "outerPreconIts": 3,
    'ankcoupledswitchtol': 1e-5, 
    'ankunsteadylstol': 1.5,
    
    # NK
    'useNKSolver':True,
    'nkswitchtol':1e-7,
    
    # General
    'monitorvariables':['resrho', 'resturb', 'cl','cd'],
    'printIterations': True,
    'writeSurfaceSolution': True,
    'writeVolumeSolution': True,
    'outputsurfacefamily': 'wall',
    'surfacevariables': ['cp','vx', 'vy','vz', 'mach'],
    'volumevariables': ['resrho'],
    'nCycles':10000,
    'L2Convergence':1e-12,
}

au = ADFLOW_UTIL(aeroOptions, solverOptions, options)
au.run()