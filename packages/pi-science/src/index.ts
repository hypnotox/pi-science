import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type, type Static } from "typebox";
import { invokeAdapter, MAX_FORMULA_BYTES } from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

const SHA = /^[0-9a-f]{40}$/;
const PRODUCT_SKILLS = fileURLToPath(new URL("../skills", import.meta.url));
const identifier = Type.String({
  pattern: "^[A-Za-z][A-Za-z0-9_]*$",
  maxLength: 128,
});
const formula = Type.String({ maxLength: MAX_FORMULA_BYTES });
const safeInteger = Type.Integer({
  minimum: Number.MIN_SAFE_INTEGER,
  maximum: Number.MAX_SAFE_INTEGER,
});
const domain = Type.Union([
  Type.Literal("integer"),
  Type.Literal("nonnegative_integer"),
  Type.Literal("positive_integer"),
  Type.Literal("real"),
  Type.Literal("positive_real"),
]);
const indexDomain = Type.Object(
  { lower: formula, upper: formula },
  { additionalProperties: false },
);
const directedDefinition = Type.Object(
  { variable: identifier, expression: formula },
  { additionalProperties: false },
);
const metadata = {
  variables: Type.Optional(
    Type.Record(
      identifier,
      Type.Object({ domain }, { additionalProperties: false }),
      { maxProperties: 256 },
    ),
  ),
  functions: Type.Optional(
    Type.Array(
      Type.Object(
        {
          name: identifier,
          parameters: Type.Array(identifier, { maxItems: 32 }),
          body: formula,
        },
        { additionalProperties: false },
      ),
      { maxItems: 128 },
    ),
  ),
  primitive_costs: Type.Optional(
    Type.Array(
      Type.Object(
        {
          name: identifier,
          parameters: Type.Array(identifier, { maxItems: 32 }),
          work: formula,
        },
        { additionalProperties: false },
      ),
      { maxItems: 128 },
    ),
  ),
  assumptions: Type.Optional(
    Type.Array(
      Type.Object(
        { name: identifier, relationship: formula },
        { additionalProperties: false },
      ),
      { maxItems: 128 },
    ),
  ),
  definitions: Type.Optional(Type.Array(directedDefinition, { maxItems: 128 })),
  scenarios: Type.Optional(
    Type.Array(
      Type.Object(
        {
          name: identifier,
          fixed: Type.Optional(
            Type.Record(identifier, safeInteger, { maxProperties: 64 }),
          ),
          choices: Type.Optional(
            Type.Record(
              identifier,
              Type.Array(safeInteger, { minItems: 1, maxItems: 32 }),
              { maxProperties: 64 },
            ),
          ),
          definitions: Type.Optional(
            Type.Array(directedDefinition, { maxItems: 64 }),
          ),
          asymptotic: Type.Optional(
            Type.Array(identifier, { maxItems: 64, uniqueItems: true }),
          ),
          bounds: Type.Optional(
            Type.Record(
              identifier,
              Type.Object(
                { lower: safeInteger, upper: safeInteger },
                { additionalProperties: false },
              ),
              { maxProperties: 64 },
            ),
          ),
        },
        { additionalProperties: false },
      ),
      { maxItems: 64 },
    ),
  ),
};
const equation = Type.Object(
  {
    name: identifier,
    expression: formula,
    domains: Type.Optional(
      Type.Record(identifier, indexDomain, { maxProperties: 32 }),
    ),
  },
  { additionalProperties: false },
);
export const formulaSchema = Type.Union([
  Type.Object(
    {
      expression: Type.String({
        description: "Restricted SymPy arithmetic expression",
        maxLength: MAX_FORMULA_BYTES,
      }),
      ...metadata,
    },
    { additionalProperties: false },
  ),
  Type.Object(
    {
      equations: Type.Array(equation, { minItems: 1, maxItems: 128 }),
      ...metadata,
    },
    { additionalProperties: false },
  ),
]);
export type FormulaParameters = Static<typeof formulaSchema>;

export type PinnedSource = { revision: string; repo: string };

export function resolvePinnedSource(
  repositoryRoot: string,
  git = "git",
): PinnedSource | undefined {
  try {
    const revision = execFileSync(
      git,
      ["-C", repositoryRoot, "rev-parse", "--verify", "HEAD^{commit}"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    const repo = execFileSync(
      git,
      ["-C", repositoryRoot, "config", "--get", "remote.origin.url"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    return SHA.test(revision) && repo ? { revision, repo } : undefined;
  } catch {
    return undefined;
  }
}

export function resolvePinnedRevision(
  repositoryRoot: string,
  git = "git",
): string | undefined {
  return resolvePinnedSource(repositoryRoot, git)?.revision;
}

function toolResult(result: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    details: result,
  };
}

function report(context: ExtensionContext, text: string, ready: boolean): void {
  if (context.hasUI) context.ui.notify(text, ready ? "info" : "warning");
  else process.stderr.write(`pi-science: ${text}\n`);
}

export async function start(
  pi: ExtensionAPI,
  readiness: Promise<Readiness>,
): Promise<void> {
  const state = await readiness;
  pi.registerCommand("pi-science-doctor", {
    description:
      "Show formula analysis readiness and reload/restart recovery guidance",
    handler: async (_args, context) => {
      const text = state.ready
        ? "Formula analysis is ready."
        : `${state.diagnosis} Reload or restart Pi to retry provisioning.`;
      report(context, text, state.ready);
    },
  });

  if (!state.ready) {
    let warned = false;
    pi.on("session_start", async (_event, context) => {
      if (warned) return;
      warned = true;
      report(
        context,
        `${state.diagnosis} Reload or restart Pi to retry provisioning.`,
        false,
      );
    });
    return;
  }

  pi.on("resources_discover", () => ({ skillPaths: [PRODUCT_SKILLS] }));

  pi.registerTool({
    name: "analyze_formula",
    label: "Analyze formula",
    description:
      "Analyze one restricted SymPy expression or named equation system without evaluating it",
    parameters: formulaSchema,
    async execute(_id, params: FormulaParameters, signal) {
      const result = await invokeAdapter(
        state.command,
        state.args,
        { syntax: "sympy", ...params },
        10_000,
        signal,
      );
      return toolResult(result);
    },
  });
}

export default async function extension(pi: ExtensionAPI): Promise<void> {
  const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
  const adapter = fileURLToPath(
    new URL("../bridge/formula_adapter.py", import.meta.url),
  );
  const source = resolvePinnedSource(repositoryRoot);
  await start(
    pi,
    provision({
      revision: source?.revision ?? "",
      repo: source?.repo ?? "",
      adapter,
      checkoutRoot: repositoryRoot,
    }),
  );
}
