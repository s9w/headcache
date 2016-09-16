from PyQt5.Qt import QTextCharFormat
from PyQt5.Qt import Qt
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont


class Highlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(Highlighter, self).__init__(parent)
        self.highlightingRules = []

        # parts
        self.format_section = QTextCharFormat()
        self.format_section.setFontWeight(QFont.Bold)
        self.format_section.setForeground(Qt.red)
        # self.format_section.setFontPointSize(20)
        re = QRegExp("##[^\n]*")
        self.highlightingRules.append((re, self.format_section))

        # bold
        format_bold = QTextCharFormat()
        format_bold.setFontWeight(QFont.Bold)
        re = QRegExp("\*\*(?!\*).+\*\*")
        re.setMinimal(True)
        self.highlightingRules.append((re, format_bold))

        # italic
        format_italic = QTextCharFormat()
        format_italic.setFontItalic(True)
        format_italic.setForeground(QColor(255,150,150))
        re = QRegExp("\*.+\*")
        re.setMinimal(True)
        self.highlightingRules.append((re, format_italic))

        # code
        self.format_code = QTextCharFormat()
        self.format_code.setForeground(QColor(255, 100, 100))
        re = QRegExp("`.+`")
        re.setMinimal(True)
        self.highlightingRules.append((re, self.format_code))

        # multiline code
        self.code_start_expr = QRegExp("```")
        self.code_end_expr = QRegExp("```")

    def set_section_size(self, size):
        self.format_section.setFontPointSize(size)

    def highlightBlock(self, text):
        offset = 0
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text, offset)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                offset = index + length
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        startIndex = 0
        starts_in_comment = True

        # not in comment
        if self.previousBlockState() != 1:
            startIndex = self.code_start_expr.indexIn(text)
            starts_in_comment = False

        # block comment start in block -> search for end
        while startIndex >= 0:
            endIndex = self.code_end_expr.indexIn(text, startIndex)
            if not starts_in_comment:
                endIndex = self.code_end_expr.indexIn(text, startIndex + 1)

            # end not in block -> state: in comment block
            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex

            # end also in block -> all done. block not set, implicit -1
            else:
                commentLength = endIndex - startIndex + self.code_end_expr.matchedLength()

            self.setFormat(startIndex, commentLength,
                           self.format_code)

            # potentially multiple block comments in one block (line)
            startIndex = self.code_start_expr.indexIn(text, startIndex + commentLength)