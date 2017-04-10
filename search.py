import whoosh
import whoosh.highlight
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListView, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem


class SearchresultWidget(QWidget):
    def __init__(self, parent=None):
        super(SearchresultWidget, self).__init__(parent)
        allLayout = QVBoxLayout()

        self.label = QLabel("test")
        self.label.setObjectName("inner_label")
        # self.label.setStyleSheet("#match{background-color: red;}")
        allLayout.addWidget(self.label)

        # allLayout.setContentsMargins(0,0,0,0)
        self.setLayout(allLayout)

    def set_text(self, text):
        self.label.setText(text)


class Overlay(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        allLayout = QVBoxLayout()

        self.l1 = QListWidget(self)
        self.l1.setObjectName("search_result_list")
        self.l1.setViewMode(QListView.ListMode)
        # self.l1.currentItemChanged.connect(self.f1click)
        self.l1.itemDoubleClicked.connect(self.item_dclick)
        allLayout.addWidget(self.l1)
        self.setLayout(allLayout)

        # self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setFocusPolicy(Qt.ClickFocus)

        # self.setAttribute(Qt.WA_ShowWithoutActivating)
        # self.l1.setAttribute(Qt.WA_ShowWithoutActivating)
        # self.setFocusPolicy(Qt.NoFocus)
        # self.l1.setFocusPolicy(Qt.NoFocus)
        # print(parent.finder)
        # self.setFocusProxy(parent.finder)

    def focusInEvent(self, ev):
        print("Overlay, focusInEvent")
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        print("Overlay, focusOutEvent")
        super().focusOutEvent(ev)

    def item_dclick(self, item):
        print("dclick", item)

    def goto_result(self):
        print("goto result")

    def update_visibility(self, show=True):
        if self.l1.count() > 0 and show:
            self.show()
        else:
            self.hide()


    def set_search_results(self, items):
        pass
        self.l1.clear()
        for item_text in items:
            item_widget = SearchresultWidget()  # parent)
            item_widget.set_text(item_text)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.l1.addItem(item)
            self.l1.setItemWidget(item, item_widget)
        self.l1.setCurrentRow(0)


class Result_formatter_simple(whoosh.highlight.Formatter):
    def __init__(self):
        pass

    def format_token(self, text, token, replace=False):
        ttext = whoosh.highlight.htmlescape(whoosh.highlight.get_text(text, token, replace), quote=False)
        return '<span style="background-color: rgba(150,0,0,150);">{}</span>'.format(ttext)