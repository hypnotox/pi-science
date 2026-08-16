import { describe, expect, it } from "vitest";
import { BridgeError, invokeAdapter } from "../src/bridge.js";
const node = process.execPath;
const script = (body: string) => ["-e", body];
describe("private formula bridge", () => {
  it("round trips a versioned success", async () =>
    expect(
      await invokeAdapter(
        node,
        script(
          'process.stdin.on("data",()=>process.stdout.write(JSON.stringify({version:1,result:{status:"success"}})))',
        ),
        { syntax: "sympy", expression: "x+1" },
      ),
    ).toEqual({ status: "success" }));
  it("rejects nonzero, malformed and incompatible output", async () => {
    await expect(
      invokeAdapter(node, script("process.exit(2)"), {
        syntax: "sympy",
        expression: "x",
      }),
    ).rejects.toMatchObject({ kind: "process" } satisfies Partial<BridgeError>);
    await expect(
      invokeAdapter(node, script('process.stdout.write("no")'), {
        syntax: "sympy",
        expression: "x",
      }),
    ).rejects.toMatchObject({
      kind: "malformed-output",
    } satisfies Partial<BridgeError>);
    await expect(
      invokeAdapter(
        node,
        script('process.stdout.write("{\\"version\\":2,\\"result\\":{}}")'),
        { syntax: "sympy", expression: "x" },
      ),
    ).rejects.toMatchObject({
      kind: "protocol",
    } satisfies Partial<BridgeError>);
  });
});
