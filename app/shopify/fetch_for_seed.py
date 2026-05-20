# app/shopify/fetcher.py

import httpx
from typing import Optional, Tuple
from app.config import settings


class ShopifyFetcher:
    """Fetch Shopify IDs for products and variants"""

    def __init__(self):
        self.store = settings.SHOPIFY_STORE_DOMAIN
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = settings.SHOPIFY_API_VERSION

    async def get_product_and_variant_by_sku(
        self,
        sku: str
    ) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[int]]:

        if not sku:
            return (None, None, None, None)

        query = """
        query GetVariantBySku($query: String!) {
            productVariants(first: 1, query: $query) {
                edges {
                    node {
                        id
                        sku
                        product {
                            id
                            handle
                        }
                    }
                }
            }
        }
        """

        async with httpx.AsyncClient(timeout=30.0) as client:

            response = await client.post(
                f"https://{self.store}/admin/api/{self.api_version}/graphql.json",
                json={
                    "query": query,
                    "variables": {
                        "query": f"sku:{sku}"
                    }
                },
                headers={
                    "X-Shopify-Access-Token": self.access_token,
                    "Content-Type": "application/json"
                }
            )

            # print("\n======================")
            # print("SKU:", sku)
            # print("STATUS:", response.status_code)
            # print("BODY:", response.text[:500])

            if response.status_code != 200:
                return (None, None, None, None)

            data = response.json()

            errors = data.get("errors")
            if errors:
                print("GRAPHQL ERRORS:", errors)
                return (None, None, None, None)

            edges = (
                data.get("data", {})
                .get("productVariants", {})
                .get("edges", [])
            )

            if not edges:
                print("No Shopify variant found")
                return (None, None, None, None)

            variant_node = edges[0]["node"]

            variant_gid = variant_node["id"]
            variant_id = int(variant_gid.split("/")[-1])

            product_node = variant_node["product"]

            product_gid = product_node["id"]
            product_id = int(product_gid.split("/")[-1])

            return (
                product_gid,
                product_id,
                variant_gid,
                variant_id
            )