import json
from app.simulation.dataset import generate_dataset
from app.simulation.engine import SimulationEngine
from app.graph.workflow import build_graph

def run_demo():
    print("--- AI Revenue Recovery: Phase 2 Demonstration ---")
    
    # 1. Initialize Engine and Graph
    engine = SimulationEngine(seed=42)
    graph = build_graph()
    
    # 2. Generate some synthetic cases
    events = generate_dataset(n=5, seed=777)
    
    for i, event in enumerate(events):
        print(f"\n[{i+1}/5] Processing Payment: {event.payment_id}")
        print(f"  Failure: {event.failure_code} - {event.failure_reason}")
        print(f"  Amount: {event.amount} {event.currency} via {event.payment_method}")
        
        # Load into DB via Simulation Engine
        case_id = engine.load_payment_event(event)
        
        # Initialize LangGraph state
        initial_state = {
            "payment_id": event.payment_id,
            "failure_code": event.failure_code,
            "failure_reason": event.failure_reason,
            "messages": [],
            "runtime_metadata": []
        }
        
        config = {"configurable": {"thread_id": f"demo_{event.payment_id}"}}
        
        print("  Running LangGraph Intake -> Diagnosis...")
        
        # Run graph
        final_state = graph.invoke(initial_state, config=config)
        
        # Print results
        print(f"  Case Status: {final_state['case_status']}")
        
        if 'diagnosis' in final_state:
            diag = final_state['diagnosis']
            print("  --- Diagnosis Result ---")
            print(f"  Category: {diag['failure_category']}")
            print(f"  Root Cause: {diag['root_cause']}")
            print(f"  Recoverable: {diag['is_recoverable']}")
            print(f"  Recommended Action: {diag['recommended_action']}")
            print(f"  Confidence: {diag.get('confidence', 0):.0%}")
        else:
            print("  No diagnosis produced.")

if __name__ == "__main__":
    run_demo()
