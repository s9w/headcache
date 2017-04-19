import mistune

class BadFormatError(RuntimeError):
    def __init__(self, filename, text):
        self.filename = filename
        self.value = text
    def __str__(self):
        return repr("{}, file: {}".format(self.value, self.filename))

class AstBlockParser(mistune.BlockLexer):
    def __init__(self, rules=None, **kwargs):
        self.ast = {}
        super().__init__(rules, **kwargs)

    def clear_ast(self):
        self.ast = {}

    def parse(self, text, rules=None, filename=None):
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

                if key != "heading" and "title" not in self.ast:
                    raise BadFormatError(filename, "content without lvl1 heading")

                if key not in ["heading", "newline"] and len(self.ast["content"]) == 0:
                    raise BadFormatError(filename, "content under lvl1 heading")

                # add content to last tree item if it's not a heading (see parse_heading())
                # or a nested list_rule (prevents double processing list items)
                if key != "heading" and rules != self.list_rules:
                    self.ast["content"][-1]["content"] += m.group(0)
                # if key == "heading" and len(self.ast["content"]) > 0:
                #     self.ast["content"][-1]["content"] += m.group(0)

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
            if "title" in self.ast:
                print("ERROR, second lvl 1 title")
            self.ast["title"] = text
            self.ast["content"] = []

        elif level == 2:
            # if file has no level 1 heading
            if "content" not in self.ast:
                self.ast["title"] = self.filename[:self.filename.find(".")]
                self.ast["content"] = []

            self.ast["content"].append({
                "title": text,
                "content": self.get_content(m.group(0))
            })
        super().parse_heading(m)

    @staticmethod
    def get_content(text):
        index_newline = text.find('\n')
        if index_newline != -1:
            content = text[index_newline + 1:].strip()
        else:
            content = ""
        return content
