"""Linux owned-session stage supervisor. No database access or system-wide signals."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def identity(pid):
    try:
        raw=Path('/proc')/str(pid)/'stat'
        fields=raw.read_text().rsplit(')',1)[1].split()
        return {'pid':pid,'state':fields[0],'ppid':int(fields[1]),'pgid':int(fields[2]),
                'sid':int(fields[3]),'started':int(fields[19])}
    except (FileNotFoundError,ProcessLookupError):
        return None


def members(owner):
    result=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        item=identity(int(path.name))
        if item and item['sid']==owner['sid']:
            if item['pgid']!=owner['pgid'] or item['started']<owner['started']:
                raise RuntimeError('Unexpected session membership; refuse broad signalling')
            if item['pid']==owner['pid'] and item['started']!=owner['started']:
                raise RuntimeError('Stage leader identity changed; refuse signalling')
            result.append(item)
    return result


def escaped(owner):
    # The supervisor creates no unrelated children. Subreaper adoption plus PPID
    # traversal detects a helper that unexpectedly leaves the owned session.
    table={}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            item=identity(int(path.name))
            if item:table[item['pid']]=item
    tree={owner['pid']}
    tree.update(pid for pid,item in table.items() if item['ppid']==os.getpid())
    while True:
        grown=tree|{pid for pid,item in table.items() if item['ppid'] in tree}
        if grown==tree:break
        tree=grown
    return [table[pid] for pid in tree if pid in table and
            (table[pid]['sid']!=owner['sid'] or table[pid]['pgid']!=owner['pgid'])]


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def run(command,timeout,proof):
    if not command or not 0<timeout<=600 or proof.exists():
        raise ValueError('Bounded command and unique proof directory required')
    proof.mkdir(parents=True)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:
        raise OSError(ctypes.get_errno(),'Stage subreaper unavailable')
    stopped=[]
    def request_stop(signum,frame):stopped.append(signum)
    previous={sig:signal.signal(sig,request_stop) for sig in (signal.SIGTERM,signal.SIGINT)}
    stage=None;owner=None;events=[];result={'group_empty':False}
    try:
        stage=subprocess.Popen(command,start_new_session=True)
        owner=identity(stage.pid)
        if not owner or owner['pgid']!=stage.pid or owner['sid']!=stage.pid or owner['pgid']==os.getpgrp():
            raise RuntimeError('Dedicated owned process session not established')
        write(proof/'owner.json',owner)
        start=time.monotonic();reason=None
        while stage.poll() is None:
            if escaped(owner):reason='escaped_descendant';break
            if stopped:reason='signal';break
            if time.monotonic()-start>=timeout:reason='timeout';break
            time.sleep(.05)
        rc=stage.poll()
        escape=escaped(owner)
        if escape:reason='escaped_descendant'
        remaining=members(owner)
        if remaining:
            if reason is None:reason='lingering_descendants'
            # Only the exact new session/group is eligible. Never signal caller or PG.
            os.killpg(owner['pgid'],signal.SIGTERM)
            events.append({'signal':'TERM','members':remaining})
            deadline=time.monotonic()+5;killed=False
            while remaining:
                while True:
                    try:pid,status=os.waitpid(-owner['pgid'],os.WNOHANG)
                    except ChildProcessError:break
                    if pid==0:break
                    events.append({'reaped_pid':pid,'exit':os.waitstatus_to_exitcode(status)})
                    if pid==stage.pid:stage.returncode=os.waitstatus_to_exitcode(status)
                remaining=members(owner)
                if not remaining:break
                if time.monotonic()>=deadline:
                    if killed:
                        raise RuntimeError('Owned group did not empty; database stop must HOLD')
                    os.killpg(owner['pgid'],signal.SIGKILL)
                    events.append({'signal':'KILL','members':remaining});killed=True;deadline=time.monotonic()+10
                time.sleep(.05)
        stage.wait()
        # Reap any adopted descendants that exited between the membership scan and wait.
        while True:
            try:pid,status=os.waitpid(-owner['pgid'],os.WNOHANG)
            except ChildProcessError:break
            if not pid:break
            events.append({'reaped_pid':pid,'exit':os.waitstatus_to_exitcode(status)})
        if members(owner):raise RuntimeError('Owned group survived; database stop must HOLD')
        # Never signal an escaped session. Give known adopted children a bounded
        # natural-exit/reap window; an unresolved escape makes PG shutdown HOLD.
        escape=escaped(owner);deadline=time.monotonic()+5
        while escape and time.monotonic()<deadline:
            for item in escape:
                try:pid,status=os.waitpid(item['pid'],os.WNOHANG)
                except ChildProcessError:continue
                if pid:events.append({'escaped_reaped_pid':pid,'exit':os.waitstatus_to_exitcode(status)})
            time.sleep(.05);escape=escaped(owner)
        if escape:
            result={'group_empty':False,'reason':'escaped_descendant','owner':owner,'escaped':escape,'events':events}
            return 125
        code=124 if reason=='timeout' else 143 if reason=='signal' else 125 if reason else stage.returncode
        result={'group_empty':True,'reason':reason,'stage_exit':stage.returncode,'supervisor_exit':code,
                'elapsed':time.monotonic()-start,'owner':owner,'events':events}
        return code
    finally:
        write(proof/'result.json',result)
        for sig,handler in previous.items():signal.signal(sig,handler)


def verify(directory):
    stages=sorted(path for path in directory.iterdir() if path.is_dir()) if directory.exists() else []
    for path in stages:
        result_path=path/'result.json'
        owner_path=path/'owner.json'
        if not result_path.exists() or not json.loads(result_path.read_text()).get('group_empty') or not owner_path.exists():
            raise RuntimeError('Unverified stage group; database stop must HOLD')
        if members(json.loads(owner_path.read_text())):
            raise RuntimeError('Owned stage group remains; database stop must HOLD')
    return len(stages)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--proof',type=Path)
    parser.add_argument('--timeout',type=float,default=300)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.verify:
        print('Verified empty owned stage groups:',verify(args.verify));return 0
    return run(args.command[1:] if args.command[:1]==['--'] else args.command,args.timeout,args.proof)


if __name__=='__main__':raise SystemExit(main())
