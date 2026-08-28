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

O gerador **não cabe** num Cloudflare Worker do plano free: são 4,19 MB de JSON
vindos da API e o free dá só 10 ms de CPU por invocação — inclusive no Cron
Trigger. Por isso o trabalho está partido em dois:

- **quem gera**: GitHub Actions, 3x ao dia (03h / 11h / 19h de Brasília)
- **quem serve**: Cloudflare Pages, arquivo estático, sem limite de CPU

### Passo a passo

1. **Cloudflare** → Workers & Pages → Create → Pages → **Upload assets**.
   Nome do projeto: `ventura-feed`. Faça um upload qualquer só para o projeto
   existir (o CI substitui depois).

2. **Token de API da Cloudflare**: My Profile → API Tokens → Create Token →
   template *Edit Cloudflare Workers*, ou um token customizado com a permissão
   **Account · Cloudflare Pages · Edit**. Guarde o token e o **Account ID**
   (fica na barra lateral de Workers & Pages).

3. **GitHub**: crie um repositório **privado** e suba esta pasta.
   O `.gitignore` já impede que `nuvem_token.json` vá junto — confira antes do
   primeiro push.

4. No repositório → Settings → Secrets and variables → Actions, crie:

   | Secret | Valor |
   |---|---|
   | `NUVEM_STORE_ID` | `5790766` |
   | `NUVEM_ACCESS_TOKEN` | o `access_token` do `nuvem_token.json` |
   | `CLOUDFLARE_API_TOKEN` | o token do passo 2 |
   | `CLOUDFLARE_ACCOUNT_ID` | o Account ID do passo 2 |

5. Actions → *Gerar e publicar feed XML* → **Run workflow**.
   O feed passa a viver em `https://ventura-feed.pages.dev/feed.xml`.

6. Opcional: Pages → Custom domains → `feed.venturadivers.com.br`.

7. Cole a URL no Merchant Center (Produtos → Feeds → feed agendado) e no
   Gerenciador de Catálogos da Meta (Fonte de dados → Feed agendado).

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
