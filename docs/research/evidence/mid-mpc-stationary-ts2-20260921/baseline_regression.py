"""Process-isolated HEAD implementation of the sole modified production method."""
import ast,subprocess,sys
from pathlib import Path
import pytest
import colav_simulator.core.colav.mid_mpc_acceptance as module
source=subprocess.check_output(['git','show','e0523bca52f528a22d1d9a6a2b31ad321d702f21:colav_simulator/core/colav/mid_mpc_acceptance.py'],text=True)
cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='MidMpcPlanAcceptance')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_colreg')
method.decorator_list=[]
namespace=dict(vars(module));exec(compile(ast.Module(body=[method],type_ignores=[]),'<HEAD _colreg>','exec'),namespace)
module.MidMpcPlanAcceptance._colreg=staticmethod(namespace['_colreg'])
print('BASELINE: unchanged HEAD _colreg loaded in isolated test process; production files untouched',flush=True)
sys.exit(pytest.main(sys.argv[1:]))
