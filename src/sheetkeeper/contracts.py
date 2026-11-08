"""Strict input/output boundaries. CSV data is never executed by the controller."""
import csv
import io
import math

MAX_CSV_BYTES = 200_000
MAX_ROWS = 2_000
MAX_COLS = 24
MAX_CODE_BYTES = 24_000


def inspect_csv(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Escolha uma planilha CSV em UTF-8.")
    if len(text.encode("utf-8")) > MAX_CSV_BYTES or "\x00" in text:
        raise ValueError("O CSV excede o limite de 200 KB ou contém caracteres inválidos.")
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        headers = next(reader)
        if not 1 <= len(headers) <= MAX_COLS:
            raise ValueError("Use entre 1 e 24 colunas.")
        if any(not h.strip() or len(h) > 80 for h in headers) or len(set(headers)) != len(headers):
            raise ValueError("As colunas precisam de nomes únicos e curtos.")
        rows = 0
        for row in reader:
            if len(row) != len(headers):
                raise ValueError("Há linhas com quantidade diferente de colunas.")
            if any(len(v) > 4_000 for v in row):
                raise ValueError("Uma célula excede o limite de tamanho.")
            rows += 1
            if rows > MAX_ROWS:
                raise ValueError("Use até 2.000 linhas nesta demonstração.")
        if rows == 0:
            raise ValueError("A planilha precisa de ao menos uma linha de dados.")
    except (StopIteration, csv.Error) as exc:
        raise ValueError("O CSV está vazio ou malformado.") from exc
    return {"headers": headers, "rows": rows, "bytes": len(text.encode("utf-8"))}


def validate_result(value):
    if not isinstance(value, dict) or set(value) != {"rows", "groups", "total"}:
        raise ValueError("A análise não retornou o contrato esperado.")
    if type(value["rows"]) is not int or not 0 <= value["rows"] <= MAX_ROWS:
        raise ValueError("Contagem de linhas inválida.")
    groups = value["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 24:
        raise ValueError("O gráfico precisa de 1 a 24 grupos.")
    def number(n):
        return type(n) in (int, float) and math.isfinite(n) and abs(n) <= 1e12
    if not number(value["total"]):
        raise ValueError("Total inválido.")
    labels = set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"label", "value"}:
            raise ValueError("Grupo inválido.")
        label = group["label"]
        if not isinstance(label, str) or not label.strip() or len(label) > 80 or label in labels:
            raise ValueError("Rótulo inválido ou repetido.")
        labels.add(label)
        if not number(group["value"]):
            raise ValueError("Valor de grupo inválido.")
    if not math.isclose(sum(g["value"] for g in groups), value["total"], rel_tol=1e-9, abs_tol=.01):
        raise ValueError("O total não coincide com os grupos.")
    return value


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"summary", "code"}:
        raise ValueError("O modelo não entregou um plano válido.")
    if not isinstance(plan["summary"], str) or not 1 <= len(plan["summary"]) <= 500:
        raise ValueError("Resumo do plano inválido.")
    if not isinstance(plan["code"], str) or not 1 <= len(plan["code"].encode()) <= MAX_CODE_BYTES:
        raise ValueError("Código fora dos limites.")
    # Syntax validation is NOT a security boundary. Never exec this on the host.
    try:
        compile(plan["code"], "analysis.py", "exec")
    except SyntaxError as exc:
        raise ValueError("O código gerado tem erro de sintaxe.") from exc
    return plan
