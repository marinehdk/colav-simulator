from pathlib import Path
import concurrent.futures,subprocess,json,time,hashlib,os,signal
root=Path.cwd();b=root/'build';v=b/'original_gnc-glibc-v8';parts=b/'original-r11-pipeline-v1';canonical=b/'reference-full-replay-stream-v3b/R11-E4-vectors-v3';remote='/home/marine.huang/colav-gnc-oracle/l45-20260824-v2/reference-full-replay-stream-v3b/R11-E4-vectors-v3'
subprocess.run(['rsync','-a',f'a4000:{remote}/manifest.json',str(canonical/'manifest.json')],check=True)
manifest=json.loads((canonical/'manifest.json').read_text());assert len(manifest['modules'])==10
jobs={'current':'current_engine_node','wave':'wave_engine_node','aggregate':'force_aggregator_node'}
def validate(item):
 name,node=item;identity=manifest['modules'][node];file=canonical/identity['file']
 subprocess.run(['rsync','-a',f'a4000:{remote}/{file.name}',str(file)],check=True)
 vectors=parts/'vectors'/name;vectors.mkdir(parents=True,exist_ok=True);link=vectors/file.name
 if not link.exists():link.symlink_to(file.resolve())
 (vectors/'manifest.json').write_text(json.dumps({'native_run':manifest['native_run'],'modules':{node:identity},'scope':'One disjoint module from the complete canonical R11-E4 export'},indent=2))
 output=parts/'results'/name;assert not output.exists(),output
 with (parts/(name+'.log')).open('w') as log:
  print('START',name,flush=True)
  result=subprocess.run(['/Users/marine/Code/Colav-Simulator/.venv/bin/python','tools/original_gnc/validate_native_vectors.py','--build',str(v),'--vectors',str(vectors),'--source','/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2','--output',str(output)],env=os.environ|{'PYTHONPATH':str(root)},stdout=log,stderr=subprocess.STDOUT)
 report=json.loads((output/'comparison.json').read_text());assert result.returncode==0 and report['passed'],name
 print('PASS',name,report['modules'][node]['calls_checked'],flush=True)
 return name
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for future in concurrent.futures.as_completed([pool.submit(validate,item) for item in jobs.items()]):future.result()
started=time.monotonic();wind=parts/'results/wind/comparison.json'
while not wind.exists():
 if time.monotonic()-started>7200:raise TimeoutError('Existing wind validation')
 time.sleep(15)
assert json.loads(wind.read_text())['passed']
cmd=subprocess.run(['ps','-p','66394','-o','command='],capture_output=True,text=True)
if cmd.returncode==0:
 assert 'build/pipeline-r11-native-validation.py' in cmd.stdout
 os.kill(66394,signal.SIGTERM);os.kill(66394,signal.SIGCONT)
reports={name:json.loads((parts/'results'/name/'comparison.json').read_text()) for name in ['core','wind',*jobs]};first=reports['core'];modules={};provenance=[]
reference_path=b/'reference-full-replay-stream-v3b/R11-E4/comparison.json';reference=json.loads(reference_path.read_text());assert reference['passed'] and reference['native_run']==manifest['native_run']
for name,report in reports.items():
 assert report['passed'] and report['native_build']==first['native_build']
 assert report['comparison_sources_sha256']==first['comparison_sources_sha256']
 for node,data in report['modules'].items():
  assert node not in modules
  assert data['passed'] and data['internal_state_verified']
  assert data['calls_total']==data['calls_checked']==manifest['modules'][node]['calls']
  assert data['reference_vector_sha256']==manifest['modules'][node]['sha256']
  modules[node]=data
 path=parts/'results'/name/'comparison.json';provenance.append({'partition':name,'modules':list(report['modules']),'report_path':str(path),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert set(modules)==set(manifest['modules'])==set(reference['nodes'])
report={**first,'modules':modules,'scope':'Complete R11-E4 fixed-input per-module parity, assembled from five disjoint independently executed partitions; not an autonomous closed loop','partition_provenance':provenance,'canonical_vector_manifest_path':str(canonical/'manifest.json'),'canonical_vector_manifest_sha256':hashlib.sha256((canonical/'manifest.json').read_bytes()).hexdigest(),'reference_self_replay_sha256':hashlib.sha256(reference_path.read_bytes()).hexdigest(),'aggregation_tool_path':str(Path(__file__).resolve()),'aggregation_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output=parts/'final-candidate.json';assert not output.exists();output.write_text(json.dumps(report,indent=2));print('ALL TEN MODULES VERIFIED',flush=True)
