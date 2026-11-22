import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

export function sourceFiles(path: string): string[] {
  return statSync(path).isDirectory()
    ? readdirSync(path, { withFileTypes: true }).flatMap((entry) =>
        entry.isDirectory() || entry.isFile() ? sourceFiles(join(path, entry.name)) : [],
      )
    : [path];
}

export function matchingSources(paths: readonly string[], pattern: RegExp): string[] {
  return paths.flatMap(sourceFiles).filter((file) => pattern.test(readFileSync(file, 'utf8')));
}
