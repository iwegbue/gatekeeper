"""
Layer-based state machine for idea progression.

State flow:
  WATCHING → SETUP_VALID → CONFIRMED → ENTRY_PERMITTED → IN_TRADE → MANAGED → CLOSED
  Any non-terminal → INVALIDATED

Advancement rules:
  WATCHING     → SETUP_VALID      requires CONTEXT layer complete
  SETUP_VALID  → CONFIRMED        requires SETUP layer complete
  CONFIRMED    → ENTRY_PERMITTED  requires CONFIRMATION + ENTRY + RISK layers complete
  ENTRY_PERMITTED → IN_TRADE      (manual — trade is opened)
  IN_TRADE     → MANAGED          requires MANAGEMENT layer complete
  MANAGED      → CLOSED           (manual — trade is closed)
  Any          → INVALIDATED      always allowed from non-terminal states

Backward regression is allowed between pre-trade states:
  CONFIRMED → SETUP_VALID, SETUP_VALID → WATCHING
  Not allowed once IN_TRADE or beyond.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idea import Idea
from app.models.state_transition import StateTransition
from app.models.enums import IdeaState
from app.services import checklist_service


class TransitionError(Exception):
    pass


class GuardError(Exception):
    def __init__(self, message: str, blockers: list[str]):
        super().__init__(message)
        self.blockers = blockers


# States that cannot be advanced from (terminal or in-progress)
TERMINAL_STATES = {IdeaState.CLOSED, IdeaState.INVALIDATED}
POST_TRADE_STATES = {IdeaState.IN_TRADE, IdeaState.MANAGED, IdeaState.CLOSED}

# Layer requirements per forward transition
LAYER_REQUIREMENTS: dict[tuple[str, str], list[str]] = {
    (IdeaState.WATCHING, IdeaState.SETUP_VALID): ["CONTEXT"],
    (IdeaState.SETUP_VALID, IdeaState.CONFIRMED): ["SETUP"],
    (IdeaState.CONFIRMED, IdeaState.ENTRY_PERMITTED): ["CONFIRMATION", "ENTRY", "RISK"],
    (IdeaState.IN_TRADE, IdeaState.MANAGED): ["MANAGEMENT"],
}

# Valid forward transitions
FORWARD_TRANSITIONS: dict[str, str] = {
    IdeaState.WATCHING: IdeaState.SETUP_VALID,
    IdeaState.SETUP_VALID: IdeaState.CONFIRMED,
    IdeaState.CONFIRMED: IdeaState.ENTRY_PERMITTED,
    IdeaState.ENTRY_PERMITTED: IdeaState.IN_TRADE,
    IdeaState.IN_TRADE: IdeaState.MANAGED,
    IdeaState.MANAGED: IdeaState.CLOSED,
}

# Valid backward regression (pre-trade only)
BACKWARD_TRANSITIONS: dict[str, str] = {
    IdeaState.CONFIRMED: IdeaState.SETUP_VALID,
    IdeaState.SETUP_VALID: IdeaState.WATCHING,
    IdeaState.ENTRY_PERMITTED: IdeaState.CONFIRMED,
}


async def advance(db: AsyncSession, idea: Idea, reason: str | None = None) -> Idea:
    """
    Advance idea to the next state in the flow.
    Checks layer completion guards for transitions that require them.
    Raises GuardError if blocked by incomplete rules.
    Raises TransitionError if advancement is not possible.
    """
    current = IdeaState(idea.state)

    if current in TERMINAL_STATES:
        raise TransitionError(f"Cannot advance from terminal state {current}")

    next_state = FORWARD_TRANSITIONS.get(current)
    if next_state is None:
        raise TransitionError(f"No forward transition from {current}")

    # Check layer requirements
    required_layers = LAYER_REQUIREMENTS.get((current, next_state), [])
    all_blockers = []
    for layer in required_layers:
        blockers = await checklist_service.get_layer_blockers(db, idea.id, layer)
        all_blockers.extend(blockers)

    if all_blockers:
        raise GuardError(
            f"Cannot advance from {current}: {len(all_blockers)} required rule(s) unchecked",
            blockers=all_blockers,
        )

    return await _apply_transition(db, idea, next_state, reason)


async def regress(db: AsyncSession, idea: Idea, reason: str | None = None) -> Idea:
    """
    Regress idea to the previous state. Only allowed pre-trade.
    Raises TransitionError if regression is not possible.
    """
    current = IdeaState(idea.state)

    if current in POST_TRADE_STATES:
        raise TransitionError(f"Cannot regress from in-trade state {current}")

    prev_state = BACKWARD_TRANSITIONS.get(current)
    if prev_state is None:
        raise TransitionError(f"No backward transition from {current}")

    return await _apply_transition(db, idea, prev_state, reason or "Regressed")


async def invalidate(db: AsyncSession, idea: Idea, reason: str | None = None) -> Idea:
    """Move idea to INVALIDATED from any non-terminal state."""
    current = IdeaState(idea.state)
    if current in TERMINAL_STATES:
        raise TransitionError(f"Cannot invalidate from terminal state {current}")
    return await _apply_transition(db, idea, IdeaState.INVALIDATED, reason or "Invalidated")


async def _apply_transition(db: AsyncSession, idea: Idea, to_state: IdeaState, reason: str | None) -> Idea:
    from_state = idea.state
    idea.state = to_state.value

    transition = StateTransition(
        idea_id=idea.id,
        from_state=from_state,
        to_state=to_state.value,
        reason=reason,
    )
    db.add(transition)
    await db.flush()
    return idea


def get_available_actions(state: str) -> dict[str, bool]:
    """Return which actions are available from the current state."""
    current = IdeaState(state)
    return {
        "can_advance": current not in TERMINAL_STATES and current in FORWARD_TRANSITIONS,
        "can_regress": current not in POST_TRADE_STATES and current in BACKWARD_TRANSITIONS,
        "can_invalidate": current not in TERMINAL_STATES,
    }


def get_transition_history_label(from_state: str, to_state: str) -> str:
    if to_state == IdeaState.INVALIDATED:
        return "Invalidated"
    if to_state in {s for s in BACKWARD_TRANSITIONS.values()}:
        return f"Regressed to {to_state}"
    return f"Advanced to {to_state}"
