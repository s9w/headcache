from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QBrush
from PyQt5.QtWidgets import QLineEdit, QListWidget, QTextBrowser


class SearchBar(QLineEdit):
    def __init__(self, parent):
        super(SearchBar, self).__init__(parent)
        self.query_old = ""

    def mousePressEvent(self, a0):
        if a0.button() == Qt.LeftButton:
            self.parent().parent().usage_mode = "search"

    def keyPressEvent(self, ev):
        super().keyPressEvent(ev)

        # arrow keys are delegated to the result list
        if ev.key() in [Qt.Key_Up, Qt.Key_Down]:
            self.parent().parent().overlay.l1.keyPressEvent(ev)
            return

        elif ev.key() == Qt.Key_Return:
            self.parent().parent().goto_result()
            return

        # only search when query is long enough and different from last (not
        # just cursor changes)
        length_threshold = 2
        length_criteria = len(self.text()) >= length_threshold
        if self.text() != self.query_old and length_criteria:
            self.parent().parent().search_with(self.text())
        self.parent().parent().overlay.update_visibility(length_criteria)

        self.query_old = self.text()

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        length_threshold = 2
        length_criteria = len(self.text()) >= length_threshold
        self.parent().parent().overlay.update_visibility(length_criteria)


class IndicatorList(QListWidget):
    def __init__(self):
        super().__init__()
    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.hasFocus():
            qp = QPainter(self.viewport())
            w = 1
            r = QRect(0, self.height()-w, self.width(), w)
            qp.fillRect(r, QBrush(QtCore.Qt.red))
            qp.end()
        self.update()


class IndicatorTextBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()
    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.hasFocus():
            qp = QPainter(self.viewport())
            w = 1
            r = QRect(0, self.height()-w, self.width(), w)
            qp.fillRect(r, QBrush(QtCore.Qt.red))
            qp.end()
        self.update()