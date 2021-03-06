import json
import logging
import mistune
# import sys
# sys.path.append("c:/dropbox/headcache")
# sys.path.append("c:/dropbox/headcache/headcache")
import os
import os.path

import watchdog.observers
from PyQt5 import QtCore
from PyQt5.Qt import QDesktopServices, QIcon, QPixmap, QColor
from PyQt5.QtCore import QDir, pyqtSignal, QFile, QFileInfo, QTimer, QUrl
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QHBoxLayout, QFrame,
                             QLabel, QVBoxLayout, QSplitter)
from PyQt5.QtWidgets import QListView, QStyleFactory
from PyQt5.QtWidgets import QListWidgetItem

from .md_parser import AstBlockParser, BadFormatError
# from md_parser import AstBlockParser

from .search import Overlay, IndexWorker
# from search import Overlay, IndexWorker

from .ui_components import SearchBar, IndicatorList, IndicatorTextBrowser
# from ui_components import SearchBar, IndicatorList, IndicatorTextBrowser

from whoosh.analysis import StandardAnalyzer, NgramFilter
from whoosh.fields import *
from whoosh.index import create_in
from whoosh.qparser import MultifieldParser

from .file_watcher import FileChangeWatcher
# from file_watcher import FileChangeWatcher
import pkg_resources



class IdRenderer(mistune.Renderer):
    def header(self, text, level, raw):
        return '<h{0} id="{1}">{1}</h{0}>\n'.format(level, text)


class FileListItemWidget(QWidget):
    def __init__(self, title: str, filename, parent=None):
        super().__init__(parent)

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


class MainWidget(QFrame):  # QDialog #QMainWindow
    msg = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        with open(pkg_resources.resource_filename("headcache", 'preview_style.css')) as file_style:
            self.preview_css_str = '<style type="text/css">{}</style>'.format(file_style.read())

        # markdown
        self.ast_generator = AstBlockParser()
        self.markdowner_simple = mistune.Markdown(renderer=IdRenderer())

        # stored data
        self.data = self.load_data()
        self.usage_mode = "browse"
        self.initUI()

        self.config = self.load_config()

        # setup search index
        analyzer_typing = StandardAnalyzer() | NgramFilter(minsize=2, maxsize=8)
        schema = Schema(
            title=TEXT(stored=True, analyzer=analyzer_typing, field_boost=self.config["search_title_weight"]),
            content=TEXT(stored=True, analyzer=analyzer_typing, field_boost=self.config["search_text_weight"]),
            time=STORED,
            path=ID(stored=True),
            tags=KEYWORD)
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        self.ix = create_in("indexdir", schema)

        # setup GUI

        self.old_sizes = self.splitter.sizes()
        self.parent().resize(*self.config["window_size"])

        if self.data:
            self.list1.setCurrentRow(0)
            self.list1.setFocus()

        self.overlay = Overlay(self)
        self.overlay.hide()
        self.setObjectName("mainframe")

        self.setFocusPolicy(Qt.StrongFocus)

        self.fileWatcher = watchdog.observers.Observer()
        watcher = FileChangeWatcher()
        self.fileWatcher.schedule(watcher, path=os.getcwd(), recursive=False)
        watcher.signal_deleted.connect(self.file_deleted)
        watcher.signal_modified.connect(self.file_modified)
        watcher.signal_added.connect(self.file_added)
        self.fileWatcher.start()

    def remove_from_file_list(self, filename):
        found_items = self.list1.findItems(filename, Qt.MatchExactly)
        if len(found_items) != 1:
            raise RuntimeError("remove_from_file_list(fn={}}): {} found items".format(filename, len(found_items)))
        self.list1.takeItem(self.list1.row(found_items[0]))

    def file_added(self, filename):
        # update data
        try:
            self.data[filename] = self.load_file(filename)
        except BadFormatError as e:
            print(e)
            return

        self.add_file_to_list(filename, self.data[filename]["title"])
        self.list1.sortItems()

        # update index
        writer = self.ix.writer()
        topic = self.data[filename]
        for part in topic["content"]:
            writer.add_document(
                title="",
                _stored_title=part["title"],
                content=part["content"],
                time=topic["time"],
                path=filename
            )
            writer.add_document(
                title=part["title"],
                time=topic["time"],
                path=filename
            )
        writer.commit()
        self.searcher = self.ix.searcher()

    def file_modified(self, filename):
        # modified event is sometimes fired twice. prevent trouble
        if filename not in self.data:
            self.file_added(filename)
        title_old = self.data[filename]["title"]

        try:
            self.data[filename] = self.load_file(filename)
        except BadFormatError as e:
            print(e)
            self.file_deleted(filename)
            return
        title_new = self.data[filename]["title"]

        # change title in file list if changed
        if title_old and title_new != title_old:
            found_items = self.list1.findItems(filename, Qt.MatchExactly)
            if len(found_items) != 1:
                raise RuntimeError("file_modified(fn={}}): {} found items".format(filename, len(found_items)))
            self.list1.itemWidget(found_items[0]).label_title.setText(title_new)


        # update part list if active file was changed
        if self.list1.currentItem().text() == filename:
            old_index = self.list_parts.currentRow()
            self.update_part_list(filename)
            self.list_parts.setCurrentRow(old_index)


        # update index
        writer = self.ix.writer()
        deleted_count = writer.delete_by_term("path", filename)

        topic = self.data[filename]
        for part in topic["content"]:
            writer.add_document(
                title="",
                _stored_title=part["title"],
                content=part["content"],
                time=topic["time"],
                path=filename
            )
            writer.add_document(
                title=part["title"],
                time=topic["time"],
                path=filename
            )
        writer.commit()
        self.searcher = self.ix.searcher()

    def file_deleted(self, filename):
        # update index
        writer = self.ix.writer()
        deleted_count = writer.delete_by_term("path", filename)
        writer.commit()
        self.searcher = self.ix.searcher()

        # update internal data
        del self.data[filename]

        # remove from file list
        i = -1
        for i in range(self.list1.count()):
            item_fn = self.list1.itemWidget(self.list1.item(i)).get_filename()
            if item_fn == filename:
                break
        self.list1.takeItem(self.list1.row(self.list1.item(i)))

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

        filename, part_title = self.overlay.get_selected_indices()

        i_filename = -1
        for i_filename in range(self.list1.count()):
            item_fn = self.list1.itemWidget(self.list1.item(i_filename)).get_filename()
            if item_fn == filename:
                break
        self.list1.setCurrentRow(i_filename)

        items = self.list_parts.findItems(part_title, Qt.MatchExactly)
        self.list_parts.setCurrentItem(items[0])

        self.view1.setFocus()

    @staticmethod
    def load_config():
        config = {
            "window_size": [800, 400],
            "search_title_weight" : 3.0,
            "search_text_weight": 1.0
        }

        try:
            with open('headcache_config.json') as data_file:
                config.update(json.load(data_file))
        except FileNotFoundError:
            pass
        return config

    def save_config(self):
        with open("headcache_config.json", "w") as f:
            json.dump(self.config, f, indent=4)

    def load_file(self, filename):
        file = QFile("{}/{}".format(os.getcwd(), filename))
        if not file.open(QtCore.QIODevice.ReadOnly):
            print("couldn't open file")
        stream = QtCore.QTextStream(file)
        stream.setCodec("UTF-8")
        content = stream.readAll()

        # built structure tree
        self.ast_generator.clear_ast()
        self.ast_generator.parse(mistune.preprocessing(content), filename=filename)
        entry = self.ast_generator.ast
        entry["time"] = QFileInfo(file).lastModified().toMSecsSinceEpoch()

        # add html code to tree nodes
        for i, lvl2 in enumerate(list(entry["content"])):
            content_markdown = "##{}\n{}".format(lvl2["title"], lvl2["content"])
            content_html = self.markdowner_simple(content_markdown)
            entry["content"][i]["html"] = self.preview_css_str + content_html
        return entry

    def load_data(self):
        data = {}
        for filename in QDir(os.getcwd()).entryList(["*.md"], QDir.Files):
            try:
                entry = self.load_file(filename)
                data[filename] = entry
            except BadFormatError as e:
                print(e)
                continue
        return data
        # return {fn: self.load_file(fn) for fn in (QDir(os.getcwd()).entryList(["*.md"], QDir.Files))}

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
        QDesktopServices.openUrl(QUrl(u"{}/{}".format(current_path, filename)))

    def initUI(self):
        allLayout = QVBoxLayout()

        top_controls = QWidget()
        layout = QHBoxLayout()

        self.finder = SearchBar(self)
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
        self.view1.setOpenExternalLinks(True)
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

    def add_file_to_list(self, filename, title):
        item = QListWidgetItem(filename, parent=self.list1)
        item_widget = FileListItemWidget(title, filename)
        item.setSizeHint(item_widget.sizeHint())
        self.list1.addItem(item)
        self.list1.setItemWidget(item, item_widget)

    def fill_filename_list(self):
        title_index_dict = {}
        for i, (filename, topic) in enumerate(sorted(self.data.items(), key=lambda k: k[1]["title"])):
            self.add_file_to_list(filename, topic["title"])
            title_index_dict[topic["title"]] = i
        self.list1.sortItems()
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

    def update_part_list(self, filename):
        part_names = [part["title"] for part in self.data[filename]["content"]]
        self.list_parts.clear()
        self.list_parts.addItems(part_names)
        self.list_parts.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def file_selected(self, list_widget_item):
        is_cleared = list_widget_item is None

        if not is_cleared:
            filename = self.list1.itemWidget(list_widget_item).get_filename()
            self.update_part_list(filename)

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
        self.fileWatcher.stop()
        self.fileWatcher.join()
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
            search_results.append((html_style+html, result["path"], result["title"]))

        self.overlay.set_search_results(search_results)
        self.overlay.update_visibility()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self.finder.hasFocus():
                self.view1.setFocus()
            else:
                self.finder.setFocus()


class MainFrame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.main_widget = MainWidget(self)
        self.setCentralWidget(self.main_widget)

        self.statusbar = self.statusBar()
        self.main_widget.msg.connect(self.statusbar.showMessage)
        # with open("style.qss") as file_style:
        with open(pkg_resources.resource_filename("headcache", 'style.qss')) as file_style:
            self.setStyleSheet(file_style.read())
        # self.statusBar().showMessage('Ready')
        self.statusBar().setMaximumHeight(18)

        self.setWindowTitle("headcache")
        self.setStyle(QStyleFactory.create("fusion"))
        pixmap = QPixmap(1,1)
        pixmap.fill()
        self.setWindowIcon(QIcon(pixmap))
        self.show()

    def closeEvent(self, *args, **kwargs):
        self.main_widget.closeEvent(*args, **kwargs)


def main():
    # print("argv", sys.argv)
    app = QApplication(sys.argv)
    ex = MainFrame()

    # print("QtGui.QStyleFactory.keys()", QStyleFactory.keys())

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    status = app.exec_()

    sys.exit(status)


if __name__ == '__main__':
    main()
