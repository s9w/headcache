import json
import logging
import os
import os.path

import mistune
from PyQt5 import QtCore
from PyQt5.QtCore import QDir, pyqtSignal, QFile
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QHBoxLayout, QFrame,
                             QPlainTextEdit, QTextEdit, QLabel, QLineEdit, QPushButton, QTextBrowser,
                             QVBoxLayout, QSplitter, QButtonGroup, QToolButton, QSizePolicy)
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer
import whoosh
import whoosh.highlight
from whoosh.fields import *
from whoosh.index import create_in
from whoosh.qparser import QueryParser

from highlighter import Highlighter


class IdRenderer(mistune.Renderer):
    def header(self, text, level, raw):
        return '<h{0} id="{1}">{1}</h{0}>\n'.format(level, text)


class QCustomQWidget(QWidget):
    def __init__(self, parent=None):
        super(QCustomQWidget, self).__init__(parent)
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

        # self.l1 = QListView()
        # model = QStandardItemModel(self.l1)
        #
        # model.appendRow(QStandardItem("one"))
        # model.appendRow(QStandardItem("two"))
        # self.l1.setModel(model)
        # self.l1.setItemDelegate(HTMLDelegate())

        self.l1 = QListWidget(self)
        self.l1.setObjectName("search_result_list")
        self.l1.setViewMode(QListView.ListMode)
        allLayout.addWidget(self.l1)

        self.setLayout(allLayout)

    def add_search_results(self, items):
        self.l1.clear()
        for item_text in items:
            item_widget = QCustomQWidget()  # parent)
            item_widget.set_text(item_text)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.l1.addItem(item)
            self.l1.setItemWidget(item, item_widget)


class MainWidget(QFrame):  # QDialog #QMainWindow
    msg = pyqtSignal(str)
    # import QSciScintilla

    def __init__(self, parent):
        super().__init__(parent)

        # create index
        schema = Schema(title=TEXT(stored=True), path=STORED, content=TEXT(stored=True), tags=KEYWORD)
        if not os.path.exists("indexdir"):
            os.mkdir("indexdir")
        self.ix = create_in("indexdir", schema)
        self.writer = self.ix.writer()

        # markdown
        self.block_lexer = AstBlockParser()
        self.markdowner = mistune.Markdown(renderer=IdRenderer(), block=self.block_lexer)
        self.part_block_lexer = AstBlockParserPart()
        self.markdowner_simple = mistune.Markdown(renderer=IdRenderer(), block=self.part_block_lexer)

        # stored data
        self.data = self.load_data()

        # search index
        for topic in self.data:
            for part in topic["content"]:
                self.writer.add_document(path=topic["filename"], content=part["content"], title=part["title"])
        # self.writer.add_document(title="performance", content="something bold indeed", tags="tag1 tag2", path="cpp.md")
        # self.writer.add_document(title="memory", content="a thing about memory", path="cpp.md")
        # self.writer.add_document(title="conda", content="installing things", path="python.md")
        self.writer.commit()

        self.active_filename = ""
        self.active_part_name = ""
        self.active_part_index = None

        # setup GUI
        self.config = self.load_config()
        self.initUI()
        self.parent().resize(*self.config["window_size"])

        with open("preview_style.css") as file_style:
            self.preview_css_str = '<style type="text/css">{}</style>'.format(file_style.read())

        if self.data:
            self.list1.setCurrentRow(0)

        self.overlay = Overlay(self)
        self.overlay.hide()
        self.setObjectName("mainframe")

    def load_config(self):
        config = {
            "window_size": [800, 400],
            "editor_font": "Source Code Pro",
            "editor_font_size": 10,
            "editor_font_size_section": 14
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

    def load_data(self):
        data = []
        for filename in QDir("data").entryList(["*.md"], QDir.Files):
            file = QFile("data/{}".format(filename))
            if not file.open(QtCore.QIODevice.ReadOnly):
                print("couldn't open file")
            stream = QtCore.QTextStream(file)
            content = stream.readAll()
            self.block_lexer.clear_ast()
            html = self.markdowner(content)
            entry = self.block_lexer.ast
            entry["html"] = html
            entry["filename"] = filename
            data.append(entry)
        return data

    def initUI(self):
        allLayout = QVBoxLayout()

        self.top_controls = QWidget()
        layout = QHBoxLayout()
        button1 = QPushButton("reload")
        button1.clicked.connect(self.reload_changes)
        layout.addWidget(button1)

        button2 = QPushButton("search")
        button2.clicked.connect(self.click_search)
        layout.addWidget(button2)

        button_debug = QPushButton("debug")
        button_debug.clicked.connect(self.click_debug)
        layout.addWidget(button_debug)

        # mode buttons
        self.button_edit = QPushButton("E")
        self.button_both = QPushButton("EV")
        self.button_view = QPushButton("V")
        self.button_edit.clicked.connect(self.click_mode)
        self.button_both.clicked.connect(self.click_mode)
        self.button_view.clicked.connect(self.click_mode)
        self.button_edit.setCheckable(True)
        self.button_both.setCheckable(True)
        self.button_view.setCheckable(True)
        self.button_both.setChecked(True)
        self.bg = QButtonGroup()
        self.bg.addButton(self.button_edit)
        self.bg.addButton(self.button_both)
        self.bg.addButton(self.button_view)
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(self.button_edit)
        bg_layout.addWidget(self.button_both)
        bg_layout.addWidget(self.button_view)
        bg_layout.setSpacing(0)
        layout.addLayout(bg_layout)

        self.finder = QLineEdit()
        layout.addWidget(self.finder)
        layout.setContentsMargins(0,0,0,0)
        self.top_controls.setLayout(layout)

        self.list1 = QListWidget()
        self.list1.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list1.setObjectName("file_list")

        for topic in self.data:
            list_item = QListWidgetItem(topic["title"])
            list_item.setFlags(list_item.flags() | Qt.ItemIsEditable)
            self.list1.addItem(list_item)

        self.list1.currentItemChanged.connect(self.list_files_changed)

        self.list_parts = QListWidget()
        self.list_parts.setObjectName("part_list")
        self.list_parts.model().rowsInserted.connect(self.list_parts_rows_ins)
        self.list_parts .currentItemChanged.connect(self.list_parts_selected)

        self.button_left_add = QPushButton("+")
        self.button_left_add.setMaximumWidth(self.button_left_add.sizeHint().height())

        self.left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.addWidget(self.list1)
        left_layout.addWidget(self.button_left_add, Qt.AlignRight)
        left_layout.setAlignment(self.button_left_add, Qt.AlignHCenter)
        self.left_widget.setLayout(left_layout)
        self.left_widget.setMinimumWidth(30)
        # left_max_width = self.list1.sizeHintForColumn(0) + self.list1.frameWidth() * 2
        left_max_width = 100
        self.left_widget.setMaximumWidth(left_max_width)

        self.editor1 = QPlainTextEdit()
        self.highlighter = Highlighter(self.editor1.document())
        self.highlighter.set_section_size(self.config["editor_font_size_section"])
        self.editor1.setObjectName("editor")
        self.editor1.textChanged.connect(self.editor_changed)
        # self.editor1.modificationChanged.connect(self.editor_changed)
        # print("doc", self.editor1.document())
        # self.editor1.document().contentsChanged.connect(self.editor_changed)

        self.view1 = QTextBrowser()
        self.view1.setObjectName("preview")
        font = QFont()
        font.setFamily(self.config["editor_font"])
        font.setFixedPitch(True)
        font.setPointSize(self.config["editor_font_size"])
        self.editor1.setFont(font)

        self.splitter = QSplitter()
        self.splitter.setHandleWidth(0)
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.list_parts)
        self.splitter.addWidget(self.editor1)
        self.splitter.addWidget(self.view1)
        self.splitter.setSizes([80,80,100,100])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setStretchFactor(3, 1)

        allLayout.addWidget(self.top_controls, stretch=0)
        allLayout.addWidget(self.splitter, stretch=1)
        self.setLayout(allLayout)

    def click_mode(self):
        sender = self.sender()
        if sender == self.button_edit:
            self.editor1.show()
            self.view1.hide()
        elif sender == self.button_both:
            self.editor1.show()
            self.view1.show()
        elif sender == self.button_view:
            self.editor1.hide()
            self.view1.show()

    def update_preview(self):
        # get current text from internal data
        editor_text = self.data[self.list1.currentRow()]["content"][self.list_parts.currentRow()]["content"]

        # parsing
        self.part_block_lexer.clear_ast()
        html_string = self.preview_css_str + self.markdowner_simple(editor_text)

        # set the preview html
        self.view1.setHtml(html_string)

        # update data and part list when part name was edited
        if self.list_parts.currentItem().text() != self.part_block_lexer.ast["title"]:
            self.list_parts.currentItem().setText(self.part_block_lexer.ast["title"])
            self.data[self.list1.currentRow()]["content"][self.list_parts.currentRow()]["title"] = self.part_block_lexer.ast["title"]

    def editor_changed(self):
        if self.list_parts.currentRow() != -1:

            # update internal data
            self.data[self.list1.currentRow()]["content"][self.list_parts.currentRow()]["content"] = self.editor1.toPlainText()

            # update GUI
            self.update_preview()

    def list_files_changed(self):
        # update part list
        part_names = [part["title"] for part in self.data[self.list1.currentRow()]["content"]]

        self.list_parts.clear()
        self.list_parts.addItems(part_names)
        max_width = self.list_parts.sizeHintForColumn(0) + self.list_parts.frameWidth() * 2
        max_width = 80
        # self.list_parts.setMaximumWidth(max_width)
        # self.list_parts.sizehint(max_width)
        # self.list_parts.setFixedWidth(max_width)
        self.list_parts.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def list_parts_rows_ins(self):
        if self.list_parts.count() > 0:
            self.list_parts.setCurrentRow(0)

    def list_parts_selected(self):
        if self.list_parts.currentRow() != -1:
            current_item = self.list_parts.currentItem()
            if current_item:
                source_string = self.data[self.list1.currentRow()]["content"][self.list_parts.currentRow()]["content"]
                self.editor1.setPlainText(source_string)

    def reload_changes(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

        self.overlay.setGeometry(QRect(self.finder.pos() + self.finder.rect().bottomLeft(), QSize(400, 200)))

    def click_debug(self):
        print("  click_debug()")
        self.view1.hide()

    def resizeEvent(self, e):
        if e.oldSize() != QSize(-1, -1):
            self.config["window_size"] = [self.parent().size().width(), self.parent().size().height()]

    def closeEvent(self, *args, **kwargs):
        self.save_config()

    def click_search(self):
        with self.ix.searcher() as searcher:
            query = QueryParser("content", self.ix.schema).parse(self.finder.text())
            results = searcher.search(query)
            results.formatter = Result_formatter_simple()
            result_count = len(results)

            search_results = [res.highlights("content") for res in results]
            self.overlay.add_search_results(search_results)

            # for i in range(result_count):
            #     print("result {}: ".format(i), results[i])
            #     print(results[i].highlights("content"))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finder.setFocus()


class Result_formatter_simple(whoosh.highlight.Formatter):
    def __init__(self):
        pass

    def format_token(self, text, token, replace=False):
        def get_text(original, token, replace):
            if replace:
                return token.text
            else:
                return original[token.startchar:token.endchar]

        ttext = whoosh.highlight.htmlescape(get_text(text, token, replace), quote=False)
        return '<span style="background-color: rgba(150,0,0,150);">{}</span>'.format(ttext)


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
        self.statusBar().showMessage('Ready')

        self.setWindowTitle("Carrie")
        self.show()

    def closeEvent(self, *args, **kwargs):
        self.main_widget.closeEvent(*args, **kwargs)


class AstBlockParser(mistune.BlockLexer):
    def __init__(self, rules=None, **kwargs):
        self.ast = {}
        super().__init__(rules, **kwargs)

    def clear_ast(self):
        self.ast = {}

    def parse(self, text, rules=None):
        text = text.rstrip('\n')

        if not rules:
            rules = self.default_rules

        def manipulate(text):
            for key in rules:
                rule = getattr(self.rules, key)
                m = rule.match(text)
                if not m:
                    continue

                getattr(self, 'parse_%s' % key)(m)

                # self.list_rules excluded to prevent the internal recalling of parse() to create double outputs
                if key != "heading" and rules != self.list_rules:
                    self.ast["content"][-1]["content"] += m.group(0)
                if key == "heading" and len(self.ast["content"]) > 0:
                    self.ast["content"][-1]["content"] += m.group(0)
                return m
            return False  # pragma: no cover

        while text:
            m = manipulate(text)
            if m is not False:
                text = text[len(m.group(0)):]
                continue
            if text:  # pragma: no cover
                raise RuntimeError('Infinite loop at: %s' % text)
        return self.tokens

    def parse_heading(self, m):
        level = len(m.group(1))
        text = m.group(2)
        if level == 1:
            self.ast["title"] = text
            self.ast["content"] = []
            self.ast["html"] = ""
        elif level == 2:
            self.ast["content"].append({"title": text, "content": ""})
        super().parse_heading(m)

class AstBlockParserPart(mistune.BlockLexer):
    def __init__(self, rules=None, **kwargs):
        self.ast = {}
        super().__init__(rules, **kwargs)

    def clear_ast(self):
        self.ast = {}

    def parse(self, text, rules=None):
        text = text.rstrip('\n')

        if not rules:
            rules = self.default_rules

        def manipulate(text):
            for key in rules:
                rule = getattr(self.rules, key)
                m = rule.match(text)
                if not m:
                    continue

                getattr(self, 'parse_%s' % key)(m)

                if key != "heading" and rules != self.list_rules:
                    self.ast["content"] += m.group(0)
                if key == "heading" and len(self.ast["content"]) > 0:
                    self.ast["content"] += m.group(0)
                return m
            return False  # pragma: no cover

        while text:
            m = manipulate(text)
            if m is not False:
                text = text[len(m.group(0)):]
                continue
            if text:  # pragma: no cover
                raise RuntimeError('Infinite loop at: %s' % text)
        return self.tokens

    def parse_heading(self, m):
        level = len(m.group(1))
        text = m.group(2)
        if level == 2:
            self.ast["title"] = text
            self.ast["content"] = ""
        super().parse_heading(m)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()

    app.setStyle("Fusion")
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
