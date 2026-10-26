# Arraste de imagens integrado ao Flet

Implementação em 26/10/2026. A camada experimental Win32 foi removida: não há janela filha sobre o canvas, observação de foco/mouse, busca por HWND ou retângulo calculado a partir de menus e abas.

## Arquitetura

- `flutter/koma_drop`: extensão local. `desktop_drop` 0.7.1 recebe o arquivo dentro do cliente Flet 1.0.5. Cada canvas possui seu registro privado de widgets. O hit-test da árvore Flutter escolhe o quadro efetivamente atingido; a cena converte o ponto com `RenderBox.globalToLocal`, incluindo a transformação visual real.
- `src/koma/ui/drop_controls.py`: protocolo de eventos e wrappers Python dos widgets de superfície, cena e quadro.
- `src/koma/editor/external_drop.py`: valida o protocolo, a sessão e a disponibilidade da aba e encaminha o ID explícito do node e as coordenadas da cena. Não estima posições de quadros e não usa a seleção ativa como destino alternativo.
- `src/koma/editor/image_input.py`: comando de importação, validação antes da alteração, uma operação de histórico e recuperação local. Mantém proteção contra troca de sessão durante a decodificação.
- `src/koma/documents/images.py`: leitura, limite de pixels, normalização e miniatura. Preserva os originais.
- `src/koma/ui/drop_runtime.py`: verifica versão, protocolo e hashes do cliente antes de habilitar os widgets da extensão. Sem cliente compatível, o editor continua com importação pelo botão e colagem, exibindo aviso.

O ID do quadro e o ponto da cena são resolvidos no cliente no mesmo evento. Widgets sobrepostos e ferramentas cobertas obedecem ao hit-test real. Registros são descartados ao desmontar a aba. O receptor não escreve diretamente no arquivo `.koma`.

## Compilação

Pré-requisitos Windows: Flutter 3.44.8 e Visual Studio Build Tools 2022 com ferramentas C++ de desktop. Dentro do projeto:

```powershell
.venv\Scripts\python.exe scripts\build_flet_client.py
.venv\Scripts\python.exe -m koma
```

O script executa análise e testes Flutter, usa os lockfiles, compila em Release, inclui o runtime C++ redistribuível e publica o cliente em `build/koma-flet/client`. Clientes anteriores são preservados em diretórios `previous-*`. No Windows sem criação de symlinks, usa junções NTFS locais para os plugins, sem alterar configurações de segurança. Nenhum SDK é necessário na máquina que recebe a distribuição pronta.

O cliente habilita Material Icons e compila com `--no-tree-shake-icons`, pois o Flet recebe os ícones dinamicamente do Python. A publicação e o carregamento verificam a presença de `MaterialIcons-Regular.otf` no cliente. Essa fonte foi conferida visualmente na janela do Koma após a correção.

`KOMA_FLET_CLIENT` seleciona outro diretório contendo cliente e manifesto válidos. `KOMA_EXTERNAL_DROP=0` desativa o recurso. O executável empacotado usa a cópia em `_internal/desktop/flet`. O hook PyInstaller local impede que um segundo cliente Flet padrão seja incluído.

## Integridade

Imagens inválidas, corrompidas, ausentes, diretórios, lotes e imagens acima do limite são recusados antes de alterar o documento. Nodes que não aceitam imagem são recusados. Um node removido não vira um destino alternativo: a soltura é cancelada. Falha de recuperação preserva o `.koma` salvo anteriormente, o arquivo de origem e a possibilidade de desfazer. Conexões, textos e durações são preservados ao substituir imagens.

Os testes verificam entrada no segundo quadro com outro selecionado, independência da câmera Python, eventos de outra sessão, arquivo corrompido, falha de gravação, troca de sessão durante leitura, desfazer e serialização dos controles.

## Evidência desta implementação

- 192 testes Python aprovados.
- 7 testes Flutter aprovados: destino do segundo quadro, vazio, ordem de sobreposição, ferramentas sobre o canvas, zoom, mudança de escala/DPI, redimensionamento e desmontagem/troca de canvas.
- Análise Dart sem problemas na extensão e no cliente.
- Cliente Windows Release compilado e aberto pelo Koma.
- Usuário confirmou importação no canvas e destino correto nos quadros, inclusive no roteiro com zoom/redimensionamento.
- Cliente: auditoria de 20 binários x64 sem dependências ausentes ou runtimes debug.
- Distribuição de validação separada: auditoria de 108 binários x64 aprovada; diagnóstico do executável aprovado para recursos, documento/histórico/imagens, PDF e legendas.

Artefatos desta validação ficam em `build/flet-drop-validation` e `build/flet-drop-package/Koma`; a distribuição anterior não foi sobrescrita. O MP4 não foi revalidado nesta mudança. A homologação em Windows limpo e o roteiro de publicação continuam necessários.

O teste antigo que esperava confirmação de exclusão foi atualizado para verificar o comportamento imediato que já existia no HEAD, preservação dos outros quadros e desfazer. O comportamento de exclusão do aplicativo não foi alterado.

## Pacote com ícones corrigidos

Em 26/10/2026, o usuário confirmou na versão empacotada os ícones, o arrastar e soltar e o desfazer por Ctrl+Z. O pacote final está em `dist/Koma`, com ZIP de validação em `dist/Koma-windows-x64-validation.zip`. Foram aprovados 197 testes Python, 7 testes Flutter, auditoria de 108 binários e diagnóstico do executável. Os 481 arquivos do ZIP e seu checksum externo foram conferidos. A publicação preserva versões anteriores e permite rollback se a promoção falhar.
