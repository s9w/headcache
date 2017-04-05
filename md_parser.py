import mistune


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

                if key not in ["heading", "newline"] and len(self.ast["content"]) == 0:
                    print("error, content under lvl1 heading")

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
            self.ast["content"].append({
                "title": text,
                "content": m.group(0)
            })
        super().parse_heading(m)