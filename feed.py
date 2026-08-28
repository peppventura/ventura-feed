#!/usr/bin/env python3
"""
Gera o feed XML (RSS 2.0 / namespace g:) do catalogo da Nuvemshop.
O mesmo arquivo serve para Google Merchant Center e para o catalogo da Meta.

    python3 feed.py                 gera feed.xml
    python3 feed.py --out /tmp/f.xml
    python3 feed.py --somente-com-estoque

Um <item> por variacao. Produtos com mais de uma variacao ganham
g:item_group_id para o Google agrupar as variantes no mesmo anuncio.
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ_TOKEN = os.environ.get("NUVEM_TOKEN_FILE") or os.path.join(AQUI, "nuvem_token.json")
UA = "VenturaDiveGear-Feed (giuseppe@venturadivers.com.br)"
MOEDA = "BRL"
PAUSA = 0.5          # a Nuvemshop limita a ~2 req/s por app
POR_PAGINA = 200

CAMPOS = ("id,name,description,handle,published,free_shipping,canonical_url,"
          "brand,variants,images,categories,attributes")


def _tok():
    """No CI o token vem por variavel de ambiente; na maquina, do arquivo."""
    env_id = os.environ.get("NUVEM_STORE_ID")
    env_tok = os.environ.get("NUVEM_ACCESS_TOKEN")
    if env_id and env_tok:
        return {"user_id": env_id, "access_token": env_tok}
    if not os.path.exists(ARQ_TOKEN):
        sys.exit(f"Token nao encontrado: defina NUVEM_STORE_ID e NUVEM_ACCESS_TOKEN, "
                 f"ou crie {ARQ_TOKEN}")
    return json.load(open(ARQ_TOKEN, encoding="utf-8"))


def chamar(tok, caminho):
    url = f"https://api.nuvemshop.com.br/v1/{tok['user_id']}{caminho}"
    req = urllib.request.Request(url, headers={
        "Authentication": "bearer " + tok["access_token"],
        "User-Agent": UA})
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 3:      # rate limit: espera e repete
                time.sleep(5 * (tentativa + 1))
                continue
            if e.code == 404:
                return []
            raise RuntimeError(f"HTTP {e.code} em {caminho}: {e.read().decode()[:300]}")
        except urllib.error.URLError:
            if tentativa < 3:
                time.sleep(3)
                continue
            raise


def baixar_produtos(tok):
    produtos, pagina = [], 1
    while True:
        lote = chamar(tok, f"/products?per_page={POR_PAGINA}&page={pagina}&fields={CAMPOS}")
        if not lote:
            break
        produtos.extend(lote)
        print(f"  pagina {pagina}: {len(lote)} produtos (total {len(produtos)})", file=sys.stderr)
        if len(lote) < POR_PAGINA:
            break
        pagina += 1
        time.sleep(PAUSA)
    return produtos


# ---------------------------------------------------------------- texto

RX_TAG = re.compile(r"<[^>]+>")
# linhas que nunca podem sair num feed publico: identificam o fornecedor
RX_INTERNO = re.compile(
    r"^\s*[-*\u2022]?\s*(c[o\u00f3]d(igo)?\.?\s*(do\s*)?fornecedor|fornecedor|"
    r"custo|pre[c\u00e7]o\s*de\s*custo|margem|nome\s*do\s*fornecedor)\s*:",
    re.I)
RX_ESPACO = re.compile(r"[ \t\r\f\v]+")
RX_LINHAS = re.compile(r"\n{3,}")


def texto_limpo(bruto, limite=4900):
    """HTML da descricao -> texto puro, respeitando o limite do Google."""
    if not bruto:
        return ""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", bruto)
    t = re.sub(r"(?i)<li[^>]*>", "\n- ", t)
    t = re.sub(r"(?i)<(br|/p|/h[1-6]|/li|/ul|/div|/tr)[^>]*>", "\n", t)
    t = RX_TAG.sub(" ", t)
    t = html.unescape(t)
    t = RX_ESPACO.sub(" ", t)
    t = "\n".join(l.strip() for l in t.split("\n") if not RX_INTERNO.match(l))
    t = RX_LINHAS.sub("\n\n", t).strip()
    return t[:limite].rstrip()


def pt(campo, padrao=""):
    """Campos multi-idioma da Nuvemshop vem como {'pt': '...'}."""
    if isinstance(campo, dict):
        return campo.get("pt") or next((v for v in campo.values() if v), padrao)
    return campo or padrao


def caminho_categoria(produto):
    cats = produto.get("categories") or []
    if not cats:
        return ""
    nomes = [pt(c.get("name")) for c in cats if pt(c.get("name"))]
    return " > ".join(dict.fromkeys(nomes))


def tag(nome, valor):
    if valor in (None, "", []):
        return ""
    return f"    <{nome}>{escape(str(valor))}</{nome}>\n"


def cdata(nome, valor):
    if not valor:
        return ""
    return f"    <{nome}><![CDATA[{str(valor).replace(']]>', ']]&gt;')}]]></{nome}>\n"


# ---------------------------------------------------------------- itens

# produto["attributes"] traz o nome de cada eixo na mesma ordem de variants[].values
MAPA_EIXO = {
    "cor": "g:color", "color": "g:color", "cores": "g:color",
    "tamanho": "g:size", "tam": "g:size", "size": "g:size",
    "numeracao": "g:size", "numero": "g:size",
    "material": "g:material", "voltagem": None, "modelo": None,
}
def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower().strip()


def eixos(produto, variacao):
    """[(nome_do_eixo, valor)] de uma variacao, na ordem cadastrada na loja."""
    nomes = [pt(a).strip() for a in (produto.get("attributes") or [])]
    valores = [pt(v).strip() for v in (variacao.get("values") or [])]
    saida = []
    for i, valor in enumerate(valores):
        if not valor:
            continue
        saida.append((nomes[i] if i < len(nomes) else "", valor))
    return saida


def nome_variacao(produto, variacao):
    return " / ".join(v for _, v in eixos(produto, variacao))


def item_xml(produto, variacao, varias, base_desc):
    preco = variacao.get("promotional_price") or variacao.get("price")
    if not preco or float(preco) <= 0:
        return None, "sem preco"
    cheio = variacao.get("price")

    gerencia = variacao.get("stock_management")
    estoque = variacao.get("stock")
    disponivel = (not gerencia) or (estoque is None) or (estoque > 0)

    titulo = pt(produto.get("name"))
    sufixo = nome_variacao(produto, variacao)
    if varias and sufixo:
        titulo = f"{titulo} - {sufixo}"
    titulo = titulo[:145]

    link = produto.get("canonical_url") or ""
    if varias and link:
        link = f"{link}?variant={variacao['id']}"

    imagens = sorted(produto.get("images") or [], key=lambda i: i.get("position") or 0)
    principal = ""
    if variacao.get("image_id"):
        principal = next((i["src"] for i in imagens if i["id"] == variacao["image_id"]), "")
    if not principal and imagens:
        principal = imagens[0]["src"]
    if not principal:
        return None, "sem imagem"
    extras = [i["src"] for i in imagens if i["src"] != principal][:10]

    gtin = (variacao.get("barcode") or "").strip()
    mpn = (variacao.get("mpn") or variacao.get("sku") or "").strip()

    s = "  <item>\n"
    s += tag("g:id", variacao.get("sku") or variacao["id"])
    if varias:
        s += tag("g:item_group_id", produto["id"])
    s += cdata("title", titulo)
    s += cdata("description", base_desc or titulo)
    s += tag("link", link)
    s += tag("g:image_link", principal)
    for e in extras:
        s += tag("g:additional_image_link", e)
    s += tag("g:availability", "in_stock" if disponivel else "out_of_stock")
    s += tag("g:condition", "new")
    s += tag("g:price", f"{float(cheio):.2f} {MOEDA}")
    if variacao.get("promotional_price") and float(variacao["promotional_price"]) < float(cheio):
        s += tag("g:sale_price", f"{float(variacao['promotional_price']):.2f} {MOEDA}")
    s += tag("g:brand", produto.get("brand") or "")
    s += tag("g:gtin", gtin)
    s += tag("g:mpn", mpn)
    if not gtin and not mpn:
        s += tag("g:identifier_exists", "no")
    s += cdata("g:product_type", caminho_categoria(produto))
    if varias:
        usados = set()
        for nome_eixo, valor in eixos(produto, variacao):
            alvo = MAPA_EIXO.get(_sem_acento(nome_eixo), "__nada__")
            if alvo == "__nada__":                    # eixo desconhecido: nao inventa campo
                continue
            if alvo and alvo not in usados:
                s += tag(alvo, valor)
                usados.add(alvo)
    s += tag("g:age_group", variacao.get("age_group") or "")
    s += tag("g:gender", variacao.get("gender") or "")
    if variacao.get("weight") and float(variacao["weight"]) > 0:
        s += tag("g:shipping_weight", f"{float(variacao['weight']):.3f} kg")
    if produto.get("free_shipping"):
        s += "    <g:shipping><g:country>BR</g:country><g:price>0.00 BRL</g:price></g:shipping>\n"
    s += "  </item>\n"
    return s, None


def gerar(produtos, titulo_loja, link_loja, somente_estoque=False, limite_desc=4900):
    corpo, incluidos = [], 0
    motivos = {}
    for p in produtos:
        if not p.get("published"):
            motivos["nao publicado"] = motivos.get("nao publicado", 0) + 1
            continue
        desc = texto_limpo(pt(p.get("description")), limite_desc)
        variacoes = [v for v in (p.get("variants") or []) if v.get("visible", True)]
        varias = len(variacoes) > 1
        for v in variacoes:
            gerencia, est = v.get("stock_management"), v.get("stock")
            if somente_estoque and gerencia and (est or 0) <= 0:
                motivos["sem estoque"] = motivos.get("sem estoque", 0) + 1
                continue
            xml, erro = item_xml(p, v, varias, desc)
            if erro:
                motivos[erro] = motivos.get(erro, 0) + 1
                continue
            corpo.append(xml)
            incluidos += 1

    cab = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
           '<channel>\n'
           f'  <title>{escape(titulo_loja)}</title>\n'
           f'  <link>{escape(link_loja)}</link>\n'
           '  <description>Catalogo de produtos</description>\n')
    return cab + "".join(corpo) + "</channel>\n</rss>\n", incluidos, motivos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(AQUI, "feed.xml"))
    ap.add_argument("--somente-com-estoque", action="store_true")
    ap.add_argument("--descricao-max", type=int, default=4900,
                    help="corta a descricao (o Google aceita ate 5000 caracteres)")
    args = ap.parse_args()

    tok = _tok()
    print("Baixando catalogo da Nuvemshop...", file=sys.stderr)
    produtos = baixar_produtos(tok)
    loja = chamar(tok, "/store")
    titulo = pt(loja.get("name"), "Loja")
    link = pt(loja.get("original_domain") or loja.get("url"), "")
    if link and not link.startswith("http"):
        link = "https://" + link

    xml, n, motivos = gerar(produtos, titulo, link, args.somente_com_estoque,
                            args.descricao_max)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"\nProdutos lidos : {len(produtos)}", file=sys.stderr)
    print(f"Itens no feed  : {n}", file=sys.stderr)
    for k, v in sorted(motivos.items(), key=lambda x: -x[1]):
        print(f"  descartados ({k}): {v}", file=sys.stderr)
    print(f"Arquivo        : {args.out}  ({os.path.getsize(args.out)/1024:.0f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
