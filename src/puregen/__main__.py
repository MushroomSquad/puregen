import ast
from collections import defaultdict
from enum import Enum
import os
import re
from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser
from datamodel_code_generator.parser.openapi import OpenAPIParser
from datamodel_code_generator.parser.graphql import GraphQLParser

import typer

app = typer.Typer()


class SupportedTypes(str, Enum):
    openapi = "openapi"
    jsonschema = "jsonschema"
    graphql = "graphql"


class AvailableParsers(Enum):
    openapi = OpenAPIParser
    jsonschema = JsonSchemaParser
    graphql = GraphQLParser


class ClassCollector(ast.NodeVisitor):
    """
    Collects class definitions from the source code.

    Note:
        Only top-level classes are recorded. Nested classes (e.g. Config inside a model)
        are included as part of the parent class.
    """

    def __init__(self, source: str):
        """
        Initializes the ClassCollector.

        Args:
            source: The source code string to analyze.
        """
        self.source = source
        self.classes = {}  # Mapping: class name -> source code of the class definition
        self.nesting = 0  # Current nesting level

    def visit_ClassDef(self, node: ast.ClassDef):
        """
        Visits a class definition node in the AST.

        If the class is top-level (nesting level 0), its source code is recorded.
        """
        if self.nesting == 0:
            snippet = ast.get_source_segment(self.source, node)
            self.classes[node.name] = snippet
        self.nesting += 1
        self.generic_visit(node)
        self.nesting -= 1


def split_into_words(name: str) -> list:
    """
    Splits a CamelCase name into its component words.

    For example, "UserTaskListBase" -> ["User", "Task", "List", "Base"]

    Args:
        name: The CamelCase string.

    Returns:
        A list of words extracted from the name.
    """
    return re.findall(r"[A-Z][a-z0-9]*", name)


def camel_to_snake(name: str) -> str:
    """
    Converts a CamelCase string to snake_case.

    For example, "Request" -> "request", "CurrentValue" -> "current_value"

    Args:
        name: The CamelCase string.

    Returns:
        The snake_case version of the string.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def generate_models(
    input_file: str,
    input_file_type: SupportedTypes,
) -> str:
    """
    Generates models from an OpenAPI specification using datamodel-code-generator.

    Args:
        input_file: A string containing the specification.
        input_file_type: A string containing one of the file types.

    Returns:
        A string containing the generated model code.
    """
    data_model_types = get_data_model_types(
        DataModelType.PydanticV2BaseModel, target_python_version=PythonVersion.PY_311
    )
    match input_file_type:
        case "openapi":
            parser = OpenAPIParser
        case "jsonschema":
            parser = JsonSchemaParser
        case "graphql":
            parser = GraphQLParser
        case _:
            raise
    return parser(
        input_file,
        data_model_type=data_model_types.data_model,
        data_model_root_type=data_model_types.root_model,
        data_model_field_type=data_model_types.field_model,
        data_type_manager_type=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
    ).parse()


def get_classes(models: str) -> dict[str, str]:
    """
    Extracts class definitions from the generated models code using AST.

    Args:
        models: A string containing the generated models code.

    Returns:
        A dictionary mapping class names to their source code definitions.
    """
    collector = ClassCollector(models)
    tree = ast.parse(models)
    collector.visit(tree)
    return collector.classes


def count_prefixes(names: list[str]) -> tuple:
    """
    Counts the occurrences of possible prefixes (sequences of initial words)
    in the given class names.

    Args:
        names: A list of class names in CamelCase.

    Returns:
        A tuple containing:
            - A dictionary mapping each prefix (as a tuple of words) to its count.
            - A dictionary mapping each class name to its list of component words.
    """
    prefix_count = defaultdict(int)
    words_by_name = {}
    for name in names:
        segments = split_into_words(name)
        words_by_name[name] = segments
        for i in range(1, len(segments)):
            prefix = tuple(segments[:i])
            prefix_count[prefix] += 1
    return prefix_count, words_by_name


def calculate_prefixes(words_by_name, prefix_count):
    """
    Determines the longest common prefix for each class name that occurs in at least two classes.

    If such a prefix is found:
        - The folder name is the concatenation of the prefix words (e.g. "UserTaskList").
        - The remainder is used to form the file name (e.g. "Base", "Request", etc.).
    If no common prefix is found, the class gets its own folder and the file name is "base.py".

    Args:
        words_by_name: A dictionary mapping class names to their list of component words.
        prefix_count: A dictionary mapping each prefix (tuple of words) to its occurrence count.

    Returns:
        A dictionary mapping each class name to a tuple (folder_name, file_suffix).
    """
    assignment = {}  # Mapping: class name -> (group_folder, file_suffix)
    for name, segments in words_by_name.items():
        best_prefix = None
        best_length = 0
        for i in range(1, len(segments)):
            prefix = tuple(segments[:i])
            if prefix_count[prefix] >= 2 and i > best_length:
                best_prefix = prefix
                best_length = i
        if best_prefix is not None:
            group_folder = "".join(best_prefix)  # e.g., "UserTaskList"
            remainder = segments[len(best_prefix) :]
            file_suffix = "".join(remainder) if remainder else "Base"
            assignment[name] = (group_folder, file_suffix)
        else:
            assignment[name] = (name, "base")
    return assignment


def group_classes(assignment: dict) -> dict:
    """
    Groups classes by their folder name as determined by the assignment mapping.

    Args:
        assignment: A dictionary mapping each class name to a tuple (folder_name, file_suffix).

    Returns:
        A dictionary mapping folder names to a list of tuples (class_name, file_suffix).
    """
    groups = defaultdict(list)
    for name, (folder, file_suffix) in assignment.items():
        groups[folder].append((name, file_suffix))
    return groups


def refined_filter_common_imports(common_imports: str, class_source: str) -> str:
    """
    Refines the common import statements to include only those whose imported names
    are actually used in the class source.

    Args:
        common_imports: A string with all top-level import statements.
        class_source: The source code of the class.

    Returns:
        A string with only the necessary import statements.
    """
    # Extract all word tokens from the class source
    used_names = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", class_source))
    filtered_lines = []
    for line in common_imports.splitlines():
        line = line.strip()
        if not line:
            continue
        # Process "import ..." statements
        if line.startswith("import "):
            parts = line[len("import ") :].split(",")
            imported = []
            for part in parts:
                part = part.strip()
                if " as " in part:
                    alias = part.split(" as ")[1].strip()
                    imported.append(alias)
                else:
                    imported.append(part.split(".")[0].strip())
            if any(name in used_names for name in imported):
                filtered_lines.append(line)
        # Process "from ... import ..." statements
        elif line.startswith("from "):
            m = re.search(r"import\s+(.*)", line)
            if m:
                names_part = m.group(1)
                imported = []
                for part in names_part.split(","):
                    part = part.strip()
                    if " as " in part:
                        alias = part.split(" as ")[1].strip()
                        imported.append(alias)
                    else:
                        imported.append(part.strip())
                if any(name in used_names for name in imported):
                    filtered_lines.append(line)
    return "\n".join(filtered_lines)


def get_relative_imports_relative(
    class_source: str, current_class: str, current_folder: str, assignment: dict
) -> str:
    """
    Analyzes the AST of a class's source code to find names that refer to other generated classes
    and returns relative import statements.

    Args:
        class_source: The source code of the class.
        current_class: The name of the class defined in class_source.
        current_folder: The folder in which the current class resides.
        assignment: A dictionary mapping class names to (folder, file_suffix) tuples.

    Returns:
        A string containing relative import statements (one per line).
    """
    used_names = set()

    class NameCollector(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name):
            used_names.add(node.id)
            self.generic_visit(node)

    NameCollector().visit(ast.parse(class_source))
    imports = []
    for name in used_names:
        if name == current_class:
            continue
        if name in assignment:
            other_folder, other_file_suffix = assignment[name]
            module = camel_to_snake(other_file_suffix)
            if other_folder == current_folder:
                # Same folder: use single dot
                import_line = f"from .{module} import {name}"
            else:
                # Different folder: use relative import with two dots
                import_line = f"from ..{other_folder}.{module} import {name}"
            imports.append(import_line)
    unique_imports = sorted(set(imports))
    return "\n".join(unique_imports)


def create_folders(
    groups: dict,
    output_folder: str,
):
    """
    Creates the folder structure for the grouped classes.

    A root folder named 'groups' is created, and within it, subfolders for each group.
    For each class, a file is created with preliminary content (this will be overwritten later).

    Args:
        groups: A dictionary mapping folder names to lists of (class_name, file_suffix) tuples.
    """
    root_dir = output_folder
    os.makedirs(root_dir, exist_ok=True)

    for folder, items in groups.items():
        folder_path = os.path.join(root_dir, folder)
        os.makedirs(folder_path, exist_ok=True)
        for original_name, file_suffix in items:
            file_name = f"{camel_to_snake(file_suffix)}.py"
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# File for class {original_name}\n")
            print(f"Created file: {file_path}")


def write_classes(
    assignment: dict,
    extracted_classes: dict[str, str],
    common_imports: str,
    output_folder: str,
):
    """
    Writes class definitions to their respective files, prepending necessary filtered library imports
    and relative imports for local dependencies.

    Args:
        assignment: A dictionary mapping class names to (folder, file_suffix) tuples.
        extracted_classes: A dictionary mapping class names to their source code.
        common_imports: A string containing all top-level import statements from the generated models.
    """
    for class_name, (folder, file_suffix) in assignment.items():
        if class_name in extracted_classes:
            target_file = os.path.join(
                output_folder, folder, f"{camel_to_snake(file_suffix)}.py"
            )
            class_source = extracted_classes[class_name]
            filtered_imports = refined_filter_common_imports(
                common_imports, class_source
            )
            relative_imports = get_relative_imports_relative(
                class_source, class_name, folder, assignment
            )
            parts = []
            if filtered_imports.strip():
                parts.append(filtered_imports)
            if relative_imports.strip():
                parts.append(relative_imports)
            parts.append(class_source)
            file_content = "\n\n".join(parts)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"Class {class_name} written to file {target_file}")
        else:
            print(f"Class {class_name} not found")


def create_init_files(
    groups: dict,
    output_folder: str,
):
    """
    Creates __init__.py files for each group folder that explicitly import all classes in that folder,
    and creates a top-level __init__.py that explicitly imports all subpackage classes.
    Each __init__.py ends with an __all__ list containing the names of the exported classes.

    Args:
        groups: A dictionary mapping folder names to lists of (class_name, file_suffix) tuples.
        assignment: A dictionary mapping class names to (folder, file_suffix) tuples.
    """
    root_dir = output_folder
    # Create __init__.py for each subpackage folder
    for folder, items in groups.items():
        init_lines = []
        all_classes = []
        for class_name, file_suffix in items:
            module_name = camel_to_snake(file_suffix)
            init_lines.append(f"from .{module_name} import {class_name}")
            all_classes.append(class_name)
        init_lines.append("")
        init_lines.append(f"__all__: list[str] = {all_classes!r}")
        init_content = "\n".join(init_lines) + "\n"
        folder_path = os.path.join(root_dir, folder)
        init_path = os.path.join(folder_path, "__init__.py")
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)
        print(f"Created __init__.py in folder: {folder_path}")

    # Create top-level __init__.py that explicitly imports all classes from each subpackage
    top_level_imports = []
    all_top_classes = []
    for folder, items in groups.items():
        class_names = [class_name for class_name, _ in items]
        top_level_imports.append(f"from .{folder} import {', '.join(class_names)}")
        all_top_classes.extend(class_names)
    top_init_content = (
        "\n".join(top_level_imports)
        + "\n\n"
        + f"__all__: list[str] = {all_top_classes!r}\n"
    )
    top_init_path = os.path.join(root_dir, "__init__.py")
    with open(top_init_path, "w", encoding="utf-8") as f:
        f.write(top_init_content)
    print(f"Created top-level __init__.py in folder: {root_dir}")


@app.callback(invoke_without_command=True)
def main(
    input: str = typer.Option(
        ...,
        "--input",
        help="Input file/directory",
    ),
    input_file_type: SupportedTypes = typer.Option(
        ...,
        "--input-file-type",
        help="{openapi, jsonschema, graphql} Input file type",
    ),
    output_folder: str = typer.Option(
        "models",
        "--output-folder",
        help="Output folder for generated models",
    ),
):
    """
    Main function that:
        1. Reads specification from file.
        2. Generates Pydantic models from the specification.
        3. Extracts class definitions from the generated models.
        4. Groups the classes based on common name prefixes.
        5. Creates the folder structure and files.
        6. Prepends each file with only the necessary library and relative imports.
        7. Creates __init__.py files for proper package structure.
    """
    read_file: str = open(input, "r").read()
    models: str = generate_models(
        read_file,
        input_file_type,
    )
    # Extract all top-level import lines from the generated models code
    common_imports: str = "\n".join(
        line
        for line in models.splitlines()
        if line.strip().startswith(("import", "from"))
    )
    classes: dict[str, str] = get_classes(models)
    classes_names: list[str] = list(classes.keys())
    prefix_count, words_by_name = count_prefixes(classes_names)
    assignment = calculate_prefixes(words_by_name, prefix_count)
    groups = group_classes(assignment)
    create_folders(
        groups,
        output_folder,
    )
    write_classes(
        assignment,
        classes,
        common_imports,
        output_folder,
    )
    create_init_files(
        groups,
        output_folder,
    )


if __name__ == "__main__":
    app()
