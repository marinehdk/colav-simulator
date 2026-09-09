"""Read-only diagnostic. --reject-saturation intentionally rejects the observed symptom."""
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from scipy.optimize import linprog, lsq_linear

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from colav_simulator.modular_gnc.contracts import NavigationState, VesselLoad
from colav_simulator.modular_gnc.fcb45_actuation import FCB45Allocator, rudder_inflow
from colav_simulator.modular_gnc.fcb45_actuation import world_ne_to_body_velocity

case = json.loads((ROOT / 'tests/fixtures/fcb45_allocator/force_roundoff.json').read_text())
nav = NavigationState(*case['navigation'])
request = VesselLoad(**case['requested'])

def run(seed, load=request):
    a = FCB45Allocator({})
    a.restore(replace(a.snapshot(), optimization_seed=tuple(seed)))
    a.set_operating_point(nav, (0.4, -0.2))
    r = a.allocate(load)
    return a, r

a, r = run(case['seed'])
for _ in range(2):
    _, repeated = run(case['seed'])
    assert dict(repeated.actuator_commands_n) == dict(r.actuator_commands_n)
_, cold = run([0.0] * 7)
_, no_yaw = run(case['seed'], replace(request, yaw_nm=0.0))
_, mild_yaw = run(case['seed'], replace(request, yaw_nm=-100000.0))
_, cold_no_yaw = run([0.0]*7, replace(request, yaw_nm=0.0))
current = world_ne_to_body_velocity((0.4, -0.2), nav.heading_rad)
u, v = nav.surge_mps-current[0], nav.sway_mps-current[1]
assert u < 0 and a.bow_authority == 1
specs = [s for s in a._asset.actuators if s.kind != 'rudder']
# Independently assemble geometry, in physical N and N*m, without allocator matrix.
B = np.array([[np.cos(s.orientation_body_rad), np.sin(s.orientation_body_rad),
               s.position_body_m[0]*np.sin(s.orientation_body_rad)-s.position_body_m[1]*np.cos(s.orientation_body_rad)] for s in specs]).T
scale = np.array([s.max_force_n for s in specs])
Bz = B * scale
bounds = [(-1,0) if s.kind == 'main' else (-1,1) for s in specs]
tau = np.array([request.surge_n, request.sway_n, request.yaw_nm])
# Negative main thrust + negative axial inflow => exactly zero modeled rudder authority.
for s in a._asset.actuators:
    if s.kind == 'rudder':
        assert rudder_inflow(a.parameters, u, v, nav.yaw_rate_radps, s.position_body_m[0], 0)[0] == 0
exact = linprog(np.zeros(5), A_eq=Bz, b_eq=tau, bounds=bounds, method='highs')
yaw_low = linprog(Bz[2], A_eq=Bz[:2], b_eq=tau[:2], bounds=bounds, method='highs')
yaw_high = linprog(-Bz[2], A_eq=Bz[:2], b_eq=tau[:2], bounds=bounds, method='highs')
assert exact.status == 2 and yaw_low.success and yaw_high.success
w = np.array([1/200000,1/40000,1/960000])
seed = np.array(case['seed'])[[0,1,2,5,6]]
A = np.vstack([w[:,None]*Bz, 1e-3*np.eye(5)])
b = np.r_[w*tau,1e-3*seed]
independent = lsq_linear(A,b,bounds=np.array(bounds).T,method='trf',tol=1e-12,max_iter=1000)
actual = np.array([r.actuator_commands_n[s.actuator_id] for s in specs])/scale
assert independent.success
assert np.max(np.abs((actual-independent.x)*scale)) < 0.01
assert r.actuator_commands_n['bow_tunnel_thruster_forward'] == -20000
assert cold.actuator_commands_n['bow_tunnel_thruster_forward'] == -20000
assert abs(mild_yaw.actuator_commands_n['bow_tunnel_thruster_forward']) < 19999
out = {
    'fixture_provenance':'Synthetic fuzz trial 994 at captured navigation; NOT original failed actuator command',
    'relative_water_velocity_mps':[u,v], 'bow_authority':a.bow_authority,
    'requested':asdict(request), 'commands_n':dict(r.actuator_commands_n),
    'achieved':asdict(r.achieved),'residual':asdict(r.residual),
    'cold_commands_n':dict(cold.actuator_commands_n),
    'zero_yaw_warm_commands_n':dict(no_yaw.actuator_commands_n),
    'zero_yaw_cold_commands_n':dict(cold_no_yaw.actuator_commands_n),
    'mild_yaw_commands_n':dict(mild_yaw.actuator_commands_n),
    'exact_load_feasible':False,
    'feasible_yaw_at_exact_surge_sway_nm':[yaw_low.fun,-yaw_high.fun],
    'independent_trf_max_force_difference_n':float(np.max(np.abs((actual-independent.x)*scale))),
    'per_actuator_load':{s.actuator_id:(B[:,i]*r.actuator_commands_n[s.actuator_id]).tolist() for i,s in enumerate(specs)},
    'checks':'PASS: deterministic replay, zero rudder model authority, infeasible requested wrench, independently confirmed optimum, cold seed saturated, reduced yaw unsaturated; zero yaw warm remains saturated but cold does not'
}
print(json.dumps(out,indent=2))
if '--reject-saturation' in sys.argv:
    assert abs(r.actuator_commands_n['bow_tunnel_thruster_forward']) < 19999, 'RED: -20 kN remains; saturation alone is not a correctness violation'
