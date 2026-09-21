"""Diagnostic only: unchanged native GNC on a straight, constant-speed route."""
import json,sys
from pathlib import Path
import numpy as np
from colav_simulator.core.ship import Config,build_ship
from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge

mode=sys.argv[1] if len(sys.argv)>1 else 'avoidance'
ship=build_ship(Config(id=0,mmsi=100,csog_state=np.array([1000.,2000.,8.,0.]),waypoints=np.array([[1000.,6000.],[2000.,2000.]]),speed_plan=np.array([8.,8.]),original_gnc=OriginalGncConfig.from_dict({})),dt_s=.5)
ship.forward(11.)
bridge=OriginalPlanBridge(ship,.5)
req=bridge._base('vo','straight-speed-contract',ship.stack.time_ns+100_000_000_000)
req['latitude'],req['longitude']=ship.frame.geographic(np.array([[1000.,1700.,6000.],[2000.,2000.,2000.]]))
req.update(command_speed_mps=[8.]*3,navigation_mode=['cruise',mode,'cruise'])
bridge._deliver(req,{'diagnostic':'straight ordinary avoidance at 8 m/s'})
ship.forward(30.)
status=ship.stack.latest['/gnc/route_execution_status'];out={'mode':mode,'identity':ship.original_gnc_evidence(),'manager_requested':status['requested_speed_mps'],'route_limit':status['current_speed_limit_mps'],'guidance_setpoint':float(ship.applied_reference[3]),'actual_speed':ship.speed,'feedback':bridge.last_outcome,'waypoints':ship.stack.latest.get('/gnc/internal_waypoints')}
p=Path(__file__).parent/(mode+'.json');p.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k not in ['identity','feedback','waypoints']}))
ship.close()
if '--assert-preserved' in sys.argv:
 assert abs(out['guidance_setpoint']-8.)<1e-6,'REPRODUCED: ordinary 8 m/s intent does not survive native guidance'
