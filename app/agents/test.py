from app.agents.runner import ChatRunner
from app.agents.graph import get_graph
import json
from pprint import pprint
from app.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def print_graph():
    logger.info("Copy this to https://www.mermaidflow.app/editor\n")
    
    graph = get_graph()
    logger.info(graph.get_graph().draw_mermaid())
    
    # Also print simple node list
    # print("NODES IN GRAPH:")
    # for node in graph.get_graph().nodes:
    #     print(f"  • {node}")

def main():
    runner = ChatRunner()

    logger.info("Shopify Chat Assistant  (type 'quit' to exit, 'reset' to restart)")

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
            logger.info("SYSTEM: Conversation reset.\n")
            
            continue

        if user_input.lower() == "filters":
            logger.info(f"SYSTEM: Active filters: \n{runner.current_filters}\n")
            continue

        reply = runner.chat(user_input)
        
        # pprint(reply)
        logger.info(json.dumps(reply, indent=2))

        # pprint(runner.current_filters)


if __name__ == "__main__":
    main()