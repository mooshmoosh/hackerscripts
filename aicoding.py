"""
Todo:

* make sure the break statement works
* implement a print / output command / statement
* optimize programs so that if some code only depends on static data it is executed at compile once, and the result is stored in a variable.
* add functions for creating new procedures, replace procedure calls, iterating over existing functions and modifying them
* Take variables from the cli?
* json decode?
* Add a cli option to not have any stdin, and run the program with prompt initially set to ""
* create a new version of system that can pause and resume execution
"""

import json
from functools import cached_property
from collections import deque
import datetime
import sys
import argparse
import traceback
import sqlite3
import hashlib
import string
import re
from functools import cached_property
from dataclasses import dataclass
from typing import Iterator, Union, Callable, Type
import subprocess as sp

# Computation model


def log(msg: str) -> None:
    print(datetime.datetime.now().isoformat(), msg, file=sys.stderr)


CompiledIterator = deque[str | dict[str, str]]


class System:
    """
    The system is the envionment where computation happens. It handles tracking of variables, and
    interaction with the rest of the world.
    """

    def __init__(
        self,
        procedures: dict[str, "BaseProcedure"],
        llm_manager: "BaseLLMManager",
        sql_manager: "SQLManager",
        verbose: bool = False,
    ):
        self.stack: list[dict[str, str]] = [{}]
        self.call_stack: list[tuple[str, int]]
        self.procedures = procedures
        self.compiled_procedures: dict[str, list["BaseByteCode"]] = {}
        self.llm_manager = llm_manager
        self.sql_manager = sql_manager
        self.verbose = verbose
        self.iterators: list[CompiledIterator] = []

    def get_procedure(self, name: str) -> "BaseProcedure":
        if self.verbose:
            log(f"Retrievieving procedure: {name}")
        return self.procedures[name]

    def get_undefined_procedures(self) -> set[str]:
        result = set()
        for procedure in self.procedures.values():
            for name in procedure.get_undefined_procedures(self):
                result.add(name)
        return result

    def get_first_procedure(self) -> "BaseProcedure":
        for procedure in self.procedures.values():
            return procedure
        else:
            raise RuntimeError("no procedures defined")

    def get_var(self, name: str) -> str:
        if self.verbose:
            log(f"Retrievieving variable value: {name}")
        for layer in reversed(self.stack):
            if name in layer:
                return layer[name]
        return ""

    def set_var(self, name: str, value: str) -> None:
        if self.verbose:
            log(f"Saving to variable: {name}, value: {value}")
        self.stack[-1][name] = value

    def new_env(self) -> None:
        self.stack.append({})
        if self.verbose:
            log(f"adding a new env. new depth: {len(self.stack)}")

    def pop_env(self) -> None:
        if len(self.stack) <= 1:
            breakpoint()
            if self.verbose:
                log(f"Tried to pop an env, but the stack is length: {len(self.stack)}")
            return
        dropped_env = self.stack.pop()
        for key, value in dropped_env.items():
            if key == "prompt":
                self.set_var("prompt", value)
            else:
                self.set_var(f"out.{key}", value)
        if self.verbose:
            log(f"Popped an env, new stack depth is: {len(self.stack)}")

    def execute_sql(self, query: str, read_only: bool) -> Iterator[dict[str, str]]:
        if self.verbose:
            log(f"Executing {read_only=} sql: {query}")
        for row in self.sql_manager.execute_sql(query, read_only, self.get_var):
            if self.verbose:
                log(f"Result: {row=}")
            yield row

    def run_llm(self, procedure: "LLMProcedure", data: dict[str, str]) -> str:
        if self.verbose:
            log(f"Calling LLM {procedure.model=} {procedure.name=} {data=}")
        result = self.llm_manager.run_llm(procedure, data)
        if self.verbose:
            log(f"Response from LLM was: {result}")
        return result

    def ask_questions(self, questions: list[tuple[str, str]]) -> None:
        for name, question in questions:
            default = self.get_var(name).strip()
            if default == "":
                result = input(f"{question}: ").strip()
            else:
                result = input(f"{question} ({default}): ").strip()
            if result == "":
                result = default
            self.set_var(name, result)

    def compile_all(self) -> None:
        if len(self.procedures) == 0:
            return
        for name, proc in self.procedures.items():
            self.compiled_procedures[name] = proc.compile(self)
        self.procedures = {}

    def new_call(self, name: str) -> None:
        self.call_stack.append((name, 0))

    def jump(self, jump: int) -> None:
        name, idx = self.call_stack[-1]
        self.call_stack[-1] = (name, idx + jump)

    def step(self) -> None:
        name, idx = self.call_stack[-1]
        procedure = self.compiled_procedures[name]
        if idx >= len(procedure):
            if len(self.call_stack) > 1:
                self.pop_env()
            self.call_stack.pop()
        else:
            command = procedure[idx]
            self.call_stack[-1] = (name, idx + 1)
            command.execute(self)

    def next_iterator_empty(self) -> bool:
        return len(self.iterators[-1]) == 0

    def get_next_iterator_value(self) -> str | dict[str, str]:
        return self.iterators[-1].popleft()

    def new_iterator(self) -> CompiledIterator:
        result: CompiledIterator = deque()
        self.iterators.append(result)
        return result

    def pop_iterator(self) -> None:
        self.iterators.pop()

    def next_commnd_like(self, cls: Type) -> int:
        name, idx = self.call_stack[-1]
        procedure = self.compiled_procedures[name]
        result = 0
        while idx + result < len(procedure):
            if isinstance(procedure[idx + result], cls):
                break
            else:
                result += 1
        return result

    def begin(self, procedure_name: str | None) -> None:
        self.compile_all()
        if procedure_name is None:
            for name in self.compiled_procedures.keys():
                procedure_name = name
                break
            else:
                return
        self.call_stack = [(procedure_name, 0)]
        while len(self.call_stack) > 0:
            self.step()
        print(self.get_var("prompt"))


# ByteCodeCommands are the most primitive part of execution. Compiling programs to VM bytecode
# makes it easier to store and restore execution state.
class BaseByteCode:
    def execute(self, system: System) -> None:
        raise NotImplementedError()


@dataclass
class CallProcedureByName(BaseByteCode):
    name: str

    def execute(self, system: System) -> None:
        system.new_env()
        system.new_call(self.name)


@dataclass
class Jump(BaseByteCode):
    jump: int

    def execute(self, system: System) -> None:
        system.jump(self.jump)


class JumpIfIteratorEmpty(Jump):
    def execute(self, system: System) -> None:
        if system.next_iterator_empty():
            system.pop_iterator()
            system.jump(self.jump)


@dataclass
class JumpIfNoMatch(Jump):
    case: str

    def execute(self, system: System) -> None:
        input_var = system.get_var("prompt").lower()
        normalized = re.compile(r"[^a-z0-9]+").sub(" ", input_var).strip()
        if normalized != self.case:
            system.jump(self.jump)


class SetIteratorItemVariables(BaseByteCode):
    def execute(self, system: System) -> None:
        data = system.get_next_iterator_value()
        if isinstance(data, str):
            system.set_var("prompt", data)
        elif isinstance(data, dict):
            for key, value in data.items():
                system.set_var(key, value)


@dataclass
class AddSQLIterator(BaseByteCode):
    query: str | None
    read_only: bool

    def execute(self, system: System) -> None:
        iterator = system.new_iterator()
        if self.query is None:
            query = system.get_var("prompt")
        else:
            query = self.query
        for row in system.execute_sql(query, read_only=self.read_only):
            iterator.append(row)


class AddLineIterator(BaseByteCode):
    def execute(self, system: System) -> None:
        iterator = system.new_iterator()
        for line in system.get_var("prompt").split("\n"):
            line = line.strip()
            if line == "":
                continue
            iterator.append(line)


class AddParagraphIterator(BaseByteCode):
    def execute(self, system: System) -> None:
        iterator = system.new_iterator()
        for line in system.get_var("prompt").split("\n\n"):
            line = line.strip()
            if line == "":
                continue
            iterator.append(line)


class EndLoopMarker(BaseByteCode):
    def execute(self, system: System) -> None:
        return None


class BreakCommand(BaseByteCode):
    def execute(self, system: System) -> None:
        jump = system.next_commnd_like(EndLoopMarker)
        system.jump(jump)


# A program / procedure is a statement which has more statements following


class BaseProcedure:
    def execute(self, system: System) -> None:
        raise NotImplementedError()

    def get_undefined_procedures(self, system: System) -> set[str]:
        return set()

    def compile(self, system: System) -> list[BaseByteCode]:
        raise NotImplementedError()


@dataclass
class Procedure(BaseProcedure):
    statements: list["Statement"]

    def execute(self, system: System) -> None:
        for statement in self.statements:
            statement.execute(system)

    def get_undefined_procedures(self, system: System) -> set[str]:
        result = set()
        for statement in self.statements:
            for name in statement.get_undefined_procedures(system):
                result.add(name)
        return result

    def compile(self, system: System) -> list[BaseByteCode]:
        result = []
        for statement in self.statements:
            result += statement.compile(system)
        return result


@dataclass
class LLMProcedure(BaseProcedure, BaseByteCode):
    model: str
    system: str
    prompt: str
    name: str
    history: list[tuple[str, str]]

    @cached_property
    def prompt_keys(self):
        result = []
        for _, name, _, _ in string.Formatter().parse(self.prompt):
            if name is not None:
                result.append(name)
        return result

    def execute(self, system: System) -> None:
        data = {key: system.get_var(key) for key in self.prompt_keys}
        system.set_var("prompt", system.run_llm(self, data))

    def compile(self, system: System) -> list[BaseByteCode]:
        return [self]


# Statements do things with the system


class Statement:
    def execute(self, system: System) -> None:
        raise NotImplementedError()

    def get_undefined_procedures(self, system: System) -> set[str]:
        return set()

    def compile(self, system: System) -> list[BaseByteCode]:
        raise NotImplementedError()


@dataclass
class ProcedureCall(Statement):
    name: str

    def execute(self, system: System) -> None:
        system.new_env()
        system.get_procedure(self.name).execute(system)
        system.pop_env()

    def get_undefined_procedures(self, system: System) -> set[str]:
        if self.name in system.procedures:
            return set()
        else:
            return set([self.name])

    def compile(self, system: System) -> list[BaseByteCode]:
        return [CallProcedureByName(self.name)]


@dataclass
class LoopStatement(Statement):
    procedure: Procedure | None

    def get_iterator_command(self) -> BaseByteCode:
        raise NotImplementedError()

    def compile(self, system: System) -> list[BaseByteCode]:
        if self.procedure is None:
            return [
                self.get_iterator_command(),
                JumpIfIteratorEmpty(3),
                SetIteratorItemVariables(),
                Jump(-3),
                EndLoopMarker(),
            ]
        else:
            sub_commands = self.procedure.compile(system)
            result = [
                self.get_iterator_command(),
                JumpIfIteratorEmpty(len(sub_commands) + 3),
                SetIteratorItemVariables(),
            ] + sub_commands
            result.append(Jump(-len(sub_commands) - 3))
            result.append(EndLoopMarker())
            return result


@dataclass
class SQLStatement(LoopStatement):
    read_only: bool
    query: str | None

    def execute(self, system: System) -> None:
        if self.query is None:
            query = system.get_var("prompt")
        else:
            query = self.query
        for row in system.execute_sql(query, read_only=self.read_only):
            if self.procedure is not None:
                for key, value in row.items():
                    system.set_var(key, value)
                try:
                    self.procedure.execute(system)
                except BreakStatementEncountered:
                    break
            else:
                for key, value in row.items():
                    system.set_var(key, value)

    def get_undefined_procedures(self, system: System) -> set[str]:
        if self.procedure is None:
            return set()
        else:
            return self.procedure.get_undefined_procedures(system)

    def get_iterator_command(self) -> BaseByteCode:
        return AddSQLIterator(self.query, self.read_only)


class ForEach(LoopStatement):
    def get_undefined_procedures(self, system: System) -> set[str]:
        if self.procedure is None:
            return set()
        else:
            return self.procedure.get_undefined_procedures(system)

    def get_lines(self) -> Iterator[str]:
        return iter(system.get_var("prompt").split("\n"))

    def execute(self, system: System) -> None:
        for line in self.get_lines():
            line = line.strip()
            if line == "":
                continue
            if system.verbose:
                log(f"looping over line: {line}")
            system.set_var("prompt", line)
            if self.procedure is not None:
                try:
                    self.procedure.execute(system)
                except BreakStatementEncountered:
                    break

    def get_iterator_command(self) -> BaseByteCode:
        return AddLineIterator()


class ForEachParagraph(ForEach):
    def get_lines(self) -> Iterator[str]:
        return iter(system.get_var("prompt").split("\n\n"))

    def get_iterator_command(self) -> BaseByteCode:
        return AddParagraphIterator()


@dataclass
class FormatString(Statement, BaseByteCode):
    template: str

    def execute(self, system: System) -> None:
        result = []
        for text, name, _, _ in string.Formatter().parse(self.template):
            result.append(text)
            if name is not None:
                result.append(system.get_var(name))
        system.set_var("prompt", "".join(result))

    def compile(self, system: System) -> list[BaseByteCode]:
        return [self]


@dataclass
class SetVariable(Statement, BaseByteCode):
    name: str

    def execute(self, system: System) -> None:
        system.set_var(self.name, system.get_var("prompt"))

    def compile(self, system: System) -> list[BaseByteCode]:
        return [self]


@dataclass
class FetchVariable(Statement, BaseByteCode):
    name: str

    def execute(self, system: System) -> None:
        system.set_var("prompt", system.get_var(self.name))

    def compile(self, system: System) -> list[BaseByteCode]:
        return [self]


@dataclass
class Branch(Statement):
    branches: dict[str, Procedure]
    default: Procedure | None = None

    def execute(self, system: System) -> None:
        for case, proc in self.branches.items():
            if re.compile(r"[^a-z0-9]+").sub(" ", system.get_var("prompt").lower()).strip().strip() == case:
                proc.execute(system)
                return
        if self.default is not None:
            self.default.execute(system)

    def get_undefined_procedures(self, system: System) -> set[str]:
        result = set()
        for branch in self.branches.values():
            for name in branch.get_undefined_procedures(system):
                result.add(name)
        if self.default is not None:
            for name in self.default.get_undefined_procedures(system):
                result.add(name)
        return result

    def compile(self, system: System) -> list[BaseByteCode]:
        result: list[BaseByteCode] = []
        jumps_to_update = {}
        for case, proc in self.branches.items():
            sub_commands = proc.compile(system)
            result.append(JumpIfNoMatch(len(sub_commands) + 1, case))
            result += sub_commands
            exit_jump = Jump(0)
            jumps_to_update[len(result)] = exit_jump
            result.append(exit_jump)
        if self.default is not None:
            result += self.default.compile(system)
        for idx, exit_jump in jumps_to_update.items():
            exit_jump.jump = len(result) - idx - 1
        return result


@dataclass
class AskQuestions(Statement, BaseByteCode):
    questions: list[tuple[str, str]]

    def execute(self, system: System) -> None:
        system.ask_questions(self.questions)

    def compile(self, system: System) -> list[BaseByteCode]:
        return [self]


class BreakStatementEncountered(Exception):
    pass


class BreakStatement(Statement):
    def execute(self, system: System) -> None:
        raise BreakStatementEncountered()

    def compile(self, system: System) -> list[BaseByteCode]:
        return [BreakCommand()]


# Parsing Classes

AtomicType = str | int | float | None
CompoundType = AtomicType | list["CompoundType"] | dict[str, "CompoundType"]


class ParseResult:
    def __init__(self, value: AtomicType | list["ParseResult"] | dict[str, "ParseResult"] | None) -> None:
        self.value = value

    def as_string(self) -> str:
        if isinstance(self.value, str):
            return self.value
        elif isinstance(self.value, list):
            return "".join(x.as_string() for x in self.value)
        else:
            return ""

    def as_data(self) -> CompoundType:
        if isinstance(self.value, AtomicType):
            return self.value
        elif isinstance(self.value, list):
            return [value.as_data() for value in self.value]
        elif isinstance(self.value, dict):
            return {key: value.as_data() for key, value in self.value.items()}


class Pattern:
    def parse(self, text) -> ParseResult | None:
        result, remaining = self.parse_partial(text)
        if remaining.strip() == "":
            return result
        else:
            breakpoint()
        return None

    def parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        result, rest = self._parse_partial(text)
        return result, rest

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        return None, text

    def optimize(self) -> "Pattern":
        return self

    def to_regex_pattern(self) -> Union["RegexPattern", None]:
        return self.optimize().to_regex_pattern()


class RegexPattern(Pattern):
    return_none = False

    @cached_property
    def final_regex(self) -> re.Pattern:
        return re.compile("^" + self.regex)

    @property
    def regex(self) -> str:
        raise NotImplementedError()

    def escape(self, value: str) -> str:
        for x, y in [
            ("\\", "\\\\"),
            (".", "\\."),
            ("+", "\\+"),
            ("(", "\\("),
            (")", "\\)"),
            ("*", "\\*"),
            ("\n", "\\n"),
        ]:
            value = value.replace(x, y)
        return value

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        result = self.final_regex.match(text)
        if result is None:
            return None, text
        inner_result = None if self.return_none else result.group(0)
        return ParseResult(inner_result), text[result.span()[1] :]

    def to_regex_pattern(self) -> Union["RegexPattern", None]:
        return self


@dataclass
class AnyCharBut(RegexPattern):
    exclude: list[str]
    empty_ok: bool

    @property
    def regex(self) -> str:
        return "[^" + "".join([self.escape(x) for x in self.exclude]) + "]" + ("*" if self.empty_ok else "+")


@dataclass
class OnlyChars(RegexPattern):
    include: list[str]
    empty_ok: bool

    @property
    def regex(self) -> str:
        return "[" + "".join([self.escape(x) for x in self.include]) + "]" + ("*" if self.empty_ok else "+")


@dataclass
class IncludeExclude(RegexPattern):
    exclude: list[str]
    include: list[str]
    empty_ok: bool

    @property
    def regex(self) -> str:
        exclude = [self.escape(x) for x in self.exclude]
        include = [self.escape(x) for x in self.include]
        return "([^" + "".join(exclude) + "]|" + "|".join(include) + ")" + ("*" if self.empty_ok else "+")


@dataclass
class BasicRegex(RegexPattern):
    _regex: str

    @property
    def regex(self) -> str:
        return self._regex


@dataclass
class ExactString(Pattern):
    search: str

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        if text.startswith(self.search):
            return ParseResult(self.search), text[len(self.search) :]
        else:
            return None, text


@dataclass
class ConcatenatedRegex(RegexPattern):
    pieces: list[RegexPattern]

    @property
    def regex(self) -> str:
        return "".join(piece.regex for piece in self.pieces)


@dataclass
class UnionRegex(RegexPattern):
    pieces: list[RegexPattern]

    @property
    def regex(self) -> str:
        return "(" + "|".join(piece.regex for piece in self.pieces) + ")"


@dataclass
class UnionPattern(Pattern):
    options: list[Pattern]

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        for option in self.options:
            result, remaining = option.parse_partial(text)
            if result is not None:
                return result, remaining
        return None, text


@dataclass
class TaggedUnionPattern(Pattern):
    options: dict[str, Pattern]

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        for tag, option in self.options.items():
            result, remaining = option.parse_partial(text)
            if result is not None:
                return ParseResult({"type": ParseResult(tag), "value": result}), remaining
        return None, text


@dataclass
class StringPiecesPattern(Pattern):
    pieces: list[Pattern]

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        all_results = []
        rest = text
        for piece in self.pieces:
            parsed_piece, rest = piece.parse_partial(rest)
            if parsed_piece is None:
                return None, text
            else:
                all_results.append(parsed_piece)
        return ParseResult("".join(x.as_string() for x in all_results)), rest


@dataclass
class StructPattern(Pattern):
    pieces: list[Pattern]
    fields: dict[str, int]

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        all_results = []
        rest = text
        for piece in self.pieces:
            parsed_piece, rest = piece.parse_partial(rest)
            if parsed_piece is None:
                return None, text
            else:
                all_results.append(parsed_piece)
        return ParseResult({key: all_results[idx] for key, idx in self.fields.items()}), rest


@dataclass
class PrefixPattern(Pattern):
    prefix: Pattern
    pattern: Pattern

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        prefix, rest = self.prefix.parse_partial(text)
        if prefix is None:
            return None, text

        result, rest = self.pattern.parse_partial(rest)
        if result is None:
            return None, text

        return result, rest


@dataclass
class ListPattern(Pattern):
    first: Pattern
    rest: Pattern

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        result, rest = self.first.parse_partial(text)
        if result is None:
            return ParseResult([]), text
        else:
            all_results = [result]
            while True:
                result, rest = self.rest.parse_partial(rest)
                if result is None:
                    return ParseResult(all_results), rest
                else:
                    all_results.append(result)


@dataclass
class RepeatedString(Pattern):
    pattern: Pattern

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        rest = text
        full_result = []
        while True:
            result, rest = self.pattern.parse_partial(rest)
            if result is None:
                break
            else:
                full_result.append(result)
        return ParseResult("".join(x.as_string() for x in full_result)), rest


@dataclass
class AsString(Pattern):
    pattern: Pattern

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        result, rest = self.pattern.parse_partial(text)
        if result is None:
            return None, text
        else:
            return ParseResult(result.as_string()), rest


@dataclass
class WithReplacements(Pattern):
    pattern: Pattern
    replacements: list[tuple[str, str]]

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        result, rest = self.pattern.parse_partial(text)
        if result is None:
            return None, text
        else:
            result_as_string = result.as_string()
            for key, value in self.replacements:
                result_as_string = result_as_string.replace(key, value)
            return ParseResult(result_as_string), rest


@dataclass
class SwappablePattern(Pattern):
    """
    This is a convenience wrapper that lets you use patterns recursively.
    """

    inner_pattern: Pattern | None

    def _parse_partial(self, text: str) -> tuple[ParseResult | None, str]:
        if self.inner_pattern is None:
            raise ValueError("Swapable pattern used without an inner pattern")
        else:
            return self.inner_pattern.parse_partial(text)


# Patterns for parsing program files

MaybeSpaces = OnlyChars([" "], empty_ok=True)
Spaces = OnlyChars([" "], empty_ok=False)
SpacesOrNewLines = OnlyChars([" ", "\n"], empty_ok=True)
StringContent = WithReplacements(IncludeExclude(['"'], ['\\"', "\n"], empty_ok=True), [('\\"', '"'), ("\\\\", "\\")])
CodeStatements = SwappablePattern(None)
VarName = BasicRegex("[a-zA-Z][a-zA-Z0-9_\\-\\.]*")

CodeBlock = StructPattern(
    [ExactString("{"), SpacesOrNewLines, CodeStatements, SpacesOrNewLines, ExactString("}")], {"statements": 2}
)

SetVarStatement = StructPattern([MaybeSpaces, ExactString("->"), Spaces, VarName], {"var": 3})
GetVarStatement = StructPattern([MaybeSpaces, VarName, Spaces, ExactString("->")], {"var": 1})
ForEachLoop = StructPattern(
    [
        MaybeSpaces,
        ExactString("for"),
        Spaces,
        ExactString("each"),
        SpacesOrNewLines,
        CodeBlock,
    ],
    {"block": 5},
)
ForEachParagraphLoop = StructPattern(
    [
        MaybeSpaces,
        ExactString("for"),
        Spaces,
        ExactString("each"),
        Spaces,
        ExactString("para"),
        SpacesOrNewLines,
        CodeBlock,
    ],
    {"block": 7},
)

SQLReadOnly = StructPattern(
    [
        MaybeSpaces,
        ExactString("SQL"),
        UnionPattern([PrefixPattern(SpacesOrNewLines, CodeBlock), ExactString("")]),
    ],
    {"block": 3},
)
SQLMut = StructPattern(
    [
        MaybeSpaces,
        ExactString("SQL!"),
        UnionPattern([PrefixPattern(SpacesOrNewLines, CodeBlock), ExactString("")]),
    ],
    {"block": 3},
)

SQLReadOnlyQuery = StructPattern(
    [
        MaybeSpaces,
        ExactString('SQL"'),
        StringContent,
        ExactString('"'),
        UnionPattern([PrefixPattern(SpacesOrNewLines, CodeBlock), ExactString("")]),
    ],
    {"query": 2, "block": 4},
)
SQLMutQuery = StructPattern(
    [
        MaybeSpaces,
        ExactString('SQL!"'),
        StringContent,
        ExactString('"'),
        UnionPattern([PrefixPattern(SpacesOrNewLines, CodeBlock), ExactString("")]),
    ],
    {"query": 2, "block": 4},
)
CaseBranch = StructPattern(
    [
        MaybeSpaces,
        ExactString('"'),
        StringContent,
        ExactString('"'),
        SpacesOrNewLines,
        CodeBlock,
    ],
    {"value": 2, "block": 5},
)
CaseBranches = ListPattern(CaseBranch, PrefixPattern(ExactString("\n"), CaseBranch))
MaybeDefaultBranch = TaggedUnionPattern(
    {
        "default": StructPattern([SpacesOrNewLines, CodeBlock], {"block": 1}),
        "none": ExactString(""),
    }
)
BranchPattern = StructPattern(
    [
        MaybeSpaces,
        ExactString("case"),
        Spaces,
        ExactString("{"),
        SpacesOrNewLines,
        CaseBranches,
        SpacesOrNewLines,
        ExactString("}"),
        MaybeDefaultBranch,
    ],
    {"branches": 5, "default": 8},
)
SingleQuestionLine = StructPattern(
    [
        MaybeSpaces,
        AnyCharBut(["\n", "}", "{", "#", "-", ">"], empty_ok=False),
        ExactString("->"),
        Spaces,
        VarName,
    ],
    {"question": 1, "var": 4},
)
QuestionList = ListPattern(SingleQuestionLine, PrefixPattern(ExactString("\n"), SingleQuestionLine))
AskPattern = StructPattern(
    [
        MaybeSpaces,
        ExactString("ask"),
        Spaces,
        ExactString("{"),
        SpacesOrNewLines,
        QuestionList,
        SpacesOrNewLines,
        ExactString("}"),
    ],
    {"questions": 5},
)
FormatStringPattern = StructPattern([MaybeSpaces, ExactString('"'), StringContent, ExactString('"')], {"template": 2})
ProcedureCallPattern = StructPattern([MaybeSpaces, AnyCharBut(["\n", "}", "{", "#"], empty_ok=False)], {"name": 1})

CodeStatement = TaggedUnionPattern(
    {
        "set_var": SetVarStatement,
        "get_var": GetVarStatement,
        "for_each_paragraph": ForEachParagraphLoop,
        "for_each": ForEachLoop,
        "ask": AskPattern,
        "sql_read_only_query": SQLReadOnlyQuery,
        "sql_mut_query": SQLMutQuery,
        "sql_read_only_no_query": SQLReadOnly,
        "sql_mut_no_query": SQLMut,
        "branch": BranchPattern,
        "format_string": FormatStringPattern,
        "call": ProcedureCallPattern,
        "blank_line": ExactString(""),
    }
)

CodeStatements.inner_pattern = ListPattern(CodeStatement, PrefixPattern(ExactString("\n"), CodeStatement))

SystemPromptPattern = StructPattern(
    [
        ExactString("## System\n\n"),
        RepeatedString(BasicRegex("([^#\n][^\n]*|)\n")),
    ],
    {"prompt": 1},
)
PromptPattern = StructPattern(
    [
        ExactString("## Prompt\n\n"),
        RepeatedString(BasicRegex("([^#\n][^\n]*|)\n")),
    ],
    {"prompt": 1},
)

MessagePattern = TaggedUnionPattern(
    {
        "user": PrefixPattern(ExactString("U: "), AnyCharBut(["\n"], empty_ok=False)),
        "assistant": PrefixPattern(ExactString("A: "), AnyCharBut(["\n"], empty_ok=False)),
        "blank": ExactString("\n"),
    }
)

HistoryPattern = PrefixPattern(
    ExactString("## History\n\n"), ListPattern(MessagePattern, PrefixPattern(ExactString("\n"), MessagePattern))
)

LLMProcedureSection = TaggedUnionPattern(
    {
        "system": SystemPromptPattern,
        "prompt": PromptPattern,
        "history": HistoryPattern,
    }
)

LLMProcedureSections = ListPattern(LLMProcedureSection, LLMProcedureSection)

LLMCode = StructPattern(
    [
        ExactString("Model:"),
        MaybeSpaces,
        AnyCharBut(["\n", " "], empty_ok=False),
        SpacesOrNewLines,
        LLMProcedureSections,
    ],
    {"model": 2, "sections": 4},
)

ProcedureDefinition = StructPattern(
    [
        ExactString("# "),
        AnyCharBut(["\n"], empty_ok=False),
        ExactString("\n\n"),
        TaggedUnionPattern({"llm": LLMCode, "procedure": CodeStatements}),
        SpacesOrNewLines,
    ],
    {"body": 3, "name": 1},
)

ProcedureDefinitions = ListPattern(ProcedureDefinition, ProcedureDefinition)


def parse_program(text: str) -> dict[str, BaseProcedure]:
    result = {}
    parsed_data = ProcedureDefinitions.parse(text)
    if parsed_data is None:
        return {}
    program_code = parsed_data.as_data()
    assert isinstance(program_code, list)
    for proc in program_code:
        assert isinstance(proc, dict)
        assert isinstance(proc["body"], dict)
        assert isinstance(proc["name"], str)
        result[proc["name"]] = make_procedure(proc["body"], proc["name"])
    return result


def make_procedure(proc: dict, name: str) -> BaseProcedure:
    if proc["type"] == "procedure":
        proc = proc["value"]
        assert isinstance(proc, list)
        return Procedure(make_statements(proc))
    elif proc["type"] == "llm":
        proc = proc["value"]
        assert isinstance(proc["model"], str)
        assert isinstance(proc["sections"], list)
        system = ""
        prompt = ""
        history: list[tuple[str, str]] = []
        for section in proc["sections"]:
            if section["type"] == "system":
                assert isinstance(section["value"]["prompt"], str)
                system = section["value"]["prompt"]
            elif section["type"] == "prompt":
                assert isinstance(section["value"]["prompt"], str)
                prompt = section["value"]["prompt"]
            elif section["type"] == "history":
                assert isinstance(section["value"], list)
                for item in section["value"]:
                    if item["type"] == "blank":
                        continue
                    else:
                        history.append((item["type"], item["value"]))
        return LLMProcedure(model=proc["model"], system=system, prompt=prompt, name=name, history=history)
    else:
        breakpoint()
        return Procedure([])


def make_statements(statements: list[dict]) -> list[Statement]:
    result: list[Statement] = []
    for statement in statements:
        statement_type = statement["type"]
        statement = statement["value"]
        match statement_type:
            case "set_var":
                result.append(SetVariable(statement["var"]))
            case "get_var":
                result.append(FetchVariable(statement["var"]))
            case "ask":
                result.append(AskQuestions([(q["var"].strip(), q["question"].strip()) for q in statement["questions"]]))
            case "for_each":
                result.append(ForEach(Procedure(make_statements(statement["block"]["statements"]))))
            case "for_each_paragraph":
                result.append(ForEachParagraph(Procedure(make_statements(statement["block"]["statements"]))))
            case "sql_read_only_query":
                result.append(
                    SQLStatement(
                        (Procedure(make_statements(statement["block"]["statements"])) if statement["block"] else None),
                        True,
                        statement["query"],
                    )
                )
            case "sql_mut_query":
                result.append(
                    SQLStatement(
                        (Procedure(make_statements(statement["block"]["statements"])) if statement["block"] else None),
                        False,
                        statement["query"],
                    )
                )
            case "sql_read_only_no_query":
                result.append(
                    SQLStatement(
                        (Procedure(make_statements(statement["block"]["statements"])) if statement["block"] else None),
                        True,
                        None,
                    )
                )
            case "sql_mut_no_query":
                result.append(
                    SQLStatement(
                        (Procedure(make_statements(statement["block"]["statements"])) if statement["block"] else None),
                        False,
                        None,
                    )
                )
            case "branch":
                if statement["default"]["type"] == "none":
                    default_branch = None
                else:
                    default_branch = Procedure(make_statements(statement["default"]["value"]["block"]["statements"]))
                result.append(
                    Branch(
                        branches={
                            branch["value"]: Procedure(make_statements(branch["block"]["statements"]))
                            for branch in statement["branches"]
                        },
                        default=default_branch,
                    )
                )
            case "format_string":
                result.append(FormatString(statement["template"]))
            case "call":
                result.append(ProcedureCall(statement["name"]))
    return result


class SQLManager:
    def __init__(self, filename="data.db") -> None:
        self.filename = filename
        self.connection = sqlite3.connect(self.filename)

    def execute_sql_script(self, query: str) -> None:
        cur = self.connection.cursor()
        cur.executescript(query)
        self.connection.commit()

    def execute_sql(
        self, query: str, read_only: bool, get_value: Callable[[str], str] | None
    ) -> Iterator[dict[str, str]]:
        cur = self.connection.cursor()
        if read_only:
            cur.execute("pragma query_only = ON;")
        data: dict[str, str] = {}
        while True:
            try:
                cur.execute(query, data)
                break
            except sqlite3.ProgrammingError as e:
                pattern = re.compile(r"^[^:]*:(.*)\.$")
                match = pattern.match(e.args[0])
                if match is not None:
                    key_name = match.group(1)
                    if get_value is None:
                        data[key_name] = ""
                    else:
                        data[key_name] = get_value(key_name)
                else:
                    print(f"Error on query: {query}")
                    self.connection.rollback()
                    traceback.print_exc()
                    breakpoint()
                    raise
            except Exception as e:
                print(f"Error on query: {query}")
                self.connection.rollback()
                traceback.print_exc()
                breakpoint()
                raise

        for row in cur.fetchall():
            result = {}
            for col, value in zip(cur.description, row):
                result[col[0]] = value
            yield result

        if read_only:
            self.connection.rollback()
        else:
            self.connection.commit()
        cur.execute("pragma query_only = OFF;")

    def __del__(self) -> None:
        self.connection.close()


class BaseLLMManager:
    sql_manager: "SQLManager"
    checked: bool

    def check(self) -> None:
        if self.checked:
            return
        self.sql_manager.execute_sql_script(
            """
        create table if not exists responses(
            model_id text,
            prompt_hash text,
            data text,
            response text,
            deleted integer default 0,
            created_at timestamp default current_timestamp);
        create table if not exists llm_models(
            id integer primary key,
            model_id text,
            model_file_id text,
            model text,
            system text,
            prompt text,
            history text,
            created_at timestamp default current_timestamp);
        create table if not exists llm_model_names(
            id integer primary key,
            model_id text,
            name text);
        create unique index if not exists llm_model_names_idx on llm_model_names(model_id, name);
        """
        )
        self.check_llm_host()
        self.checked = True

    def check_llm_host(self) -> None:
        pass

    def _get_model_id(self, proc: LLMProcedure) -> tuple[str, str]:
        messages_flat = ":".join([x[0] + ":" + x[1] for x in proc.history])
        data = re.compile(r"[^a-zA-Z0-9\{\}\-_]+").sub(" ", f"{proc.model}{proc.system}{proc.prompt}{messages_flat}")
        model_id = hashlib.sha256(data.encode()).hexdigest()
        data = re.compile(r"[^a-zA-Z0-9\{\}\-_]+").sub(" ", f"{proc.model}{proc.system}{messages_flat}")
        model_file_id = hashlib.sha256(data.encode()).hexdigest()
        model_exists = list(
            self.sql_manager.execute_sql(
                "select count(*) as count from llm_models where model_file_id=:model_file_id",
                True,
                ValueGetter(model_file_id=model_file_id),
            )
        )[0]["count"]
        if model_exists == 0:
            message_list = "\n".join([f"MESSAGE {x[0]} {x[1]}" for x in proc.history])
            model_file = f'''FROM {proc.model}
SYSTEM """{proc.system}"""
{message_list}
'''
            self._upload_model_file(model_file_id, model_file)
            list(
                self.sql_manager.execute_sql(
                    """insert into llm_models(
                        model_id,
                        model_file_id,
                        model,
                        system,
                        prompt,
                        history
                    ) values (
                        :model_id,
                        :model_file_id,
                        :model,
                        :system,
                        :prompt,
                        :history
                    )""",
                    False,
                    ValueGetter(
                        model=proc.model,
                        system=proc.system,
                        model_id=model_id,
                        model_file_id=model_file_id,
                        prompt=proc.prompt,
                        history=json.dumps(proc.history),
                    ),
                )
            )
        return model_id, model_file_id

    def check_model_existance(self, model_file_id: str) -> bool:
        raise NotImplementedError()

    def _upload_model_file(self, model_file_id: str, model_file: str) -> None:
        raise NotImplementedError()

    def _get_input_data_hash(self, data: dict[str, str]) -> str:
        pattern = re.compile(r"[^a-zA-Z]+")
        text = []
        for key in sorted(data.keys()):
            value = data[key]
            text.append(key)
            text.append(pattern.sub(" ", value))
        return hashlib.sha256(":".join(text).encode()).hexdigest()

    def run_llm(self, procedure: LLMProcedure, data: dict[str, str]) -> str:
        self.check()
        result = None
        prompt_hash = self._get_input_data_hash(data)
        model_id, model_file_id = self._get_model_id(procedure)
        list(
            self.sql_manager.execute_sql(
                "insert into llm_model_names(model_id, name) values (:model_id, :name) on conflict do nothing",
                False,
                ValueGetter(model_id=model_id, name=procedure.name),
            )
        )
        for row in self.sql_manager.execute_sql(
            "select response from responses where model_id = :model_id and prompt_hash=:prompt_hash and deleted = 0",
            True,
            ValueGetter(model_id=model_id, prompt_hash=prompt_hash),
        ):
            result = row["response"].strip()
            break
        if result is not None and result != "":
            return result
        result = self.run_model(model_file_id, procedure.prompt.format(**data))
        list(
            self.sql_manager.execute_sql(
                "insert into responses(model_id, prompt_hash, data, response) values (:model_id, :prompt_hash, :data, :response)",
                False,
                ValueGetter(model_id=model_id, prompt_hash=prompt_hash, data=json.dumps(data), response=result),
            )
        )
        return result

    def run_model(self, model_file_id: str, prompt: str) -> str:
        raise NotImplementedError()


class RemoteLLMRunner(BaseLLMManager):
    def __init__(self, llm_host) -> None:
        self.sql_manager = SQLManager("llm_data.db")
        self.checked = False
        self.llm_host = llm_host

    def check_llm_host(self) -> None:
        result = sp.run(["ssh", self.llm_host, f"echo 'hi'"], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"couldn't connect to llm server:\n{result.stderr.decode()}")
        return None

    def _upload_model_file(self, model_file_id: str, model_file: str) -> None:
        result = sp.run(["ssh", self.llm_host, f"ollama show {model_file_id}"], capture_output=True)
        if result.returncode == 0:
            return
        result = sp.run(
            ["ssh", self.llm_host, f"cat > /tmp/{model_file_id}.txt"], input=model_file.encode(), capture_output=True
        )
        result = sp.run(
            ["ssh", self.llm_host, f"ollama create {model_file_id} -f /tmp/{model_file_id}.txt"],
            capture_output=True,
        )

    def run_model(self, model_file_id: str, prompt: str) -> str:
        process_result = sp.run(
            ["ssh", self.llm_host, f"ollama run {model_file_id} --nowordwrap"],
            input=prompt.encode(),
            capture_output=True,
        )
        result = process_result.stdout.decode().strip()
        if result == "":
            breakpoint()
        return result


class LocalLLMRunner(BaseLLMManager):
    def __init__(self) -> None:
        self.sql_manager = SQLManager("llm_data.db")
        self.checked = False

    def _upload_model_file(self, model_file_id: str, model_file: str) -> None:
        result = sp.run(["ollama", "show", model_file_id], capture_output=True)
        if result.returncode == 0:
            return
        with open(f"/tmp/{model_file_id}.txt", "w") as f:
            f.write(model_file)
        result = sp.run(
            ["ollama", "create", model_file_id, "-f", f"/tmp/{model_file_id}.txt"],
            capture_output=True,
        )

    def run_model(self, model_file_id: str, prompt: str) -> str:
        process_result = sp.run(
            ["ollama", "run", model_file_id, "--nowordwrap"],
            input=prompt.encode(),
            capture_output=True,
        )
        result = process_result.stdout.decode().strip()
        if result == "":
            breakpoint()
        return result


class ValueGetter(dict):
    def __call__(self, key) -> str:
        return self[key]


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--program", default="workflow.md")
    argparser.add_argument("--procedure", default=None)
    argparser.add_argument("--input-file", default=None)
    argparser.add_argument("--check", action="store_true", default=False)
    argparser.add_argument("--add-undefined", action="store_true", default=False)
    argparser.add_argument("--verbose", action="store_true", default=False)
    argparser.add_argument("--llm-host", default=None)
    args = argparser.parse_args()

    llm_runner: BaseLLMManager
    if args.llm_host is None:
        llm_runner = LocalLLMRunner()
    else:
        llm_runner = RemoteLLMRunner(llm_host=args.llm_host)

    with open(args.program, "r") as f:
        program_code = f.read()
        system = System(parse_program(program_code), llm_runner, SQLManager(), args.verbose)

    if args.check or args.add_undefined:
        undefined = system.get_undefined_procedures()
        if len(undefined) > 0:
            if args.add_undefined:
                new_procedures = [
                    f"""# {name}

Model: llama3.2

## System

...

## Prompt

{{prompt}}

## History

U: ...
A: ...
"""
                    for name in undefined
                ]
                with open(args.program, "a") as f:
                    f.write("\n" + "\n".join(new_procedures))
                print("added new procedures")
            if args.add_undefined or args.check:
                print("Some undefined procedures:")
                for proc in undefined:
                    print(f"  {proc}")
            exit(1)
        else:
            print("No undefined procedures!")
            exit(0)

    if args.input_file is None:
        input_file = sys.stdin.read()
    else:
        with open(args.input_file, "r") as f:
            input_file = f.read()

    system.set_var("prompt", input_file)

    system.begin(args.procedure)
