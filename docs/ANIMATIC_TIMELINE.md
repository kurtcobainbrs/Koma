# Timeline do animatic

A visualização mostra um bloco por quadro ativo da cena, na ordem do fluxo.
A largura representa a duração. Clique no bloco para visualizar o quadro ou
arraste sua borda direita para ajustar a duração em passos de um frame, usando
o FPS do projeto. Frames e segundos representam a mesma duração do documento.
Os controles permitem enquadrar a sequência, alterar o zoom e desfazer/refazer.
Áudio e marcadores usam a mesma escala; veja [trilha de áudio](TIMELINE_AUDIO.md).

A navegação acontece na própria trilha, com régua temporal e agulha arrastável.
Clique ou arraste na régua para percorrer a prévia com precisão de um frame.
Esse gesto pausa a reprodução e não altera o documento ou o histórico. A barra
de busca separada foi removida. Os blocos mostram a duração em frames; os
segundos continuam disponíveis na dica do bloco e na identificação da prévia.
O zoom preserva o tempo no centro da área visível, e a rolagem horizontal permite
percorrer a sequência ampliada. As marcas da régua são geradas apenas na área
visível para não criar controles proporcionais à duração total do projeto.

Durante o arraste, o player e o rótulo do node mostram uma prévia temporária.
Soltar confirma uma única edição pelo caminho normal de propriedades,
persistência e histórico. Cancelar, perder o foco da janela ou fechar a prévia
descarta o arraste pendente. O formato `.koma` não foi alterado.

## Responsabilidades

- `editor/timeline.py`: sequência, escala de tempo e ajuste por frame, sem Flet.
- `editor/timing.py`: conversão e validação compartilhadas com propriedades.
- `editor/timeline_edit.py`: transação do gesto, prévia, cancelamento e confirmação.
- `editor/timeline_navigation.py`: busca por frame, estado do arraste da agulha e marcas visíveis da régua.
- `ui/timeline_strip.py`: blocos, gestos, zoom e indicador de reprodução.
- `ui/player_layout.py`: limites visuais configuráveis da janela de reprodução.
- `editor/animatic.py`: reprodução, integração dos módulos e ciclo da janela.

A escala vem da largura medida do controle; não há coordenadas de tela nem
quantidade fixa de quadros. O gesto captura sua escala inicial para que a
mudança na duração total não desloque o cálculo durante o próprio arraste.
Sessão e documento são conferidos antes de confirmar gestos antigos.

Os testes em `tests/test_animatic_timeline.py` cobrem limites, diferentes FPS,
sequências no limite do modelo, prévia sem gravação, confirmação única,
cancelamento, desfazer/refazer, duração fracionária preexistente, falha de
persistência, busca sem gravação e coordenadas após zoom/rolagem.
A distribuição empacotada anterior é preservada nesta etapa.
