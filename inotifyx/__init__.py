# Copyright (c) 2005 Manuel Amador
# Copyright (c) 2009-2011 Forest Bond
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""
inotifyx is a simple Python binding to the Linux inotify file system event
monitoring API.

Generally, usage is as follows:

>>> fd = init()
>>> try:
...     wd = add_watch(fd, '/path', IN_ALL_EVENTS)
...     events = get_events(fd)
...     rm_watch(fd, wd)
... finally:
...     os.close(fd)
"""
import ctypes
import os
import selectors

# Constants from include/sys/inotify.h
# Supported events suitable for MASK parameter of INOTIFY_ADD_WATCH.
IN_ACCESS = 0x00000001  # File was accessed.
IN_MODIFY = 0x00000002  # File was modified.
IN_ATTRIB = 0x00000004  # Metadata changed.
IN_CLOSE_WRITE = 0x00000008  # Writtable file was closed.
IN_CLOSE_NOWRITE = 0x00000010  # Unwrittable file closed.
IN_CLOSE = 0x00000018  # Close.
IN_OPEN = 0x00000020  # File was opened.
IN_MOVED_FROM = 0x00000040  # File was moved from X.
IN_MOVED_TO = 0x00000080  # File was moved to Y.
IN_MOVE = 0x000000c0  # Moves.
IN_CREATE = 0x00000100  # Subfile was created.
IN_DELETE = 0x00000200  # Subfile was deleted.
IN_DELETE_SELF = 0x00000400  # Self was deleted.
IN_MOVE_SELF = 0x00000800  # Self was moved.
# Events sent by the kernel.
IN_UNMOUNT = 0x00002000  # Backing fs was unmounted.
IN_Q_OVERFLOW = 0x00004000  # Event queued overflowed.
IN_IGNORED = 0x00008000  # File was ignored.
#  Special flags.
IN_ONLYDIR = 0x01000000  # Only watch the path if it is a directory.
IN_DONT_FOLLOW = 0x02000000  # Do not follow a sym link.
IN_EXCL_UNLINK = 0x04000000  # Exclude events on unlinked objects.
IN_MASK_CREATE = 0x10000000  # Only create watches.
IN_MASK_ADD = 0x20000000  # Add to the mask of an already existing watch.
IN_ISDIR = 0x40000000  # Event occurred against dir.
IN_ONESHOT = 0x80000000  # Only send event once.
# All events which a program can wait on.
IN_ALL_EVENTS = (IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | IN_CLOSE_NOWRITE | IN_OPEN | IN_MOVED_FROM
                 | IN_MOVED_TO | IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF)
constants = {attr: value for attr, value in globals().items() if attr.startswith('IN_')}

ctypes.cdll.LoadLibrary('libc.so.6')
libc = ctypes.CDLL('libc.so.6', use_errno=True)


class _InotifyEvent(ctypes.Structure):
    _fields_ = [
        ('wd', ctypes.c_int),
        ('mask', ctypes.c_uint32),
        ('cookie', ctypes.c_uint32),
        ('len', ctypes.c_uint32),
    ]


NAME_MAX = 255  # From include/linux/limits.h
BUF_LEN = constants['BUF_LEN'] = max(ctypes.sizeof(_InotifyEvent) + NAME_MAX + 1, 32768)


class InotifyEvent:
    """
    InotifyEvent(wd, mask, cookie, name)

    A representation of the inotify_event structure.  See the inotify
    documentation for a description of these fields.
    """

    wd = None
    mask = None
    cookie = None
    name = None

    def __init__(self, wd, mask, cookie, name):
        self.wd = wd
        self.mask = mask
        self.cookie = cookie
        self.name = name

    def __str__(self):
        return '%s: %s' % (self.wd, self.get_mask_description())

    def __repr__(self):
        return '%s(%r, %r, %r, %r)' % (type(self).__name__, self.wd, self.mask, self.cookie, self.name)

    def get_mask_description(self):
        """
        Return an ASCII string describing the mask field in terms of
        bitwise-or'd IN_* constants, or 0.  The result is valid Python code
        that could be eval'd to get the value of the mask field.  In other
        words, for a given event:

        >>> from inotifyx import *
        >>> assert (event.mask == eval(event.get_mask_description()))
        """
        parts = []
        for name, value in constants.items():
            overlap = self.mask & value
            if overlap and not overlap ^ value:
                parts.append(name)
        if parts:
            return '|'.join(parts)
        return '0'


class Inotify:
    def __init__(self):
        self.fd = init()
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.fd, selectors.EVENT_READ)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def add_watch(self, path, mask=IN_ALL_EVENTS):
        return add_watch(self.fd, path, mask)

    def close(self):
        self.selector.close()
        # The watches are automatically removed when closing the file descriptor.
        os.close(self.fd)

    def get_events(self, timeout=None):
        yield from get_events_iter(self.fd, self.selector, timeout=timeout)

    def rm_watch(self, wd):
        return rm_watch(self.fd, wd)


def add_watch(fd, path, mask=IN_ALL_EVENTS):
    """
    Add a watch for path and return the watch descriptor.
    fd should be the file descriptor returned by init.
    If left unspecified, mask defaults to IN_ALL_EVENTS.
    See the inotify documentation for details.
    """
    watch_descriptor = libc.inotify_add_watch(fd, path.encode(), ctypes.c_uint32(mask))
    if watch_descriptor < 0:
        raise IOError(os.strerror(ctypes.get_errno()))
    return watch_descriptor


def get_events(fd, timeout=None):
    """
    Return a list of InotifyEvent instances representing events read from
    inotify.  If timeout is None, this will block forever until at least one
    event can be read.  Otherwise, timeout should be an integer or float
    specifying a timeout in seconds.  If get_events times out waiting for
    events, an empty list will be returned.  If timeout is zero, get_events
    will not block.
    """
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        return list(get_events_iter(fd, selector, timeout=timeout))


def get_events_iter(fd, selector, timeout=None):
    offset = ctypes.sizeof(_InotifyEvent)
    for key, mask in selector.select(timeout=timeout):
        buf = os.read(fd, BUF_LEN)
        while buf:
            event = _InotifyEvent.from_buffer_copy(buf[:offset])
            if event.len > 0:
                name = buf[offset:offset + event.len]
                yield InotifyEvent(event.wd, event.mask, event.cookie, name.rstrip(b'\x00').decode() or None)
            else:
                yield InotifyEvent(event.wd, event.mask, event.cookie, None)
            buf = buf[offset + event.len:]


def init():
    """
    Initialize an inotify instance and return the associated file
    descriptor.  The file descriptor should be closed via os.close
    after it is no longer needed.
    """
    fd = libc.inotify_init()
    if fd < 0:
        raise IOError(os.strerror(ctypes.get_errno()))
    return fd


def rm_watch(fd, wd):
    """
    Remove the watch associated with watch descriptor wd.
    fd should be the file descriptor returned by init
    """
    retvalue = libc.inotify_rm_watch(fd, wd)
    if retvalue < 0:
        raise IOError(os.strerror(ctypes.get_errno()))
    return retvalue


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        sys.stderr.write('usage: inotify path [path ...]')
        sys.exit(1)
    paths = sys.argv[1:]
    wd_to_path = {}
    with Inotify() as inotify:
        for path in paths:
            wd = inotify.add_watch(path)
            wd_to_path[wd] = path
        try:
            while True:
                for event in inotify.get_events():
                    path = wd_to_path[event.wd]
                    parts = [event.get_mask_description()]
                    if event.name:
                        parts.append(event.name)
                    print('%s: %s' % (path, ' '.join(parts)))
        except KeyboardInterrupt:
            pass
