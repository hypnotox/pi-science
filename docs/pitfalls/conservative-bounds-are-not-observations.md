# Conservative bounds are not observations

Recursive preflight arithmetic often computes a safe upper bound rather than an exact value: coefficient bit lengths have arithmetic slack, expanded terms may combine, and rational degrees may cancel across a numerator and denominator. Keep the conservative refusal, but render a value as observed only when the bounded traversal proves that metric exact; otherwise omit the observation and retain the reason and recovery guidance.
