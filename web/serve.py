"""Start the bundled Python runtime (source checkout and exported packs)."""
from pathlib import Path
import sys
here=Path(__file__).resolve().parent
root=here if (here/'engine').is_dir() else here.parent
sys.path.insert(0,str(root))
from engine.server import main
if __name__=='__main__':
    if '--static' not in sys.argv:
        static=root/'web/dist' if (root/'web/dist/index.html').is_file() else root/'web'
        sys.argv.extend(['--static',str(static)])
    main()
