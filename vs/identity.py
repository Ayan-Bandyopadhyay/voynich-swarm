"""Who gets credit. Credit goes to the GitHub account that runs an agent; the agent itself is
shown as a detail. Agents that share one owner's account (like the launch swarm, four agents
run from one person's machine) use distinct seat names on the desk so leases don't collide;
this table maps each seat to its owner and a readable agent label.

An outside contributor uses their GitHub login as the handle and may add "agent" (free text,
e.g. "Claude Code / Opus") to experiment.json.
"""
SEATS = {
    "fleet-opus": ("Ayan-Bandyopadhyay", "Opus · Claude Code"),
    "fleet-fable": ("Ayan-Bandyopadhyay", "Fable · Claude Code"),
    "fleet-astra": ("Ayan-Bandyopadhyay", "Astra · Codex"),
    "fleet-sol": ("Ayan-Bandyopadhyay", "Sol · Codex"),
    "fleet-corpora": ("Ayan-Bandyopadhyay", "Opus · Claude Code"),
    "fleet-blue": ("Ayan-Bandyopadhyay", "Fable · Claude Code"),
    "fleet-vision": ("Ayan-Bandyopadhyay", "Opus · Claude Code"),
    "fleet-lead": ("Ayan-Bandyopadhyay", "scheduled lead · OpenRouter"),
}


def owner(handle):
    return SEATS.get(handle, (handle, None))[0]


def agent(handle, declared=None):
    return SEATS.get(handle, (handle, None))[1] or declared
