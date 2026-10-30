# Interface aprovada

Referências aprovadas em 28 de outubro de 2026:

- [Canvas](canvas-approved.png)
- [Animatic](animatic-approved.png)

As imagens são propostas visuais, não capturas do aplicativo. Orientam a
organização, a hierarquia, as cores e a densidade dos componentes existentes.

## Organização

Os modos Canvas e Animatic mantêm menus e abas na mesma posição. O Canvas
apresenta cards com título, imagem, duração e conectores no centro das laterais;
ações secundárias ficam no menu do card. O início de cena é um bloco compacto.

O Animatic apresenta seletor de cena, desenho e exportação acima do preview.
Abaixo, a timeline ocupa toda a largura: transporte centralizado, ferramentas à
esquerda, tempo à direita, régua, marcas, quadros com miniaturas e waveform.
O rodapé agrupa os controles de áudio. Preview, timeline e inspetor têm divisores
redimensionáveis; recolher o inspetor mantém uma aba visível para reabrir.

O mesmo inspetor apresenta título, frames/segundos, mídias com miniaturas,
enquadramento e seções recolhíveis de roteiro e desenho. A seleção usa azul
discreto; bordas e ícones são neutros e a waveform usa o acento terciário do tema.
Menus e seções abrem imediatamente, sem animações.

## Manutenção

- `ui/workspace_style.py`: dimensões da área de trabalho.
- `ui/design.py` e `themes/koma-dark.json`: tokens e cores compartilhados.
- `ui/node_layout.py`: medidas dos cards e âncoras das conexões.
- `editor/work_modes.py`: composição das duas áreas com um único inspetor.
- `ui/animatic_workspace.py`: distribuição do preview e da timeline.

O layout não duplica dados dos nodes nem altera o formato dos documentos.
Miniaturas reutilizam os arquivos preparados e seus controles. Alterar a largura
de um bloco aplica uma transformação à apresentação existente, sem reconstruir
os vetores do desenho a cada movimento. Listas de mídias continuam paginadas;
nenhum vídeo inativo é decodificado para montar o inspetor.
