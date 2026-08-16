The implemented evaluation flow is:

```text
typed request
    |
    v
strict Pydantic contract
    |
    v
allowlisted syntax parser --> typed expression tree --> operation analyzer
                                      |
                                      v
                                SymPy adapter
                                      |
                                      v
                         typed success or failure
```

Submitted text is inspected as Python expression syntax but never evaluated. Only validated expression-tree nodes reach SymPy. Parsing and analysis do not depend on the SymPy representation, and transport semantics remain outside the evaluator.

The broader multi-frontend analysis flow remains defined by [Vision](vision.md) and [Analysis Model](analysis-model.md).
