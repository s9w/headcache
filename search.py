import whoosh
import whoosh.highlight
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListView, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem


class SearchresultWidget(QWidget):
    def __init__(self, label_text, file_index, part_index, parent=None):
        super(SearchresultWidget, self).__init__(parent)
        allLayout = QVBoxLayout()

        self.label = QLabel("test")
        self.label.setObjectName("inner_label")
        # self.label.setStyleSheet("#match{background-color: red;}")
        allLayout.addWidget(self.label)

        allLayout.setContentsMargins(5,5,5,5)
        self.setLayout(allLayout)

        self.label.setText(label_text)
        self.file_index = file_index
        self.part_index = part_index


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
        # self.setFocusPolicy(Qt.ClickFocus)

        # self.setAttribute(Qt.WA_ShowWithoutActivating)
        # self.l1.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)
        # self.l1.setFocusPolicy(Qt.NoFocus)
        # print(parent.finder)
        # self.setFocusProxy(parent.finder)

    def item_dclick(self, item):
        self.parent().goto_result()

    def get_selected_indices(self):
        item_widget = self.l1.itemWidget(self.l1.currentItem())
        return item_widget.file_index, item_widget.part_index

    def update_visibility(self, other_criteria=True):
        if self.l1.count() > 0 and other_criteria:
            self.show()
        else:
            self.hide()


    def set_search_results(self, items):
        self.l1.clear()
        for item_text, file_index, part_index in items:
            item_widget = SearchresultWidget(item_text, file_index, part_index)  # parent)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.l1.addItem(item)
            self.l1.setItemWidget(item, item_widget)
        self.l1.setCurrentRow(0)
