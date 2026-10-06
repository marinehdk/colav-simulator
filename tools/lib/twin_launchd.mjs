// twin_launchd — probes × launchd twin-player coexistence protocol (spec #91 前置批).
//
// The twin player runs as the user LaunchAgent
// com.marine.colav-simulator.twin-player (deploy/twin/; manual start via
// deploy/twin/twinctl — not resident since 2026-10-06). Player-spawning
// probes need the machine solo: a running launchd player mid-probe double-connects
// the signaling page (SingleConnection steals the video). Protocol: DOWN before the
// probe spawns its own player (bootout = job removed),
// UP on exit (bootstrap + kickstart, back to serving the user's T viewport).
// Down/Up are no-ops when the service (or its plist) is absent — fresh machines and
// CI keep the pre-launchd probe semantics untouched.
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const LABEL = 'com.marine.colav-simulator.twin-player';
const PLIST = join(process.env.HOME, 'Library/LaunchAgents', `${LABEL}.plist`);
const SERVICE = `gui/${process.getuid()}/${LABEL}`;
let downedByUs = false;

function run(cmd, args) {
  try { return execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); }
  catch { return null; } // non-zero (not loaded / not found) is a normal state here
}

export function twinLaunchdLoaded() {
  if (!existsSync(PLIST)) return false;
  return run('launchctl', ['print', SERVICE]) !== null;
}

/** bootout the launchd twin-player so the probe owns the machine. Returns true when a loaded service was stopped. */
export function twinLaunchdPlayerDown(check) {
  if (!twinLaunchdLoaded()) return false;
  run('launchctl', ['bootout', SERVICE]);
  // wait until the sango binary is gone (KeepAlive cannot race: the job itself is removed)
  for (let waited = 0; waited < 15000; waited += 300) {
    const alive = (run('pgrep', ['-fl', 'MacOS/sango']) ?? '').trim();
    if (!alive) break;
    execFileSync('sleep', ['0.3'], { stdio: 'ignore' });
  }
  downedByUs = true;
  check?.('launchd twin-player downed for probe (single-instance)', true, SERVICE);
  return true;
}

/** restore the launchd twin-player after the probe (bootstrap + kickstart). */
export function twinLaunchdPlayerUp(check) {
  if (!downedByUs) return false;
  downedByUs = false;
  if (!existsSync(PLIST)) return false;
  const boot = run('launchctl', ['bootstrap', `gui/${process.getuid()}`, PLIST]);
  run('launchctl', ['kickstart', `-k`, SERVICE]);
  check?.('launchd twin-player restored after probe', true, boot === null ? 'kickstarted' : 'bootstrapped+kickstarted');
  return true;
}
