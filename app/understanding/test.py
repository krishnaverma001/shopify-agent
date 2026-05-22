from pprint import pprint

from .normalizer import QueryNormalizer
from .parser import LLMQueryParser
from .validator import QueryValidator
from .models import ParsedQuery
from app.config import settings

from app.retrieval.hybrid import HybridRetriever

from app.cache.brand_catalog import KNOWN_BRANDS

def build_vector_query(parsed):
    parts = [
        parsed.retrieval_query,
        *parsed.attributes,
        *parsed.semantic_constraints
    ]

    return " ".join([p for p in parts if p]).strip()

def main():
    print("Initializing\n")

    normalizer = QueryNormalizer()

    parser = LLMQueryParser(
        api_key=settings.GROQ_API_KEY
    )

    validator = QueryValidator(
        known_brands=KNOWN_BRANDS
    )

    retriever = HybridRetriever()

    queries = [
        # "comfortable headset for long gaming sessions",
        "nintendo joystick between 50 to 100 dollars",
        # "wireless gaming mouse with good reviews",
        # "playstation controller between 40 and 100 dollars",
        # "cheap xbox headset",
        # "durable keyboard for competitive gaming",
        # "nintnod joystk with ratings above 3"
    ]

    for query in queries:

        print("=" * 80)
        print(f"QUERY: {query}")
        print("=" * 80)

        normalized = normalizer.normalize(query)

        print("\n[1] NORMALIZED")
        print(normalized)

        extracted = parser.parse(
            query=normalized
        )

        print("\n[2] LLM OUTPUT")
        pprint(extracted)

        parsed = ParsedQuery(
            raw_query=query,
            normalized_query=normalized
        )

        parsed = validator.validate(parsed, extracted)

        print("\n[3] VALIDATED PARSED QUERY")
        pprint(parsed.to_dict())

        vector_query = build_vector_query(parsed)

        print("\n[4] VECTOR QUERY")
        print(vector_query)

        print("\n[5] SEARCHING...\n")

        results = retriever.search(
            query_text=vector_query,
            brand=parsed.brand,
            min_price=parsed.min_price,
            max_price=parsed.max_price,
            min_rating=parsed.min_rating,
            limit=1
        )

        pprint(results)

        if results:
            top_product = results[0]

            similar = retriever.get_similar_products(
                product_handle=top_product['product_handle'],
                limit=1
            )

            print("\n[SIMILAR PRODUCTS]")
            pprint(similar)

if __name__ == "__main__":
    main()