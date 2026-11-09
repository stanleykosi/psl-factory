#!/bin/bash
# Reuse only the explicitly owned stopped cluster. No allocation or live providers.
set -euo pipefail
[[ -z ${PSL_LEDGER_PROVISIONAL:-} || ${PSL_LEDGER_PROVISIONAL:-} == 0 ]]
cd "$(dirname "$0")/.."
ROOT=$PWD;MAIN=/workspace/scratch/6bb434063736/psl-factory
PY=$MAIN/.venv313/bin/python;PG=$MAIN/.runtime/browser-change/postgres/bin
DATA=/tmp/psl-sourceunit777b-owned/data
[[ ${RUN795_RUNTIME_CLEARANCE:-} == coordinator-cleared-impact795 ]]
[[ -n ${RUN795_EXPECTED_HEAD:-} && $(git rev-parse HEAD) == "$RUN795_EXPECTED_HEAD" ]]
[[ $(git -C "$MAIN" rev-parse HEAD) == $RUN795_PREDECESSOR ]]
[[ -z $(git -C "$MAIN" status --porcelain) ]]
[[ -n ${RUN795_MANIFEST_SHA:-} && $(sha256sum docs/design/impact795-selection.json | cut -d' ' -f1) == "$RUN795_MANIFEST_SHA" ]]
[[ $(sha256sum scripts/source_units777_snapshot.py | cut -d' ' -f1) == 31f0d3b370cfb696b02edb1d5919346ed186ba1b3b8bd0714647a673f8d2aaa5 ]]
[[ -n ${PSL_EVIDENCE_DIR:-} && $PSL_EVIDENCE_DIR == /workspace/scratch/6bb434063736/impact795-native/* && ! -e $PSL_EVIDENCE_DIR ]]
# Final accepted comparison impact794 baselines and predecessor are mandatory; pending pins fail closed.
"$PY" scripts/impact795_inputs.py
E=$PSL_EVIDENCE_DIR
[[ ! -e "$DATA/postmaster.pid" ]]
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=$ROOT DJANGO_SETTINGS_MODULE=config.settings
export PGHOST=127.0.0.1 PGPORT=55777 PGUSER=psl PGDATABASE=psl_sourceunit777
export PSL_782_SOURCE=$ROOT PSL_782_PREDECESSOR=$MAIN
"$PY" scripts/impact795_harness.py preflight --expected-head "$RUN795_EXPECTED_HEAD" --predecessor "$RUN795_PREDECESSOR"
"$PG/pg_controldata" "$DATA" | grep -q 'Database system identifier:.*7705450556148731993'
"$PG/pg_controldata" "$DATA" | grep -q 'Database cluster state:.*shut down'
mkdir -p "$E"
# Frozen inputs reject all untracked execution files.
"$PY" - <<'PY'
import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd();e=Path(os.environ['PSL_EVIDENCE_DIR'])
allowed=set()
untracked=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines())
if not untracked<=allowed:raise RuntimeError('Unexpected untracked execution input: '+str(untracked-allowed))
v=json.loads((root/'docs/design/impact795-selection.json').read_text())['source_pins']
for p,h in v.items():
 if p in allowed or hashlib.sha256((root/p).read_bytes()).hexdigest()!=h:raise RuntimeError('Source pin differs: '+p)
(e/'frozen-inputs.json').write_text(json.dumps({'head':os.environ['RUN795_EXPECTED_HEAD'],'files':v,'excluded_untracked':sorted(untracked)},indent=2)+'\n')
for label,path in [('candidate',root),('predecessor',Path(os.environ['PSL_782_PREDECESSOR']))]:
 (e/(label+'-index-before.txt')).write_bytes(subprocess.check_output(['git','-C',str(path),'ls-files','--stage']))
PY
started=0;owned_pid=;guard_pid=;child_pid=;run_pid=$$
resources(){ printf '%s pgdata=%s overlay=%s tmp=%s\n' "$(date -u +%FT%TZ)" "$(du -sb "$DATA" | cut -f1)" "$(df --output=avail -B1 "$ROOT" | tail -1)" "$(df --output=avail -B1 /tmp | tail -1)"; }
# Pure threshold check; measurements are freshly obtained synchronously at stop.
final_resource_check(){
 local sz=$1 wf=$2 tf=$3
 [[ $sz =~ ^[0-9]+$ && $wf =~ ^[0-9]+$ && $tf =~ ^[0-9]+$ ]] || return 96
 (( sz<=183500800 && wf>=234881024 && tf>=440401920 )) || return 96
}
cleanup(){
 rc=$?
 # Once cleanup owns reaping, repeated signals must not interrupt it.
 trap '' TERM INT
 trap - EXIT
 set +e
 : > "$E/clean-stop-active"
 if [[ -n "$child_pid" ]];then
  printf "terminate_pid=%s\n" "$child_pid" >> "$E/child-reap.log"
  kill -TERM "$child_pid" 2>/dev/null
  wait "$child_pid" 2>/dev/null;child_rc=$?
  printf "reaped_pid=%s exit=%s\n" "$child_pid" "$child_rc" >> "$E/child-reap.log"
  child_pid=
 fi
 groups_clear=1
 "$PY" scripts/native_stage_supervisor782.py --verify "$E/groups" > "$E/groups-final-verification.log" 2>&1 || groups_clear=0
 if [[ $groups_clear != 1 ]];then echo 'Owned stage group unresolved; PG stop held' > "$E/group-HOLD.txt";rc=97;fi
 if [[ $started == 1 && $groups_clear == 1 ]];then
  if [[ -f "$DATA/postmaster.pid" && $(sed -n '1p' "$DATA/postmaster.pid") == "$owned_pid" && $(sed -n '2p' "$DATA/postmaster.pid") == "$DATA" ]];then
   "$PG/pg_ctl" -D "$DATA" -m fast -w stop > "$E/stop.log" 2>&1 || rc=90
  else echo 'Owned PID/path mismatch; no stop attempted' > "$E/stop-HOLD.txt";rc=91;fi
 fi
 [[ ! -e "$DATA/postmaster.pid" ]] || rc=92
 "$PG/pg_controldata" "$DATA" > "$E/stopped-control.txt" 2>&1
 "$PG/pg_ctl" -D "$DATA" status > "$E/stopped-status.log" 2>&1
 resources >> "$E/resource-watch.log"
 final_size=$(du -sb "$DATA" | cut -f1)
 final_overlay=$(df --output=avail -B1 "$ROOT" | tail -1 | tr -d '[:space:]')
 final_tmp=$(df --output=avail -B1 /tmp | tail -1 | tr -d '[:space:]')
 if ! final_resource_check "$final_size" "$final_overlay" "$final_tmp";then
  echo 'Final synchronous175MiB cap or224MiB overlay/420MiB tmp floor failed' > "$E/resource-HOLD.txt";rc=96
 fi
 if [[ -n "$guard_pid" ]];then kill "$guard_pid" 2>/dev/null;wait "$guard_pid" 2>/dev/null;fi
 [[ ! -f "$E/resource-HOLD.txt" ]] || rc=96
 "$PY" - <<'PY'
import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd();e=Path(os.environ['PSL_EVIDENCE_DIR']);v=json.loads((e/'frozen-inputs.json').read_text())
if subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=v['head']:raise RuntimeError('Source head changed during proof')
for p,h in v['files'].items():
 if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h:raise RuntimeError('Source changed during proof: '+p)
for label,path in [('candidate',root),('predecessor',Path(os.environ['PSL_782_PREDECESSOR']))]:
 index=subprocess.check_output(['git','-C',str(path),'ls-files','--stage'])
 (e/(label+'-index-after.txt')).write_bytes(index)
 if index!=(e/(label+'-index-before.txt')).read_bytes():raise RuntimeError('Tracked index identity changed: '+label)
 for args in [['diff','--name-only'],['diff','--cached','--name-only']]:
  if subprocess.check_output(['git','-C',str(path),*args],text=True).strip():raise RuntimeError('Tracked source modified: '+label)
if subprocess.check_output(['git','-C',os.environ['PSL_782_PREDECESSOR'],'rev-parse','HEAD'],text=True).strip()!=os.environ['RUN795_PREDECESSOR']:raise RuntimeError('Accepted predecessor HEAD changed')
(e/'source-unchanged.txt').write_text('Exact frozen permitted input hashes and complete tracked index/blob identities unchanged.\n')
PY
 [[ $? == 0 ]] || rc=94
 date -u +%FT%TZ > "$E/finished-at.txt";printf '%s\n' "$rc" > "$E/exit.txt";exit "$rc"
}
trap cleanup EXIT
trap 'exit 93' TERM INT
resource_guard(){
 while true;do
  if ! sz=$(du -sb "$DATA" 2>>"$E/resource-measurement.log" | cut -f1);then
   if ! sz=$(du -sb "$DATA" 2>>"$E/resource-measurement.log" | cut -f1);then
    echo 'Size measurement failed twice' > "$E/resource-HOLD.txt";kill -TERM "$run_pid";return
   fi
  fi
  wf=$(df --output=avail -B1 "$ROOT" | tail -1);tf=$(df --output=avail -B1 /tmp | tail -1)
  printf '%s pgdata=%s overlay=%s tmp=%s\n' "$(date -u +%FT%TZ)" "$sz" "$wf" "$tf" >> "$E/resource-watch.log"
  if [[ -f "$E/clean-stop-active" ]];then
   if (( sz>183500800 || wf<234881024 || tf<440401920 ));then echo 'Through-stop cap/floor exceeded' > "$E/resource-HOLD.txt";fi
  elif (( sz>173015040 || wf<268435456 || tf<471859200 ));then
   echo '165MiB early-stop threshold or launch floor reached; retain normal-stop reserve' > "$E/resource-HOLD.txt"
   [[ -z "$child_pid" ]] || kill -TERM "$child_pid" 2>/dev/null || true
   kill -TERM "$run_pid";return
  fi
  sleep 1
 done
}
step(){
 local name=$1;shift
 local timeout=300
 case "$1" in
  harness) shift;set -- "$PY" scripts/impact795_harness.py "$@" --expected-head "$RUN795_EXPECTED_HEAD" --predecessor "$RUN795_PREDECESSOR" ;;
  equal) shift;set -- "$PY" scripts/native782_compare.py "$E/$1/before.json.gz" "$E/$2/before.json.gz" ;;
  compare_files) shift;set -- "$PY" scripts/native782_compare.py "$@" ;;
 esac
 if [[ $name == tests-* ]];then
  timeout=$("$PY" -c 'import json,sys;print(json.load(open("docs/design/impact795-selection.json"))["batches"][int(sys.argv[1])-1]["outer_timeout_seconds"])' "${name#tests-}")
 fi
 "$PY" scripts/native_stage_supervisor782.py --proof "$E/groups/$name" --timeout "$timeout" -- "$@" > "$E/$name.log" 2>&1 & child_pid=$!
 set +e;wait "$child_pid";local rc=$?;set -e
 printf "reaped_supervisor=%s exit=%s stage=%s\n" "$child_pid" "$rc" "$name" >> "$E/child-reap.log"
 child_pid=
 printf '%s\n' "$rc" > "$E/$name.exit";return "$rc"
}

start(){
 local rc=0 sz wf tf limit=152043520
 [[ -z "$owned_pid" ]] || limit=173015040
 sz=$(du -sb "$DATA" | cut -f1);wf=$(df --output=avail -B1 "$ROOT" | tail -1);tf=$(df --output=avail -B1 /tmp | tail -1)
 printf '%s synchronous-start pgdata=%s overlay=%s tmp=%s\n' "$(date -u +%FT%TZ)" "$sz" "$wf" "$tf" >> "$E/resource-watch.log"
 (( sz<=limit && wf>=268435456 && tf>=471859200 )) || { echo 'Synchronous startup budget check failed' > "$E/resource-HOLD.txt";return 96; }

 "$PG/pg_ctl" -D "$DATA" -l "$E/postgres.log" -o "-h127.0.0.1 -p55777 -c unix_socket_directories='' -c max_wal_size=24MB -c min_wal_size=2MB" -w start || rc=$?
 if [[ -f "$DATA/postmaster.pid" && $(sed -n '2p' "$DATA/postmaster.pid") == "$DATA" ]];then
  owned_pid=$(sed -n '1p' "$DATA/postmaster.pid");started=1
 fi
 [[ $rc == 0 ]] || return "$rc"
 [[ $started == 1 ]]
 [[ $(sed -n '2p' "$DATA/postmaster.pid") == "$DATA" ]]
 cp "$DATA/postmaster.pid" "$E/owned-postmaster.txt"
}
resource_guard & guard_pid=$!
start > "$E/start.log" 2>&1
step pre-seed harness snapshot --evidence "$E/pre-seed"
# Exact current baseline must be supplied by coordinator; no guessed alternate path.
[[ -n ${RUN795_BASELINE:-} && -n ${RUN795_BASELINE_SHA:-} && $(sha256sum "$RUN795_BASELINE" | cut -d' ' -f1) == "$RUN795_BASELINE_SHA" ]]
step baseline-compare compare_files "$RUN795_BASELINE" "$E/pre-seed/before.json.gz"
[[ -n ${RUN795_TEST_BASELINE:-} && -n ${RUN795_TEST_BASELINE_SHA:-} && $(sha256sum "$RUN795_TEST_BASELINE" | cut -d' ' -f1) == "$RUN795_TEST_BASELINE_SHA" ]]
step declared-test harness snapshot --target test_psl_sourceunit777 --evidence "$E/declared-test"
step test-baseline-compare compare_files "$RUN795_TEST_BASELINE" "$E/declared-test/before.json.gz"
step upgrade-test harness upgrade-test --target test_psl_sourceunit777 --evidence "$E/upgrade-test"
step primary-after-upgrade-test harness snapshot --evidence "$E/primary-after-upgrade-test"
step primary-upgrade-test-equal equal pre-seed primary-after-upgrade-test
step upgrade-primary harness upgrade-primary --evidence "$E/upgrade-primary"
step declared-primary harness snapshot --evidence "$E/declared-primary"
for batch in $(seq 1 8);do
 step "tests-$batch" harness tests --target test_psl_sourceunit777 --batch "$batch" --evidence "$E/tests-$batch"
 step "primary-$batch" harness snapshot --evidence "$E/primary-$batch"
 step "primary-equal-$batch" equal declared-primary "primary-$batch"
done

step after-tests harness snapshot --evidence "$E/after-tests"
step primary-preserved equal declared-primary after-tests
step test-final harness snapshot --target test_psl_sourceunit777 --evidence "$E/test-final"
"$PY" scripts/native_stage_supervisor782.py --verify "$E/groups" > "$E/groups-restart-verification.log"
"$PG/pg_ctl" -D "$DATA" -m fast -w stop > "$E/restart-stop.log" 2>&1;started=0
[[ ! -e "$DATA/postmaster.pid" ]]
start > "$E/restart-start.log" 2>&1
step after-restart harness snapshot --evidence "$E/after-restart"
step restart-equality equal after-tests after-restart

step test-restart harness snapshot --target test_psl_sourceunit777 --evidence "$E/test-restart"
step test-restart-equality equal test-final test-restart
