# Koma App

Aplicativo desktop independente para storyboard e animatic, extraído do Storyboard do AppAkira. Mantém o editor de nodes, conexões, cenas, molduras, enquadramento, atalhos, histórico, PDF e MP4.

## Executar com Python

Requer Python 3.11 ou superior. No PowerShell, dentro desta pasta:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m koma
```

Depois da instalação, também é possível usar `koma` ou `python -m koma caminho\documento.koma`. O arraste externo usa o cliente Flet com a extensão local do Koma. Compile-o com `python scripts/build_flet_client.py` antes de iniciar. Sem esse cliente, a interface mantém Importar imagens e colagem, com aviso de indisponibilidade do arraste. A distribuição Windows inclui o cliente compilado.

## Documentos

- **Novo**, **Abrir**, **Salvar** e **Salvar como** ficam no menu Arquivo.
- Arraste um arquivo **.koma** do Explorador para a janela para abri-lo em uma aba. Se já estiver aberto, a aba existente é selecionada. Solte um projeto por vez; arquivos inválidos são recusados sem substituir o projeto atual.
- Atalhos: Ctrl+N, Ctrl+O, Ctrl+S e Ctrl+Shift+S, com foco no canvas. Campos de texto mantêm seus atalhos de edição.
- Os projetos ficam em abas no topo, logo abaixo dos menus. Use **+** ou **Arquivo → Novo** para criar outra aba; **Abrir** também abre em uma nova aba.
- Cada aba mantém documento, histórico, seleção, câmera e imagens próprios. O asterisco na aba indica alterações ainda não salvas no `.koma`.
- Clique no nome para alternar; dê dois cliques para renomear ou use **Arquivo → Renomear**. O **×** fecha a aba, com Salvar/Descartar/Cancelar quando necessário.
- O painel de propriedades mantém título e duração visíveis, com seções **Imagem** e **Roteiro** recolhíveis sem animação. Ao recolher o painel inteiro, use a seta na borda direita para reabri-lo; o atalho de Propriedades continua disponível.
- Abrir um arquivo já presente seleciona sua aba, preservando as alterações em memória. Salvar como não pode sobrescrever um arquivo aberto em outra aba.
- Ao fechar a janela, todos os projetos com alterações são verificados antes de descartar qualquer sessão. Fechar a última aba cria um projeto vazio.
- Salvar mantém uma cópia da versão anterior em `<nome>.koma.bak`. Para abrir esse backup, copie-o para um nome terminado em `.koma`.
- Se outro programa ou outra janela modificar o arquivo, o salvamento é recusado. Use Salvar como para preservar ambas as versões.
- Um documento novo permanece sem caminho até o primeiro salvamento.

O `.koma` é um ZIP com `manifest.json` (formato `koma`, versão 3), `images/<uuid>.png` e áudio em `audio/<uuid>.wav`. Inclui título, nodes, conexões, grupos, textos, duração, legenda, cor, posições, enquadramento, trilhas e marcadores. Projetos das versões 1 e 2 continuam abrindo em 1920 × 1080; clientes antigos rejeitam a versão 3 para preservar os novos dados. As imagens importadas são cópias normalizadas de até 2560 × 2560; os originais não são modificados. Miniaturas e waveforms são regeneráveis e não entram no pacote.

Não há compatibilidade com `.akira-storyboard`.

## Canvas e mute

O arraste externo é integrado aos widgets Flutter do próprio Flet; veja a [arquitetura e validação](docs/EXTERNAL_IMAGE_DROP.md). `KOMA_EXTERNAL_DROP=0` desativa o recurso nesta instância, mantendo importação pelo botão e colagem.

No Windows, arraste uma imagem do Explorador para o canvas: sobre um quadro, substitui apenas a imagem e reinicia o enquadramento; no espaço vazio, cria um quadro no ponto da soltura, respeitando zoom e grade. Inícios de cena não aceitam imagens. Solte uma imagem por vez (PNG, JPEG, WebP, BMP ou TIFF). O arquivo precisa ser decodificado e respeitar o limite de 40 megapixels antes de alterar o documento; arquivos inválidos são recusados com uma mensagem. A operação participa de Desfazer/Refazer, preserva os originais e não muda as conexões. O destino é escolhido pelo hit-test real do Flutter, inclusive com zoom, pan, sobreposição e redimensionamento. Não depende da seleção ativa, do foco do Windows nem de áreas invisíveis sobrepostas à janela.

Botão direito no canvas abre opções de inserção no ponto clicado, importação e enquadramento. Sobre um node, também oferece mutar/desmutar, duplicar e excluir. No modo Zoom, o botão direito continua reduzindo o zoom; Ctrl + arraste direito continua cortando conexões.

Use **M** para mutar/desmutar os nodes selecionados ou a opção no menu do node. Nodes mutados ficam esmaecidos e são pulados no animatic e no MP4, sem remover suas conexões. Mutar um início de cena desativa os quadros dessa cena na reprodução. A duração dos nodes mutados não entra na timeline. O estado é salvo no `.koma` e participa do desfazer/refazer. O PDF mantém os quadros do documento.

## Recuperação e preferências

Edições confirmadas atualizam uma recuperação local, sem sobrescrever o `.koma`. Após interrupção, use **Arquivo → Recuperar sessão**. A recuperação permanece disponível até a resolução explícita da sessão. Sessões em uso em outra janela não são oferecidas para recuperação.

Dados locais ficam no diretório do usuário definido por `platformdirs` para `Koma`. A variável `KOMA_DATA_DIR` permite substituí-lo. Preferências do Blender e atalhos ficam em `settings.json`; opções de legendas em `options.json`; câmera em `viewports/`; recuperação em `recovery/`; logs em `logs/`.

Seleção e câmera não alteram o documento. Imagens antigas são mantidas durante a sessão para permitir desfazer. O histórico possui até 100 snapshots e não é gravado no `.koma`.

## Exportações

Em **Arquivo → Projeto…**, escolha um formato pronto ou edite **Proporção** (por exemplo, `9:16`, `1:1`, `5:4` ou `2.39:1`). Enter recalcula as dimensões; **Aplicar** confirma. Largura e altura também podem ser editadas diretamente, com dimensões pares de 64 a 8192 px e até 32 megapixels. A configuração é salva no `.koma`, aceita desfazer e orienta os quadros, a prévia, as legendas e as exportações. O PDF mantém a folha e acomoda a imagem na proporção do projeto.

Em **Arquivo → Projeto…**, **FPS** define a taxa de 24, 25, 30 ou 60 FPS, salva no `.koma` e usada pelo MP4. Documentos antigos usam 24 FPS. A duração de cada quadro pode ser editada em **segundos** ou **frames**; o outro valor é atualizado automaticamente, inclusive com vírgula decimal. Por exemplo, a 24 FPS, 48 frames equivalem a 2 segundos. Alterar o FPS mantém os segundos e recalcula os frames. Frações de frame são permitidas; a exportação arredonda os limites acumulados para frames inteiros, com pelo menos um frame por quadro. Durações de um frame a 60 FPS são aceitas. Desfazer/refazer inclui durações e FPS.

**PDF:** ReportLab, fontes Archivo incluídas, folhas de seis quadros e continuação de textos longos. Funciona sem Blender.

**Timeline e áudio:** a prévia permite importar WAV, MP3, FLAC ou OGG por cena, visualizar a waveform, ajustar o início em frames, mutar e substituir/remover áudio. Marcadores têm nome e posição; clique para navegar e duplo clique para editar. Zoom, régua e agulha são compartilhados. Veja [arquitetura, limites e validação](docs/TIMELINE_AUDIO.md).

**MP4:** configure o executável em **Arquivo → Preferências do Blender**. O Blender é instalado separadamente. Selecione uma cena ou um quadro pertencente a ela antes de exportar. O resultado usa cortes diretos, inclui a trilha ativa da cena e legendas opcionais; suporta 24/25/30/60 FPS e usa o formato definido no projeto, preservando suas dimensões.

A exportação com áudio foi validada com **Blender 5.2 no Windows**; a exportação anterior sem áudio também foi validada com Blender 5.0.1. Outras versões precisam de validação. Não instala `bpy` no Python do aplicativo e não abre arquivos `.blend`.

O runner usa um processo cancelável e um arquivo temporário. Falhas e cancelamento preservam o MP4 anterior. A preparação das imagens e o PDF trabalham fora do loop da interface.

## Testes e validação real

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe scripts\validate_exports.py --blender 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe'
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts\check_video.py -- build\validation\validation.mp4
```

Os testes verificam grafo, gestos, controles Flet, histórico, documentos, falhas de gravação, conflitos externos, recuperação e fechamento cancelável. A validação real gera `.koma`, PDF e MP4 em `build/validation`. O segundo script verifica resolução, duração em frames e FPS do vídeo por leitura no Blender.

## Distribuição Windows

Para gerar instalador, portátil, notas e checksums a partir de um commit limpo e publicar no remote `origin`:

```powershell
.venv\Scripts\python.exe scripts\release.py --notes docs\releases\v0.2.0.md --publish
```

Atualize a versão em `pyproject.toml` e registre as mudanças antes de executar. Sem `--publish`, os artefatos ficam apenas em `dist/releases/v<versão>`. O comando reutiliza o cliente Flutter validado em cache e não executa suítes de testes por padrão; `--full-tests` as habilita. Uma publicação interrompida pode ser retomada com o mesmo comando e commit.

```powershell
.venv\Scripts\python.exe -m pip install -e '.[build]'
.\scripts\build_windows.ps1
```

O build produz o wheel/sdist Python e `dist/Koma/Koma.exe`. Distribua **a pasta `dist/Koma` inteira**: ela inclui Python, bibliotecas, fontes, estilos, script de exportação e cliente Flet. O Blender continua externo. Não é necessário instalar Python na máquina de destino.

A compilação requer Flutter 3.44.8 e Visual Studio Build Tools 2022 com ferramentas C++ para desktop. `scripts/build_flet_client.py` executa análise, testes Flutter e build Release, usando as versões dos arquivos `pubspec.lock`. O build Windows inclui esse cliente para inicialização offline. O executável portátil ainda requer uma conferência em uma máquina Windows limpa antes de publicação; não há instalador assinado nem associação automática de extensão nesta etapa.

O build verifica arquitetura x64, imports e delay-imports de cada binário. Ele falha se houver DLL ausente, runtime de depuração ou dependência do runtime Visual C++ que só exista no host. O cliente próprio usa Flet 1.0.5 e desktop_drop 0.7.1, com manifesto de protocolo e hashes de seus arquivos. Um hook local do PyInstaller impede a inclusão automática do cliente Flet padrão. O cache Flet instalado não é modificado.

O arquivo `dist/Koma-windows-x64-validation.zip` contém a distribuição, hashes, auditorias e o [roteiro Windows limpo](docs/CLEAN_WINDOWS.md). O diagnóstico funciona sem Python:

```powershell
Start-Process .\dist\Koma\Koma.exe -ArgumentList '--diagnostics', 'C:\Testes\diagnostics.json' -PassThru -Wait
```

Use `--blender <executável>` junto de `--diagnostics` para incluir a exportação MP4 no ensaio. A conferência da interface e a homologação em Windows limpo continuam necessárias.

## Organização e origem

- `src/koma/editor`: módulos do editor reaproveitados.
- `src/koma/documents`: sessão, recuperação, manifesto, pacote e imagens.
- `src/koma/exports`: PDF, composição e processo de vídeo.
- `src/koma/ui`: componentes visuais extraídos.
- `src/koma/app.py`: janela e transição entre sessões.

Origem: `kurtcobainbrs/AppAkira`, referência `a06edd15f2bd38a25d2d8b6311a09d584d7b233c`. O repositório AppAkira é apenas referência de extração e não é necessário em execução, nos testes ou no build. A licença das fontes está em `src/koma/assets/fonts/OFL.txt`.
