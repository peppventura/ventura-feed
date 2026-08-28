# Feed XML da Nuvemshop — Ventura Dive Gear

Substitui o app "Feed XML" da loja de aplicativos (R$ 59/mês) por R$ 0,00.
Gera um RSS 2.0 com namespace `g:` — o mesmo arquivo serve para o
**Google Merchant Center** e para o **catálogo da Meta**.

## Rodar na mão (agora)

    python3 feed.py                        # gera feed.xml aqui na pasta
    python3 feed.py --out public/feed.xml
    python3 feed.py --somente-com-estoque   # descarta o que está zerado
    python3 feed.py --descricao-max 500     # feed menor (3,9 MB -> 1,7 MB)

O token sai de `nuvem_token.json` (loja 5790766, não expira) ou das variáveis
`NUVEM_STORE_ID` / `NUVEM_ACCESS_TOKEN`.

## Publicação automática (grátis)

**Já está no ar:** https://peppventura.github.io/ventura-feed/feed.xml

O GitHub Actions gera o XML 3x ao dia (03h / 11h / 19h de Brasília, e a cada
push) e o GitHub Pages serve o arquivo. Custo zero, sem token de API externo.

Para rodar na hora, sem esperar o horário: aba **Actions** → *Gerar e publicar
feed XML* → **Run workflow**. Ou pelo terminal:

    gh workflow run "Gerar e publicar feed XML" -R peppventura/ventura-feed

Secrets já cadastrados no repositório: `NUVEM_STORE_ID` e `NUVEM_ACCESS_TOKEN`.
O repositório é público (nada sigiloso nele — os secrets seguem privados), o que
é o que permite usar o Pages de graça.

### Por que não é um Cloudflare Worker

Não cabe no plano free: são 4,19 MB de JSON vindos da API a cada geração, contra
**10 ms de CPU por invocação** — limite que vale também para os Cron Triggers.
Só o parse já estoura. Daria para fazer no Workers Paid (US$ 5/mês), mas aqui
o custo é R$ 0,00.

### Ligar nos canais

- **Google Merchant Center**: Produtos → Feeds → feed agendado, cole a URL.
- **Meta**: Gerenciador de Catálogos → Fonte de dados → Feed agendado.

## Antes de ligar isso no Google, resolver

- **162 produtos publicados não têm nenhuma foto** na Nuvemshop (432 variações).
  O Google recusa item sem `image_link`, então eles ficam de fora de qualquer
  feed — o app pago teria exatamente o mesmo problema.
- **A vitrine está travada por senha** ("loja em desenvolvimento") e os links
  apontam para `venturadivegear2.lojavirtualnuvem.com.br`. O Merchant Center
  precisa rastrear a página do produto; com a loja fechada ele reprova o feed
  inteiro. Isso tem que ser resolvido primeiro.

## O que vai no XML

Um `<item>` por variação, com `g:item_group_id` agrupando as variações do mesmo
produto. Campos: `title`, `description` (HTML convertido em texto puro),
`link`, `g:image_link` + até 10 adicionais, `g:availability` (lê
`stock_management` e o estoque real), `g:price`, `g:sale_price` quando há
promoção, `g:brand`, `g:gtin` (código de barras), `g:mpn` (SKU),
`g:identifier_exists: no` quando falta os dois, `g:product_type` com o caminho
da categoria, `g:color` / `g:size` lidos dos nomes dos eixos em `attributes`,
`g:age_group`, `g:gender`, `g:shipping_weight` e frete grátis quando marcado.

Última rodada: 354 produtos lidos, **644 itens no feed**, 472 em estoque,
328 com GTIN.
