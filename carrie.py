import sys
import os, os.path
import markdown2
import mistune
import logging
import json

import time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QComboBox, QDialog,
        QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QFrame,
        QLabel, QLineEdit, QMenu, QMenuBar, QPushButton, QSpinBox, QTextEdit, QTextBrowser,
        QVBoxLayout)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QDir, pyqtSignal, QFile
from PyQt5.QtGui import QFont
from PyQt5 import QtCore
from PyQt5 import QtGui

from whoosh.index import create_in
from whoosh.fields import *
from whoosh.filedb.filestore import FileStorage
from whoosh.qparser import QueryParser

class IdRenderer(mistune.Renderer):
    def header(self, text, level, raw):
        return '<h{0} id="{1}">{1}</h{0}>\n'.format(level, text)

class MainWidget(QFrame): #QDialog #QMainWindow
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

        self.source_files = QDir("data").entryList(QDir.Files)
        for filename in self.source_files:
            file = QFile("data/{}".format(filename))
            if not file.open(QtCore.QIODevice.ReadOnly):
                print("couldn't open file")
            stream = QtCore.QTextStream(file)
            content = stream.readAll()
            self.writer.add_document(path=filename, content=content)
        self.writer.commit()

        self.block_lexer = AstBlockParser()

        self.markdowner = mistune.Markdown(renderer=IdRenderer(), block=self.block_lexer)
        self.data = self.load_data()

        self.initUI()
        if self.source_files:
            self.list1.setCurrentRow(0)

    def load_data(self):
        data_dict = {}
        for filename in self.source_files:
            file = QFile("data/{}".format(filename))
            if not file.open(QtCore.QIODevice.ReadOnly):
                print("couldn't open file")
            stream = QtCore.QTextStream(file)
            content = stream.readAll()
            self.block_lexer.clear_ast()
            html = self.markdowner(content)
            self.block_lexer.ast["html"] = html
            data_dict[filename] = self.block_lexer.ast
        # print(json.dumps(data_dict["cpp.md"], indent=2))
        return data_dict

    def initUI(self):
        font = QtGui.QFont()
        allLayout = QVBoxLayout()

        self.horizontalGroupBox = QGroupBox("Horizontal layout")
        layout = QHBoxLayout()
        button1 = QPushButton("reload")
        button1.clicked.connect(self.reload_changes)
        layout.addWidget(button1)

        button2 = QPushButton("search")
        button2.clicked.connect(self.click_search)
        layout.addWidget(button2)

        self.finder = QLineEdit()
        layout.addWidget(self.finder)
        self.horizontalGroupBox.setLayout(layout)

        self.list1 = QListWidget()
        if self.source_files:
            self.list1.addItems(self.source_files)
        self.list1.currentItemChanged.connect(self.listChanged)

        self.list_parts = QListWidget()
        self.list_parts .currentItemChanged.connect(self.list_parts_selected)

        button_left_add = QPushButton("add file")

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.list1)

        left_layout.addWidget(button_left_add)
        left_widget.setLayout(left_layout)

        self.editor1 = QTextEdit()
        # self.editor1.setFont(font)

        self.view1 = QTextBrowser()
        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.editor1.setFont(font)

        mainWidget = QWidget()
        mainLayout = QHBoxLayout()
        mainLayout.addWidget(left_widget)
        mainLayout.addWidget(self.list_parts)
        mainLayout.addWidget(self.editor1)
        mainLayout.addWidget(self.view1)

        allLayout.addWidget(self.horizontalGroupBox)
        # allLayout.addWidget(mainWidget)
        allLayout.addLayout(mainLayout)

        self.setLayout(allLayout)

    def listChanged(self):
        filename = self.list1.currentItem().text()
        part_names = [part["title"] for part in self.data[filename]["content"]]
        self.list_parts.clear()
        self.list_parts.addItems(part_names)

    def list_parts_selected(self):
        filename = self.list1.currentItem().text()
        part_index = self.list_parts.currentRow()
        current_item = self.list_parts.currentItem()
        if current_item:
            part_name = current_item.text()
            source_string = self.data[filename]["content"][part_index]["content"]
            self.editor1.setPlainText(source_string)
            self.view1.setHtml(self.data[filename]["html"])
            self.view1.scrollToAnchor(part_name)


    def reload_changes(self):
        print("reload")

    def click_search(self):
        with self.ix.searcher() as searcher:
            query = QueryParser("content", self.ix.schema).parse(self.finder.text())
            results = searcher.search(query)
            result_count = len(results)
            print("click_search", self.finder.text(), "len: ", result_count)
            for i in range(result_count):
                print("result {}: ".format(i), results[i])
                print(results[i].highlights("content"))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finder.setFocus()
            # self.close()

class Example(QMainWindow): #QDialog #QMainWindow
    # NumGridRows = 3
    # NumButtons = 4

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.main_widget = MainWidget(self)
        # textEdit = QTextEdit()
        # self.setCentralWidget(textEdit)
        self.setCentralWidget(self.main_widget)

        self.statusbar = self.statusBar()
        self.main_widget.msg.connect(self.statusbar.showMessage)
        # self.statusBar().showMessage('Ready')

        self.setWindowTitle("Basic Layouts")
        self.show()

    def createMenu(self):
        self.menuBar = QMenuBar()

        self.fileMenu = QMenu("&File", self)
        self.exitAction = self.fileMenu.addAction("E&xit")
        self.menuBar.addMenu(self.fileMenu)

        self.exitAction.triggered.connect(self.accept)

    def createHorizontalGroupBox(self):
        self.horizontalGroupBox = QGroupBox("Horizontal layout")
        layout = QHBoxLayout()

        button1 = QPushButton("Button A")
        button1.clicked.connect(self.click1)
        layout.addWidget(button1)


        button2 = QPushButton("Button B")
        layout.addWidget(button2)

        self.horizontalGroupBox.setLayout(layout)

    def click1(self):
        sender = self.sender()
        print("click1", sender.text())
        a = QDir("data")
        print(a.entryList(QDir.Files))

    def listChanged(self):
        print("listChanged")

    def createGridGroupBox(self):
        self.gridGroupBox = QGroupBox("Grid layout")
        layout = QGridLayout()

        for i in range(Dialog.NumGridRows):
            label = QLabel("Line %d:" % (i + 1))
            lineEdit = QLineEdit()
            layout.addWidget(label, i + 1, 0)
            layout.addWidget(lineEdit, i + 1, 1)

        self.smallEditor = QTextEdit()
        self.smallEditor.setPlainText("This widget takes up about two thirds "
                "of the grid layout.")

        layout.addWidget(self.smallEditor, 0, 2, 4, 1)

        layout.setColumnStretch(1, 10)
        layout.setColumnStretch(2, 20)
        self.gridGroupBox.setLayout(layout)

    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox("Form layout")
        layout = QFormLayout()
        layout.addRow(QLabel("Line 1:"), QLineEdit())
        layout.addRow(QLabel("Line 2, long text:"), QComboBox())
        layout.addRow(QLabel("Line 3:"), QSpinBox())
        self.formGroupBox.setLayout(layout)


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

                if key != "heading":
                    self.ast["content"][-1]["content"] += m.group(0)
                if key == "heading" and len(self.ast["content"]) > 0:
                    self.ast["content"][-1]["content"] += m.string[:m.end()]
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()

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
