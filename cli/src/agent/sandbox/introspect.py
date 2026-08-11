"""Dataset loading, PTC tool injection, and namespace introspection helpers."""


class SandboxIntrospectMixin:
    """Owns dataset/tool injection and human-readable namespace descriptions."""

    def load_datasets(self) -> dict:
        """Load configured datasets into the namespace. Returns dict of loaded names."""
        loaded = {}
        loaders = {
            "crispr": "load_crispr",
            "prism": "load_prism",
            "l1000": "load_l1000",
            "proteomics": "load_proteomics",
            "mutations": "load_mutations",
            "model_metadata": "load_model_metadata",
        }
        for name, func_name in loaders.items():
            try:
                from data import loaders as data_loaders
                loader_fn = getattr(data_loaders, func_name, None)
                if loader_fn:
                    df = loader_fn()
                    self._namespace[name] = df
                    loaded[name] = f"DataFrame {df.shape[0]} rows x {df.shape[1]} cols"
            except (FileNotFoundError, Exception):
                pass  # Dataset not configured — skip silently
        return loaded

    def inject_tools(self, tools_namespace) -> None:
        """Bind a ``tools`` namespace of domain-tool callables (PTC mode).

        Enables Programmatic Tool Calling: the model invokes domain tools as
        ``tools.<category>.<name>(...)`` inside executed code rather than via
        individual tool-call schemas. See :mod:`agent.ptc_tools`.
        """
        self._namespace["tools"] = tools_namespace

    def get_variable(self, name: str, default=None):
        """Retrieve a variable from the sandbox namespace."""
        return self._namespace.get(name, default)

    def inject_prior_results(self, prior_results: dict):
        """Add prior step results into namespace as step_1, step_2, etc."""
        if not prior_results:
            return
        for step_id, result in prior_results.items():
            self._namespace[f"step_{step_id}"] = result

    def describe_namespace(self) -> str:
        """Generate a text description of available data and libraries for the LLM."""
        lines = ["## Available in your namespace\n"]

        # Libraries
        libs = []
        lib_names = ["pd", "np", "plt", "sns", "scipy_stats", "scipy", "sklearn",
                     "json", "re", "math", "collections", "itertools", "datetime",
                     "ro"]
        for name in lib_names:
            if name in self._namespace:
                libs.append(name)
        lines.append(f"**Libraries**: {', '.join(libs)}")
        lines.append(f"**OUTPUT_DIR**: Path('{self.output_dir}') — save plots/CSVs here\n")

        # PTC: domain tools injected as callables (see agent.ptc_tools)
        tools_ns = self._namespace.get("tools")
        if tools_ns is not None:
            cats = getattr(tools_ns, "categories", None)
            total = sum(cats.values()) if isinstance(cats, dict) else 0
            lines.append(
                f"**tools**: {total} domain tools as callables — "
                "`tools.<category>.<name>(**kwargs) -> dict`. "
                "Use `tools.search('query')` / `tools.list('<category>')` to discover.\n"
            )

        # Datasets
        dataset_names = ["crispr", "prism", "l1000", "proteomics", "mutations", "model_metadata"]
        for name in dataset_names:
            if name in self._namespace:
                df = self._namespace[name]
                cols_preview = list(df.columns[:8])
                if len(df.columns) > 8:
                    cols_preview.append(f"... ({len(df.columns)} total)")
                lines.append(
                    f"**{name}**: DataFrame({df.shape[0]} rows x {df.shape[1]} cols), "
                    f"columns: {cols_preview}, index: {df.index.name or type(df.index).__name__}"
                )

        # Pre-built helpers
        helpers = []
        if "compute_pi_percentage" in self._namespace:
            helpers.append("compute_pi_percentage(seqs) — computes parsimony informative site % with gap exclusion")
        if "safe_subprocess_run" in self._namespace:
            helpers.append("safe_subprocess_run(cmd) — run whitelisted bioinformatics CLI tools")
        if helpers:
            lines.append("**Pre-imported helper functions** (already available — just call them):")
            for h in helpers:
                lines.append(f"  - `{h}`")
            lines.append("")

        # Prior results
        steps = [k for k in self._namespace if k.startswith("step_")]
        if steps:
            lines.append(f"\n**Prior step results**: {', '.join(sorted(steps))}")
            for s in sorted(steps):
                val = self._namespace[s]
                if isinstance(val, dict):
                    keys = list(val.keys())[:6]
                    lines.append(f"  {s}: dict with keys {keys}")
                else:
                    lines.append(f"  {s}: {type(val).__name__}")

        return "\n".join(lines)
