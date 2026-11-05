# Diretrizes permanentes do projeto

- Manter o código modular, com responsabilidades e contratos claros entre modelo, comandos, interface e persistência.
- Implementar comportamentos reutilizáveis como funções ou componentes compartilhados. Os pontos de uso devem fornecer ações, parâmetros ou dados, sem repetir a lógica.
- Não identificar ações por textos de botões, títulos, posições fixas ou identificadores específicos. Usar capacidades, contratos e configurações explícitas.
- Evitar hardcode de regras de negócio e soluções especiais por tela. Centralizar constantes de interface e limites do modelo nos módulos responsáveis, seguindo os padrões existentes.
- Preservar a integridade dos documentos, o histórico e a compatibilidade ao alterar contratos ou formatos de salvamento.
- Manter a interface compacta, sem animações, priorizando a visualização do conteúdo.
- Usar o Blender como referência de organização visual e interação: controles compactos agrupados por função, painéis independentes, valores ajustáveis por arraste e atalhos consistentes. Adaptar esses padrões ao fluxo do Koma, preservando as decisões já aprovadas pelo usuário.
- Usar textos de interface claros, curtos e diretos. Nomear ações pelo que fazem, manter os termos consistentes e incluir explicações apenas quando ajudarem no uso, evitando jargão, redundância e abreviações ambíguas.
- Não executar testes manuais sem solicitação do usuário. Usar apenas verificações automatizadas pontuais e relevantes; evitar suítes exaustivas sem necessidade.
- Cada node é a fonte única de verdade dos seus dados. Todas as suas propriedades, camadas e alterações devem pertencer à sua própria estrutura, sem armazenamento paralelo baseado em referências ao node. A interface apenas apresenta e modifica esses dados. Estado temporário de interface, como foco, ferramenta ativa ou gesto em andamento, deve ficar separado e não se tornar outra fonte dos dados do node.
- Canvas, timeline, propriedades e exportação devem consumir os mesmos dados do modelo, sem manter cópias autoritativas divergentes.
- Separar prévia de confirmação: durante um gesto, apresentar uma alteração temporária; ao confirmar ou soltar, registrar a alteração no modelo e no histórico. Cancelar deve descartar a prévia e preservar os dados confirmados.
- Priorizar a fluidez da usabilidade, inclusive no primeiro movimento e nas trocas de ferramenta. Não bloquear a interface. Operações pesadas devem ocorrer fora dos eventos do mouse e do fluxo de interação; durante gestos, atualizar apenas o necessário, sem reconstruir ou atualizar o canvas inteiro quando apenas controles locais mudarem.
- Versionar mudanças no formato dos documentos, com migrações explícitas, validação dos dados e proteção dos projetos anteriores.
- Direcionar verificações automatizadas às integrações críticas afetadas: salvar e abrir, copiar entre projetos, desfazer e refazer e exportar. Não ampliar a bateria sem uma necessidade concreta.
- Concluir o fluxo completo de cada função nova, considerando atalhos, confirmação, cancelamento, persistência, histórico e exportação quando aplicável.
- Definir limites claros para arquivos, pontos de desenho e consumo de memória nos módulos responsáveis, com mensagens compreensíveis quando atingidos.
- Registrar falhas com informações úteis para diagnóstico e reprodução, sem expor imagens, textos, áudios ou outros conteúdos dos projetos nos logs.
- Reaproveitar os componentes, o processo de release e o cache de compilação existentes. Evitar reconstruir ou repetir etapas que continuam válidas.

## Ambiente de desenvolvimento

Use Python 3.11 ou superior. No PowerShell, na raiz do repositório:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m koma
```

O cliente desktop próprio usa Flet 1.0.5 e Flutter 3.44.8. Para compilar as extensões nativas no Windows, use Visual Studio Build Tools 2022 com as ferramentas C++ para desktop e execute `.venv\Scripts\python.exe scripts\build_flet_client.py`. O script reaproveita o cliente validado pelo manifesto e pelo fingerprint das fontes. Use `--flutter` se o SDK estiver fora do caminho padrão. `KOMA_EXTERNAL_DROP=0` desativa o arraste externo e mantém a importação e a colagem. Consulte [Arraste externo](docs/EXTERNAL_IMAGE_DROP.md) e [Estabilidade no Windows](docs/WINDOWS_STABILITY.md).

## Onde manter as mudanças

- `src/koma/editor` concentra modelo, comandos, histórico e projeções do Canvas e da timeline.
- `src/koma/ui` contém controles e apresentação. `flutter/koma_drop` implementa integrações e gestos nativos.
- `src/koma/documents` cuida de sessões, recuperação, importação de mídias e pacotes `.koma`. Consulte `DOCUMENT_VERSION` em `src/koma/documents/store.py` para a versão do manifesto aceita pelo código. O formato é um ZIP com `manifest.json` e as mídias. Miniaturas e formas de onda são regeneráveis.
- `src/koma/exports` concentra seleção de cenas, composição e exportações. Consulte [Tempos do projeto](docs/PROJECT_TIMING.md) e [Exportação MP4](docs/MP4_EXPORT.md).
- `src/koma/app.py` coordena a janela e as sessões. `src/koma/paths.py` resolve os dados locais do usuário, com substituição opcional por `KOMA_DATA_DIR`.

## Verificações e distribuição

Rode módulos ou casos específicos com `.venv\Scripts\python.exe -m unittest <módulo-ou-caso> -q`. Para mudanças que exijam validar os arquivos exportados, `scripts/validate_exports.py` gera exemplos em `build/validation`. `scripts/check_video.py` inspeciona o MP4 gerado. Os testes Dart ficam em `flutter/koma_drop/test`.

Instale as dependências de build com `.venv\Scripts\python.exe -m pip install -e '.[build]'`. Use `scripts/build_windows.ps1` para gerar a distribuição em `dist/Koma`. Distribua a pasta inteira, incluindo os binários, codecs, fontes e cliente Flet. O processo audita dependências nativas e roda o diagnóstico do pacote. Os parâmetros `-IncludePythonArtifacts` e `-ValidationKit` geram os artefatos adicionais quando necessários.

Para uma release, atualize a versão em `pyproject.toml`, escreva as notas em `docs/releases` e parta de um commit limpo. Substitua `<versão>` pela versão registrada:

```powershell
.venv\Scripts\python.exe scripts\release.py --notes 'docs/releases/v<versão>.md'
```

O comando gera instalador, portátil, notas e checksums em `dist/releases/v<versão>`. Acrescente `--publish` quando a publicação no remote `origin` estiver autorizada. Uma publicação interrompida pode ser retomada com o mesmo comando e commit. Use `--full-tests` apenas quando houver motivo para rodar as suítes completas. O [roteiro Windows limpo](docs/CLEAN_WINDOWS.md) documenta a homologação manual quando solicitada.

Mantenha o README voltado a quem instala e usa o Koma. Registre mudanças de processo neste arquivo, contratos nos documentos técnicos de `docs/` e recursos publicados nas notas da versão correspondente.
