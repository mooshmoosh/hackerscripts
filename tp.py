#!/usr/bin/env python
import os
import itertools

try:
    import yaml
except ImportError:
    import pip

    pip.main(["install", "pyyaml"])
    import yaml

try:
    import jinja2
except ImportError:
    import pip

    pip.main(["install", "jinja2"])
    import jinja2

import shutil
import argparse

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

    elif args.new_template is not None:
        layers = os.listdir(".")
        layers.sort()
        top_layer = layers[-1]
        filename = os.path.join(top_layer, "static", args.new_template)
        new_filename = os.path.join(top_layer, "templates", args.new_template)
        print(f"making {filename} into a template")
        os.makedirs(os.path.dirname(new_filename), exist_ok=True)
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
            # TODO: Do something with data to build a SAT problem / LP, solve it and produce some more data to be used in the templating
            try:
                int(source[:3])
                int(target[:3])
            except:
                continue
            data = {}
            print(f"processing {source} -> {target}")
            data_dir = os.path.join(source, "data")
            for filename in os.listdir(data_dir):
                with open(os.path.join(data_dir, filename), "r") as f:
                    if filename == "main.yaml":
                        to_generate = yaml.safe_load(f.read())
                    else:
                        data[os.path.splitext(filename)[0]] = yaml.safe_load(f.read())
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
