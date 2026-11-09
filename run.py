import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from stm_simulator.app import main
        sys.exit(main())
    except Exception:
        Path(__file__).with_name("startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        sys.exit(1)
