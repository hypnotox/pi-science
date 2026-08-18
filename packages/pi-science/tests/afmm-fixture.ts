import type { AnalysisRequest } from "../src/bridge.js";

export const afmmRequest: AnalysisRequest = {
  syntax: "sympy",
  equations: [
    {
      name: "displacement",
      expression: "Eq(D[i, d], x[i, d] - center[box[i], d])",
      domains: {
        i: { lower: "0", upper: "N - 1" },
        d: { lower: "0", upper: "dim - 1" },
      },
    },
    {
      name: "multipoles",
      expression:
        "Eq(M[b, k], Sum(K(p) * basis(D[i, 0], k), (i, 0, n[b] - 1)))",
      domains: {
        b: { lower: "0", upper: "B - 1" },
        k: { lower: "0", upper: "p - 1" },
      },
    },
    {
      name: "translation",
      expression:
        "Eq(L[b, k], Sum(translate(M[neighbor[b, c], k]) + M[neighbor[b, c], k], (c, 0, C - 1)))",
      domains: {
        b: { lower: "0", upper: "B - 1" },
        k: { lower: "0", upper: "p - 1" },
      },
    },
  ],
  variables: {
    N: { domain: "positive_integer" },
    dim: { domain: "positive_integer" },
    B: { domain: "positive_integer" },
    p: { domain: "positive_integer" },
    C: { domain: "positive_integer" },
    x: { domain: "real" },
    center: { domain: "real" },
    box: { domain: "nonnegative_integer" },
    n: { domain: "nonnegative_integer" },
    neighbor: { domain: "nonnegative_integer" },
  },
  functions: [{ name: "K", parameters: ["z"], body: "z * z" }],
  primitive_costs: [
    { name: "basis", parameters: ["value", "k"], work: "k + 1" },
  ],
  assumptions: [
    {
      name: "population",
      relationship: "Sum(n[b], (b, 0, B - 1)) == N",
    },
  ],
  definitions: [],
  scenarios: [{ name: "fixed_order", fixed: { p: 3 }, asymptotic: ["N"] }],
};

const { syntax: _syntax, ...parameters } = afmmRequest;
export const afmmParameters = parameters;

export const afmmTotalWork =
  "B*p*(2*C - 1) + N*dim + N*p*(p + 1)/2 + p*Sum(2*n[b], (b, 0, B - 1)) + p*Sum(Max(0, n[b] - 1), (b, 0, B - 1)) + Sum(C_translate(M[neighbor[b, c], k]), (c, 0, C - 1), (k, 0, p - 1), (b, 0, B - 1))";

export const afmmTailParameters = {
  expression: "Sum((k + 1) * q**k, (k, p, oo))",
  variables: {
    p: { domain: "nonnegative_integer" as const },
    q: { domain: "real" as const },
  },
  assumptions: [
    { name: "q_nonnegative", relationship: "0 <= q" },
    { name: "tail_ratio", relationship: "q < 1" },
  ],
  queries: [{ name: "afmm_tail", kind: "closed_form" as const }],
};
