import logging
import os
import tempfile

__author__ = 'Steve Marple'
__version__ = '0.0.1'
__license__ = 'PSF'


class smart_open:
    """Smarter way to open files for writing.

    This class mimics the behaviour of 'with open(file) as handle:'
    but with two additional benefits:

    1. When opening a file for write access (including appending) the
    parent directory will be created automatically if it does not
    already exist.

    2. When opening a file for write access it is created with a
    temporary name (with same same extension) and if there are no errors it is
    renamed automatically when closed. In the case of errors the
    default is to delete the temporary file (set delete_temp_on_error
    to False to keep the temporary file).

    The use of a temporary file is automatically disabled when the mode
    includes 'r', 'x', 'a', or '+'. It can be prevented manually by
    setting temp_ext to an empty string.

    Example use

        with smart_open('/tmp/dir/file.txt', 'w') as f:
            f.write('some text')

    """

    def __init__(self,
                 filename,
                 mode='r',
                 use_temp=None,
                 delete_temp_on_error=True,
                 chmod=None):
        # Modes which rely on an existing file should not change the name
        cannot_use_temp = 'r' in mode or 'x' in mode or 'a' in mode or '+' in mode

        self.filename = filename
        self.mode = mode
        self.delete_temp_on_error = delete_temp_on_error
        self.chmod = chmod
        self.file = None

        if use_temp and cannot_use_temp:
            raise ValueError('cannot use temporary file with mode "%s"' % mode)
        elif use_temp is None:
            self.use_temp = not cannot_use_temp
        else:
            self.use_temp = use_temp

    def __enter__(self):
        d = os.path.dirname(self.filename)
        if (not os.path.exists(d) and
            ('w' in self.mode or 'x' in self.mode
             or 'a' in self.mode or '+' in self.mode)):
            logger.debug('creating directory %s', d)
            os.makedirs(d)
        if self.use_temp:
            s = os.path.splitext(self.filename)[1]
            d = os.path.dirname(self.filename)
            self.file = tempfile.NamedTemporaryFile(self.mode, suffix=s, dir=d, delete=False)
        else:
            self.file = open(self.filename, self.mode)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        if self.file is not None:
            if not self.file.closed:
                self.file.close()

            if exc_type is None:
                if self.chmod:  # Deliberately not applied when chmod == 0
                    os.chmod(self.file.name, self.chmod)
                if self.file.name != self.filename:
                    logger.debug('renaming %s to %s',
                                 self.file.name, self.filename)
                    # For better compatibility with Microsoft Windows use os.replace() if available,
                    # otherwise use os.rename()
                    getattr(os, 'replace', os.rename)(self.file.name, self.filename)
            elif self.delete_temp_on_error:
                os.remove(self.file.name)


def atomic_symlink(src, dst):
    """Create or update a symlink atomically.

    The symlink is created or updated so that the operation appears atomic at the filesystem level."""
    dst_dir = os.path.dirname(dst)
    tmp = None
    try:
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        tmp = tempfile.mktemp(dir=dst_dir)
        os.symlink(src, tmp)
        os.rename(tmp, dst)
    except:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
        raise


logger = logging.getLogger(__name__)
