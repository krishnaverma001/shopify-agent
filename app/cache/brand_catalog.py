from app.db.repositories.product_repository import ProductRepository
from app.logging import get_logger

logger = get_logger(__name__)

KNOWN_BRANDS = ['ADIDAS', 'ASICS TIGER', 'CONVERSE', 'DR MARTENS', 'FISHER PRICE', 
                'FLEX FIT', 'HASBRO', 'HERSCHEL', 'LEGO', 'MATTEL', 'MEGA BLOCKS', 
                'NERF', 'NIKE', 'NINTENDO', 'PALLADIUM', 'PUMA', 'SUPRA', 
                'TIMBERLAND', 'VANS']

def load_catalog_metadata():

    repo = ProductRepository()

    brands = repo.get_all_brands()

    KNOWN_BRANDS.clear()
    KNOWN_BRANDS.extend(sorted(brands))

    logger.info("Catalog metadata loaded")