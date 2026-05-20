"""
Quick CLI to test the LangGraph shopping assistant.
Run from project root:
    python -m agent.test_cli
"""
from app.agents.runner import ChatRunner
from app.agents.graph import get_graph
from pprint import pprint

def print_graph():
    # Print Mermaid code (copy to https://www.mermaidflow.app/editor)
    print("\n📊 Copy this to https://www.mermaidflow.app/editor\n")
    
    graph=get_graph()
    print(graph.get_graph().draw_mermaid())
    
    # Also print simple node list
    # print("NODES IN GRAPH:")
    # for node in graph.get_graph().nodes:
    #     print(f"  • {node}")

def main():
    runner = ChatRunner()

    print("  Shopify Chat Assistant  (type 'quit' to exit, 'reset' to restart)")

    # Optional: run a scripted scenario first
    # scenario = [
    #     "vans between 50 to 100 dollars",
    #     # "only show ones with 3 stars or above",
    #     # "what about under $60",
    #     # "tell me more about the second one",
    #     # "show me similar products",
    # ]

    # print("\n[Running demo scenario...]\n")
    # for msg in scenario:
    #     print(f"USER: {msg}")
    #     reply = runner.chat(msg)
    #     print(f"ASSISTANT: {reply}")
    #     print(f"  [Filters: {runner.current_filters}]")
    #     print()

    print("\n[Interactive mode — type your own messages]\n")
    runner.reset()

    while True:
        try:
            user_input = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "reset":
            runner.reset()
            print("SYSTEM: Conversation reset.\n")
            continue
        if user_input.lower() == "filters":
            print(f"SYSTEM: Active filters: {runner.current_filters}\n")
            continue

        reply = runner.chat(user_input)
        # print(f"ASSISTANT: {reply}")
        
        pprint(reply)

        # print(f"  [Filters: {runner.current_filters}]")

        pprint(runner.current_filters)
        print()


if __name__ == "__main__":
    main()