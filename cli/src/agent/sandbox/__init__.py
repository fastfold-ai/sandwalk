"""
Sandboxed Python execution environment for ct code generation.

Provides a safe exec() environment with access to scientific Python libraries
and loaded datasets. Used by the code.execute tool.
"""

import warnings

from agent.sandbox.execution import SandboxExecutionMixin
from agent.sandbox.introspect import SandboxIntrospectMixin
from agent.sandbox.namespace_setup import SandboxSetupMixin

warnings.filterwarnings("ignore", message="Unable to import Axes3D")
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")


class Sandbox(SandboxExecutionMixin, SandboxIntrospectMixin, SandboxSetupMixin):
    """Sandboxed execution environment for generated Python code."""
