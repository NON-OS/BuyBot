import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.getLogger("buybot").setLevel(logging.CRITICAL)
for name in ("rpc", "chain", "post", "watch", "cmd", "tg", "state"):
    logging.getLogger(f"buybot.{name}").setLevel(logging.CRITICAL)
