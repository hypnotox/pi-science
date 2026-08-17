import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import type { TSchema } from "typebox";
import formulaSchemaJson from "./formula-schema.json" with { type: "json" };
import {
  invokeAdapter,
  type ExpressionAnalysisRequest,
  type SystemAnalysisRequest,
} from "./bridge.js";
import { provision, type Readiness } from "./provision.js";

const SHA = /^[0-9a-f]{40}$/;
const PRODUCT_SKILLS = fileURLToPath(new URL("../skills", import.meta.url));
export const formulaSchema = formulaSchemaJson as TSchema;
export type FormulaParameters =
  | Omit<ExpressionAnalysisRequest, "syntax">
  | Omit<SystemAnalysisRequest, "syntax">;

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
