import json,math,time,traceback,pickle
from dataclasses import replace
from pathlib import Path
import numpy as np
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
root=Path('tmp/mid_mpc_t1061_20260921')
source=Path('runs/a0994641-670d-460b-9ec8-fe0199234b40')
old=json.loads((source/'manifest.json').read_text())
spec=replace(RunSpec.from_dict(old['spec']),output_root=str(root/'runs-thin'))
r=ExperimentRunner();p=r.prepare(spec);s=p.session;s.enable_pickle_frames()
identity={key:{'original':old[key],'replay':getattr(p.manifest,key)} for key in ('simulation_config_hash','scenario_hash','episode_hash')}
(root/'replay-identity.json').write_text(json.dumps(identity,indent=2))
print('IDENTITY',identity,flush=True)
assert all(v['original']==v['replay'] for v in identity.values()),identity
rows=[];physical=[];started=time.monotonic();s.start();error=None
try:
 while s.state.value=='RUNNING':
  snap=s.advance();rows.append([snap.sim_time,*[x for n in range(4) for x in snap.payload[f'Ship{n}']['state']]])
  physical.append(pickle.dumps({k:{f:v[f] for f in ('state','input','references','timestamp','date_time_utc')} for k,v in snap.payload.items()}))
  s._frame_blobs.clear()
  if s.sequence%1000==0:
   np.save(root/'full-physical-states.npy',np.asarray(rows))
   print('PROGRESS',snap.sim_time,flush=True)
 s._frame_blobs=physical
 print('SIMULATION_FINISHED',s.simulator.t,flush=True)
 result=r.finalize(p)
 summary={'run_id':p.manifest.run_id,'state':s.state.value,'time_s':s.simulator.t,'goal_reached':any(e['type']=='goal_reached' for e in s.events),'hard_gate':result.evaluation.hard_gate.outcome.value,'aggregate':result.evaluation.aggregate,'fallback_used':p.manifest.fallback_used,'wall_s':time.monotonic()-started}
except Exception as exc:
 s._frame_blobs=physical
 error=str(exc);traceback.print_exc();p.artifact_sink.close(timeout_s=10);r.persist_original_gnc(p);r.persist_failure(p.manifest,p.writer,exc,s.frame_view,s.events)
 summary={'run_id':p.manifest.run_id,'time_s':s.simulator.t,'failure':error}
np.save(root/'full-physical-states.npy',np.asarray(rows));(root/'full-summary.json').write_text(json.dumps(summary,indent=2,default=str));print('SUMMARY',summary,flush=True)
assert not error,summary
assert summary['goal_reached'] and summary['hard_gate']=='PASS' and not summary['fallback_used'],summary
