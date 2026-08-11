"""Code execution: helper-redefinition guard plus the exec() runner."""

import io
import signal
import sys
import traceback


class SandboxExecutionMixin:
    """Owns protected-helper stripping and the actual code execution."""

    def _protect_preimported_helpers(self, code: str) -> str:
        """Remove any user redefinition of pre-imported helper functions.

        The sandbox pre-imports correct versions of helpers like compute_pi_percentage.
        LLM-generated code sometimes redefines these incorrectly (e.g., including gap
        characters in PI computation). This method strips such redefinitions so the
        pre-imported versions are used instead.
        """
        import ast

        protected = {"compute_pi_percentage"}
        # Only protect functions that are actually in the namespace
        protected = {f for f in protected if f in self._namespace}
        if not protected:
            return code

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code  # Can't parse — let execution handle the error

        # Find line ranges of protected function definitions
        lines = code.split('\n')
        remove_ranges = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in protected:
                start = node.lineno - 1  # 0-indexed
                end = node.end_lineno  # end_lineno is 1-indexed, exclusive after -1+1
                remove_ranges.append((start, end))

        if not remove_ranges:
            return code

        # Remove the function definitions (replace with comment)
        new_lines = []
        skip_until = -1
        for i, line in enumerate(lines):
            if i < skip_until:
                continue
            removed = False
            for start, end in remove_ranges:
                if i == start:
                    new_lines.append(f'# {line.strip()} — REMOVED: using pre-imported sandbox version')
                    skip_until = end
                    removed = True
                    break
            if not removed and i >= skip_until:
                new_lines.append(line)

        return '\n'.join(new_lines)

    def execute(self, code: str) -> dict:
        """Execute code in the sandbox and return results.

        Returns dict with: stdout, stderr, result, error, plots, exports.
        """
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot output dir contents before execution
        existing_files = set(self.output_dir.iterdir()) if self.output_dir.exists() else set()

        # Capture stdout/stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        captured_out = io.StringIO()
        captured_err = io.StringIO()

        result = {
            "stdout": "",
            "stderr": "",
            "result": None,
            "error": None,
            "plots": [],
            "exports": [],
        }

        # Set up timeout (Unix only)
        import threading
        has_alarm = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
        if has_alarm:
            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Code execution timed out after {self.timeout}s")
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.timeout)

        try:
            sys.stdout = captured_out
            sys.stderr = captured_err

            # Strip any redefinition of pre-imported helpers to ensure sandbox versions are used
            code = self._protect_preimported_helpers(code)

            # Compile and execute
            compiled = compile(code, "<ct-sandbox>", "exec")
            exec(compiled, self._namespace)

            # Capture the 'result' variable if set by the code
            if "result" in self._namespace:
                result["result"] = self._namespace["result"]

        except TimeoutError as e:
            result["error"] = str(e)
        except Exception:
            result["error"] = traceback.format_exc()
        finally:
            # Restore
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            if has_alarm:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        result["stdout"] = captured_out.getvalue()
        result["stderr"] = captured_err.getvalue()

        # Detect new files in output dir
        if self.output_dir.exists():
            new_files = set(self.output_dir.iterdir()) - existing_files
            for f in sorted(new_files):
                if f.suffix in (".png", ".svg", ".jpg", ".jpeg", ".pdf"):
                    result["plots"].append(str(f))
                elif f.suffix in (".csv", ".xlsx", ".tsv", ".json"):
                    result["exports"].append(str(f))

        return result
