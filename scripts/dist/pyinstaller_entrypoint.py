import os
import sys

from taguette.web import main


if sys.platform == 'win32':
    os.environ['PATH'] = os.path.join(
        os.path.dirname(sys.executable),
        'Calibre2',
    ) + os.pathsep + os.environ['PATH']

main()
