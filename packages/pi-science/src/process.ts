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
  if (process.platform === "win32") {
    try {
      const taskkill = spawn(
        "taskkill",
        ["/PID", String(child.pid), "/T", "/F"],
        {
          stdio: "ignore",
          windowsHide: true,
        },
      );
      taskkill.on("error", () => {
        // The process may have already exited before taskkill starts.
      });
    } catch {
      // The child may have already exited between cleanup and signalling.
    }
    return;
  }
  const kill = (signal: NodeJS.Signals) => {
    try {
      process.kill(-child.pid!, signal);
    } catch {
      // The child may have already exited between cleanup and signalling.
    }
  };
  kill("SIGTERM");
  setTimeout(() => kill("SIGKILL"), TERMINATION_GRACE_MS).unref();
}
