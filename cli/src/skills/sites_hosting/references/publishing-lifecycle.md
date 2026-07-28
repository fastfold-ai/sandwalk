# Publishing Lifecycle

The installed `sites.manage` description is the source of truth because the
publishing tool is introduced independently of this skill.

## State Handling

1. Submit one publish request and retain every returned site, operation, or
   deployment identifier.
2. If the response is accepted, queued, uploading, building, processing, or any
   other nonterminal state, tell the user it was accepted and begin status polling.
3. Poll the matching status action. Follow tool-provided retry timing; otherwise
   use a modest delay and a bounded wait.
4. Report success only when the status response is the documented ready/success
   terminal state. Use its final URL verbatim.
5. Treat documented failed or cancelled states as terminal. For an unknown state
   or local timeout, preserve the identifier and say readiness is unconfirmed.

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
