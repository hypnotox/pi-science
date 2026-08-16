Current repository flow is limited to `./awf render` generating managed documentation and workflow artifacts from `.awf/`, with `./awf check` verifying the result.

The intended analysis flow is:

```text
LaTeX request -----+
                   +--> safe parsers --> normalized mathematical model
SymPy request -----+                           |
                                               +--> symbolic algebra
                                               +--> cost analysis
                                               +--> dependency and rewrite analysis
                                                          |
                                                          v
                                                  scenario evaluator
                                                          |
                                                          v
                                                structured analysis report
```

Both frontends share the same model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation.
