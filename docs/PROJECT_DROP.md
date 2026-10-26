# Projetos por arrastar e soltar

Soltar um `.koma` na janela abre uma aba pelo mesmo fluxo de validação usado
pelo menu Arquivo. Um caminho já aberto seleciona a aba existente, preservando
suas alterações em memória. Arquivos inválidos, eventos de outra sessão e
solturas mistas não alteram o projeto atual.

- `documents/file_drop.py` identifica projetos e exige um arquivo por soltura.
- `ui/project_drop.py` adapta os eventos da superfície da janela.
- `KomaApplication.open_project` seleciona uma aba ou chama a abertura existente.
- A extensão Flutter distingue a superfície de projetos da superfície de imagens.
  Assim, soltar um projeto não o encaminha ao importador de imagens nem gera
  dois eventos de abertura. Imagens mantêm o hit-test dos widgets do canvas.
- O adaptador do canvas conserva um fallback para clientes anteriores.

O cliente de desenvolvimento é publicado em uma pasta versionada e selecionado
por `build/koma-flet/current.json`, gravado atomicamente. Isso evita substituir
executáveis em uso; janelas abertas continuam com seu cliente original. Sem
ponteiro, o caminho antigo `build/koma-flet/client` continua válido. A distribuição
empacotada mantém seu cliente interno e não usa esse ponteiro de desenvolvimento.
