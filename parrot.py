import json
import logging
import mistune
import os
import os.path
import time

from PyQt5 import QtCore
from PyQt5.QtCore import QDir, pyqtSignal, QFile, QTimer, QUrl, QThread
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QHBoxLayout, QFrame,
                             QLabel, QLineEdit, QTextBrowser,
                             QVBoxLayout, QSplitter)
from PyQt5.QtWidgets import QListView, QStyleFactory
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.Qt import QDesktopServices
from PyQt5.QtGui import QPainter, QBrush
from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer
from whoosh.analysis import StandardAnalyzer, NgramFilter
from whoosh.fields import *
from whoosh.index import create_in
from whoosh.qparser import MultifieldParser
from whoosh.highlight import ContextFragmenter, SentenceFragmenter

from md_parser import AstBlockParser
from search import Overlay


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
            qp.begin(self)
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
            qp.begin(self)
            w = 1
            r = QRect(0, self.height()-w, self.width(), w)
            qp.fillRect(r, QBrush(QtCore.Qt.red))
            qp.end()
        self.update()


class IndexWorker(QThread):
    op = pyqtSignal(int)
    def __init__(self, parent = None):
        QThread.__init__(self, parent)

    def begin(self, writer, data):
        self.writer = writer
        self.data = data
        self.start()

    def run(self):
        for file_index, (filename, topic) in enumerate(sorted(self.data.items(), key=lambda k: k[1]["title"])):
            for part_index, part in enumerate(topic["content"]):
                self.writer.add_document(
                    file_index=file_index,
                    part_index=part_index,
                    title="",
                    _stored_title=part["title"],
                    content=part["content"]
                )
                self.writer.add_document(
                    file_index=file_index,
                    part_index=part_index,
                    title=part["title"]
                )
        self.writer.commit()


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
        self.usage_mode = "browse"
        self.initUI()

        # setup search index
        analyzer_typing = StandardAnalyzer() | NgramFilter(minsize=2, maxsize=8)
        schema = Schema(
            title=TEXT(stored=True, analyzer=analyzer_typing),
            content=TEXT(stored=True, analyzer=analyzer_typing),
            file_index=STORED,
            part_index=STORED,
            tags=KEYWORD)
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        self.ix = create_in("indexdir", schema)

        # setup GUI
        self.config = self.load_config()
        self.old_sizes = self.splitter.sizes()
        self.parent().resize(*self.config["window_size"])

        if self.data:
            self.list1.setCurrentRow(0)

        self.overlay = Overlay(self)
        self.overlay.hide()
        self.setObjectName("mainframe")

        self.setFocusPolicy(Qt.StrongFocus)

    def indexing_finished(self):
        self.finder.setEnabled(True)
        self.searcher = self.ix.searcher()
        self.parent().statusBar().showMessage('ready')
        self.finder.setText("")

    def start_indexing(self):
        self.parent().statusBar().showMessage('indexing...')
        self.finder.setText("indexing...")
        self.finder.setEnabled(False)

        self.thread = IndexWorker()
        self.thread.finished.connect(self.indexing_finished)
        writer = self.ix.writer()
        self.thread.begin(writer, self.data)

    # immediately before they are shown
    def showEvent(self, event):
        self.old_sizes = self.splitter.sizes()
        self.overlay.setGeometry(QRect(self.finder.pos() + self.finder.rect().bottomLeft(), QSize(400, 200)))
        QTimer.singleShot(50, self.start_indexing)

    def goto_result(self):
        self.overlay.hide()
        self.finder.setText("")

        file_index, part_index = self.overlay.get_selected_indices()
        self.list1.setCurrentRow(file_index)
        self.list_parts.setCurrentRow(part_index)
        self.view1.setFocus()

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

    def main_focused(self, *_):
        """hides the search result overlay"""
        self.overlay.hide()

    def file_dclick(self, item):
        """opens the file with an external editor"""
        current_path = QDir.currentPath()
        filename = self.list1.itemWidget(item).get_filename()
        QDesktopServices.openUrl(QUrl(u"{}/data/{}".format(current_path, filename)))

    def initUI(self):
        allLayout = QVBoxLayout()

        top_controls = QWidget()
        layout = QHBoxLayout()

        self.finder = MySearchBar(self)
        self.finder.setObjectName("finder")
        layout.addWidget(self.finder)
        layout.setContentsMargins(5, 0, 5, 0)
        top_controls.setLayout(layout)

        self.list1 = IndicatorList()
        self.list1.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list1.setObjectName("file_list")
        self.list1.itemDoubleClicked.connect(self.file_dclick)

        self.fill_filename_list()

        self.list1.currentItemChanged.connect(self.file_selected)

        self.list_parts = IndicatorList()
        self.list_parts.setObjectName("part_list")
        self.list_parts.model().rowsInserted.connect(self.list_parts_rows_ins)
        self.list_parts.currentItemChanged.connect(self.list_parts_selected)

        self.list1.setContentsMargins(0, 0, 0, 0)
        self.list1.setMinimumWidth(30)

        left_max_width = 100
        self.list1.setMaximumWidth(left_max_width)
        self.list1.setResizeMode(QListView.Adjust)

        # self.view1 = QTextBrowser()
        self.view1 = IndicatorTextBrowser()
        self.view1.setObjectName("preview")

        self.list1.focusInEvent = self.main_focused
        self.list_parts.focusInEvent = self.main_focused
        self.view1.focusInEvent = self.main_focused

        self.splitter = QSplitter()
        self.splitter.setObjectName("splitter_lists_working")
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.list1)
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

    @staticmethod
    def highlight_keyword(text, keyword, len_max=60):
        keyword_sane = keyword.strip().lower()
        i_begin = text.lower().find(keyword_sane)
        i_end = i_begin + len(keyword_sane)

        # max length the text before and after the keyword can have
        len_context = (len_max - len(keyword_sane)) // 2

        part_highlight = '<span style="color: rgb(0,0,0); background-color: rgba(255,231,146,220);">{}</span>'.format(
            text[i_begin:i_end])

        # trim context strings if too long
        part_start = text[:i_begin]
        if len(part_start) > len_context:
            part_start = "..." + part_start[len(part_start)-len_context:]

        part_end = text[i_end:]
        if len(part_end) > len_context:
            part_end = part_end[:len_context] + "..."

        return part_start + part_highlight + part_end

    def search_with(self, text):
        parser = MultifieldParser(["title", "content"], self.ix.schema)
        query = parser.parse("{}".format(text))
        results = self.searcher.search(query)

        search_results = []
        for i, result in enumerate(results):
            if "content" in result:
                high_content = self.highlight_keyword(result["content"], text).replace("\n", "<br>")
                html = "<b>{}</b><br>{}".format(result["title"], high_content)
            else:
                # highl_title = result.highlights("title", text=result["title"])
                highl_title = self.highlight_keyword(result["title"], text, len_max=80)
                html = "<h4>{}</h4>".format(highl_title)
            html_style = "<style>color: red</style>"
            search_results.append((html_style+html, result["file_index"], result["part_index"]))

        self.overlay.set_search_results(search_results)
        self.overlay.update_visibility()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self.finder.hasFocus():
                self.view1.setFocus()
            else:
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
    # app.focusChanged.connect(f1)
    # app = Appp(sys.argv)
    # app.focusChanged = f1
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
