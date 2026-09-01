import json
from app.simulation.dataset import generate_dataset
from app.simulation.engine import SimulationEngine
from app.graph.workflow import build_graph

def run_demo():
    print("--- AI Revenue Recovery: Phase 3 Demonstration ---")
    
    # 1. Initialize Engine and Graph
    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    # 2. Generate synthetic cases
    events = generate_dataset(n=5, seed=777)
    
    for i, event in enumerate(events):
        print(f"\n{'='*50}")
        print(f"[{i+1}/5] Processing Payment: {event.payment_id}")
        print(f"  Failure: {event.failure_code} - {event.failure_reason}")
        print(f"  Amount: {event.amount} {event.currency} via {event.payment_method}")
        print(f"{'='*50}")
        
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
        }
        
        config = {"configurable": {"thread_id": f"demo3_{event.payment_id}"}}
        
        print("Running full LangGraph pipeline (Intake -> Diagnosis -> Strategy -> Policy -> Action)...")
        
        # Run graph
        final_state = graph.invoke(initial_state, config=config)
        
        print(f"\nFinal Case Status: {final_state.get('case_status')}")
        
        if 'diagnosis' in final_state:
            diag = final_state['diagnosis']
            print("\n[DIAGNOSIS]")
            print(f"  Category: {diag.get('failure_category')}")
            print(f"  Recoverable: {diag.get('is_recoverable')}")
            
        if 'strategy' in final_state:
            strat = final_state['strategy']
            print("\n[STRATEGY]")
            print(f"  Action: {strat.get('action')}")
            print(f"  Channel: {strat.get('channel')}")
            print(f"  Delay (hrs): {strat.get('retry_timing_hours')}")
            print(f"  Rationale: {strat.get('rationale')}")

        if 'policy_decision' in final_state:
            pol = final_state['policy_decision']
            print("\n[POLICY GUARD]")
            print(f"  Allowed: {pol.get('allowed')}")
            print(f"  Reason: {pol.get('reason')}")
            if not pol.get('allowed'):
                print(f"  Mutated Action: {pol.get('mutated_action')}")

        if 'action_result' in final_state:
            res = final_state['action_result']
            print("\n[SIMULATED ACTION RESULT]")
            print(f"  Success: {res.get('success')}")
            print(f"  Outcome: {res.get('simulated_outcome')}")
            if res.get('customer_response'):
                print(f"  Customer Response: {res.get('customer_response')}")

if __name__ == "__main__":
    run_demo()
