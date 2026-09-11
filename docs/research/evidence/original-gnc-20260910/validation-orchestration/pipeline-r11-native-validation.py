from pathlib import Path
import subprocess,json,time,hashlib,gzip,os
root=Path.cwd();b=root/'build';v=b/'original_gnc-glibc-v8';remote='/home/marine.huang/colav-gnc-oracle/l45-20260824-v2';group='reference-full-replay-stream-v3b';case='R11-E4';canonical=b/group/(case+'-vectors-v3');canonical.mkdir(parents=True,exist_ok=True);parts=b/'original-r11-pipeline-v1';parts.mkdir(exist_ok=True)
core=['ship_dynamics_node','ship_control_node','ship_guidance_node','thrust_allocation_node','coordinate_transform_node','active_route_manager_node'];partitions={'core':core,'wind':['wind_engine_node'],'current':['current_engine_node'],'wave':['wave_engine_node'],'aggregate':['force_aggregator_node']};started=time.monotonic();reports={}
reference_path=b/group/case/'comparison.json';reference_path.parent.mkdir(exist_ok=True)
subprocess.run(['rsync','-a',f'a4000:{remote}/{group}/{case}/comparison.json',str(reference_path)],check=True)
reference=json.loads(reference_path.read_text());assert reference['passed'] and set(reference['nodes'])==set(sum(partitions.values(),[]))
for name,nodes in partitions.items():
 while True:
  log=subprocess.check_output(['ssh','a4000',f'cat {remote}/reference-full-replay-r11-priority-v3.log'],text=True)
  done={line.split()[0]:int(line.split()[1]) for line in log.splitlines() if len(line.split())==2 and line.split()[1].isdigit()}
  if all(node in done for node in nodes):break
  if time.monotonic()-started>14400:raise TimeoutError((name,done))
  time.sleep(15)
 vectors=parts/'vectors'/name;vectors.mkdir(parents=True,exist_ok=True);manifest={'native_run':reference['native_run'],'modules':{},'scope':'Disjoint module partition of one canonical R11-E4 export; canonical manifest reconciliation required'}
 for node in nodes:
  file=canonical/(node+'.jsonl.gz')
  subprocess.run(['rsync','-a',f'a4000:{remote}/{group}/{case}-vectors-v3/{file.name}',str(file)],check=True)
  digest=hashlib.sha256(file.read_bytes()).hexdigest()
  with gzip.open(file,'rt') as stream:header=json.loads(stream.readline())
  assert header['module']==node and header['call_count']==done[node],node
  manifest['modules'][node]={'file':file.name,'calls':header['call_count'],'sha256':digest}
  link=vectors/file.name
  if not link.exists():link.symlink_to(file.resolve())
  del header
 (vectors/'manifest.json').write_text(json.dumps(manifest,indent=2))
 output=parts/'results'/name
 with (parts/(name+'.log')).open('w') as log:
  print('START',name,flush=True)
  process=subprocess.run(['/Users/marine/Code/Colav-Simulator/.venv/bin/python','tools/original_gnc/validate_native_vectors.py','--build',str(v),'--vectors',str(vectors),'--source','/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2','--output',str(output)],env=os.environ|{'PYTHONPATH':str(root)},stdout=log,stderr=subprocess.STDOUT)
 assert process.returncode==0,(name,process.returncode)
 report=json.loads((output/'comparison.json').read_text());assert report['passed'];reports[name]=report
 print('PASS',name,sum(d['calls_checked'] for d in report['modules'].values()),flush=True)
while subprocess.run(['ssh','a4000',f'test -f {remote}/{group}/{case}-vectors-v3/manifest.json']).returncode:
 if time.monotonic()-started>14400:raise TimeoutError('Canonical export manifest')
 time.sleep(15)
subprocess.run(['rsync','-a',f'a4000:{remote}/{group}/{case}-vectors-v3/manifest.json',str(canonical/'manifest.json')],check=True)
manifest=json.loads((canonical/'manifest.json').read_text());modules={};provenance=[];first=next(iter(reports.values()))
assert manifest['native_run']==reference['native_run']
for name,report in reports.items():
 assert report['native_build']==first['native_build']
 assert report['comparison_sources_sha256']==first['comparison_sources_sha256']
 for node,data in report['modules'].items():
  assert node not in modules,node
  identity=manifest['modules'][node]
  assert data['passed'] and data['internal_state_verified']
  assert data['calls_total']==data['calls_checked']==identity['calls']
  assert data['reference_vector_sha256']==identity['sha256']
  modules[node]=data
 path=parts/'results'/name/'comparison.json';provenance.append({'partition':name,'modules':list(report['modules']),'report_path':str(path),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert set(modules)==set(manifest['modules'])==set(reference['nodes'])
report={**first,'modules':modules,'scope':'Complete R11-E4 fixed-input per-module parity, assembled from disjoint independently executed module partitions; not an autonomous closed loop','partition_provenance':provenance,'canonical_vector_manifest_path':str(canonical/'manifest.json'),'canonical_vector_manifest_sha256':hashlib.sha256((canonical/'manifest.json').read_bytes()).hexdigest(),'reference_self_replay_sha256':hashlib.sha256(reference_path.read_bytes()).hexdigest()}
(parts/'final-candidate.json').write_text(json.dumps(report,indent=2));print('ALL TEN MODULES VERIFIED; candidate ready for final index installation',flush=True)
