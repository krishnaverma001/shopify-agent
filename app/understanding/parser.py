import json
from typing import Optional, List, Dict
from groq import Groq
from app.understanding.models import ParsedQuery, Intent

class LLMQueryParser:
    """Extract structured data from natural language queries using LLM"""
    
    def __init__(
            self, 
            api_key: str, 
            # model: str = "llama-3.1-8b-instant"
            model: str = "llama-3.3-70b-versatile"
        ):
        self.client = Groq(api_key=api_key)
        self.model = model
    
    def parse(self, query: str) -> Dict:
        """Extract structured data from query"""
    
    # In parser.py, update the prompt examples:
        prompt = f"""Extract ecommerce search parameters from this query.

Query: "{query}"

Return ONLY valid JSON. No explanation.

{{
  "retrieval_query": "main search terms (remove filters like 'under $50', '4 stars', etc.)",
  "intent": "search|compare|details|similar",
  "brand": "extracted brand name or null",
  "category": "category from known categories or null",
  "min_price": number or null,
  "max_price": number or null,
  "min_rating": number between 1-5 or null,
  "attributes": ["feature1", "feature2"],
  "semantic_constraints": ["comfortable", "durable", "lightweight"]
}}

Examples:
Input: "nintendo joystick under $50 with good reviews"
Output: {{"retrieval_query": "joystick", "intent": "search", "brand": "Nintendo", "category": "joystick", "min_price": null, "max_price": 50, "min_rating": 4.0, "attributes": [], "semantic_constraints": []}}

Input: "under $60"
Output: {{"retrieval_query": "", "intent": "search", "brand": null, "category": null, "min_price": null, "max_price": 60, "min_rating": null, "attributes": [], "semantic_constraints": []}}

Input: "what about cheaper ones"
Output: {{"retrieval_query": "", "intent": "search", "brand": null, "category": null, "min_price": null, "max_price": null, "min_rating": null, "attributes": [], "semantic_constraints": []}}

Rules:
1. retrieval_query MUST contain only searchable product terms. Empty string if no product terms.
2. For standalone price queries, set max_price/min_price accordingly.
3. Return null when unknown.
4. Return STRICT JSON only.

Now extract for: "{query}" """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You extract structured ecommerce search parameters. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            return {
                "retrieval_query": query,
                "intent": "search",
                "brand": None,
                "category": None,
                "min_price": None,
                "max_price": None,
                "min_rating": None,
                "attributes": [],
                "semantic_constraints": []
            }