# Fluxo de edição — implementação para validação

Esta rodada reúne os comandos de documentos, edição de seleção e timeline. A implementação passou por análise estática e compilação do cliente Flutter. A validação de uso fica com o usuário; não foram executados testes manuais nem suítes de testes nesta rodada.

Na revisão de integração posterior, foram acrescentadas sete verificações automatizadas pontuais, sem abrir o app. Elas cobrem colagem entre documentos com mídias e histórico, importação sem acessar o clipboard, troca de destino durante a importação, reordenação e propriedades em lote, proteção contra valores inválidos e opções de exportação desatualizadas, movimento do áudio e recorte para exportação. Essas verificações passaram; a interação real na janela continua pendente de validação pelo usuário.

## Documentos e abas

- **Arquivo → Recentes** lista os últimos projetos abertos ou salvos em um submenu. Arquivos indisponíveis aparecem desabilitados; o caminho completo fica na dica do item.
- **Arquivo → Importar → Projeto** acrescenta os nodes de outro `.koma` ao projeto atual, com novos identificadores e cópias das imagens e áudios. O arquivo de origem permanece independente.
- `Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S` e `Ctrl+W`: novo, abrir, salvar, salvar como e fechar aba, inclusive com o foco em campos de texto.
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: próxima aba / aba anterior.
- `Ctrl+Shift+O`: recentes. `Ctrl+F`: localizar quadros e cenas.

## Nodes e propriedades

- `Ctrl+C`, `Ctrl+X`, `Ctrl+V`: copiar, recortar e colar a seleção, no mesmo projeto ou entre abas do mesmo Koma. Imagens copiadas externamente continuam usando a importação de imagem ao colar.
- A cópia preserva conexões internas e molduras inteiramente selecionadas. Áudio e marcadores acompanham suas cenas quando o início de cena faz parte da seleção.
- Seleções múltiplas permitem editar propriedades compatíveis em uma única operação de histórico. Valores diferentes aparecem como mistos; campos de tempo continuam aceitando expressões.
- Arrastar a divisória do inspetor ajusta sua largura. A faixa lateral continua permitindo reabrir o painel recolhido.
- **Exibir → Localizar** pesquisa título, legenda, ação, diálogo e notas, selecionando e enquadrando o resultado.
- **Exibir → Painéis → Mídias** lista imagens, dimensões, referências e áudios. Clicar em uma imagem seleciona os nodes que a utilizam.
- Os comandos de desfazer e refazer mostram a operação correspondente.

Os menus seguem a mesma densidade e abertura instantânea de **Arquivo**:

- **Editar** separa histórico, recortar/copiar/colar, duplicar/mover e excluir.
- **Exibir** reúne enquadramento e zoom, grade, painéis e busca. **Painéis** contém propriedades, ferramentas e mídias.
- **Seleção** mantém todos, nenhum e inverter em uma lista curta.
- **Inserir** separa os tipos de node de **Importar**, que compartilha os comandos de imagens, áudio e projeto com **Arquivo**.
- **Fluxo** separa moldura, organização e operações que removem conexões ou nodes.

## Animatic

- Arrastar o corpo de um quadro para outro quadro muda sua posição no fluxo; a borda direita continua ajustando a duração.
- Arrastar a waveform muda o início do áudio. A posição é quantizada em frames e registrada como uma operação ao soltar. `Esc` cancela o arraste.
- Soltar um arquivo de áudio suportado na janela importa a trilha da cena ativa. O arquivo passa pela importação e normalização já usadas pelo seletor de áudio. Não é aceita uma mistura de tipos ou vários áudios simultâneos.
- `Ctrl+I` importa áudio no animatic e imagens no canvas.
- A divisória abaixo da prévia ajusta a proporção de espaço entre a imagem e os controles/trilhas, sem animação.
- A exportação MP4 permite cena atual, projeto completo ou conjunto de cenas, com intervalo de início/fim em frames e expressões. Áudio recortado usa arquivos temporários; a mídia original do projeto é preservada.

## Roteiro sugerido para sua validação

1. Abrir dois projetos, copiar e recortar seleções com conexões e imagens entre as abas; desfazer e refazer.
2. Editar durações de uma seleção mista, usando expressões, e redimensionar o inspetor.
3. Reordenar quadros, mover o áudio, cancelar um movimento e conferir o histórico.
4. Importar áudio pelo Explorador, consultar recentes, localizar nodes e inspecionar mídias.
5. Exportar uma cena, duas cenas e um intervalo que comece no meio de um quadro com áudio.

O novo suporte nativo a arquivos de áudio está compilado no cliente de desenvolvimento. O instalador e a versão portátil publicados anteriormente não foram substituídos nesta rodada.
