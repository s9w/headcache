import logging

from watchdog.events import FileSystemEventHandler
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class FileChangeWatcher(FileSystemEventHandler, QThread):
    signal_deleted = pyqtSignal(str)
    signal_modified = pyqtSignal(str)
    signal_added = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def on_moved(self, event):
        # super(LoggingEventHandler, self).on_moved(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Moved %s: from %s to %s", what, event.src_path,
                     event.dest_path)

    def on_created(self, event):
        # super(LoggingEventHandler, self).on_created(event)

        if not event.is_directory and event.src_path.endswith(".md"):
            filename = event.src_path.split(u"\\")[-1]
            self.signal_added.emit(filename)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            filename = event.src_path.split(u"\\")[-1]
            self.signal_deleted.emit(filename)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            filename = event.src_path.split(u"\\")[-1]
            self.signal_modified.emit(filename)
