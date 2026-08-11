# Publishing Lifecycle

The installed `sites.manage` description is the source of truth because the
publishing tool is introduced independently of this skill.

## State Handling

1. Submit one publish request and retain the local site identifier.
2. The publish action uploads and waits for remote processing. Keep progress
   factual while that single call is running.
3. Report success only when publish returns `status="published"`. Use its final URL
   verbatim.
4. Treat a returned failure as terminal. For an unknown result or local timeout,
   preserve the local site identifier and say readiness is unconfirmed.
5. The status action only reads the last confirmed local state. Do not use it as a
   remote deployment poll or claim that it resumes a timed-out publish.

Do not turn a status timeout into another publish request. A retry can create a
duplicate deployment unless the tool explicitly documents idempotency.

## User Communication

- Before upload: “Validated and packaged N files.”
- Accepted: “Upload accepted; publication is processing.”
- Still pending: give the current state without predicting completion.
- Ready: “Ready at <tool-returned URL>.”
- Failed: give the state and concise tool-provided reason, then suggest the next
  reversible action.

Never derive a URL from an unconfirmed custom slug, describe an accepted request as
live, or mention an underlying hosting provider.
