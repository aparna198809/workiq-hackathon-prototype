"""Quick test for proposal evaluation agent."""
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

sys.path.insert(0, "simulator")
sys.path.insert(0, "agent/subagents")
import engine
import proposal_eval_agent

sc = engine.load_scenario("simulator/scenarios/c1-northbridge")

print("=== Testing evaluate_proposals (CDC scan + re-score) ===")
result = proposal_eval_agent.evaluate_and_rescore(sc, persona_id="procurement_eval")
print(f"Status: {result['status']}")
print(f"Events detected: {len(result['events'])}")
for evt in result["events"][:5]:
    print(f"  [{evt['event_type']}] {evt['source_type']} {evt['source_id']}: {evt['summary'][:60]}")
if len(result["events"]) > 5:
    print(f"  ... and {len(result['events']) - 5} more")
print(f"\nProposals re-scored: {len(result['rescored'])}")
for r in result["rescored"]:
    old = r["old_score"]
    new = r["new_score"]
    delta = r["score_change"]
    delta_str = f" (delta {delta:+.2f})" if delta is not None else " (new)"
    print(f"  {r['vendor_name']}: {old} -> {new}{delta_str}  "
          f"citations={len(r['scoring_citations'])}, new_evidence={len(r['new_evidence'])}")

print(f"\nEvaluation log: {len(proposal_eval_agent.get_evaluation_history())} events")
