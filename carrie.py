
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QComboBox, QDialog,
        QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QFrame,
        QLabel, QLineEdit, QMenu, QMenuBar, QPushButton, QSpinBox, QTextEdit, QTextBrowser,
        QVBoxLayout)
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QDir, pyqtSignal, QFile
from PyQt5 import QtCore
from PyQt5 import QtGui

class MainWidget(QFrame): #QDialog #QMainWindow
    msg = pyqtSignal(str)
    # import QSciScintilla

    def __init__(self, parent):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        font = QtGui.QFont()
        # font.setStyleStrategy(QtGui.QFont.PreferAntialias)

        allLayout = QVBoxLayout()
        # allLayout.setMenuBar(self.menuBar)

        self.horizontalGroupBox = QGroupBox("Horizontal layout")
        layout = QHBoxLayout()
        button1 = QPushButton("Button A")
        button1.clicked.connect(self.click1)
        layout.addWidget(button1)
        button2 = QPushButton("Button B")
        layout.addWidget(button2)

        self.finder = QLineEdit()
        layout.addWidget(self.finder)
        self.horizontalGroupBox.setLayout(layout)

        self.list1 = QListWidget()
        source_files = QDir("data").entryList(QDir.Files)
        print(source_files)
        self.list1.addItems(source_files)
        self.list1.currentItemChanged.connect(self.listChanged)

        button_left_add = QPushButton("add file")

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.list1)
        left_layout.addWidget(button_left_add)
        left_widget.setLayout(left_layout)

        self.editor1 = QTextEdit()
        self.editor1.setPlainText("text fill")
        # self.editor1.setFont(font)

        view1 = QTextBrowser()
        view1.setHtml("<h1>Abc Test Superduper</h1>")

        mainWidget = QWidget()
        mainLayout = QHBoxLayout()
        mainLayout.addWidget(left_widget)
        mainLayout.addWidget(self.editor1)
        mainLayout.addWidget(view1)

        allLayout.addWidget(self.horizontalGroupBox)
        # allLayout.addWidget(mainWidget)
        allLayout.addLayout(mainLayout)

        self.setLayout(allLayout)

    def listChanged(self):
        filename = self.list1.currentItem().text()
        file = QFile("data/{}".format(filename))
        if not file.open(QtCore.QIODevice.ReadOnly):
            print("blah")
        stream = QtCore.QTextStream(file)
        self.editor1.setText(stream.readAll())

    def click1(self):
        sender = self.sender()
        print("click1", sender.text())
        a = QDir("data")
        print(a.entryList(QDir.Files))
        self.msg.emit(str("wohoo"))

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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # ex = Example()
    # sys.exit(app.exec_())

    ex = Example()
    sys.exit(app.exec_())
