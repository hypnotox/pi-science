import { spawn } from "node:child_process";

export const TERMINATION_GRACE_MS = 250;

export function spawnIsolated(
  command: string,
  args: string[],
  options: Parameters<typeof spawn>[2],
) {
  return spawn(command, args, {
    ...options,
    detached: process.platform !== "win32",
  });
}

export function terminateTree(child: ReturnType<typeof spawn>): void {
  if (child.pid === undefined) return;
  const kill = (signal: NodeJS.Signals) => {
    try {
      if (process.platform === "win32") child.kill(signal);
      else process.kill(-child.pid!, signal);
    } catch {
      // The child may have already exited between cleanup and signalling.
    }
  };
  kill("SIGTERM");
  setTimeout(() => kill("SIGKILL"), TERMINATION_GRACE_MS).unref();
}
