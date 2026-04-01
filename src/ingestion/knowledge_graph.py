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
    """Build a rich structural summary from the knowledge graph for agent context."""
    stats = kg["stats"]
    G = kg["graph"]
    lines = [
        "=== Repository Knowledge Graph ===",
        f"Files: {stats['total_files']} | Functions: {stats['functions']} | Classes: {stats['classes']}",
        f"Graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges",
    ]

    if G.number_of_nodes() == 0:
        return "\n".join(lines)

    # ── Hub files (most connected — likely core modules) ────────────────
    file_nodes = [(n, G.degree(n)) for n, d in G.nodes(data=True) if d.get("type") == "file"]
    file_nodes.sort(key=lambda x: x[1], reverse=True)
    if file_nodes:
        lines.append("\n--- Critical Hub Files (most connections = highest blast radius) ---")
        for path, deg in file_nodes[:8]:
            in_deg = G.in_degree(path)
            out_deg = G.out_degree(path)
            lines.append(f"  {path}  (in:{in_deg} out:{out_deg} total:{deg})")

    # ── Import dependency chains ────────────────────────────────────────
    import_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "imports"]
    if import_edges:
        lines.append(f"\n--- Import Dependencies ({len(import_edges)} edges) ---")
        for src, dst in import_edges[:20]:
            lines.append(f"  {src} → {dst}")

    # ── Call relationships ──────────────────────────────────────────────
    call_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "calls"]
    if call_edges:
        lines.append(f"\n--- Cross-File Call Graph ({len(call_edges)} calls) ---")
        for src, dst in call_edges[:20]:
            dst_short = dst.split("::")[-1] if "::" in dst else dst
            lines.append(f"  {src} calls {dst_short}")

    # ── Files with no inbound imports (entry points / dead code) ───────
    file_paths = {n for n, d in G.nodes(data=True) if d.get("type") == "file"}
    imported_files = {v for u, v, d in G.edges(data=True) if d.get("relation") == "imports" and v in file_paths}
    entry_points = file_paths - imported_files
    if entry_points:
        lines.append(f"\n--- Entry Points / Standalone Files ({len(entry_points)}) ---")
        for ep in sorted(entry_points)[:10]:
            lines.append(f"  {ep}")

    # ── Classes and their methods ───────────────────────────────────────
    class_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("type") in ("class", "struct")]
    if class_nodes:
        lines.append(f"\n--- Classes ({len(class_nodes)}) ---")
        for cls_node, cls_data in class_nodes[:10]:
            methods = [v.split("::")[-1] for _, v, ed in G.edges(cls_data.get("file", ""), data=True)
                       if ed.get("relation") == "defines" and "::" in v]
            cls_name = cls_node.split("::")[-1] if "::" in cls_node else cls_node
            lines.append(f"  {cls_name} ({cls_data.get('file', '?')})")

    return "\n".join(lines)
