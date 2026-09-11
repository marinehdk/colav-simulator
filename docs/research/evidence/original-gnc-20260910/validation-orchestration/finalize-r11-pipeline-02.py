from pathlib import Path
import json,hashlib,os,signal,subprocess,time
root=Path.cwd();b=root/'build';v=b/'original_gnc-glibc-v8';results=v/'full-vector-validation-01';candidate=b/'original-r11-pipeline-v1/final-candidate.json';started=time.monotonic();stopped=False
while not candidate.exists() or not (results/'R08-E4/comparison.json').exists():
 if not stopped and (results/'R08-E4/comparison.json').exists():
  assert json.loads((results/'R08-E4/comparison.json').read_text())['passed']
  cmd=subprocess.run(['ps','-p','61850','-o','command='],capture_output=True,text=True)
  if cmd.returncode==0:
   assert 'build/coordinate-final-r1.py' in cmd.stdout
   os.kill(61850,signal.SIGTERM);os.kill(61850,signal.SIGCONT)
  stopped=True;print('All other 27 cases complete; retired the paused whole-case launcher',flush=True)
 if time.monotonic()-started>18000:raise TimeoutError('R11 pipeline finalization')
 time.sleep(15)
if not stopped:
 cmd=subprocess.run(['ps','-p','61850','-o','command='],capture_output=True,text=True)
 if cmd.returncode==0:
  assert 'build/coordinate-final-r1.py' in cmd.stdout
  os.kill(61850,signal.SIGTERM);os.kill(61850,signal.SIGCONT)
report=json.loads(candidate.read_text());assert report['passed'] and len(report['modules'])==10
manifest=Path(report['canonical_vector_manifest_path']);assert hashlib.sha256(manifest.read_bytes()).hexdigest()==report['canonical_vector_manifest_sha256']
for part in report['partition_provenance']:
 p=Path(part['report_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==part['report_sha256'];assert json.loads(p.read_text())['passed']
assert hashlib.sha256(Path(report['aggregation_tool_path']).read_bytes()).hexdigest()==report['aggregation_tool_sha256']
report['finalization_tool_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
output=results/'R11-E4';assert not output.exists();output.mkdir();(output/'comparison.json').write_text(json.dumps(report,indent=2))
expected={x['case_id'] for x in json.loads((root/'tests/fixtures/original_gnc/cases/manifest.json').read_text())['cases'] if x['case_id'].endswith(('-E0','-E4'))}
reports={p.parent.name:json.loads(p.read_text()) for p in results.glob('*/comparison.json')};assert set(reports)==expected and len(reports)==28
assert all(d['passed'] for d in reports.values())
assert len({d['native_build']['library_sha256'] for d in reports.values()})==1
summary={'schema':'original-gnc.final-validation-summary.v1','producer':'finalize-r11-pipeline.py','complete':True,'passed':all(d['passed'] for d in reports.values()),'count':len(reports),'errors':{},'r11_partitioned':True,'native_library_sha256':report['native_build']['library_sha256']}
(b/'original-final-r1-coordinator-result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
