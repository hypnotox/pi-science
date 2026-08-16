import { describe, expect, it, vi } from "vitest";
import { start } from "../src/index.js";
const pi = () => ({
  registerTool: vi.fn(),
  registerCommand: vi.fn(),
  on: vi.fn(),
});
describe("readiness gate", () => {
  it("registers analysis only when ready", async () => {
    const host = pi();
    await start(host, Promise.resolve({ ready: true, command: "x", args: [] }));
    expect(host.registerTool).toHaveBeenCalledOnce();
    expect(host.registerCommand).toHaveBeenCalledOnce();
  });
  it("retains doctor while disabled", async () => {
    const host = pi();
    await start(
      host,
      Promise.resolve({ ready: false, diagnosis: "install uv" }),
    );
    expect(host.registerTool).not.toHaveBeenCalled();
    expect(host.registerCommand).toHaveBeenCalledOnce();
  });
});
