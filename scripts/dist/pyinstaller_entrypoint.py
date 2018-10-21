import os
import sys

from taguette.main import main


if sys.platform == 'win32':
    os.environ['CALIBRE'] = os.path.join(
        os.path.dirname(sys.executable),
        'Calibre2',
    )
elif sys.platform == 'darwin':
    os.environ['CALIBRE'] = os.path.join(
        os.path.dirname(os.path.dirname(sys.executable)),
        'Resources/calibre.app/Contents/MacOS',
    )


main()
