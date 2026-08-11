"""Mixin: _set_active_usage, _set_active_streamed_chars, _estimate_output_tokens_from_chars, _coerce_cost, _record_sdk_usage, _usage_snapshot."""

from __future__ import annotations

import re
import time


class _UsageTrackingMixin:
    def _set_active_usage(self, input_tokens=None, output_tokens=None,
                          cache_read_tokens=None) -> None:
        # Track fresh (non-cached) input only — subtract prompt-cache reads so the
        # live counter doesn't balloon when a large cached prefix is re-sent on
        # every model call of a long agentic turn.
        cache_read = self._coerce_token_count(cache_read_tokens)
        in_tokens = max(0, self._coerce_token_count(input_tokens) - cache_read)
        out_tokens = self._coerce_token_count(output_tokens)
        with self._run_lock:
            if in_tokens > self._active_input_tokens:
                self._active_input_tokens = in_tokens
            if out_tokens > self._active_output_tokens:
                self._active_output_tokens = out_tokens

    def _set_active_streamed_chars(self, streamed_chars=None) -> None:
        chars = self._coerce_token_count(streamed_chars)
        with self._run_lock:
            if chars > self._active_streamed_chars:
                self._active_streamed_chars = chars

    @staticmethod
    def _estimate_output_tokens_from_chars(char_count: int) -> int:
        # Rough fallback while SDK usage counters are not yet emitted.
        return max(0, int(round(char_count / 4.0)))

    @staticmethod
    def _coerce_cost(value) -> float:
        try:
            if value is None:
                return 0.0
            if isinstance(value, bool):
                return float(int(value))
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            text = str(value).strip()
            if not text:
                return 0.0
            return max(0.0, float(text))
        except Exception:
            return 0.0

    def _record_sdk_usage(self, result) -> None:
        metadata = getattr(result, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return

        input_tokens = self._coerce_token_count(metadata.get("sdk_input_tokens"))
        output_tokens = self._coerce_token_count(metadata.get("sdk_output_tokens"))
        cache_read_tokens = self._coerce_token_count(metadata.get("sdk_cache_read_input_tokens"))
        cache_creation_tokens = self._coerce_token_count(metadata.get("sdk_cache_creation_input_tokens"))
        sdk_turns = self._coerce_token_count(metadata.get("sdk_turns"))
        cost_split_known = bool(metadata.get("sdk_cost_split_known", False))
        total_cost_usd = self._coerce_cost(metadata.get("sdk_total_cost_usd"))
        model_usage_cost_usd = self._coerce_cost(metadata.get("sdk_model_usage_cost_usd"))
        if total_cost_usd <= 0.0:
            total_cost_usd = self._coerce_cost(metadata.get("sdk_cost_usd"))
        # Main display cost aligns with token rows when split is known.
        if cost_split_known and model_usage_cost_usd > 0.0:
            cost_usd = model_usage_cost_usd
            extra_server_tool_cost_usd = self._coerce_cost(
                metadata.get("sdk_server_tool_cost_usd")
            )
            if extra_server_tool_cost_usd <= 0.0 and total_cost_usd > cost_usd:
                extra_server_tool_cost_usd = total_cost_usd - cost_usd
        else:
            # SDK didn't provide model-usage cost; avoid double-reporting.
            cost_usd = total_cost_usd
            extra_server_tool_cost_usd = 0.0
        models_raw = metadata.get("sdk_models") or []
        if isinstance(models_raw, str):
            models = [models_raw]
        elif isinstance(models_raw, (list, tuple, set)):
            models = [str(m).strip() for m in models_raw if str(m).strip()]
        else:
            models = []
        if not models:
            fallback_model = str(metadata.get("sdk_model") or self.session.current_model or "").strip()
            if fallback_model:
                models = [fallback_model]

        has_usage = any((
            input_tokens > 0,
            output_tokens > 0,
            cache_read_tokens > 0,
            cache_creation_tokens > 0,
            cost_usd > 0.0,
            sdk_turns > 0,
        ))
        if not has_usage:
            return

        with self._run_lock:
            self._session_sdk_calls += 1
            turn_idx = self._session_sdk_calls
            self._session_sdk_input_tokens += input_tokens
            self._session_sdk_output_tokens += output_tokens
            self._session_sdk_cache_read_tokens += cache_read_tokens
            self._session_sdk_cache_creation_tokens += cache_creation_tokens
            self._session_sdk_cost_usd += cost_usd
            self._session_sdk_total_cost_usd += total_cost_usd
            self._session_sdk_extra_server_tool_cost_usd += extra_server_tool_cost_usd
            for model in models:
                if model:
                    self._session_sdk_models.add(model)
            self._session_sdk_turn_rows.append(
                {
                    "turn": turn_idx,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read_tokens,
                    "cache_creation_tokens": cache_creation_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": total_cost_usd,
                    "extra_server_tool_cost_usd": extra_server_tool_cost_usd,
                    "models": list(models),
                    "timestamp": time.time(),
                }
            )
        self._persist_usage_to_trajectory()

    def _usage_snapshot(self) -> dict:
        """Create a serializable snapshot of current session usage counters."""
        with self._run_lock:
            return {
                "sdk_calls": int(self._session_sdk_calls),
                "sdk_input_tokens": int(self._session_sdk_input_tokens),
                "sdk_output_tokens": int(self._session_sdk_output_tokens),
                "sdk_cache_read_tokens": int(self._session_sdk_cache_read_tokens),
                "sdk_cache_creation_tokens": int(self._session_sdk_cache_creation_tokens),
                "sdk_cost_usd": float(self._session_sdk_cost_usd),
                "sdk_total_cost_usd": float(self._session_sdk_total_cost_usd),
                "sdk_extra_server_tool_cost_usd": float(self._session_sdk_extra_server_tool_cost_usd),
                "sdk_models": sorted(self._session_sdk_models),
                "sdk_turn_rows": list(self._session_sdk_turn_rows),
            }
