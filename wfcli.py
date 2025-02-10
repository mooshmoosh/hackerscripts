import subprocess as sp
import re
import sys
import os
import yaml
import sqlite3
import readline
import traceback


class BreakProcedureLoop(Exception):
    pass


class StateMachine:
    def __init__(self, states_file, connection):
        self.state = None
        self.states_file = states_file
        self.conn = connection
        self.data = {}

    def update_with_data(self, row):
        for key, value in self.data.items():
            if key not in row:
                row[key] = value

    def next(self):
        if self.state is None:
            self.reload_state_file()
            self.state = next(iter(self.states.keys()))
        os.system("clear")
        for query in self.states[self.state].get("queries", []):
            try:
                self.perform_query(query)
            except BreakProcedureLoop:
                break
        self.display(self.states[self.state].get("display", ""))
        if "tables" in self.states[self.state]:
            tables = self.states[self.state]["tables"]
            for query, template in zip(tables[:-1:2], tables[1::2]):
                if query is None or query.strip() == "":
                    rows = [{}]
                else:
                    rows = self.exec_many(query)
                previous_row = {}
                for row in rows:
                    self.update_with_data(row)
                    self.display(template, row, previous_row)
                    previous_row = row
        input_text = input(">>> ")
        self.reload_state_file()
        for command in self.states[self.state].get("commands", []):
            if "command" not in command:
                self.do_command(command, input_text)
                break
            elif command["command"] == input_text:
                self.do_command(command, "")
                break
            elif input_text.startswith(command["command"] + " "):
                self.do_command(command, input_text[len(command["command"]) :].strip())
                break

    def reload_state_file(self):
        with open(self.states_file, "r") as f:
            self.states = yaml.safe_load(f.read())

    def display(self, template, data=None, previous_data=None):
        if isinstance(template, str):
            return self.display_one(template, data)
        elif isinstance(template, dict):
            return self.display_with_grouping(template["display"], template["groups"], data, previous_data)

    def display_one(self, template, data):
        if data is None:
            data = self.data
        while True:
            try:
                print(template.format(**data))
                return
            except KeyError as e:
                data[e.args[0]] = None

    def display_with_grouping(self, template, groups, data, previous_data):
        """
        How should this work?
        ideas:
            groups is a list of columns to group by
                if the column changes, then the new value is used
                otherwise an empty string is used
            the template object is a list of cascading objects
                column: the column to check, if this one has changed, use
                  display. if the column hasb't changed, move on to the next
                  item in template
                display: the format string to use to format data
        """
        new_data = data.copy()
        for group in groups:
            if new_data.get(group) == previous_data.get(group):
                new_data[group] = ""
        return self.display_one(template, new_data)

    def do_command(self, command, input_text):
        self.data["__input"] = input_text
        for query in command.get("queries", []):
            try:
                self.perform_query(query)
            except BreakProcedureLoop:
                break
        next_state = command.get("to", self.state)
        if next_state == "__next" and "__next" in self.data:
            next_state = self.data.pop("__next")
        if next_state in self.states:
            self.state = next_state

    def perform_query(self, query):
        if isinstance(query, str):
            self.exec_one(query)
        elif isinstance(query, dict):
            if "filename" in query:
                self.write_file_command(**query)
            elif "bash" in query:
                self.bash_command(**query)
            elif "choices" in query:
                self.choice_command(**query)
            elif "select_from" in query:
                self.multi_choice_command(**query)
            elif "prompt" in query:
                self.get_prompt(**query)

    def get_prompt(self, prompt, target, display=""):
        """
        Simple: ask a prompt and save the result to a variable
        """
        self.display(display)
        self.data[target] = input(prompt + " >>>")

    def multi_choice_command(self, select_from: str, query: str, format: str, display: str | None = None):
        """
        display some text
        perform a query
        display the output with an enumerated number next to each row
        ask for input (space separated list of numbers)
        perform a query using each of the selected options
        """
        if display is not None:
            self.display(display)

        all_rows = {}
        try:
            for idx, row in enumerate(self.exec_many(select_from)):
                all_rows[idx] = row.copy()
                self.update_with_data(row)
                self.display(f"{1 + idx} " + format, row)
        except sqlite3.OperationalError:
            print(traceback.format_exc())
            input("(Error raised, hit enter)")
            raise BreakProcedureLoop()

        if len(all_rows) == 0:
            raise BreakProcedureLoop()

        while True:
            chosen = input(">>> ")
            if chosen == "":
                rows = []
                break
            try:
                chosen = [int(x) - 1 for x in chosen.split()]
                rows = [all_rows[x] for x in chosen]
                break
            except (KeyError, ValueError):
                pass

        cur = self.conn.cursor()
        for row in rows:
            self.update_with_data(row)
            cur.execute(query, row)

    def choice_command(self, choices: str, format: str, display: str | None = None, null_check=None):
        """
        display some text
        perform a query
        display the output with an enumerated number next to each row
        ask for input (a number)
        use the row selected to set variables

        null_check: if null_check is not null, look at the variable it refers to. If that variable
        is not null then do not ask for a selection. This lets you implement defaults but ask a
        question if they're missing
        """
        if null_check is not None:
            if self.data.get(null_check, None) is not None:
                return

        if display is not None:
            self.display(display)

        all_rows = {}
        any_results = False
        try:
            for idx, row in enumerate(self.exec_many(choices)):
                any_results = True
                all_rows[idx] = row.copy()
                self.update_with_data(row)
                self.display(f"{1 + idx} " + format, row)
        except sqlite3.OperationalError:
            print(traceback.format_exc())
            input("(Error raised, hit enter)")
            raise BreakProcedureLoop()
        if not any_results:
            raise BreakProcedureLoop()

        if len(all_rows) == 0:
            return

        while True:
            chosen = input(">>> ")
            if chosen == "":
                chosen = None
                raise BreakProcedureLoop()
            try:
                chosen = int(chosen) - 1
                all_rows[chosen]
                break
            except (KeyError, ValueError):
                pass

        if chosen is not None:
            for key, value in all_rows[chosen].items():
                self.data[key] = value

    def bash_command(self, bash: str, query=None, system=False, multiline=True, sep="|"):
        """
        bash is a template string that will be executed
        stdout and stdin will be captured and saved as __stdout and __stdin

        if the result is a json object, the values that are atoms will be unpacked into variables

        if a query is provided:
            if stdout is a json array, the query will be run for each item in the array
            if each item is an atom it will be in the __value variable
            if its an object it will be unpacked
            if they're arrays, teh values will be unpacked as __1, __2, __3...

            if stdout is is not json, the query will be run for each line
            the whole line will be in __line
            the line will be split on spaces, and each field will be in __1, __2, __3...
        """
        command = bash.format(**self.data)
        if system:
            # System commands are just run without expecting any output.
            # this is for running other applications like text editors.
            os.system(command)
            return
        else:
            command_result = sp.run(command, shell=True, capture_output=True)

        self.data["__stdout"] = command_result.stdout.decode()
        self.data["__stderr"] = command_result.stderr.decode()

        try:
            json_data = json.loads(self.data["__stdout"])
        except:
            json_data = None

        if isinstance(json_data, dict):
            for key, value in json_data.items():
                self.data[key] = value

        if query is not None and isinstance(json_data, list):
            cur = self.conn.cursor()
            for item in json_data:
                item.update(self.data)
                cur.execute(query, item)
            self.conn.commit()
        elif query is not None and json_data is None:
            if multiline:
                cur = self.conn.cursor()
                for line in self.data["__stdout"].splitlines():
                    item = {"__line": line}
                    for idx, field in enumerate(line.split(sep)):
                        item[f"__{idx+1}"] = field
                    item.update(self.data)
                    cur.execute(query, item)
                self.conn.commit()
            else:
                cur = self.conn.cursor()
                cur.execute(query, self.data)
                self.conn.commit()

    def write_file_command(self, filename, template, query=None, append=False):
        """
        filename is the filename to write

        template is the template of text to write
        if query is none, the template is powered by variables in self.data

        if query is a string, then run the query and get a list of rows
        template each row with the template, concatenate them all together, and write that to the
        file

        if append == true, append to the file instead of overwriting
        """
        mode = "a" if append else "w"
        with open(filename, mode) as f:
            if query is None:
                while True:
                    try:
                        formatted = template.format(**self.data)
                        break
                    except KeyError as e:
                        self.data[e.args[0]] = ""
                f.write(formatted)
            else:
                for row in self.exec_many(query):
                    self.update_with_data(row)
                    f.write(template.format(**row))

    def exec_one(self, query):
        cur = self.conn.cursor()
        self.exec_query_with_missing_key_handling(cur, query)
        row = cur.fetchone()
        if cur.description is not None and row is not None:
            for col, value in zip(cur.description, row):
                self.data[col[0]] = value
        self.conn.commit()

    def exec_many(self, query):
        cur = self.conn.cursor()
        self.exec_query_with_missing_key_handling(cur, query)
        if cur.description is None:
            return
        for row in cur.fetchall():
            result = {}
            for col, value in zip(cur.description, row):
                result[col[0]] = value
            yield result

    def exec_query_with_missing_key_handling(self, cur, query):
        while True:
            try:
                cur.execute(query, self.data)
                break
            except sqlite3.ProgrammingError as e:
                pattern = re.compile(r"^[^:]*:(.*)\.$")
                match = pattern.match(e.args[0])
                if match is not None:
                    key_name = match.group(1)
                    self.data[key_name] = None
                else:
                    print(f"Error on query: {query}")
                    raise
            except:
                print(f"Error on query: {query}")
                raise


def main():
    if len(sys.argv) >= 2:
        states_file = sys.argv[1]
    else:
        print("Need a workflow yaml file")
        return
    if len(sys.argv) >= 3:
        conn = sqlite3.connect(sys.argv[2])
    else:
        conn = sqlite3.connect("wfcli.db")
    machine = StateMachine(states_file, conn)
    while True:
        try:
            machine.next()
        except EOFError:
            print("Bye!")
            return


if __name__ == "__main__":
    main()
