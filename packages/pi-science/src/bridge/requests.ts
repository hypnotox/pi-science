export type MathematicalDomain =
  | "integer"
  | "nonnegative_integer"
  | "positive_integer"
  | "real"
  | "positive_real"
  | "nonnegative_real";
export type IndexDomain = { lower: string; upper: string };
export type VariableDeclaration = { domain: MathematicalDomain };
export type DomainConstraint = {
  name: string;
  target: string;
  relationship: string;
};
export type EquationRequest = {
  name: string;
  expression: string;
  domains?: Record<string, IndexDomain>;
  constraints?: DomainConstraint[];
};
export type FunctionDefinition = {
  name: string;
  parameters: string[];
  body: string;
};
export type PrimitiveCost = {
  name: string;
  parameters: string[];
  work: string;
};
export type Assumption = { name: string; relationship: string };
export type DirectedDefinition = { variable: string; expression: string };
export type ExactScenarioScalar = string | number;
export type OptimizationObjectiveInput =
  | { kind: "unit_work_v1" }
  | {
      kind: "weighted_operations_v1";
      weights: Record<
        | "additions"
        | "subtractions"
        | "multiplications"
        | "divisions"
        | "powers",
        ExactScenarioScalar
      >;
    };
export type AlgorithmicOptimizationFamily = "finite_polynomial_sum_v1";
export type OptimizationConfig = {
  max_suggestions?: number;
  objective?: OptimizationObjectiveInput;
  enabled_algorithmic_families?: AlgorithmicOptimizationFamily[];
};
export type IntervalBound = {
  lower: ExactScenarioScalar;
  upper: ExactScenarioScalar;
  lower_inclusive?: boolean;
  upper_inclusive?: boolean;
};
export type Scenario = {
  name: string;
  fixed?: Record<string, ExactScenarioScalar>;
  choices?: Record<string, ExactScenarioScalar[]>;
  definitions?: DirectedDefinition[];
  asymptotic?: string[];
  bounds?: Record<string, IntervalBound>;
};
export type EquationTarget = { kind: "equation"; name: string };
export type DerivedTarget = { kind: "derived"; query: string };
export type PropertyCheckRequest =
  | { kind: "sign" }
  | {
      kind: "valid_domain" | "singularities" | "monotonicity";
      variable: string;
    };
type QueryCore =
  | {
      name: string;
      kind: "equivalence";
      comparison: string;
      target?: DerivedTarget;
    }
  | { name: string; kind: "closed_form" }
  | {
      name: string;
      kind: "properties";
      checks: PropertyCheckRequest[];
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: "oo" | "-oo";
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      order: number;
      target?: DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: "oo" | "-oo";
      order: number;
      target?: DerivedTarget;
    };
export type ExpressionQueryRequest = QueryCore;
export type SystemQueryRequest =
  | {
      name: string;
      kind: "equivalence";
      comparison: string;
      target: EquationTarget | DerivedTarget;
    }
  | { name: string; kind: "closed_form"; target: EquationTarget }
  | {
      name: string;
      kind: "properties";
      checks: PropertyCheckRequest[];
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "limit";
      variable: string;
      point: "oo" | "-oo";
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: ExactScenarioScalar;
      direction: "left" | "right" | "both";
      order: number;
      target: EquationTarget | DerivedTarget;
    }
  | {
      name: string;
      kind: "asymptotic";
      variable: string;
      point: "oo" | "-oo";
      order: number;
      target: EquationTarget | DerivedTarget;
    };
export type QueryRequest = ExpressionQueryRequest | SystemQueryRequest;

type RequestMetadata<Query extends QueryRequest> = {
  variables?: Record<string, VariableDeclaration>;
  functions?: FunctionDefinition[];
  primitive_costs?: PrimitiveCost[];
  assumptions?: Assumption[];
  definitions?: DirectedDefinition[];
  scenarios?: Scenario[];
  queries?: Query[];
  optimization?: OptimizationConfig;
};
export type ExpressionAnalysisRequest =
  RequestMetadata<ExpressionQueryRequest> & {
    syntax: "sympy";
    expression: string;
    equations?: never;
    outputs?: ["expression"];
  };
export type SystemAnalysisRequest = RequestMetadata<SystemQueryRequest> & {
  syntax: "sympy";
  equations: EquationRequest[];
  expression?: never;
  outputs?: string[];
};
export type AnalysisRequest = ExpressionAnalysisRequest | SystemAnalysisRequest;
export type CandidateComputation =
  | { name: string; expression: string; equations?: never }
  | { name: string; equations: EquationRequest[]; expression?: never };
export type CandidateTarget = { kind: "expression" } | EquationTarget;
export type CandidateOutputMapping = {
  name: string;
  targets: Array<{ candidate: string; target: CandidateTarget }>;
};
export type CandidateComparisonRequest = Omit<
  RequestMetadata<QueryRequest>,
  "scenarios" | "queries" | "optimization"
> & {
  syntax: "sympy";
  operation: "compare_candidates";
  candidates: [CandidateComputation, CandidateComputation];
  outputs: CandidateOutputMapping[];
};
export type DominanceRange = {
  lower?: ExactScenarioScalar | "-oo";
  upper?: ExactScenarioScalar | "oo";
  lower_inclusive?: boolean;
  upper_inclusive?: boolean;
};
export type DominanceRequest = Omit<
  RequestMetadata<QueryRequest>,
  "scenarios" | "queries" | "optimization"
> & {
  syntax: "sympy";
  operation: "analyze_dominance";
  axis: string;
  fixed?: Record<string, ExactScenarioScalar>;
  range?: DominanceRange;
} & (
    | { expression: string; equations?: never }
    | { equations: EquationRequest[]; expression?: never }
  );
export type OptimizeRequest = Omit<
  RequestMetadata<QueryRequest>,
  "scenarios" | "queries" | "optimization"
> & {
  syntax: "sympy";
  operation: "optimize";
  max_plans?: number;
  objective?: OptimizationObjectiveInput;
  enabled_algorithmic_families?: AlgorithmicOptimizationFamily[];
} & (
    | { expression: string; equations?: never }
    | { equations: EquationRequest[]; expression?: never }
  );
export type FormulaRequest =
  | AnalysisRequest
  | CandidateComparisonRequest
  | DominanceRequest
  | OptimizeRequest;

export function formulaSources(request: FormulaRequest): string[] {
  const sources: string[] = [];
  if ("expression" in request && request.expression !== undefined)
    sources.push(request.expression);
  if ("equations" in request && request.equations !== undefined)
    for (const equation of request.equations) {
      sources.push(equation.expression);
      for (const domain of Object.values(equation.domains ?? {}))
        sources.push(domain.lower, domain.upper);
      for (const constraint of equation.constraints ?? [])
        sources.push(constraint.relationship);
    }
  for (const definition of request.functions ?? [])
    sources.push(definition.body);
  for (const cost of request.primitive_costs ?? []) sources.push(cost.work);
  for (const assumption of request.assumptions ?? [])
    sources.push(assumption.relationship);
  for (const definition of request.definitions ?? [])
    sources.push(definition.expression);
  for (const scenario of "scenarios" in request
    ? (request.scenarios ?? [])
    : [])
    for (const definition of scenario.definitions ?? [])
      sources.push(definition.expression);
  for (const candidate of "candidates" in request ? request.candidates : []) {
    if (candidate.expression !== undefined) sources.push(candidate.expression);
    for (const equation of candidate.equations ?? []) {
      sources.push(equation.expression);
      for (const domain of Object.values(equation.domains ?? {}))
        sources.push(domain.lower, domain.upper);
      for (const constraint of equation.constraints ?? [])
        sources.push(constraint.relationship);
    }
  }
  for (const query of "queries" in request ? (request.queries ?? []) : []) {
    if (query.kind === "equivalence") sources.push(query.comparison);
    if (query.kind === "limit" || query.kind === "asymptotic")
      sources.push(String(query.point));
  }
  return sources;
}
