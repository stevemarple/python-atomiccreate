"""Create files and symbolic links in a way that appears to be an atomic file-system operation.

It is sometimes useful that files and symbolic links are created with the intermediate write operations hidden.
Temporary files and symbolic links are used and the final update operation is atomic.
"""

import errno
import logging
import os
import tempfile

__author__ = 'Steve Marple'
__version__ = '0.3.0'
__license__ = 'MIT'


class smart_open:
    """A smarter way to open files for writing.

    This class mimics the behaviour of::

        with open(filename) as handle:

    but with two additional benefits:

    1.  When opening a file for write access (including appending) the
        parent directory will be created automatically if it does not
        already exist.

    2.  When opening a file for write access it is created with a temporary
        name (with a .tmp extension) and if there are no errors it is renamed automatically
        when closed. In the case of errors the default is to delete the temporary file,
        to keep the temporary file call :py:func:`smart_open` with ``delete_temp_on_error=False``.
        The temporary extension can be overridden with the ``temp_ext`` parameter.

    The use of a temporary file is automatically disabled when the mode
    includes ``'r'``, ``'x'``, ``'a'``, or ``'+'``. It can be prevented manually by calling :py:func:`smart_open`
    with ``use_temp=False``. When a temporary file is used it will be
    deleted automatically if an exception occurs; this behaviour can be prevented by calling
    with ``delete_temp_on_error=False``.

    For security reasons the temporary files are created with restricted read and write permissions.
    To maintain the atomic behaviour do not call :py:func:`os.chmod` after :py:func:`smart_open`, instead pass
    the appropriate file mode permissions with ``chmod=perms``.

    Example use::

        with smart_open('/tmp/dir/file.txt', 'w') as f:
            f.write('some text')

    """

    def __init__(self,
                 filename,
                 mode='r',
                 use_temp=None,
                 delete_temp_on_error=True,
                 chmod=None,
                 temp_ext='.tmp'):
        # Modes which rely on an existing file should not change the name
        cannot_use_temp = 'r' in mode or 'x' in mode or 'a' in mode or '+' in mode

        self.filename = filename
        self.mode = mode
        self.delete_temp_on_error = delete_temp_on_error
        if chmod is None:
            # Must set umask to find current umask
            current_umask = os.umask(0)
            os.umask(current_umask)
            self.chmod = (~current_umask & 0o666)  # No execute, read and write as umask allows
        else:
            self.chmod = chmod

        self.file = None
        self.temp_ext = temp_ext

        if use_temp and cannot_use_temp:
            raise ValueError('cannot use temporary file with mode "%s"' % mode)
        elif use_temp is None:
            self.use_temp = not cannot_use_temp
        else:
            self.use_temp = use_temp

    def __enter__(self):
        d = os.path.dirname(self.filename)
        if (d and not os.path.exists(d) and
            ('w' in self.mode or 'x' in self.mode
             or 'a' in self.mode or '+' in self.mode)):
            logger.debug('creating directory %s', d)
            os.makedirs(d)
        if self.use_temp:
            d = os.path.dirname(self.filename)
            self.file = tempfile.NamedTemporaryFile(self.mode, suffix=self.temp_ext, dir=d, delete=False)
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
    """Create or update a symbolic link atomically.

    This function is similar to :py:func:`os.symlink` but will update a symlink atomically."""

    dst_dir = os.path.dirname(dst)
    tmp = None
    max_tries = getattr(os, 'TMP_MAX', 10000)

    try:
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for n in range(max_tries):
            try:
                # mktemp is described as being unsafe. That is not true in this case since symlink is an
                # atomic operation at the file system level; if some other processes creates a file with
                # 'our' name then symlink will fail.
                tmp = tempfile.mktemp(dir=dst_dir)
                os.symlink(src, tmp)
                logger.debug('created symlink %s', tmp)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    continue  # Someone else grabbed the temporary name first
                else:
                    raise
            logger.debug('renaming %s to %s', tmp, dst)
            os.rename(tmp, dst)
            return
    except:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
        raise
    raise IOError(errno.EEXIST, 'No usable temporary file name found')


logger = logging.getLogger(__name__)
