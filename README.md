# Koma App

Aplicativo desktop independente para storyboard e animatic, extraído do Storyboard do AppAkira. Mantém o editor de nodes, conexões, cenas, molduras, enquadramento, atalhos, histórico, PDF e MP4.

## Executar com Python

Requer Python 3.11 ou superior. No PowerShell, dentro desta pasta:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m koma
```

Depois da instalação, também é possível usar `koma` ou `python -m koma caminho\documento.koma`. O cliente desktop do Flet é baixado na primeira execução com Python. A distribuição Windows inclui esse cliente.

## Documentos

- **Novo**, **Abrir**, **Salvar** e **Salvar como** ficam no menu Arquivo.
- Atalhos: Ctrl+N, Ctrl+O, Ctrl+S e Ctrl+Shift+S, com foco no canvas. Campos de texto mantêm seus atalhos de edição.
- O asterisco no título indica alterações ainda não salvas no arquivo `.koma`.
- Abrir outro documento reinicia o histórico. O arquivo atual só é abandonado após Salvar, Descartar ou Cancelar.
- Salvar mantém uma cópia da versão anterior em `<nome>.koma.bak`. Para abrir esse backup, copie-o para um nome terminado em `.koma`.
- Se outro programa ou outra janela modificar o arquivo, o salvamento é recusado. Use Salvar como para preservar ambas as versões.
- Um documento novo permanece sem caminho até o primeiro salvamento.

O `.koma` é um ZIP com `manifest.json` (formato `koma`, versão 1) e `images/<uuid>.png`. Inclui título, nodes, conexões, grupos, textos, duração, legenda, cor, posições e enquadramento. As imagens importadas são cópias normalizadas de até 2560 × 2560; os originais não são modificados. Miniaturas de até 640 × 640 são regeneráveis e não entram no pacote.

Não há compatibilidade com `.akira-storyboard`.

## Recuperação e preferências

Edições confirmadas atualizam uma recuperação local, sem sobrescrever o `.koma`. Após interrupção, use **Arquivo → Recuperar sessão**. A recuperação permanece disponível até a resolução explícita da sessão. Sessões em uso em outra janela não são oferecidas para recuperação.

Dados locais ficam no diretório do usuário definido por `platformdirs` para `Koma`. A variável `KOMA_DATA_DIR` permite substituí-lo. Preferências do Blender e atalhos ficam em `settings.json`; opções de legendas em `options.json`; câmera em `viewports/`; recuperação em `recovery/`; logs em `logs/`.

Seleção e câmera não alteram o documento. Imagens antigas são mantidas durante a sessão para permitir desfazer. O histórico possui até 100 snapshots e não é gravado no `.koma`.

## Exportações

**PDF:** ReportLab, fontes Archivo incluídas, folhas de seis quadros e continuação de textos longos. Funciona sem Blender.

**MP4:** configure o executável em **Arquivo → Preferências do Blender**. O Blender é instalado separadamente. Selecione uma cena ou um quadro pertencente a ela antes de exportar. O resultado usa cortes diretos, sem áudio, com legendas opcionais; suporta 24/25/30/60 FPS e 1920 × 1080 ou 1280 × 720.

Validado nesta implementação com **Blender 5.0.1 no Windows**. Outras versões precisam de validação. Não instala `bpy` no Python do aplicativo e não abre arquivos `.blend`.

O runner usa um processo cancelável e um arquivo temporário. Falhas e cancelamento preservam o MP4 anterior. A preparação das imagens e o PDF trabalham fora do loop da interface.

## Testes e validação real

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe scripts\validate_exports.py --blender 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe'
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts\check_video.py -- build\validation\validation.mp4
```

Os testes verificam grafo, gestos, controles Flet, histórico, documentos, falhas de gravação, conflitos externos, recuperação e fechamento cancelável. A validação real gera `.koma`, PDF e MP4 em `build/validation`. O segundo script verifica resolução, duração em frames e FPS do vídeo por leitura no Blender.

## Distribuição Windows

```powershell
.venv\Scripts\python.exe -m pip install -e '.[build]'
.\scripts\build_windows.ps1
```

O build produz o wheel/sdist Python e `dist/Koma/Koma.exe`. Distribua **a pasta `dist/Koma` inteira**: ela inclui Python, bibliotecas, fontes, estilos, script de exportação e cliente Flet. O Blender continua externo. Não é necessário instalar Python na máquina de destino.

O build pode baixar o cliente Flet durante sua preparação. A distribuição resultante inclui esse cliente para inicialização offline. O executável portátil ainda requer uma conferência em uma máquina Windows limpa antes de publicação; não há instalador assinado nem associação automática de extensão nesta etapa.

O build verifica arquitetura x64, imports e delay-imports de cada binário. Ele falha se houver DLL ausente, runtime de depuração ou dependência do runtime Visual C++ que só exista no host. O cliente Flet 1.0.5 é empacotado sem duas DLLs órfãs (`dartjni.dll` e `zlib.dll`); hashes e referências são conferidos antes da exclusão. O cache Flet instalado não é modificado.

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
