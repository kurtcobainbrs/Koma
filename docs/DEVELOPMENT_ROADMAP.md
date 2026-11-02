# Evolução do fluxo de produção

Ordem aprovada: concluir cada etapa como um fluxo funcional, preservando os
dados dos nodes, histórico, compatibilidade e fluidez. Preferências globais
entram no catálogo e no painel existente; não ficam espalhadas nas telas.

1. **Colar imagens — implementado:** sem quadro ativo cria um quadro; com
   quadro ativo adiciona uma mídia, preservando duração e mídias anteriores.
   Posição e destino são capturados antes da importação. Cancelamento de
   contextos antigos não confirma dados; criação participa do histórico e da
   recuperação. Colagem de nodes e imagens compartilha a conversão de posição.
2. **Cenas e montagem — implementado:** lista lateral recolhível e redimensionável com código,
   nome, miniatura e duração; montagem do projeto inteiro, ordem das cenas,
   reprodução e acesso à edição interna. Consumir os mesmos nodes.
3. **Navegação — implementado:** zoom e pan independentes do preview e da
   timeline, ancoragem no cursor e enquadramento com F na área em uso.
   Padrões em Preferências. Gestos locais e pedidos de zoom agrupados evitam
   acumular eventos; as câmeras não alteram nodes, histórico ou exportação.
4. **Transformação da mídia:** mover, escalar e girar a mídia ativa; gesto
   temporário, confirmação única e Esc. Contrato preparado para propriedades
   animáveis e tempo local do quadro, sem introduzir keyframes incompletos.
5. **Guias e câmera:** terços, centro, áreas seguras e guias personalizadas;
   exibição e exportação independentes. Indicações de pan, tilt, zoom e
   deslocamento pertencem ao node; preferências de exibição são globais.
6. **Filtros:** preto e branco, saturação, brilho e contraste não destrutivos
   na mídia, com composição compartilhada na prévia e exportação.
7. **Referências:** canvas próprio de imagens livres, sem fluxo narrativo;
   seleção, movimento, escala, duplicação, grupos e ordem de sobreposição.
   Dados persistidos em estruturas proprietárias dos elementos, sem mapas
   paralelos de propriedades por referência.

Mudanças de formato exigem migração explícita e proteção dos arquivos antigos.
Verificações automatizadas devem focar salvar/abrir, copiar, desfazer/refazer e
exportar. Não executar testes manuais sem solicitação.
