import re


def extract_functions_and_classes(content: str, extension: str) -> list[dict]:
    """Extract function and class definitions using regex-based parsing.
    Lightweight alternative to tree-sitter that requires no grammar compilation."""
    items = []

    if extension in (".py",):
        items.extend(_parse_python(content))
    elif extension in (".js", ".ts", ".jsx", ".tsx"):
        items.extend(_parse_javascript(content))
    elif extension in (".java", ".cs", ".kt", ".scala"):
        items.extend(_parse_java_like(content))
    elif extension in (".go",):
        items.extend(_parse_go(content))
    elif extension in (".rb",):
        items.extend(_parse_ruby(content))
    elif extension in (".c", ".cpp", ".h", ".hpp"):
        items.extend(_parse_c_like(content))

    return items


def _parse_python(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"^(class\s+(\w+).*?:)", content, re.MULTILINE):
        items.append({"type": "class", "name": m.group(2), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"^(\s*(?:async\s+)?def\s+(\w+)\s*\(.*?\).*?:)", content, re.MULTILINE):
        items.append({"type": "function", "name": m.group(2), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"^(\w+)\s*=\s*(?:import|__import__)", content, re.MULTILINE):
        items.append({"type": "variable", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items


def _parse_javascript(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"class\s+(\w+)", content):
        items.append({"type": "class", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\(|function))", content):
        name = m.group(1) or m.group(2)
        items.append({"type": "function", "name": name, "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"(\w+)\s*\(.*?\)\s*{", content):
        if m.group(1) not in ("if", "for", "while", "switch", "catch"):
            items.append({"type": "method", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items


def _parse_java_like(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"(?:public|private|protected)?\s*(?:static\s+)?class\s+(\w+)", content):
        items.append({"type": "class", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(", content):
        items.append({"type": "method", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items


def _parse_go(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", content):
        items.append({"type": "function", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"type\s+(\w+)\s+struct", content):
        items.append({"type": "struct", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items


def _parse_ruby(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"class\s+(\w+)", content):
        items.append({"type": "class", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"def\s+(\w+)", content):
        items.append({"type": "method", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items


def _parse_c_like(content: str) -> list[dict]:
    items = []
    for m in re.finditer(r"(?:class|struct)\s+(\w+)", content):
        items.append({"type": "class", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r"[\w*]+\s+(\w+)\s*\([^)]*\)\s*{", content):
        if m.group(1) not in ("if", "for", "while", "switch"):
            items.append({"type": "function", "name": m.group(1), "line": content[:m.start()].count("\n") + 1})
    return items
