#!/usr/bin/env python
import csv
import os
import itertools
import shutil
import argparse
import functools

try:
    import yaml
    import jinja2
    import z3
except ImportError:
    for pkg, name in [x.split() for x in """
pyyaml yaml
jinja2 jinja2
z3solver z3
""".strip().split("\n")]:
        try:
            globals()[name] = __import__(name)
        except ImportError:
            import pip

            pip.main(["install", pkg])
            globals()[name] = __import__(name)


def parse_csv_value(value):
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    value = value.strip()
    if value == "":
        return None
    return value


def load_data(data_dir):
    data = {}
    for filename in os.listdir(data_dir):
        name, extension = os.path.splitext(filename)
        with open(os.path.join(data_dir, filename), "r") as f:
            if filename == "main.yaml":
                to_generate = yaml.safe_load(f.read())
            elif extension == ".yaml":
                data[name] = yaml.safe_load(f.read())
            elif extension == ".icsv":
                data[name] = {}
                reader = csv.DictReader(f)
                index_column = reader.fieldnames[0]
                for text_row in reader:
                    for key, value in text_row.items():
                        data[name][text_row[index_column]] = {
                            key: parse_csv_value(value) for key, value in text_row.items()
                        }
            elif extension == ".csv":
                data[name] = []
                reader = csv.DictReader(f)
                for row in reader:
                    data[name].append({key: parse_csv_value(value) for key, value in row.items()})
    return to_generate, data


class ObjectWrapper(dict):
    def __getattr__(self, key):
        result = self.get(key)
        if isinstance(result, dict):
            return ObjectWrapper(result)
        elif isinstance(result, list):
            return ListWrapper(result)
        else:
            return result

    def __getitem__(self, key):
        result = self.get(key)
        if isinstance(result, dict):
            return ObjectWrapper(result)
        elif isinstance(result, list):
            return ListWrapper(result)
        else:
            return result


class ListWrapper(list):
    def __getitem__(self, index):
        try:
            result = super().__getitem__(index)
        except IndexError:
            return None
        if isinstance(result, dict):
            return ObjectWrapper(result)
        elif isinstance(result, list):
            return ListWrapper(result)
        else:
            return result


def wrapper(item):
    if isinstance(item, list):
        return ListWrapper(item)
    elif isinstance(item, dict):
        return ObjectWrapper(item)
    else:
        return item


def set_path(root, path, value):
    for step, following in itertools.pairwise(path):
        if isinstance(root, list):
            while len(root) <= step:
                root.append(None)
            if root[step] == None:
                if isinstance(following, int):
                    root[step] = []
                else:
                    root[step] = {}
            root = root[step]
        elif isinstance(root, dict):
            if isinstance(following, int):
                root = root.setdefault(step, [])
            else:
                root = root.setdefault(step, {})
    if isinstance(root, list):
        while len(root) <= path[-1]:
            root.append(None)
    root[path[-1]] = value


class Z3Enum:
    def __init__(self, options, name):
        self.variables = {option: z3.Bool(f"{name}.{option}") for option in options}

    def __eq__(self, value):
        if isinstance(value, Z3Enum):
            result = True
            for key in set(self.variables.keys()).union(set(value.variables.keys())):
                result = z3.And(result, (self.variables.get(key, False) == value.variables.get(key, False)))
            return result
        else:
            return self.variables.get(value, False)

    def __ne__(self, other):
        return z3.Not(self == other)

    def get_value(self, model):
        for option, variable in self.variables.items():
            if bool(model[variable]):
                return option
        return None

    def get_constraints(self):
        return (z3.AtLeast(*self.variables.values(), 1), z3.AtMost(*self.variables.values(), 1))


def get_model_value(model, var_type, variable):
    if var_type == "Real":
        return float(model[variable].as_fraction())
    elif var_type == "Int":
        return int(model[variable].py_value())
    elif var_type == "Bool":
        return bool(model[variable])
    elif var_type == "Enum":
        return variable.get_value(model)
    else:
        return model[variable]


def solve_model(model, data):
    variables = {}
    types = {}
    sets = model.get("sets", {})
    eval_locals = {}
    eval_locals.update(sets)
    eval_locals["d"] = data
    for var_name, var_defn in model.get("variables", {}).items():
        [var_type, *set_defs] = var_defn.split()
        dimensions = []
        for set_def in set_defs:
            try:
                dimensions.append(range(int(set_def)))
            except ValueError:
                dimensions.append(sets[set_def])
        if var_type == "Enum":
            options = dimensions[-1]
            dimensions = dimensions[:-1]
            var_class = functools.partial(Z3Enum, options)
        else:
            var_class = getattr(z3, var_type)
        for instance in itertools.product(*dimensions):
            z3_name = [var_name]
            for step in instance:
                z3_name += ['["', str(step), '"]']
            variable_path = (var_name,) + instance
            variables[variable_path] = var_class("".join(z3_name))
            types[variable_path] = var_type
            set_path(eval_locals, variable_path, variables[variable_path])
    eval_locals = {k: wrapper(v) for k, v in eval_locals.items()}
    eval_locals["z3"] = z3

    if "minimize" in model:
        solver = z3.Optimize()
        solver.minimize(eval(model["minimize"], globals=eval_locals))
    elif "maximize" in model:
        solver = z3.Optimize()
        solver.maximize(eval(model["maximize"], globals=eval_locals))
    else:
        solver = z3.Solver()
    # solver.set("sat.cardinality.solver", True)

    # Add constraints that the enums take at least one value
    for var_path, var_type in types.items():
        if var_type == "Enum":
            solver.add(variables[var_path].get_constraints())

    for constraint in model["satisfy"]:
        try:
            solver.add(eval(constraint, globals=eval_locals))
        except:
            print(f"Error adding {constraint=}")
            breakpoint()
            raise

    if solver.check() != z3.sat:
        raise RuntimeError(f"Unsat model")

    m = solver.model()
    result = {}
    for var_path, variable in variables.items():
        set_path(result, var_path, get_model_value(m, types[var_path], variable))
    return result


def merge_var_types(a, b):
    if a is None:
        return b
    if a == b:
        return a
    if set((a, b)) == set(("Int", "Real")):
        return "Real"
    else:
        raise ValueError()


def merge_dimensions(a, b):
    result = []
    for idx in range(max(len(a), len(b))):
        if idx >= len(a):
            a_piece = []
        else:
            a_piece = a[idx]
        if idx >= len(b):
            b_piece = []
        else:
            b_piece = b[idx]
        result.append(list(set(a_piece).union(set(b_piece))))
    return result


def tree_to_variables(var_tree, var_name):
    try:
        if isinstance(var_tree, bool):
            if var_tree:
                return "Bool", [], [f"{var_name}"]
            else:
                return "Bool", [], [f"~{var_name}"]
        elif isinstance(var_tree, int):
            return "Int", [], [f"{var_name} == {var_tree}"]
        elif isinstance(var_tree, float):
            return "Real", [], [f"{var_name} == {var_tree}"]
        elif isinstance(var_tree, str):
            return "Enum", [[var_tree]], [f'{var_name} == "{var_tree}"']
        elif isinstance(var_tree, list):
            first_dimension = len(var_tree)
            final_var_type = None
            final_dimensions = []
            all_satisfy = []
            for idx, value in enumerate(var_tree):
                var_type, remaining_dimensions, satisfy = tree_to_variables(value, f"{var_name}[{idx}]")
                final_var_type = merge_var_types(final_var_type, var_type)
                final_dimensions = merge_dimensions(final_dimensions, remaining_dimensions)
                all_satisfy += satisfy
            return (final_var_type, [first_dimension] + final_dimensions, all_satisfy)
        elif isinstance(var_tree, dict):
            first_dimension = []
            final_var_type = None
            final_dimensions = []
            all_satisfy = []
            for key, value in var_tree.items():
                first_dimension.append(key)
                var_type, remaining_dimensions, satisfy = tree_to_variables(value, f"{var_name}.{key}")
                final_var_type = merge_var_types(final_var_type, var_type)
                final_dimensions = merge_dimensions(final_dimensions, remaining_dimensions)
                all_satisfy += satisfy
            return (final_var_type, [first_dimension] + final_dimensions, all_satisfy)
    except ValueError as e:
        raise ValueError("Could not get consistent types for variable: {var_name=}. ({e.args})")


if __name__ == "__main__":
    arg_config = argparse.ArgumentParser()
    arg_config.add_argument("--new-layer")
    arg_config.add_argument("--new-project")
    arg_config.add_argument("--new-template")
    arg_config.add_argument("--new-model")
    args = arg_config.parse_args()
    if args.new_project is not None:
        # Create a new project with all the files in this directory and one layer
        files = os.listdir(".")
        new_dir_name = f"000_{args.new_project}"
        os.mkdir(new_dir_name)
        for filename in files:
            os.rename(filename, os.path.join(new_dir_name, filename))
        print("ok")
    elif args.new_model is not None:
        # Convert a data file to a model
        layers = os.listdir(".")
        layers.sort()
        top_layer = layers[-1]
        filename = os.path.join(top_layer, "data", args.new_model)
        new_filename = os.path.join(top_layer, "models", args.new_model)
        with open(filename, "r") as f:
            target = yaml.safe_load(f.read())

        model = {"output": os.path.splitext(args.new_model)[0], "sets": {}, "variables": {}, "satisfy": []}
        for key, var_tree in target.items():
            var_type, dimensions, path_values = tree_to_variables(var_tree, key)
            var_spec = [var_type]
            for idx, dimension in enumerate(dimensions):
                if isinstance(dimension, list):
                    dimension_name = f"{key}_{idx}"
                    model["sets"][dimension_name] = dimension
                    var_spec.append(dimension_name)
                elif isinstance(dimension, int):
                    var_spec.append(str(dimension))
            model["variables"][key] = " ".join(var_spec)
            model["satisfy"] += path_values

        with open(new_filename, "w") as f:
            f.write(yaml.safe_dump(model))

        os.remove(filename)
        print(f"Created a model for generating {filename} as {new_filename}")

    elif args.new_layer is not None:
        # Create a new layer
        layers = os.listdir(".")
        layers.sort()
        top_layer = int(layers[-1].split("_")[0])
        previous_top_layer = layers[-1]
        print(f"Top layer is {layers[-1]}, ({top_layer})")
        new_dir_name = f"{top_layer+1:03d}_{args.new_layer}"
        print(f"Creating directory {new_dir_name}")
        for path, _, filenames in os.walk(previous_top_layer):
            sub_path = os.path.splitroot(path[len(previous_top_layer) :])[2]
            new_subdir_name = os.path.join(new_dir_name, "static", sub_path)
            os.makedirs(new_subdir_name, exist_ok=True)
            for filename in filenames:
                new_path = os.path.join(new_subdir_name, filename)
                shutil.copyfile(os.path.join(path, filename), new_path)
        os.mkdir(os.path.join(new_dir_name, "data"))
        with open(os.path.join(new_dir_name, "data", "main.yaml"), "w") as f:
            f.write("[]")
        os.mkdir(os.path.join(new_dir_name, "templates"))
        os.mkdir(os.path.join(new_dir_name, "models"))
    elif args.new_template is not None:
        # Move a previously static file to be a template
        layers = os.listdir(".")
        layers.sort()
        top_layer = layers[-1]
        filename = os.path.join(top_layer, "static", args.new_template)
        new_filename = os.path.join(top_layer, "templates", args.new_template)
        print(f"making {filename} into a template")
        os.makedirs(os.path.dirname(new_filename), exist_ok=True)
        with open(filename, "r") as of:
            with open(new_filename, "w") as nf:
                nf.write(of.read().replace("{{", '{{"{{"}}').replace("{%", '{{"{%"}}'))
        os.remove(filename)
        with open(os.path.join(top_layer, "data", "main.yaml"), "r") as f:
            main_data = yaml.safe_load(f.read())
        main_data.append({"template": args.new_template, "filename": args.new_template})
        with open(os.path.join(top_layer, "data", "main.yaml"), "w") as f:
            f.write(yaml.safe_dump(main_data))
    else:
        print("Ready to run?")
        if input() != "y":
            exit()
        layers = os.listdir(".")
        layers.sort()
        for source, target in itertools.pairwise(reversed(layers)):
            try:
                int(source[:3])
                int(target[:3])
            except:
                continue
            print(f"processing {source} -> {target}")
            for path, _, filenames in os.walk(target):
                for filename in filenames:
                    os.remove(os.path.join(path, filename))
            data_dir = os.path.join(source, "data")
            to_generate, data = load_data(data_dir)
            model_dir = os.path.join(source, "models")
            for model_file in os.listdir(model_dir):
                model_filename = os.path.join(model_dir, model_file)
                if os.path.splitext(model_filename)[-1] == ".yaml":
                    with open(model_filename, "r") as f:
                        model = yaml.safe_load(f.read())
                    try:
                        data[model["output"]] = solve_model(model, data)
                    except RuntimeError:
                        raise RuntimeError(f"Could not get a solution to model in {model_filename}")
                with open(os.path.join(source, "data", f'{model["output"]}.yaml'), "w") as f:
                    f.write(yaml.safe_dump(data[model["output"]]))
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(source, "templates")))
            for dest_file in to_generate:
                with open(os.path.join(target, dest_file["filename"]), "w") as f:
                    dest_file["d"] = data
                    f.write(env.get_template(dest_file["template"]).render(dest_file))
            static_base_path = os.path.join(source, "static")
            for path, _, filenames in os.walk(static_base_path):
                for filename in filenames:
                    # get the new path
                    # replace source with target
                    # remove 'static'
                    sub_path = os.path.splitroot(path[len(static_base_path) :])[2]
                    new_path = os.path.join(target, sub_path, filename)
                    shutil.copyfile(os.path.join(path, filename), new_path)
