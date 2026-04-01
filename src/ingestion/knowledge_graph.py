import re
import networkx as nx
from src.ingestion.ast_parser import extract_functions_and_classes


def build_knowledge_graph(files: list[dict]) -> dict:
    """Build a dependency/call graph from the file list."""
    G = nx.DiGraph()

    file_symbols = {}
    for f in files:
        path = f["path"]
        symbols = extract_functions_and_classes(f["content"], f["extension"])
        file_symbols[path] = symbols

        G.add_node(path, type="file", extension=f["extension"])
        for sym in symbols:
            node_id = f"{path}::{sym['name']}"
            G.add_node(node_id, type=sym["type"], line=sym["line"], file=path)
            G.add_edge(path, node_id, relation="defines")

    for f in files:
        path = f["path"]
        content = f["content"]
        _add_import_edges(G, path, content, f["extension"], files)
        _add_call_edges(G, path, content, file_symbols)

    stats = {
        "total_files": len(files),
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "functions": sum(1 for _, d in G.nodes(data=True) if d.get("type") == "function"),
        "classes": sum(1 for _, d in G.nodes(data=True) if d.get("type") in ("class", "struct")),
    }

    return {"graph": G, "file_symbols": file_symbols, "stats": stats}


def _add_import_edges(G: nx.DiGraph, path: str, content: str, ext: str, files: list[dict]):
    if ext == ".py":
        for m in re.finditer(r"(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", content):
            module = (m.group(1) or m.group(2)).replace(".", "/")
            for f in files:
                if module in f["path"]:
                    G.add_edge(path, f["path"], relation="imports")
                    break
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        for m in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", content):
            target = m.group(1)
            for f in files:
                if target.lstrip("./") in f["path"]:
                    G.add_edge(path, f["path"], relation="imports")
                    break
    elif ext in (".java", ".kt", ".scala"):
        for m in re.finditer(r"import\s+([\w.]+)", content):
            pkg = m.group(1).replace(".", "/")
            for f in files:
                if pkg in f["path"]:
                    G.add_edge(path, f["path"], relation="imports")
                    break


def _add_call_edges(G: nx.DiGraph, path: str, content: str, file_symbols: dict):
    all_symbols = {}
    for fpath, symbols in file_symbols.items():
        for sym in symbols:
            node_id = f"{fpath}::{sym['name']}"
            all_symbols[sym["name"]] = node_id

    my_symbols = {s["name"] for s in file_symbols.get(path, [])}
    for sym_name, node_id in all_symbols.items():
        if sym_name in my_symbols:
            continue
        if re.search(rf"\b{re.escape(sym_name)}\s*\(", content):
            caller_node = path
            G.add_edge(caller_node, node_id, relation="calls")


def get_graph_summary(kg: dict) -> str:
    stats = kg["stats"]
    lines = [
        f"Repository Knowledge Graph:",
        f"  Files: {stats['total_files']}",
        f"  Functions: {stats['functions']}",
        f"  Classes: {stats['classes']}",
        f"  Graph nodes: {stats['total_nodes']}",
        f"  Graph edges: {stats['total_edges']}",
    ]

    G = kg["graph"]
    if G.number_of_nodes() > 0:
        try:
            hubs = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:5]
            lines.append("  Most connected nodes:")
            for h in hubs:
                lines.append(f"    - {h} (degree: {G.degree(h)})")
        except Exception:
            pass

    return "\n".join(lines)
