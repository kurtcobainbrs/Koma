# Mídias por quadro

Em **Propriedades → Mídias → Adicionar mídia**, escolha uma ou mais imagens ou
vídeos. Clique em um item para torná-lo ativo; o **×** remove somente aquele item.
O botão de mídias no cabeçalho do animatic abre a mesma lista para o quadro selecionado.
Soltar um vídeo sobre um quadro adiciona uma alternativa e a ativa; no canvas
vazio, cria um quadro. Imagens soltas ou coladas também preservam as alternativas.

Trocar a mídia mantém a duração do quadro, conexões, roteiro, desenhos e
marcadores. Cada mídia guarda seu próprio enquadramento. O vídeo começa no início
do quadro: se for maior, é cortado pela duração definida; se for menor, seu último
frame permanece até o fim. A mesma regra vale no animatic e no MP4. O áudio do vídeo
não é reproduzido: a trilha de áudio da cena continua sendo a fonte sonora.
O PDF, o canvas e os blocos da timeline usam a imagem estática de prévia da mídia ativa.

## Estrutura e desempenho

`NodeMedia` e `MediaTransform` são valores imutáveis dentro de `StoryFrame.media`.
`active_media_id` seleciona um desses valores dentro do próprio node. Não há um
cadastro paralelo. Os acessos antigos de imagem e enquadramento são adaptadores
derivados para manter os consumidores existentes compatíveis.

`NodeMediaActions` concentra importação, ativação e remoção. A lista compartilhada
apresenta os metadados em páginas de 24 itens, sem abrir vídeos inativos. Leitura,
validação, cópia de arquivos e codificação acontecem fora da interface. A prévia
usa um único decodificador e substitui pedidos de busca pendentes pelo mais recente.
Vídeos copiados entre projetos usam arquivos temporários próprios, sem carregar
todo o vídeo em memória nem depender da sessão de origem.

O PyAV fornece a leitura e a [exportação MP4 interna](MP4_EXPORT.md), sem Blender.
O hook oficial do PyInstaller inclui suas bibliotecas na distribuição Windows.
As exportações preservam enquadramento, desenhos e legendas sobre os frames do vídeo.

## Persistência e limites

O formato **6** salva a lista e a escolha ativa no manifesto, os vídeos em
`videos/` e as imagens e prévias em `images/`. Todas as alternativas entram no
`.koma`, na recuperação, duplicação e cópia entre projetos. Remover ou trocar uma
mídia participa de desfazer/refazer; arquivos necessários ao histórico permanecem
na sessão. Os arquivos originais não são alterados.

Documentos dos formatos **1 a 5** continuam abrindo. A imagem antiga se torna o
primeiro item, preservando o enquadramento e a duração. Clientes antigos rejeitam
o formato 6; mantenha uma cópia anterior para voltar a uma versão antiga do app.

Os limites atuais são 4.096 itens por projeto, 512 MB e uma hora por vídeo,
40 megapixels por frame e 2 GB por pacote `.koma`. São limites de recursos,
centralizados no modelo e no formato, sem quantidade fixa de slots por node.
Formatos de vídeo: MP4, MOV, MKV, WebM, AVI e M4V, conforme os codecs disponíveis.
Arquivos inválidos são recusados antes de alterar o documento.
