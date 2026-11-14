#!/bin/bash
# usage: runall.sh <outroot> [board-filter-regex]
D=$(cd "$(dirname "$0")" && pwd); R=$1; FILTER=${2:-.}
while read b p u; do
  bb=${b#_}
  for v in desktop:1440 mobile:390; do
    name=SCR-02-${v%%:*}$bb
    [[ $name =~ $FILTER ]] && $D/fid.sh $name ${v##*:} $p $u $R
  done
done <<LIST
_ finance_lead /work/W-1701
-ready pm /work/W-1702
-processing pm /work/W-1703
-waiting pm /work/W-1704
-verified finance_lead /work/W-1705
-history finance_lead /work/W-1705/history
-issue finance_lead /work/W-1706
-cancelled finance_lead /work/W-1707
-owner-needed pm /work/W-1708
-setup-needed pm /work/W-1709
-permission finance_lead /work/W-1099
-effect-uncertain finance_lead /work/W-1710
-awaiting-reconciliation finance_lead /work/W-1711
LIST
