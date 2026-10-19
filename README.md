# ramonperez.dev

Landing page pessoal em português brasileiro, com HTML5 e CSS puro. Os dados
profissionais ficam em `profile.yaml`; Python gera o HTML antes da publicação.
O navegador não executa Python, YAML, templates ou JavaScript.

## Instalação

Na raiz do repositório, com Python 3.10 ou superior:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows, ative o ambiente com `.venv\Scripts\activate`.
As dependências são **PyYAML** (leitura segura do YAML) e **Jinja2** (templates
com escape automático de HTML).

## Editar o perfil

Edite apenas `profile.yaml` para alterar conteúdo:

- `site`: título da página, descrição dos metadados e texto do link de salto.
- `personal`: nome, título, localização e contatos com `label` e `value`.
- `presentation`: resumo profissional.
- `specialties`: título e lista de especialidades.
- `skills`: título e grupos com `category` e lista de competências em `items`.
- `impact`: título e indicadores com `value` e `description`.
- `community`: título e lista de participações.
- `contact`: título e descrição da seção de contato.

Para adicionar ou remover uma informação, adicione ou remova seu item na lista
correspondente, mantendo a indentação com espaços. Para criar uma categoria,
adicione um grupo em `skills.groups` com pelo menos uma competência. Use `[]`
para esvaziar as listas de especialidades, grupos, indicadores ou comunidade;
seções sem itens não aparecem.

Todas as seções do YAML são obrigatórias, assim como seus títulos e os campos
descritos acima, exceto `personal.location`, `personal.contacts` e
`contact.description`. Remova esses campos opcionais quando não houver informação.
Cada contato (`email`, `linkedin`, `website`) também é opcional; remova sua entrada
inteira para não gerar o link. Use `contacts: {}` para remover todos os contatos.
Nesse caso, a seção de contato também não será exibida.

URLs devem ser absolutas, com `https://` ou `http://`, sem credenciais.
O e-mail deve ser um endereço simples, sem `mailto:`. O contato `website` fornece
a URL canônica e `og:url`; esses metadados são omitidos se ele não estiver presente.
Textos devem ser strings não vazias: coloque valores numéricos e textos com
caracteres especiais entre aspas quando necessário para preservar o tipo YAML.
O ano do rodapé é calculado automaticamente durante a geração.

Não edite `index.html` manualmente: ele é um artefato gerado. Não replique dados
profissionais no template. Mudanças de estrutura pertencem a `templates/index.html`;
mudanças visuais, a `style.css`.

## Gerar a página

Na raiz do repositório:

```sh
python scripts/generate.py
```

O comando lê `profile.yaml` e `templates/index.html` e grava `index.html` em UTF-8.
Também pode ser executado de outro diretório usando o caminho absoluto do script.
Campos ausentes, tipos incorretos, contatos inválidos e erros de YAML produzem
mensagens de erro e código de saída diferente de zero, sem substituir o HTML
existente. Os valores são escapados automaticamente, inclusive nos atributos.
A geração não modifica o YAML, o template ou o CSS e é determinística dentro
do mesmo ano.

## Verificar localmente

Execute as verificações automatizadas da biblioteca padrão:

```sh
python -m unittest discover -s tests -v
```

Abra `index.html` no navegador ou sirva a raiz localmente:

```sh
python -m http.server 8000 --bind 127.0.0.1
```

Acesse `http://127.0.0.1:8000`. Confira o layout em telas estreitas e largas,
o foco dos links com Tab, o link “Ir para o conteúdo”, os contatos e o código-fonte
(título, descrição, Open Graph e URL canônica). Desative JavaScript e confirme que
todo o conteúdo continua disponível. O CSS usa caminho relativo para funcionar
tanto na raiz de um domínio quanto em subdiretórios do GitHub Pages.

## Publicar no GitHub Pages

Regere a página após cada alteração dos dados ou do template e versione o HTML
resultante. Os únicos arquivos necessários no site publicado são:

- `index.html`
- `style.css`

Mantenha também os arquivos-fonte no repositório para manutenção. Não publique
o ambiente `.venv`. Selecione uma origem de publicação contendo os dois arquivos
estáticos; o GitHub Pages não precisa executar o gerador. Este projeto não
configura workflows, DNS, domínio personalizado ou infraestrutura.

## Estrutura

```text
profile.yaml          Dados e textos
templates/index.html  Estrutura HTML com Jinja2
style.css             Estilos responsivos
scripts/generate.py   Validação e geração estática
requirements.txt      Dependências Python
index.html            Página gerada, pronta para publicação
tests/                Verificações do gerador e do HTML
```
