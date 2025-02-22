from typing import Any
import re
from dataclasses import dataclass, field


@dataclass(eq=True)
class Token:
    content: str | list | None

    def optimize(self):
        return self


class String(Token):
    pass


class Nil(Token):
    pass


class List(Token):
    pass


class Matrix(Token):
    pass


class Symbol(Token):
    pass


class Number(Token):
    pass


class Tokeniser:
    string_pattern = re.compile(r'^"((\\"|[^"])*)"')
    number_pattern = re.compile(r"^(-?\d+\.\d+|-?\d+)")
    symbol_pattern = re.compile(r"([a-zA-Z_\-\.<>\!\@\#\$\%\^\&\*\+\/][a-zA-Z0-9_\-\.<>\!\@\#\$\%\^\&\*\+\/]*)")
    current_list = None
    outer_list = None

    def __init__(self, text):
        self.text = text.lstrip()

    def tokenise(self):
        while len(self.text) > 0:
            if m := self.string_pattern.match(self.text):
                yield from self.yield_string(m.group(1).replace('\\"', '"'))
                self.text = self.text[m.span()[1] :]
            elif m := self.number_pattern.match(self.text):
                try:
                    yield from self.yield_number(int(m.group(1)))
                except:
                    yield from self.yield_number(float(m.group(1)))
                self.text = self.text[m.span()[1] :]
            elif m := self.symbol_pattern.match(self.text):
                yield from self.yield_symbol(m.group(1))
                self.text = self.text[m.span()[1] :]
            elif self.text[0] == "[":
                self.start_list()
                self.text = self.text[1:]
            elif self.text[0] == ";":
                yield from self.next_row()
                self.text = self.text[1:]
            elif self.text[0] == "]":
                yield from self.end_list()
                self.text = self.text[1:]
            elif self.text[:3] == "nil":
                yield from self.nil()
                self.text = self.text[3:]
            else:
                return
            self.text = self.text.lstrip()

    def start_list(self):
        self.current_list = []

    def end_list(self):
        if self.outer_list is not None:
            self.outer_list.append(self.current_list)
            yield Matrix(self.outer_list)
        elif self.current_list is not None:
            yield List(self.current_list)
        self.outer_list = None
        self.current_list = None

    def next_row(self):
        if self.outer_list is not None:
            self.outer_list.append(self.current_list)
            self.current_list = []
        elif self.current_list is not None:
            self.outer_list = [self.current_list]
            self.current_list = []
        else:
            yield Symbol(";")

    def yield_symbol(self, value):
        if self.current_list is None:
            yield Symbol(value)
        else:
            self.current_list.append(value)

    def yield_string(self, value):
        if self.current_list is None:
            yield String(value)
        else:
            self.current_list.append(value)

    def yield_number(self, value):
        if self.current_list is None:
            yield Number(value)
        else:
            self.current_list.append(value)

    def nil(self):
        if self.current_list is None:
            yield Nil(None)
        else:
            self.current_list.append(None)


def tokenise(text):
    yield from Tokeniser(text).tokenise()


class Function:
    @classmethod
    def arity(self):
        return 0


@dataclass(eq=True)
class BinaryOp(Function):
    op1: Any
    op2: Any

    @classmethod
    def arity(self):
        return 2

    def optimize(self):
        op1 = self.op1.optimize()
        op2 = self.op2.optimize()
        if op1 != self.op1 or op2 != self.op2:
            return self.__class__(op1, op2)
        else:
            return self

    def build(self, definitions: list):
        if self.op1.table != self.op2.table:
            op1, op2 = op1.zip_with(op2)
            return self.__class__(op1, op2).build(definitions)
        else:
            SQLBinaryColumnExpression(self.op1.as_column(), self.op2.as_column(), self.op1.table, self.operation)


class Add(BinaryOp):
    pass


class Mul(BinaryOp):
    pass


class Sub(BinaryOp):
    pass


class Div(BinaryOp):
    pass


@dataclass(eq=True)
class Column(Function):
    table: Any
    column_idx: int


@dataclass(eq=True)
class ConstantTable(Function):
    rows: list[list]


@dataclass(eq=True)
class TableRef(Function):
    table_name: str
    known_columns: list[str]

    @classmethod
    def from_str(self, name):
        [table_name, *column] = name.split(".", 1)
        return self(table_name, column)


class Parser:
    def __init__(self, text):
        self.text = text
        self.stack = []

    functions = {
        "+": Add,
        "*": Mul,
        "-": Sub,
        "/": Div,
    }

    def arity(self, function):
        if function in self.functions:
            return self.functions[function].arity()
        else:
            return 0

    def function(self, function):
        if function in self.functions:
            return self.functions[function]
        else:
            return lambda *args: TableRef.from_str(function)

    def parse(self):
        for token in tokenise(self.text):
            if isinstance(token, Symbol):
                args = []
                for _ in range(self.arity(token.content)):
                    args.append(self.stack.pop())
                self.stack.append(self.function(token.content)(*reversed(args)))
            else:
                self.stack.append(token)
        return self.stack


def parse(text):
    return Parser(text).parse()


def optimise(code):
    return [defn.optimize() for defn in code]


def build(text):
    code = optimise(parse(text))
    return code[-1].build(code[:-1])


def tests():
    assert (list(tokenise('"hello" 1 2.3 [ 1 2 3 4 ] [1 2 ; 3 4 5 ; 6 7 8] hello blah -> "cool\\"" '))) == [
        String("hello"),
        Number(1),
        Number(2.3),
        List([1, 2, 3, 4]),
        Matrix([[1, 2], [3, 4, 5], [6, 7, 8]]),
        Symbol("hello"),
        Symbol("blah"),
        Symbol("->"),
        String('cool"'),
    ]
    assert list(tokenise("1 2 +")) == [Number(1), Number(2), Symbol("+")]
    assert list(tokenise("-1 -2.6 ")) == [Number(-1), Number(-2.6)]
    assert parse("[ 1 2 3 ] [4 5 6] +")[0] == Add(List([1, 2, 3]), List([4, 5, 6]))
    assert parse("1 3 + 2 / 12 * 5 -")[0] == Sub(
        op1=Mul(
            op1=Div(op1=Add(op1=Number(content=1), op2=Number(content=3)), op2=Number(content=2)),
            op2=Number(content=12),
        ),
        op2=Number(content=5),
    )
    assert parse("1 records + ")[0] == Add(Number(1), TableRef("records", []))

    print(build("[1 2 3] [2 3 4] +"))
    print("OK")


if __name__ == "__main__":
    tests()
