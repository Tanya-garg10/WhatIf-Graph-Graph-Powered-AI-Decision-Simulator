import logging
import sys

logger = logging.getLogger("whatif-graph")
logger.setLevel(logging.INFO)

# Console handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
