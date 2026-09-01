import json
from app.simulation.dataset import generate_dataset
from app.simulation.engine import SimulationEngine
from app.graph.workflow import build_graph
from app.db.state.db import create_tables

def run_demo():
    print("--- AI Revenue Recovery: Phase 4 Demonstration ---")
    print("Simulating an Adaptive Recovery Loop on 3 Trajectories\n")
    
    # 0. Initialize Database
    create_tables()
    
    # 1. Initialize Engine and Graph
    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    # We will create specific mock events for the 3 trajectories
    # A. Successful recovery (transient technical recovers fast)
    # B. Adaptive recovery (nsf fails, channel switched, eventually recovers)
    # C. Exhausted recovery (permanent failure or exhausted limits)
    from app.simulation.interfaces import SimulatedPaymentEvent
    import datetime
    
    events = [
        SimulatedPaymentEvent(
            payment_id="pay_tech_001",
            merchant_id="merchant_001",
            customer_id="cust_001",
            amount=100.0,
            currency="INR",
            payment_method="card",
            failure_code="bank_timeout",
            failure_reason="Bank timeout",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        ),
        SimulatedPaymentEvent(
            payment_id="pay_nsf_002",
            merchant_id="merchant_001",
            customer_id="cust_002",
            amount=50.0,
            currency="USD",
            payment_method="card",
            failure_code="insufficient_funds",
            failure_reason="Insufficient funds",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        ),
        SimulatedPaymentEvent(
            payment_id="pay_perm_003",
            merchant_id="merchant_001",
            customer_id="cust_003",
            amount=999.0,
            currency="EUR",
            payment_method="card",
            failure_code="invalid_card",
            failure_reason="Card expired or invalid",
            timestamp=datetime.datetime.now(datetime.UTC).isoformat()
        )
    ]
    
    labels = ["A. Successful Recovery", "B. Adaptive Recovery", "C. Exhausted/Permanent Recovery"]

    for i, event in enumerate(events):
        print(f"\n{'='*60}")
        print(f"Trajectory {labels[i]}")
        print(f"Payment: {event.payment_id} | Failure: {event.failure_code}")
        print(f"{'='*60}")
        
        # Load into DB via Simulation Engine
        case_id = engine.load_payment_event(event)
        
        # Initialize LangGraph state
        initial_state = {
            "payment_id": event.payment_id,
            "failure_code": event.failure_code,
            "failure_reason": event.failure_reason,
            "messages": [],
            "runtime_metadata": [],
            "attempt_count": 0,
            "max_attempts": 3,
            "safety_cleared": False,
            "safety_flags": [],
            "simulated_time_hours": 0,
            "strategy_history": [],
            "action_history": [],
            "outcome_history": []
        }
        
        config = {"configurable": {"thread_id": f"demo4_{event.payment_id}"}, "recursion_limit": 20}
        
        # We will stream the graph to show the timeline
        print("Timeline:")
        for output in graph.stream(initial_state, config=config):
            for node, state in output.items():
                if node == "strategy":
                    strat = state.get("strategy", {})
                    print(f"  [STRATEGY] Proposed: {strat.get('action')} via {strat.get('channel')}. Rationale: {strat.get('rationale')}")
                elif node == "policy":
                    dec = state.get("policy_decision", {})
                    if not dec.get("allowed"):
                        print(f"  [POLICY] Blocked! Mutated to {dec.get('mutated_action')}. Reason: {dec.get('reason')}")
                    else:
                        print(f"  [POLICY] Allowed.")
                elif node == "action":
                    req = state.get("action_request", {})
                    res = state.get("action_result", {})
                    t = state.get("simulated_time_hours", 0)
                    print(f"  [ACTION] Executed {req.get('action_type')} at T+{t}h. Success: {res.get('success')}. Outcome: {res.get('simulated_outcome')}")
                elif node == "outcome":
                    out = state.get("latest_outcome", {})
                    sig = state.get("recovery_signal", "")
                    print(f"  [OUTCOME] Category: {out.get('outcome_category')}. Signal: {sig}. Terminal: {out.get('is_terminal')}")
                elif node == "adaptive_planner":
                    strat = state.get("strategy", {})
                    print(f"  [ADAPTIVE PLANNER] New Strategy: {strat.get('action')} via {strat.get('channel')}. Reason: {strat.get('rationale')}")
                    
        # Fetch the final state
        final_state = graph.invoke(initial_state, config=config)
        print(f"\nFinal Case Status: {final_state.get('case_status')}")
        print(f"Total Attempts: {final_state.get('attempt_count')}")
        print(f"Total Simulated Time: {final_state.get('simulated_time_hours')} hours")

if __name__ == "__main__":
    run_demo()
