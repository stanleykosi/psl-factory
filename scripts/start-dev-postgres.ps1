$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path $PSScriptRoot -Parent
$studioRuntime = Join-Path $studioRoot '.runtime'
$studioBin = Join-Path $studioRuntime 'pgsql/bin'
$studioData = Join-Path $studioRuntime 'pgdata'
New-Item -ItemType Directory -Force $studioRuntime | Out-Null
if (!(Test-Path (Join-Path $studioBin 'pg_ctl.exe'))) {
    throw 'Download the official portable PostgreSQL archive and extract pgsql/bin, pgsql/lib and pgsql/share under .runtime first. See docs/runbooks/development.md.'
}
if (!(Test-Path (Join-Path $studioData 'PG_VERSION'))) {
    & (Join-Path $studioBin 'initdb.exe') -D $studioData -U psl -A trust --encoding=UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
}
& (Join-Path $studioBin 'pg_ctl.exe') -D $studioData -l (Join-Path $studioRuntime 'postgres.log') -o '-h 127.0.0.1 -p 55432' start
if ($LASTEXITCODE -ne 0) { throw 'Database start failed; check whether it is already running and inspect the log' }
& (Join-Path $studioBin 'createdb.exe') -h 127.0.0.1 -p 55432 -U psl psl
if ($LASTEXITCODE -ne 0) { Write-Warning 'Database creation failed or database already exists; inspect before proceeding.' }
