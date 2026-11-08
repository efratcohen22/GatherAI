# AI agent specification

## Organizer assistant
Tool loop with a budget of 8 model turns, a request timeout and limited retries. Tool inputs are validated with Pydantic; invalid input returns a structured error to the model.

Tools: get_event_summary, list_participants, get_participant, list_transportation_requests, list_available_vehicles, validate_ride_assignment, propose_ride_assignments, list_accommodation_requests, list_available_accommodations, validate_accommodation_assignment, propose_accommodation_assignments, list_tasks, propose_task_creation, draft_participant_message, get_pending_proposals. Proposal tools cover `create_action_proposal`.

There are no tools for SQL, shell or HTTP.

## Language contract
Replies separate confirmed data, unknowns, suggestions, pending actions and executed actions. A proposal is never described as done.

## Proposal lifecycle
pending, then approved and executed, or rejected, expired or failed. Stale proposals become failed with a reason and write nothing.

## Participant assistant
A state machine holds the conversation. The model may only extract fields. Tool data and other participants' records are never placed in its context.
