CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    handle TEXT PRIMARY KEY,
    shopify_product_id BIGINT UNIQUE,  -- xxx
    shopify_gid TEXT UNIQUE,           -- Full GID: gid://shopify/Product/xxx
    title TEXT,
    description TEXT,
    vendor TEXT,
    category TEXT,
    product_type TEXT,
    tags TEXT,
    image_url TEXT,
    seo_title TEXT,
    seo_description TEXT,
    status TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_variants (
    variant_id TEXT PRIMARY KEY,
    shopify_variant_id BIGINT UNIQUE,    -- Real Shopify variant ID
    shopify_gid TEXT UNIQUE,             -- Full GID for cart API
    product_handle TEXT NOT NULL REFERENCES products(handle) ON DELETE CASCADE,
    sku TEXT,
    price DECIMAL(10,2),
    option1_name TEXT,
    option1_value TEXT,
    option2_name TEXT,
    option2_value TEXT,
    option3_name TEXT,
    option3_value TEXT,
    variant_image TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_embeddings (
    product_handle TEXT PRIMARY KEY NOT NULL REFERENCES products(handle) ON DELETE CASCADE,
    searchable_text TEXT,
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    product_id TEXT,
    product_handle TEXT NOT NULL REFERENCES products(handle) ON DELETE CASCADE,
    reviewer_name TEXT,
    reviewer_email TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title TEXT,
    body TEXT,
    review_date TEXT,
    verified BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_embeddings (
    review_id TEXT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    product_handle TEXT NOT NULL REFERENCES products(handle) ON DELETE CASCADE,
    searchable_text TEXT,
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_variants_product_handle ON product_variants(product_handle);
CREATE INDEX IF NOT EXISTS idx_reviews_product_handle ON reviews(product_handle);
CREATE INDEX IF NOT EXISTS idx_review_embeddings_product_handle ON review_embeddings(product_handle);
CREATE INDEX IF NOT EXISTS idx_products_fts
ON products
USING GIN (
    to_tsvector(
        'english',
        COALESCE(title, '') || ' ' ||
        COALESCE(vendor, '') || ' ' ||
        COALESCE(category, '')
    )
);

CREATE INDEX IF NOT EXISTS idx_product_embeddings_vector 
ON product_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 12);

CREATE INDEX IF NOT EXISTS idx_review_embeddings_vector 
ON review_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 12);



CREATE OR REPLACE FUNCTION match_products(
    query_embedding VECTOR(384),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 10
)
RETURNS TABLE(
    product_handle TEXT,
    shopify_product_id BIGINT,
    shopify_gid TEXT,
    title TEXT,
    description TEXT,
    vendor TEXT,
    category TEXT,
    min_price DECIMAL(10,2),
    image_url TEXT,
    searchable_text TEXT,
    similarity DOUBLE PRECISION
)
LANGUAGE SQL
AS $$
    SELECT 
        p.product_handle,
        pr.shopify_product_id,
        pr.shopify_gid,
        pr.title,
        pr.description,
        pr.vendor,
        pr.category,
        (SELECT MIN(v.price) FROM product_variants v WHERE v.product_handle = pr.handle) as min_price,
        pr.image_url,
        p.searchable_text,
        1 - (p.embedding <=> query_embedding) as similarity
    FROM product_embeddings p
    JOIN products pr ON p.product_handle = pr.handle
    WHERE 1 - (p.embedding <=> query_embedding) > match_threshold
    ORDER BY p.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION match_reviews(
    query_embedding VECTOR(384),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 10
)
RETURNS TABLE(
    review_id TEXT,
    product_handle TEXT,
    rating INTEGER,
    title TEXT,
    body TEXT,
    reviewer_name TEXT,
    searchable_text TEXT,
    similarity DOUBLE PRECISION
)
LANGUAGE SQL
AS $$
    SELECT 
        r.review_id,
        r.product_handle,
        rev.rating,
        rev.title,
        rev.body,
        rev.reviewer_name,
        r.searchable_text,
        1 - (r.embedding <=> query_embedding) as similarity
    FROM review_embeddings r
    JOIN reviews rev ON r.review_id = rev.review_id
    WHERE 1 - (r.embedding <=> query_embedding) > match_threshold
    ORDER BY r.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION match_reviews_by_handles(
    query_embedding VECTOR(384),
    product_handles TEXT[],
    match_threshold FLOAT DEFAULT 0.2,
    match_count INT DEFAULT 20
)
RETURNS TABLE(
    review_id TEXT,
    product_handle TEXT,
    rating INTEGER,
    title TEXT,
    body TEXT,
    reviewer_name TEXT,
    similarity DOUBLE PRECISION
)
LANGUAGE SQL
AS $$
    SELECT 
        r.review_id,
        r.product_handle,
        rev.rating,
        rev.title,
        rev.body,
        rev.reviewer_name,
        1 - (r.embedding <=> query_embedding) as similarity
    FROM review_embeddings r
    JOIN reviews rev ON r.review_id = rev.review_id
    WHERE r.product_handle = ANY(product_handles)
    AND 1 - (r.embedding <=> query_embedding) > match_threshold
    ORDER BY r.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION get_similar_products(
    product_handle TEXT,
    match_count INT DEFAULT 5
)
RETURNS TABLE(
    product_handle TEXT,
    shopify_product_id BIGINT,
    shopify_gid TEXT,
    title TEXT,
    vendor TEXT,
    category TEXT,
    image_url TEXT,
    min_price DECIMAL(10,2),
    similarity DOUBLE PRECISION
)
LANGUAGE SQL
AS $$
    WITH source_embedding AS (
        SELECT embedding
        FROM product_embeddings
        WHERE product_embeddings.product_handle = $1
    )
    SELECT
        pe.product_handle,
        p.shopify_product_id,
        p.shopify_gid,
        p.title,
        p.vendor,
        p.category,
        p.image_url,
        (
            SELECT MIN(v.price)
            FROM product_variants v
            WHERE v.product_handle = pe.product_handle
        ) AS min_price,
        1 - (pe.embedding <=> se.embedding) AS similarity
    FROM product_embeddings pe
    JOIN products p
        ON pe.product_handle = p.handle
    CROSS JOIN source_embedding se
    WHERE pe.product_handle != $1
    ORDER BY pe.embedding <=> se.embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION keyword_search_products(
    search_query TEXT,
    match_limit INT DEFAULT 50
)
RETURNS TABLE(
    product_handle TEXT,
    shopify_product_id BIGINT,
    shopify_gid TEXT,
    title TEXT,
    description TEXT,
    vendor TEXT,
    category TEXT,
    min_price DECIMAL(10,2),
    image_url TEXT,
    keyword_score REAL,
    rank BIGINT
)
LANGUAGE SQL
AS $$
    WITH ranked_products AS (
        SELECT 
            p.handle as product_handle,
            p.shopify_product_id,
            p.shopify_gid,
            p.title,
            p.description,
            p.vendor,
            p.category,
            p.image_url,
            COALESCE(
                (SELECT MIN(v.price)::DECIMAL(10,2) 
                 FROM product_variants v 
                 WHERE v.product_handle = p.handle), 
                NULL
            ) as min_price,
            ts_rank(
                to_tsvector('english', 
                    COALESCE(p.title, '') || ' ' || 
                    COALESCE(p.vendor, '') || ' ' || 
                    COALESCE(p.category, '')
                ),
                websearch_to_tsquery('english', search_query)
            )::REAL as keyword_score
        FROM products p
        WHERE to_tsvector('english', 
            COALESCE(p.title, '') || ' ' || 
            COALESCE(p.vendor, '') || ' ' || 
            COALESCE(p.category, '')
        ) @@ websearch_to_tsquery('english', search_query)
    )
    SELECT 
        ranked_products.product_handle,
        ranked_products.shopify_product_id,
        ranked_products.shopify_gid,
        ranked_products.title,
        ranked_products.description,
        ranked_products.vendor,
        ranked_products.category,
        ranked_products.min_price,
        ranked_products.image_url,
        ranked_products.keyword_score,
        ROW_NUMBER() OVER (ORDER BY keyword_score DESC)::BIGINT as rank
    FROM ranked_products
    ORDER BY keyword_score DESC
    LIMIT match_limit;
$$;



SELECT 
    table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('products', 'product_variants', 'product_embeddings', 'reviews', 'review_embeddings');

SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role;