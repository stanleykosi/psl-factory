#!/bin/bash
S=/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad
F=$S/fid.sh
$F SCR-01-desktop 1440
$F SCR-01-desktop-my-work 1440 "" "?queue=waiting_on_others"
$F SCR-01-desktop-empty 1440 psl_mock_persona=pm
$F SCR-01-desktop-filter 1440 "" "" filter
$F SCR-01-mobile 390
$F SCR-01-mobile-my-work 390 "" "?queue=waiting_on_others"
$F SCR-01-mobile-empty 390 psl_mock_persona=pm
$F SCR-01-mobile-filter 390 "" "" filter
$F SCR-01-mobile-lead 390
