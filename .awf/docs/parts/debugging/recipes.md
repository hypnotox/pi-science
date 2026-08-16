### Managed documentation is stale

1. Edit the owning source under `.awf/`, not the generated file.
2. Run `./awf render`.
3. Review the source, rendered output, and `.awf/awf.lock` together.
4. Run `./awf check`.

### A generated file was edited directly

Restore the generated file or move the intended change to the `awf:edit` source named in its marker, then render and check again.