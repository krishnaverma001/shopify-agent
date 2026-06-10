import httpx
from typing import Optional, Tuple
from app.config import settings
from  app.logging import get_logger

logger = get_logger(__name__)

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
        """
        It queries Shopify's GraphQL Admin API using a product's SKU (from your CSV) 
        to retrieve the real Shopify product ID, variant ID, and GID strings, 
        then updates your Supabase database so you can generate direct product links 
        and enable future features like add-to-cart – it's essentially a one-time 
        sync that bridges your offline CSV data with Shopify's live system
        """

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

            if response.status_code != 200:
                return (None, None, None, None)

            data = response.json()

            errors = data.get("errors")
            if errors:
                logger.error("GRAPHQL ERRORS:", errors)
                return (None, None, None, None)

            edges = (
                data.get("data", {})
                .get("productVariants", {})
                .get("edges", [])
            )

            if not edges:
                logger.error("No Shopify variant found")
                return (None, None, None, None)

            variant_node = edges[0]["node"]

            variant_gid = variant_node["id"]
            variant_id = int(variant_gid.split("/")[-1])

            product_node = variant_node["product"]

            product_gid = product_node["id"]
            product_id = int(product_gid.split("/")[-1])

        return (
            product_gid,    # "gid://shopify/Product/987654321"
            product_id,     # 987654321
            variant_gid,    # "gid://shopify/ProductVariant/123456789"
            variant_id      # 123456789
        )