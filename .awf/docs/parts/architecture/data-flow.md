The implemented formula-analysis flow is:

```text
typed analysis request
    |
    v
strict Pydantic contract
    |
    v
deterministic resource budget
    |
    v
allowlisted syntax parser --> typed expression tree --> operation analyzer
                                      |
                                      v
                                SymPy adapter
                                      |
                                      v
                         typed analysis success or failure
```

Submitted text is inspected as Python expression syntax but never evaluated. Input size, tree size, nesting, and integer literals are bounded before conversion. Only validated expression-tree nodes reach SymPy, and powers are constructed without eager evaluation. Parsing and analysis do not depend on the SymPy representation, and transport semantics remain outside the formula-analysis package.

The broader multi-frontend analysis flow remains defined by [Vision](vision.md) and [Analysis Model](analysis-model.md).
