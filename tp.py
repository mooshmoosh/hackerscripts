#!/usr/bin/env python
import csv
import os
import itertools
import shutil
import argparse

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
                for row in reader:
                    data[name][row[index_column]] = row
            elif extension == ".csv":
                data[name] = []
                reader = csv.DictReader(f)
                for row in reader:
                    data[name].append(row)
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


def solve_model(model, data):
    solver = z3.Solver()
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
        for instance in itertools.product(*dimensions):
            z3_name = [var_name]
            for step in instance:
                z3_name += ['["', step, '"]']
            variable_path = (var_name,) + instance
            variables[variable_path] = getattr(z3, var_type)("".join(z3_name))
            types[variable_path] = var_type
            set_path(eval_locals, variable_path, variables[variable_path])

    eval_locals = {k: wrapper(v) for k, v in eval_locals.items()}
    for constraint in model["satisfy"]:
        try:
            solver.add(eval(constraint, globals=eval_locals))
        except:
            print(f"Error adding {constraint=}")
            breakpoint()
            raise
    solver.check()
    m = solver.model()
    result = {}
    for var_path, variable in variables.items():
        if types[var_path] == "Real":
            try:
                set_path(result, var_path, float(m[variable].as_fraction()))
            except:
                breakpoint()
                raise
        elif types[var_path] == "Int":
            set_path(result, var_path, int(m[variable].as_fraction()))
        elif types[var_path] == "Bool":
            set_path(result, var_path, bool(m[variable]))
    return result


if __name__ == "__main__":
    arg_config = argparse.ArgumentParser()
    arg_config.add_argument("--new-layer")
    arg_config.add_argument("--new-project")
    arg_config.add_argument("--new-template")
    args = arg_config.parse_args()
    if args.new_project is not None:
        # Create a new project with all the files in this directory and one layer
        files = os.listdir(".")
        new_dir_name = f"000_{args.new_project}"
        try:
            os.mkdir(new_dir_name)
        except e:
            breakpoint()
            print(e)
            exit()
        for filename in files:
            os.rename(filename, os.path.join(new_dir_name, filename))
        print("ok")

    elif args.new_layer is not None:
        # Create a new layer
        # TODO: Alternatively, move the file and create a symlink from the old file location to the new file (possibly if this is not the first new layer we're creating)
        # TODO: gitignore the files in the previous top layer
        # (unless the previous top layer was the only one) We should track the very top layer and
        # the very bottom layer in git. If you do this by creating a .gitignore file in the directly
        # that ignores all files in that directory, then you'll still have the directory in git,
        # which we need because that defines how many layers there are in the system
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
                # TODO: replace the following with a symlink to the old file called the new filename (os.symlink)
                # os.symlink(os.path.join(path, filename), new_path)
                # but we still want to be able to check that we haven't changed the final generated text with git
                # So we might want to do this with each layer except the last one.
                shutil.copyfile(os.path.join(path, filename), new_path)
        os.mkdir(os.path.join(new_dir_name, "data"))
        with open(os.path.join(new_dir_name, "data", "main.yaml"), "w") as f:
            f.write("[]")
        os.mkdir(os.path.join(new_dir_name, "templates"))
        os.mkdir(os.path.join(new_dir_name, "models"))

    elif args.new_template is not None:
        layers = os.listdir(".")
        layers.sort()
        top_layer = layers[-1]
        filename = os.path.join(top_layer, "static", args.new_template)
        new_filename = os.path.join(top_layer, "templates", args.new_template)
        print(f"making {filename} into a template")
        os.makedirs(os.path.dirname(new_filename), exist_ok=True)
        # TODO: replace all jinja directives with escapes
        # {{ -> {{"{{"}}
        # {% -> {{"{%"}}
        os.rename(filename, new_filename)
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
            # TODO: Delete all files in target recursively
            try:
                int(source[:3])
                int(target[:3])
            except:
                continue
            print(f"processing {source} -> {target}")
            data_dir = os.path.join(source, "data")
            to_generate, data = load_data(data_dir)
            model_dir = os.path.join(source, "models")
            for model_file in os.listdir(model_dir):
                model_filename = os.path.join(model_dir, model_file)
                if os.path.splitext(model_filename)[-1] == ".yaml":
                    with open(model_filename, "r") as f:
                        model = yaml.safe_load(f.read())
                    data[model["output"]] = solve_model(model, data)
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
                    # TODO: replace the following with a symlink to the old file called the new filename (os.symlink)
                    # os.symlink(os.path.join(path, filename), new_path)
                    # but we still want to be able to check that we haven't changed the final generated text with git
                    # So we might want to do this with each layer except the last one.
                    shutil.copyfile(os.path.join(path, filename), new_path)
