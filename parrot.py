import json
import logging
import mistune
import os
import os.path

from PyQt5 import QtCore
from PyQt5.QtCore import QDir, pyqtSignal, QFile, QTimer
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QHBoxLayout, QFrame,
                             QLabel, QLineEdit, QTextBrowser,
                             QVBoxLayout, QSplitter)
from PyQt5.QtWidgets import QListView, QStyleFactory
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer
from whoosh.analysis import StandardAnalyzer, NgramFilter
from whoosh.fields import *
from whoosh.index import create_in
from whoosh.qparser import MultifieldParser

from md_parser import AstBlockParser
from search import Overlay, Result_formatter_simple


class IdRenderer(mistune.Renderer):
    def header(self, text, level, raw):
        return '<h{0} id="{1}">{1}</h{0}>\n'.format(level, text)


class FileListItemWidget(QWidget):
    def __init__(self, title: str, filename, parent=None):
        super(FileListItemWidget, self).__init__(parent)

        self.real_parent = parent

        layout = QVBoxLayout()
        self.label_title = QLabel(title)
        self.label_filename = QLabel(filename)
        layout.addWidget(self.label_title)
        layout.addWidget(self.label_filename)
        self.label_title.setObjectName("file_list_title")
        self.label_filename.setObjectName("file_list_filename")
        layout.setAlignment(self.label_filename, Qt.AlignRight)
        layout.setContentsMargins(2, 0, 2, 2)
        layout.setSpacing(0)
        self.setLayout(layout)

    def get_title(self):
        return self.label_title.text()

    def get_filename(self):
        return self.label_filename.text()

    def set_modified(self, mod):
        self.label_title.setProperty("modified", mod)

        self.label_title.style().unpolish(self.label_title)
        self.label_title.style().polish(self.label_title)


class MySearchBar(QLineEdit):
    def __init__(self, parent):
        super(MySearchBar, self).__init__(parent)
        self.query_old = ""

    def keyPressEvent(self, ev):
        super().keyPressEvent(ev)
        length_threshold = 2
        length_criteria = len(self.text()) >= length_threshold
        if self.text() != self.query_old and length_criteria:
            self.parent().parent().search_with(self.text())

        # hide search overlay if search query is too short
        if not length_criteria:
            self.parent().parent().overlay.hide()

        self.query_old = self.text()


class MainWidget(QFrame):  # QDialog #QMainWindow
    msg = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        with open("preview_style.css") as file_style:
            self.preview_css_str = '<style type="text/css">{}</style>'.format(file_style.read())

        # markdown
        self.ast_generator = AstBlockParser()
        self.markdowner_simple = mistune.Markdown(renderer=IdRenderer())

        # stored data
        self.data = self.load_data()
        self.initUI()

        # setup search index
        analyzer_typing = StandardAnalyzer() | NgramFilter(minsize=2, maxsize=8)
        schema = Schema(
            title=TEXT(stored=True, analyzer=analyzer_typing),
            path=STORED,
            content=TEXT(stored=True, analyzer=analyzer_typing),
            tags=KEYWORD)
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        self.ix = create_in("indexdir", schema)

        # setup GUI
        self.config = self.load_config()
        # print("initUI done")
        self.old_sizes = self.splitter.sizes()
        self.parent().resize(*self.config["window_size"])

        if self.data:
            self.list1.setCurrentRow(0)

        self.overlay = Overlay(self)
        self.overlay.hide()
        self.setObjectName("mainframe")

        self.setFocusPolicy(Qt.StrongFocus)

    def index_search(self):
        self.parent().statusBar().showMessage('indexing...')
        writer = self.ix.writer()
        for filename, topic in self.data.items():
            for part in topic["content"]:
                writer.add_document(path=filename, content=part["content"])
                writer.add_document(path=filename, title=part["title"])
        writer.commit()
        self.parent().statusBar().showMessage('done')

    # immediately before they are shown
    def showEvent(self, event):
        self.old_sizes = self.splitter.sizes()
        self.overlay.setGeometry(QRect(self.finder.pos() + self.finder.rect().bottomLeft(), QSize(400, 200)))
        QTimer.singleShot(50, self.index_search)

    @staticmethod
    def load_config():
        config = {
            "window_size": [800, 400],
            "editor_font": "Source Code Pro",
            "editor_font_size": 10,
            "editor_font_size_section": 10
        }

        try:
            with open('config.json') as data_file:
                config.update(json.load(data_file))
        except FileNotFoundError:
            pass
        return config

    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)

    def load_file(self, filename):
        file = QFile("data/{}".format(filename))
        if not file.open(QtCore.QIODevice.ReadOnly):
            print("couldn't open file")
        stream = QtCore.QTextStream(file)
        stream.setCodec("UTF-8")
        content = stream.readAll()

        # built structure tree
        self.ast_generator.clear_ast()
        self.ast_generator.parse(mistune.preprocessing(content))
        entry = self.ast_generator.ast

        # add html code to tree nodes
        for i, lvl2 in enumerate(list(entry["content"])):
            content_markdown = "##{}\n{}".format(lvl2["title"], lvl2["content"])
            content_html = self.markdowner_simple(content_markdown)
            entry["content"][i]["html"] = self.preview_css_str + content_html
        return entry

    def load_data(self):
        return {fn: self.load_file(fn) for fn in QDir("data").entryList(["*.md"], QDir.Files)}

    def change_file_title(self, title_new):
        filename = self.list1.itemWidget(self.list1.currentItem()).get_filename()
        self.data[filename]["title"] = title_new
        # self.data[filename] = self.data.pop(filename)
        self.list1.clear()
        title_index_dict = self.fill_filename_list()
        self.list1.setCurrentRow(title_index_dict[title_new])

        # mark file with changed title as modified
        self.list1.itemWidget(self.list1.currentItem()).set_modified(True)

    def initUI(self):
        allLayout = QVBoxLayout()

        top_controls = QWidget()
        layout = QHBoxLayout()

        self.finder = MySearchBar(self)
        layout.addWidget(self.finder)
        layout.setContentsMargins(5, 0, 5, 0)
        top_controls.setLayout(layout)

        self.list1 = QListWidget(self)
        self.list1.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list1.setObjectName("file_list")

        self.fill_filename_list()

        self.list1.currentItemChanged.connect(self.file_selected)

        self.list_parts = QListWidget()
        self.list_parts.setObjectName("part_list")
        self.list_parts.model().rowsInserted.connect(self.list_parts_rows_ins)
        self.list_parts.currentItemChanged.connect(self.list_parts_selected)

        self.left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.list1)
        self.left_widget.setLayout(left_layout)
        self.left_widget.setMinimumWidth(30)
        # left_max_width = self.list1.sizeHintForColumn(0) + self.list1.frameWidth() * 2
        left_max_width = 100
        self.left_widget.setMaximumWidth(left_max_width)
        self.list1.setResizeMode(QListView.Adjust)

        self.view1 = QTextBrowser()
        self.view1.setObjectName("preview")

        self.splitter = QSplitter()
        self.splitter.setObjectName("splitter_lists_working")
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.list_parts)
        self.splitter.addWidget(self.view1)
        self.splitter.setSizes([80, 80, 100])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.splitterMoved.connect(self.splitter_moved)

        allLayout.addWidget(top_controls, stretch=0)
        allLayout.addWidget(self.splitter, stretch=1)
        allLayout.setContentsMargins(0, 5, 0, 0)
        self.setLayout(allLayout)

    def fill_filename_list(self):
        title_index_dict = {}
        for i, (filename, topic) in enumerate(sorted(self.data.items(), key=lambda k: k[1]["title"])):
            item_widget = FileListItemWidget(topic["title"], filename, self)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.list1.addItem(item)
            self.list1.setItemWidget(item, item_widget)
            title_index_dict[topic["title"]] = i
        return title_index_dict

    def splitter_moved(self, pos, handle_index):
        if handle_index == 1:
            moved_amount = self.splitter.sizes()[0] - self.old_sizes[0]
            if moved_amount != 0:
                old_state = self.splitter.blockSignals(True)
                pos_second_old = self.old_sizes[0] + self.old_sizes[1] + self.splitter.handleWidth()
                self.splitter.moveSplitter(pos_second_old + moved_amount, 2)
                self.splitter.blockSignals(old_state)

        self.old_sizes = self.splitter.sizes()

    def update_preview(self):
        print("update_preview()")
        filename = self.list1.itemWidget(self.list1.currentItem()).get_filename()
        html = self.data[filename]["content"][self.list_parts.currentRow()]["html"]
        self.view1.setHtml(html)

    def file_selected(self, list_widget_item):
        is_cleared = list_widget_item is None

        if not is_cleared:
            filename = self.list1.itemWidget(list_widget_item).get_filename()
            part_names = [part["title"] for part in self.data[filename]["content"]]

            self.list_parts.clear()
            self.list_parts.addItems(part_names)
            # max_width = self.list_parts.sizeHintForColumn(0) + self.list_parts.frameWidth() * 2
            max_width = 80
            # self.list_parts.setMaximumWidth(max_width)
            # self.list_parts.sizehint(max_width)
            # self.list_parts.setFixedWidth(max_width)
            self.list_parts.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def list_parts_rows_ins(self):
        if self.list_parts.count() > 0:
            self.list_parts.setCurrentRow(0)

    def list_parts_selected(self, curr, prev):
        filename = self.list1.itemWidget(self.list1.currentItem()).get_filename()
        # print(self.list1.itemWidget(self.list1.currentItem()).get_filename(), self.list1.itemWidget(curr).get_filename())
        if self.list_parts.currentRow() != -1:
            current_item = self.list_parts.currentItem()
            if current_item:
                source_string = self.data[filename]["content"][self.list_parts.currentRow()]["content"]

                # old_state = self.editor1.blockSignals(True)
                # self.editor1.setPlainText(source_string)
                self.update_preview()
                # self.editor1.blockSignals(old_state)

    def resizeEvent(self, e):
        if e.oldSize() != QSize(-1, -1):
            self.config["window_size"] = [self.parent().size().width(), self.parent().size().height()]

    def closeEvent(self, *args, **kwargs):
        self.save_config()

    def search_with(self, text):
        print("search_with()")
        with self.ix.searcher() as searcher:
            parser = MultifieldParser(["title", "content"], self.ix.schema)
            # parser.add_plugin(FuzzyTermPlugin())
            query = parser.parse("{}".format(text))
            results = searcher.search(query, terms=True)
            results.formatter = Result_formatter_simple()

            search_results = []
            for i, result in enumerate(results):
                if "title" in result:
                    high = result.highlights("title", text=result["title"])
                    high = "<h2>{}</h2>".format(high)
                else:
                    high = result.highlights("content", text=result["content"])
                print(i, result, high)
                search_results.append(high)

            # search_results = [res.highlights("content") for res in results]
            self.overlay.set_search_results(search_results)
            visible = text and len(results) > 0
            self.overlay.setVisible(visible)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finder.setFocus()


class Example(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.main_widget = MainWidget(self)
        self.setCentralWidget(self.main_widget)

        self.statusbar = self.statusBar()
        self.main_widget.msg.connect(self.statusbar.showMessage)
        with open("style.qss") as file_style:
            self.setStyleSheet(file_style.read())
        # self.statusBar().showMessage('Ready')
        self.statusBar().setMaximumHeight(18)

        self.setWindowTitle("Carrie")
        self.setStyle(QStyleFactory.create("fusion"))
        self.show()

    def closeEvent(self, *args, **kwargs):
        self.main_widget.closeEvent(*args, **kwargs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()

    # print("QtGui.QStyleFactory.keys()", QStyleFactory.keys())

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path="data", recursive=True)
    observer.start()
    status = app.exec_()
    observer.stop()
    observer.join()
    sys.exit(status)
